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
from functools import lru_cache

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


def impronta(percorso: Path) -> str:
    """Un codice breve che cambia quando cambia il file.

    Serve ad attaccarlo agli indirizzi di CSS e JavaScript: senza, i browser
    continuerebbero a usare la copia vecchia anche dopo un aggiornamento del
    sito, e le correzioni non si vedrebbero.
    """
    if not percorso.exists():
        return "1"
    import hashlib
    return hashlib.sha1(percorso.read_bytes()).hexdigest()[:8]


def peso_file(percorso: str) -> str:
    """Quanto pesa un documento, per dirlo prima di farlo scaricare."""
    file = DIST / percorso
    if not file.exists():
        return ""
    mb = file.stat().st_size / (1024 * 1024)
    return f"{mb:.1f} MB".replace(".", ",") if mb >= 1 else f"{file.stat().st_size // 1024} kB"


@lru_cache(maxsize=None)
def dimensioni_img(percorso: str) -> tuple:
    """Larghezza e altezza vere di un'immagine in assets/img.

    Servono a scrivere width e height nel tag: il browser riserva lo spazio
    giusto prima ancora di scaricarla, e la pagina non salta mentre carica.
    """
    try:
        from PIL import Image
        with Image.open(ASSETS / "img" / percorso) as im:
            return im.size
    except Exception:
        # senza Pillow si rinuncia all'attributo: meglio nessuna misura che
        # una misura sbagliata, che schiaccerebbe l'immagine a zero
        return (None, None)


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


_FIUMI = None


def corsi_dacqua() -> list:
    """Il tracciato dell'Aniene e del Tevere, da OpenStreetMap.

    Serve a disegnare le mappe dei punti di campionamento sul corso reale del
    fiume, senza chiedere le mappe di sfondo a nessun servizio esterno: il
    disegno è un SVG scritto dentro la pagina.
    """
    global _FIUMI
    if _FIUMI is None:
        percorso = DATI / "fiumi.geojson"
        if not percorso.exists():
            _FIUMI = []
        else:
            dati = json.loads(percorso.read_text(encoding="utf-8"))
            _FIUMI = [
                {
                    "nome": f.get("properties", {}).get("name", ""),
                    "linee": f["geometry"]["coordinates"]
                    if f["geometry"]["type"] == "MultiLineString"
                    else [f["geometry"]["coordinates"]],
                }
                for f in dati.get("features", [])
            ]
    return _FIUMI


