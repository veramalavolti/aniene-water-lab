#!/usr/bin/env python3
"""Estrae i dati dei monitoraggi dai file Excel originali e scrive i JSON in dati/.

I file Excel non stanno nel repository: vivono nella cartella Aniene insieme al
resto del materiale di campagna. Il percorso si passa con --sorgente (per
default la cartella che contiene il repository).

    python3 scripts/estrai_dati.py
    python3 scripts/estrai_dati.py --sorgente "/percorso/della/cartella/Aniene"

Ogni campagna produce un file con la stessa forma:

    {"id", "etichetta", "stazioni": [...], "campagne": [...], "misure": [...]}

dove una misura e' {"s": id stazione, "d": data, "p": {parametro: valore}} e un
valore e' un numero oppure {"v": numero, "lim": "<" | ">"} quando il kit di
campo ha restituito un valore fuori scala.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

try:
    import openpyxl
except ImportError:  # pragma: no cover
    sys.exit("Serve openpyxl: pip install openpyxl")

REPO = Path(__file__).resolve().parent.parent
USCITA = REPO / "dati"

# ---------------------------------------------------------------- utilita' ---

PARAMETRI = (
    "temperatura",
    "ph",
    "conducibilita",
    "ossigeno",
    "torbidita",
    "ammonio",
    "nitrati",
    "fosfati",
    "ecoli",
    "coliformi",
)


def senza_accenti(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def chiave_parametro(intestazione: str) -> str | None:
    """Riconosce il parametro dall'intestazione, qualunque sia la grafia usata."""
    t = senza_accenti(str(intestazione or "")).lower()
    if not t.strip():
        return None
    if "temperatura" in t:
        return "temperatura"
    if t.strip() in {"ph", "ph "} or re.search(r"\bph\b", t):
        return "ph"
    if "conducibilita" in t or "conduttivita" in t:
        return "conducibilita"
    if "ossi" in t:  # copre "Ossigeno" e il refuso "Ossiggeno"
        return "ossigeno"
    if "torbid" in t:
        return "torbidita"
    if "ammoni" in t or "nh4" in t:
        return "ammonio"
    if "nitrat" in t or "no3" in t:
        return "nitrati"
    if "fosfat" in t or "po4" in t:
        return "fosfati"
    if "coli" in t and ("coliform" in t or "fecali" in t):
        return "coliformi"
    if "escherichia" in t or "e. coli" in t or "e.coli" in t:
        return "ecoli"
    return None


def numero(valore) -> float | dict | None:
    """Normalizza una cella in numero, oppure {"v":…, "lim":"<"|">"}.

    Accetta i formati che si trovano nei fogli: 1.234, "1,234", "< 14", "> 10",
    "5-10" (intervallo: si prende il valore centrale), "n.d.", celle vuote.
    """
    if valore is None:
        return None
    if isinstance(valore, bool):
        return None
    if isinstance(valore, (int, float)):
        if isinstance(valore, float) and math.isnan(valore):
            return None
        return float(valore)
    if isinstance(valore, (dt.datetime, dt.date, dt.time)):
        return None

    t = str(valore).strip()
    if not t:
        return None
    t = t.replace(" ", " ")
    basso = senza_accenti(t).lower()
    if basso in {"n.d.", "nd", "na", "n/a", "-", "--", "/", "assente", "assenza di acqua"}:
        return None

    lim = None
    if t.startswith("<"):
        lim, t = "<", t[1:]
    elif t.startswith(">"):
        lim, t = ">", t[1:]
    t = t.strip().replace(" ", "")

    # intervalli tipo "5-10" oppure "5–10"
    m = re.fullmatch(r"([0-9]+(?:[.,][0-9]+)?)[-–]([0-9]+(?:[.,][0-9]+)?)", t)
    if m:
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", "."))
        return {"v": (a + b) / 2, "lim": "~"}

    t = re.sub(r"[^0-9.,eE+-]", "", t)
    if not t:
        return None
    # "1.234,5" -> 1234.5 ; "1234,5" -> 1234.5 ; "1234.5" -> 1234.5
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    if math.isnan(v):
        return None
    return {"v": v, "lim": lim} if lim else v


