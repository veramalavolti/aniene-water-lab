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
import math
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
    from markupsafe import Markup, escape
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


def grassetto(testo) -> "Markup":
    """Permette il grassetto nei testi di contenuto scrivendo **così**.

    Chi scrive dal pannello di redazione non deve conoscere l'HTML: mette due
    asterischi attorno alle parole da mettere in evidenza. Tutto il resto viene
    comunque reso innocuo, quindi un testo non può rompere la pagina.
    """
    t = str(escape(str(testo)))
    fuori = []
    for i, pezzo in enumerate(t.split("**")):
        fuori.append(f"<strong>{pezzo}</strong>" if i % 2 else pezzo)
    return Markup("".join(fuori))


def peso_file(percorso: str) -> str:
    """Quanto pesa un documento, per dirlo prima di farlo scaricare."""
    file = DIST / percorso
    if not file.exists():
        return ""
    mb = file.stat().st_size / (1024 * 1024)
    return f"{mb:.1f} MB".replace(".", ",") if mb >= 1 else f"{file.stat().st_size // 1024} kB"


def pagine_pdf(percorso: str) -> str:
    """Il numero di pagine di un PDF, quando la libreria è disponibile."""
    file = DIST / percorso
    if not file.exists():
        return ""
    try:
        import pypdfium2
    except ImportError:
        return ""
    try:
        with pypdfium2.PdfDocument(str(file)) as pdf:
            n = len(pdf)
        return f"{n} pagine" if n > 1 else "1 pagina"
    except Exception:
        return ""


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


def mappa_svg(nome: str, altezza: int = 420) -> "Markup":
    """Disegna la mappa dei punti di campionamento dalle loro coordinate.

    Non usa mappe di sfondo né servizi esterni: i punti stanno alle loro
    coordinate reali, uniti nell'ordine in cui scorre il fiume. L'immagine è
    un SVG scritto dentro la pagina, quindi si carica subito e resta nitida.
    """
    dati = dati_campagna(nome)
    punti = [s for s in dati["stazioni"]
             if isinstance(s.get("lat"), (int, float))
             and isinstance(s.get("lon"), (int, float))]
    if not punti:
        return Markup("")

    larghezza = 900
    bordo = 54
    lat = [p["lat"] for p in punti]
    lon = [p["lon"] for p in punti]
    k = math.cos((min(lat) + max(lat)) / 2 * math.pi / 180)
    xs = [p * k for p in lon]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(lat), max(lat)
    scala = min(
        (larghezza - bordo * 2) / max(max_x - min_x, 1e-6),
        (altezza - bordo * 2) / max(max_y - min_y, 1e-6),
    )
    off_x = bordo + (larghezza - bordo * 2 - (max_x - min_x) * scala) / 2
    off_y = bordo + (altezza - bordo * 2 - (max_y - min_y) * scala) / 2

    def xy(p):
        return (off_x + (p["lon"] * k - min_x) * scala,
                off_y + (max_y - p["lat"]) * scala)

    ordinati = sorted(punti, key=lambda p: p.get("ordine", 0))
    percorso = " ".join(
        ("M" if i == 0 else "L") + f"{xy(p)[0]:.1f} {xy(p)[1]:.1f}"
        for i, p in enumerate(ordinati)
    )

    pezzi = [
        f'<svg viewBox="0 0 {larghezza} {altezza}" role="img" '
        f'aria-label="Mappa dei punti di campionamento" '
        f'xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block;'
        f'background:#EFF4F2">',
        f'<path d="{percorso}" fill="none" stroke="#9CC4D6" stroke-width="7" '
        f'stroke-linejoin="round" stroke-linecap="round"/>',
    ]
    for p in punti:
        x, y = xy(p)
        nome_punto = html.escape(p["nome"])
        pezzi.append(
            f'<g><title>{html.escape(str(p["id"]))} · {nome_punto}</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="#1A3340" stroke="#fff" stroke-width="2.5"/>'
            f'<text x="{x:.1f}" y="{y - 15:.1f}" text-anchor="middle" '
            f'font-family="Barlow, sans-serif" font-size="13" font-weight="700" '
            f'fill="#1A3340">{html.escape(str(p["id"]))}</text></g>'
        )
    pezzi.append(
        f'<text x="{bordo}" y="{altezza - 16}" font-family="Barlow, sans-serif" '
        f'font-size="12" font-weight="700" fill="#4A5568" '
        f'letter-spacing="1">VALLE</text>'
        f'<text x="{larghezza - bordo}" y="{altezza - 16}" text-anchor="end" '
        f'font-family="Barlow, sans-serif" font-size="12" font-weight="700" '
        f'fill="#4A5568" letter-spacing="1">MONTE</text>'
    )
    pezzi.append("</svg>")
    return Markup("".join(pezzi))


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
    # l'elenco dei loghi per la chiusura della home: uno solo per realtà
    loghi, visti = [], set()
    for realta in contatti["rete"]["realta"]:
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
    env.filters["t"] = grassetto
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
            "peso": peso_file,
            "mappa_svg": mappa_svg,
            "pagine": pagine_pdf,
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