def mappa_svg(nome: str, altezza: int = 420, verticale: bool = False) -> "Markup":
    """Disegna la mappa dei punti di campionamento sul corso reale del fiume.

    L'inquadratura si adatta ai punti della campagna: il fiume entra ed esce
    dai bordi come in una mappa vera, e ogni punto sta alle sue coordinate.

    Con verticale=True la mappa viene ruotata di un quarto di giro, così da
    stare in una colonna stretta accanto alle schede dei luoghi: il monte
    finisce in alto, la valle in basso e il nord punta a sinistra.
    """
    dati = dati_campagna(nome)
    punti = [s for s in dati["stazioni"]
             if isinstance(s.get("lat"), (int, float))
             and isinstance(s.get("lon"), (int, float))]
    if not punti:
        return Markup("")

    larghezza = 520 if verticale else 900
    bordo = 46

    lat = [p["lat"] for p in punti]
    lon = [p["lon"] for p in punti]
    k = math.cos((min(lat) + max(lat)) / 2 * math.pi / 180)

    # Coordinate già orientate come lo schermo: "a" cresce verso destra,
    # "b" verso il basso. Ruotare la mappa vuol dire solo scambiarle.
    def assi(lon_, lat_):
        if verticale:
            # un quarto di giro: il monte va in alto e il nord punta a sinistra
            return (-lat_, -lon_ * k)
        return (lon_ * k, -lat_)

    coppie = [assi(p["lon"], p["lat"]) for p in punti]
    a_min, a_max = min(c[0] for c in coppie), max(c[0] for c in coppie)
    b_min, b_max = min(c[1] for c in coppie), max(c[1] for c in coppie)

    # un margine minimo perché i punti agli estremi non tocchino il bordo
    respiro = max(a_max - a_min, b_max - b_min) * 0.07
    a_min, a_max = a_min - respiro, a_max + respiro
    b_min, b_max = b_min - respiro, b_max + respiro

    # la scala tiene le proporzioni geografiche: niente mappe schiacciate.
    # Poi la finestra si allarga fino a riempire il riquadro, così attorno ai
    # punti si vede altro fiume invece di fondo vuoto.
    utile_x, utile_y = larghezza - bordo * 2, altezza - bordo * 2
    scala = min(utile_x / (a_max - a_min), utile_y / (b_max - b_min))
    centro_a, centro_b = (a_min + a_max) / 2, (b_min + b_max) / 2
    a_min, a_max = centro_a - utile_x / scala / 2, centro_a + utile_x / scala / 2
    b_min, b_max = centro_b - utile_y / scala / 2, centro_b + utile_y / scala / 2

    def proietta(lon_, lat_):
        a, b = assi(lon_, lat_)
        return (bordo + (a - a_min) * scala, bordo + (b - b_min) * scala)

    def dentro(x, y, tolleranza=240):
        return -tolleranza < x < larghezza + tolleranza and -tolleranza < y < altezza + tolleranza

    riquadro = f"maschera-{occhiello(nome)}"
    pezzi = [
        f'<svg viewBox="0 0 {larghezza} {altezza}" role="img" '
        f'aria-label="Mappa dei punti di campionamento sul fiume Aniene" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto;display:block">',
        f'<defs><clipPath id="{riquadro}">'
        f'<rect x="0" y="0" width="{larghezza}" height="{altezza}" rx="8"/>'
        f'</clipPath></defs>',
        f'<rect width="{larghezza}" height="{altezza}" rx="8" fill="#EDF1EE"/>',
        f'<g clip-path="url(#{riquadro})">',
    ]

    # i corsi d'acqua: il Tevere più sottile, l'Aniene in evidenza
    for fiume in corsi_dacqua():
        principale = fiume["nome"].lower().startswith("aniene")
        colore = "#2D7A9A" if principale else "#9CC4D6"
        spessore = 5 if principale else 3.2
        for linea in fiume["linee"]:
            tratto, visibile = [], False
            for lon_, lat_ in linea:
                x, y = proietta(lon_, lat_)
                if dentro(x, y):
                    visibile = True
                tratto.append(f"{x:.1f} {y:.1f}")
            if visibile and len(tratto) > 1:
                d = "M" + " L".join(tratto)
                pezzi.append(
                    f'<path d="{d}" fill="none" stroke="{colore}" '
                    f'stroke-width="{spessore}" stroke-linejoin="round" '
                    f'stroke-linecap="round" opacity="{1 if principale else .7}"/>'
                )

    # i punti di campionamento, da valle a monte
    etichette = len(punti) <= 10
    for indice, p in enumerate(punti):
        x, y = proietta(p["lon"], p["lat"])
        sigla = html.escape(str(p["id"]))
        nome_punto = html.escape(p["nome"])
        pezzi.append(
            f'<g><title>{sigla} · {nome_punto}</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="#1A3340" '
            f'stroke="#fff" stroke-width="2.5"/>'
            f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" '
            f'font-family="Barlow, sans-serif" font-size="11.5" '
            f'font-weight="800" fill="#B8D432">{sigla}</text></g>'
        )
        if etichette:
            # i nomi si alternano sopra e sotto il punto: nel tratto urbano le
            # stazioni sono vicine e le scritte finirebbero una sull'altra
            if verticale:
                # in colonna i nomi stanno di fianco, alternati destra e sinistra
                destra = indice % 2 == 0
                x_testo = x + 17 if destra else x - 17
                y_testo = y + 4.5
                ancora = "start" if destra else "end"
            else:
                sopra = indice % 2 == 0
                x_testo, y_testo = x, (y - 18 if sopra else y + 26)
                ancora = "middle"
            pezzi.append(
                f'<text x="{x_testo:.1f}" y="{y_testo:.1f}" text-anchor="{ancora}" '
                f'font-family="Barlow, sans-serif" font-size="13" '
                f'font-weight="700" fill="#1A3340" '
                f'stroke="#EDF1EE" stroke-width="4" paint-order="stroke" '
                f'>{nome_punto}</text>'
            )

    pezzi.append("</g>")
    stile = ('font-family="Barlow, sans-serif" font-size="12" font-weight="800" '
             'fill="#4A5568" letter-spacing="1.4"')
    if verticale:
        pezzi.append(
            f'<text x="{larghezza / 2:.0f}" y="24" text-anchor="middle" {stile}>MONTE</text>'
            f'<text x="{larghezza / 2:.0f}" y="{altezza - 14}" text-anchor="middle" '
            f'{stile}>VALLE</text>'
            f'<text x="12" y="{altezza - 14}" font-family="Barlow, sans-serif" '
            f'font-size="10.5" fill="#6B7A85">← nord</text>'
            f'<text x="{larghezza - 12}" y="{altezza - 14}" text-anchor="end" '
            f'font-family="Barlow, sans-serif" font-size="10.5" fill="#6B7A85">'
            f'Corso del fiume: OpenStreetMap</text>'
        )
    else:
        pezzi.append(
            f'<text x="{bordo - 18}" y="{altezza - 14}" {stile}>VALLE</text>'
            f'<text x="{larghezza - bordo + 18}" y="{altezza - 14}" text-anchor="end" '
            f'{stile}>MONTE</text>'
            f'<text x="{larghezza - bordo + 18}" y="18" text-anchor="end" '
            f'font-family="Barlow, sans-serif" font-size="10.5" fill="#6B7A85">'
            f'Corso del fiume: OpenStreetMap</text>'
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
    # disponibile anche dentro le macro di parti.html.j2
    env.globals["dimensioni"] = dimensioni_img
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
            "versione": {
                "css": impronta(ASSETS / "css" / "sito.css"),
                "js": impronta(ASSETS / "js" / "dashboard.js"),
            },
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