def decimale(valore) -> float | None:
    """Legge una coordinata scritta come 41.9232, "41,9232" o "41, 923199"."""
    if valore is None:
        return None
    if isinstance(valore, (int, float)):
        return float(valore)
    t = re.sub(r"\s+", "", str(valore)).replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def data_iso(valore) -> str | None:
    if isinstance(valore, (dt.datetime, dt.date)):
        return valore.strftime("%Y-%m-%d")
    t = str(valore or "").strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", t)
    if m:
        g, me, a = (int(x) for x in m.groups())
        a = a + 2000 if a < 100 else a
        try:
            return dt.date(a, me, g).isoformat()
        except ValueError:
            return None
    return None


def coordinate(valore) -> tuple[float, float] | None:
    nums = re.findall(r"-?\d{1,3}[.,]\d+", str(valore or ""))
    if len(nums) < 2:
        return None
    lat = float(nums[0].replace(",", "."))
    lon = float(nums[1].replace(",", "."))
    if not (35 < lat < 48 and 6 < lon < 20):
        return None
    return lat, lon


def foglio_tidy(ws) -> tuple[list[str], list[tuple]]:
    intestazioni = [c for c in next(ws.iter_rows(max_row=1, values_only=True))]
    righe = [r for r in ws.iter_rows(min_row=2, values_only=True) if r[0] is not None]
    return intestazioni, righe


MESI = ("gen", "feb", "mar", "apr", "mag", "giu",
        "lug", "ago", "set", "ott", "nov", "dic")


def raggruppa_campagne(dati: dict, giorni: int = 10) -> dict:
    """Raggruppa in una sola campagna i prelievi fatti a pochi giorni di distanza.

    Capita spesso che le stazioni di una stessa uscita mensile siano campionate
    in due o tre giorni vicini: nei grafici devono comparire come un unico
    momento, altrimenti l'asse del tempo si riempie di colonne mezze vuote.
    """
    date = sorted({m["d"] for m in dati["misure"]})
    if not date:
        dati["campagne"] = []
        return dati

    gruppi: list[list[str]] = [[date[0]]]
    for d in date[1:]:
        precedente = dt.date.fromisoformat(gruppi[-1][-1])
        if (dt.date.fromisoformat(d) - precedente).days <= giorni:
            gruppi[-1].append(d)
        else:
            gruppi.append([d])

    campagne, appartenenza = [], {}
    for g in gruppi:
        inizio = dt.date.fromisoformat(g[0])
        cid = g[0]
        campagne.append({
            "id": cid,
            "etichetta": f"{MESI[inizio.month - 1]} {inizio.year}",
            "date": g,
        })
        for d in g:
            appartenenza[d] = cid

    for m in dati["misure"]:
        m["c"] = appartenenza[m["d"]]
    dati["campagne"] = campagne
    return dati


