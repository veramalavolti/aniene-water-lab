#!/usr/bin/env python3
"""Costruisce il sito statico in dist/ a partire da contenuti/, templates/ e dati/.

    python3 build.py

Chi modifica i testi dal pannello di redazione tocca solo i file in contenuti/:
questo script rigenera le pagine e viene eseguito automaticamente a ogni
modifica (vedi .github/workflows/pubblica.yml).
"""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:  # pragma: no cover
    sys.exit("Servono PyYAML e Jinja2: pip install pyyaml jinja2")

REPO = Path(__file__).resolve().parent
CONTENUTI = REPO / "contenuti"
TEMPLATES = REPO / "templates"
ASSETS = REPO / "assets"
DATI = REPO / "dati"
DIST = REPO / "dist"

PAGINE = [
    ("index", "index.html.j2", "home.yml"),
    ("citizen-science", "citizen-science.html.j2", "citizen-science.yml"),
    ("campagna-2022-2023", "campagna-2022-2023.html.j2", "campagna-2022-2023.yml"),
    ("campagna-2023-2024", "campagna-2023-2024.html.j2", "campagna-2023-2024.yml"),
    ("campagna-2025-2026", "campagna-2025-2026.html.j2", "campagna-2025-2026.yml"),
    ("contatti", "contatti.html.j2", "contatti.yml"),
]


def leggi(nome: str) -> dict:
    with (CONTENUTI / nome).open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def numero_it(valore) -> str:
    """Formatta un numero all'italiana: 1.234,5 invece di 1234.5."""
    if valore is None:
        return "—"
    if isinstance(valore, str):
        return valore
    if float(valore) == int(valore):
        t = f"{int(valore):,}".replace(",", ".")
    else:
        t = f"{valore:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
        t = t.rstrip("0").rstrip(",") if "," in t else t
    return t


def occhiello(testo: str) -> str:
    """Trasforma il nome di una pagina in una stringa adatta a un id HTML."""
    t = re.sub(r"[^a-z0-9]+", "-", testo.lower())
    return t.strip("-")


def copia_cartella(sorgente: Path, destinazione: Path) -> int:
    if not sorgente.is_dir():
        return 0
    destinazione.mkdir(parents=True, exist_ok=True)
    n = 0
    for file in sorgente.rglob("*"):
        if file.is_dir() or file.name == ".DS_Store":
            continue
        fuori = destinazione / file.relative_to(sorgente)
        fuori.parent.mkdir(parents=True, exist_ok=True)
        if not fuori.exists() or fuori.stat().st_mtime < file.stat().st_mtime:
            shutil.copy2(file, fuori)
        n += 1
    return n


def dati_campagna(nome: str) -> dict:
    percorso = DATI / f"{nome}.json"
    if not percorso.exists():
        raise SystemExit(
            f"Manca {percorso.relative_to(REPO)}. "
            "Esegui prima: python3 scripts/estrai_dati.py"
        )
    return json.loads(percorso.read_text(encoding="utf-8"))


def riepilogo(dati: dict, parametri: dict) -> dict:
    """Numeri di sintesi mostrati sopra la dashboard."""
    valori = [
        (p, (v["v"] if isinstance(v, dict) else v))
        for m in dati["misure"] for p, v in m["p"].items()
    ]
    return {
        "stazioni": len(dati["stazioni"]),
        "campagne": len(dati["campagne"]),
        "prelievi": len(dati["misure"]),
        "misure": len(valori),
        "parametri": sorted(
            {p for p, _ in valori},
            key=lambda p: list(parametri).index(p) if p in parametri else 99,
        ),
        "da": dati["campagne"][0]["etichetta"] if dati["campagne"] else "",
        "a": dati["campagne"][-1]["etichetta"] if dati["campagne"] else "",
    }


def main() -> int:
    if not TEMPLATES.is_dir():
        return print("Manca la cartella templates/") or 1

    impostazioni = leggi("impostazioni.yml")
    contatti = leggi("contatti.yml")
    # l'elenco dei loghi, senza ripetizioni, per la chiusura della home
    loghi, visti = [], set()
    for gruppo in contatti["partner"]["gruppi"]:
        for realta in gruppo["realta"]:
            if realta.get("logo") and realta["logo"] not in visti:
                visti.add(realta["logo"])
                loghi.append(realta)
    parametri_file = leggi("parametri.yml")
    parametri = parametri_file["parametri"]

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["numero"] = numero_it
    env.filters["ancora"] = occhiello

    DIST.mkdir(exist_ok=True)
    # ripulisce solo le pagine, non gli assets copiati in modo incrementale
    for vecchia in DIST.glob("*.html"):
        vecchia.unlink()

    print("Pagine")
    for nome, template, contenuto in PAGINE:
        pagina = leggi(contenuto)
        contesto = {
            "pagina": nome,
            "impostazioni": impostazioni,
            "parametri": parametri,
            "legenda_livelli": parametri_file["legenda_livelli"],
            "c": pagina,
            "loghi": loghi,
            "dati_campagna": dati_campagna,
            "riepilogo": lambda n: riepilogo(dati_campagna(n), parametri),
        }
        uscita = DIST / f"{nome}.html"
        uscita.write_text(env.get_template(template).render(**contesto), encoding="utf-8")
        print(f"  dist/{nome}.html  ({uscita.stat().st_size // 1024} kB)")

    print("Dati")
    (DIST / "dati").mkdir(exist_ok=True)
    n = copia_cartella(DATI, DIST / "dati")
    # le schede dei parametri servono anche al browser, per i tooltip delle soglie
    (DIST / "dati" / "parametri.json").write_text(
        json.dumps(parametri_file, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"  {n + 1} file in dist/dati/")

    print("Assets")
    for sotto in ("css", "js", "img"):
        n = copia_cartella(ASSETS / sotto, DIST / "assets" / sotto)
        if n:
            print(f"  {n} file in dist/assets/{sotto}/")

    for file in ("favicon.svg",):
        origine = ASSETS / "img" / file
        if origine.exists():
            shutil.copy2(origine, DIST / file)

    print("Fatto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