def scrivi(nome: str, dati: dict) -> None:
    dati = raggruppa_campagne(dati)
    USCITA.mkdir(exist_ok=True)
    percorso = USCITA / nome
    percorso.write_text(
        json.dumps(dati, ensure_ascii=False, indent=1, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    n = len(dati["misure"])
    print(f"  {percorso.relative_to(REPO)}: {len(dati['stazioni'])} stazioni, "
          f"{len(dati['campagne'])} campagne, {n} prelievi")


def pulisci(p: dict) -> dict:
    return {k: v for k, v in p.items() if v is not None}


# ------------------------------------------------- campagna 2021/2022-2023 ---


def romaup(sorgente: Path) -> dict:
    """RomaUp: 5 stazioni sull'Aniene, aprile 2022 - marzo 2023.

    Il foglio contiene anche il Tevere: l'anagrafica dice quali punti sono
    sull'Aniene e teniamo solo quelli, come chiede il testo della pagina.
    """
    f = sorgente / "RomaUp 2022-2023 + 2021" / "Dati-Tevere-e-Aniene22-23.xlsx"
    wb = openpyxl.load_workbook(f, data_only=True)

    # Lettere usate nella pagina e nel report: Ponte Salario = A.
    etichette = {"2A": "A", "B": "B", "C": "C", "D": "D", "E": "E"}
    nomi = {"C": "Casa del Parco"}
    ordine = ["E", "D", "C", "B", "A"]  # da monte a valle

    stazioni: dict[str, dict] = {}
    for r in wb["anagrafica_stazioni"].iter_rows(min_row=2, values_only=True):
        if r[0] is None:
            break
        if str(r[1]).strip().lower() != "aniene":
            continue
        codice = str(r[0]).strip()
        sid = etichette.get(codice, codice)
        stazioni[codice] = {
            "id": sid,
            "nome": nomi.get(sid, str(r[2]).strip()),
            "lat": decimale(r[3]),
            "lon": decimale(r[4]),
        }

    ws = wb["dati_grezzi"]
    intestazioni, righe = foglio_tidy(ws)
    colonne = {i: chiave_parametro(h) for i, h in enumerate(intestazioni)}

    misure, campagne = [], set()
    for r in righe:
        codice = str(r[0]).strip()
        if codice not in stazioni:
            continue
        d = data_iso(r[3])
        if not d:
            continue
        p = {}
        for i, chiave in colonne.items():
            if chiave and i < len(r):
                v = numero(r[i])
                if v is not None:
                    p[chiave] = v
        if not p:
            continue
        campagne.add(d)
        misure.append({"s": stazioni[codice]["id"], "d": d, "p": p})

    elenco = sorted(stazioni.values(), key=lambda s: ordine.index(s["id"]))
    for i, s in enumerate(elenco):
        s["ordine"] = i
    return {
        "id": "2022-2023",
        "etichetta": "RomaUp · aprile 2022 – marzo 2023",
        "nota_fonte": "Foglio «dati_grezzi» di «Dati-Tevere-e-Aniene22-23.xlsx», "
                      "limitato alle cinque stazioni sull'Aniene.",
        "stazioni": elenco,
        "campagne": sorted(campagne),
        "misure": sorted(misure, key=lambda m: (m["d"], m["s"])),
    }


# -------------------------------------------------------- dataset ordinati ---


def dataset_tidy(percorso: Path, foglio: str, meta: dict,
                 solo_punti: range | None = None,
                 nomi_stazioni: dict | None = None) -> dict:
    """Legge un foglio già in forma tabellare (una riga per prelievo)."""
    wb = openpyxl.load_workbook(percorso, data_only=True)
    ws = wb[foglio]
    intestazioni, righe = foglio_tidy(ws)
    colonne = {i: chiave_parametro(h) for i, h in enumerate(intestazioni)}

    stazioni: dict[int, dict] = {}
    misure, campagne = [], set()
    for r in righe:
        try:
            punto = int(float(r[0]))
        except (TypeError, ValueError):
            continue
        if solo_punti is not None and punto not in solo_punti:
            continue
        d = data_iso(r[4])
        if not d:
            continue
        nome = (nomi_stazioni or {}).get(punto) or str(r[1] or "").strip()
        if punto not in stazioni:
            stazioni[punto] = {
                "id": str(punto),
                "nome": nome,
                "lat": decimale(r[2]),
                "lon": decimale(r[3]),
            }
        elif len(nome) > len(stazioni[punto]["nome"]):
            stazioni[punto]["nome"] = nome

        p = {}
        for i, chiave in colonne.items():
            if chiave and i < len(r):
                v = numero(r[i])
                if v is not None:
                    p[chiave] = v
        if not p:
            continue
        campagne.add(d)
        misure.append({"s": str(punto), "d": d, "p": p})

    # i punti sono numerati da valle verso monte: l'ordine di lettura è l'inverso
    elenco = [pulisci(stazioni[k]) for k in sorted(stazioni, reverse=True)]
    for i, s in enumerate(elenco):
        s["ordine"] = i
    return {
        **meta,
        "stazioni": elenco,
        "campagne": sorted(campagne),
        "misure": sorted(misure, key=lambda m: (m["d"], int(m["s"]))),
    }


# ------------------------------------------------------------- 2025 / 2026 ---

# Il foglio «Dati gommone» è organizzato a blocchi, uno per punto, con una
# colonna per campagna. Le date non sono nell'intestazione ma sparse nei
# blocchi, e la numerazione riparte da 1 a ogni tratto: qui ricostruiamo
# numerazione progressiva da monte a valle e date di campagna per tratto.

TRATTI_GOMMONE = [
    {
        "id": "alto",
        "nome": "Tratto alto",
        "dove": "dai depuratori di Guidonia e Tivoli al fosso dell'Osa",
        "date": ["2025-11-15", "2026-05-20"],
    },
    {
        "id": "medio",
        "nome": "Tratto medio",
        "dove": "da Settecamini al depuratore di Roma est",
        "date": ["2025-12-18", "2026-05-27"],
    },
    {
        "id": "urbano",
        "nome": "Tratto urbano e foce",
        "dove": "da Casal de' Pazzi alla confluenza nel Tevere",
        "date": ["2026-02-24", "2026-06-22"],
    },
]


def _titolo_gommone(testo: str) -> tuple[str, bool, str]:
    """Dal titolo del blocco ricava numero progressivo, se è un BIS, e il nome.

    I titoli hanno forme come «Punto 8 BIS 500 mt a valle…», «Punto 3 (12) sx
    Aqua Virgo Salone», «Punto 1 /500mt a valle». Il numero tra parentesi, dove
    c'è, è la numerazione progressiva da monte a valle usata nel report.
    """
    t = re.sub(r"\s+", " ", str(testo)).strip()
    corpo = re.sub(r"^punto\s*", "", t, flags=re.I)
    bis = bool(re.search(r"\bbis\b|/\s*500|500\s*mt", corpo, re.I))

    progressivo = re.search(r"\((\s*\d+\s*)\)", corpo)
    locale = re.match(r"(\d+)", corpo)
    numero_blocco = int(progressivo.group(1)) if progressivo else (
        int(locale.group(1)) if locale else None
    )

    nome = corpo
    if progressivo:
        nome = corpo[progressivo.end():]
    elif locale:
        nome = corpo[locale.end():]
    nome = re.sub(r"^\s*(bis|BIS)\b", "", nome).strip(" ·-–/")
    nome = re.sub(r"\s+", " ", nome).strip()
    return nome or corpo, bis, (str(numero_blocco) if numero_blocco else "")


def gommone(sorgente: Path) -> dict:
    f = (sorgente / "Risultati campionamento 2025-2026"
         / "Dati campionamento Aniene 2025-2026.xlsx")
    wb = openpyxl.load_workbook(f, data_only=True)
    ws = wb["Dati gommone"]
    righe = list(ws.iter_rows(values_only=True))

    inizi = [i for i, r in enumerate(righe)
             if r[0] and str(r[0]).strip().lower().startswith("punto")]
    inizi.append(len(righe))

    # I tratti si riconoscono dal fatto che la numerazione locale riparte da 1.
    tratto_di_blocco, tratto = [], -1
    precedente = 99
    for i in inizi[:-1]:
        locale = re.match(r"punto\s*(\d+)", str(righe[i][0]).strip(), re.I)
        n = int(locale.group(1)) if locale else precedente
        if n < precedente:
            tratto += 1
        precedente = n
        tratto_di_blocco.append(min(tratto, len(TRATTI_GOMMONE) - 1))

    stazioni, misure, campagne = [], [], set()
    progressivo = 0
    for b, (i, fine) in enumerate(zip(inizi[:-1], inizi[1:])):
        blocco = righe[i:fine]
        titolo = str(blocco[0][0])
        nome, bis, _ = _titolo_gommone(titolo)
        info = TRATTI_GOMMONE[tratto_di_blocco[b]]

        if not bis:
            progressivo += 1
        sid = f"{progressivo:02d}" + ("bis" if bis else "")

        # date: nel titolo o nella riga Note; altrimenti quelle del tratto
        date_colonna: dict[int, str] = {}
        for riga in blocco[:4]:
            for col, cella in enumerate(riga[1:6], start=1):
                d = data_iso(cella) if isinstance(cella, (dt.datetime, dt.date)) else None
                if d:
                    date_colonna.setdefault(col, d)
        for col, d in enumerate(info["date"], start=1):
            date_colonna.setdefault(col, d)

        coord = None
        valori: dict[int, dict] = {}
        note: dict[int, str] = {}
        for riga in blocco:
            etichetta = str(riga[0] or "").strip()
            if etichetta.lower().startswith("coordinate"):
                for cella in riga[1:4]:
                    coord = coord or coordinate(cella)
                continue
            if etichetta.lower() == "note":
                for col, cella in enumerate(riga[1:4], start=1):
                    if isinstance(cella, str) and cella.strip():
                        note[col] = cella.strip()
                continue
            chiave = chiave_parametro(etichetta)
            if not chiave:
                continue
            for col, cella in enumerate(riga[1:4], start=1):
                v = numero(cella)
                if v is not None:
                    valori.setdefault(col, {})[chiave] = v

        stazione = {
            "id": sid,
            "nome": nome,
            "tratto": info["id"],
            "bis": bis,
            "ordine": len(stazioni),
        }
        if coord:
            stazione["lat"], stazione["lon"] = coord
        stazioni.append(stazione)

        for col, p in sorted(valori.items()):
            d = date_colonna.get(col)
            if not d or not p:
                continue
            campagne.add(d)
            m = {"s": sid, "d": d, "p": p}
            if note.get(col):
                m["nota"] = note[col]
            misure.append(m)

    return {
        "id": "2025-2026-gommone",
        "etichetta": "Campagne in gommone · novembre 2025 – giugno 2026",
        "nota_fonte": "Foglio «Dati gommone» di «Dati campionamento Aniene "
                      "2025-2026.xlsx». Le date di campagna sono quelle "
                      "registrate nel foglio.",
        "tratti": TRATTI_GOMMONE,
        "stazioni": stazioni,
        "campagne": sorted(campagne),
        "misure": sorted(misure, key=lambda m: (m["d"], m["s"])),
    }


def gommone_tremila(sorgente: Path) -> dict:
    """I prelievi lungo l'asta ogni 3 km circa (punti A–M), maggio–giugno 2026."""
    f = (sorgente / "Risultati campionamento 2025-2026"
         / "Dati campionamento Aniene 2025-2026.xlsx")
    wb = openpyxl.load_workbook(f, data_only=True)
    ws = wb["Extra ogni 3km circa"]
    righe = list(ws.iter_rows(values_only=True))
    inizi = [i for i, r in enumerate(righe)
             if r[0] and str(r[0]).strip().lower().startswith("punto")]
    inizi.append(len(righe))

    stazioni, misure, campagne = [], [], set()
    ultima_data = "2026-05-20"
    for i, fine in zip(inizi[:-1], inizi[1:]):
        blocco = righe[i:fine]
        testo = re.sub(r"\s+", " ", str(blocco[0][0])).strip()
        m = re.match(r"punto\s*([A-Za-z])\s*(.*)", testo, re.I)
        sid = (m.group(1).upper() if m else testo[:2]).strip()
        nome = (m.group(2) if m else testo).strip(" ·-–") or sid

        data = None
        for riga in blocco[:4]:
            for cella in riga[1:4]:
                if isinstance(cella, (dt.datetime, dt.date)):
                    data = data or data_iso(cella)
        data = data or ultima_data
        ultima_data = data

        coord, p = None, {}
        for riga in blocco:
            etichetta = str(riga[0] or "").strip()
            if etichetta.lower().startswith("coordinate"):
                for cella in riga[1:4]:
                    coord = coord or coordinate(cella)
                continue
            chiave = chiave_parametro(etichetta)
            if chiave:
                v = numero(riga[1])
                if v is not None:
                    p[chiave] = v

        stazione = {"id": sid, "nome": nome, "ordine": len(stazioni)}
        if coord:
            stazione["lat"], stazione["lon"] = coord
        stazioni.append(stazione)
        if p:
            campagne.add(data)
            misure.append({"s": sid, "d": data, "p": p})

    return {
        "id": "2025-2026-asta",
        "etichetta": "Prelievi lungo l'asta ogni 3 km · maggio – giugno 2026",
        "nota_fonte": "Foglio «Extra ogni 3km circa» di «Dati campionamento "
                      "Aniene 2025-2026.xlsx».",
        "stazioni": stazioni,
        "campagne": sorted(campagne),
        "misure": sorted(misure, key=lambda m: (m["d"], m["s"])),
    }


# ----------------------------------------------------------------- comandi ---


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sorgente", type=Path, default=REPO.parent,
                    help="cartella che contiene i file Excel di campagna")
    args = ap.parse_args()
    sorgente: Path = args.sorgente.expanduser().resolve()
    if not sorgente.is_dir():
        return print(f"Cartella non trovata: {sorgente}") or 1

    print(f"Sorgente: {sorgente}")

    print("Campagna 2021 | 2022-2023 (RomaUp)")
    scrivi("campagna-2022-2023.json", romaup(sorgente))

    print("Campagna 2023-2024 (Aniene WaterLab, punti fissi)")
    scrivi("campagna-2023-2024.json", dataset_tidy(
        sorgente / "Risultati campionamento 2023-2024"
        / "Dataset definitivo dati monitoraggio AnieneWaterLab 23_24.xlsx",
        "Dataset",
        {
            "id": "2023-2024",
            "etichetta": "Aniene WaterLab · dicembre 2023 – ottobre 2024",
            "nota_fonte": "Foglio «Dataset» di «Dataset definitivo dati "
                          "monitoraggio AnieneWaterLab 23_24.xlsx». I punti "
                          "10–14 sono i rilievi straordinari in gommone e "
                          "stanno nel file a parte.",
        },
        solo_punti=range(1, 10),
        nomi_stazioni={3: "Casa del Parco"},
    ))

    print("Campagna 2023-2024 (rilievi in gommone)")
    scrivi("campagna-2023-2024-gommone.json", dataset_tidy(
        sorgente / "Risultati campionamento 2023-2024"
        / "Dataset definitivo dati monitoraggio AnieneWaterLab 23_24.xlsx",
        "Dataset",
        {
            "id": "2023-2024-gommone",
            "etichetta": "Discese in gommone · giugno e settembre 2024",
            "nota_fonte": "Punti 10–14 del foglio «Dataset», rilevati durante "
                          "le discese in gommone.",
        },
        solo_punti=range(10, 20),
    ))

    print("Campagna 2025-2026 (punti fissi)")
    scrivi("campagna-2025-2026.json", dataset_tidy(
        sorgente / "Dataset dati monitoraggio AnieneWaterLab 25_26.xlsx",
        "Dataset 9 punti",
        {
            "id": "2025-2026",
            "etichetta": "Aniene WaterLab · ottobre 2025 – ottobre 2026",
            "nota_fonte": "Foglio «Dataset 9 punti» di «Dataset dati "
                          "monitoraggio AnieneWaterLab 25_26.xlsx».",
        },
        solo_punti=range(1, 10),
    ))

    print("Campagna 2025-2026 (gommone)")
    scrivi("campagna-2025-2026-gommone.json", gommone(sorgente))

    print("Campagna 2025-2026 (prelievi ogni 3 km)")
    scrivi("campagna-2025-2026-asta.json", gommone_tremila(sorgente))

    print("Fatto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
