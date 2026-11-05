#!/usr/bin/env python3
"""Legge i punti dei grafici vettoriali della relazione (PDF) e li salva in data/grafici_relazione.json.

Le campagne 2022/23 non sono nell'Excel: esistono solo come grafici. I grafici sono vettoriali, quindi le
coordinate dei punti si convertono in valori con la scala di ciascun grafico.
Uso: python3 scripts/extract_report_charts.py "Risultati ANIENE 22-23 e 2023-2024 definitivo (1).pdf"
Richiede PyMuPDF.
"""
import json, sys
from pathlib import Path
import fitz

M2223 = ['2022-04','2022-05','2022-06','2022-07','2022-08','2022-09','2022-10','2022-11','2022-12','2023-01','2023-03']
M2223B = M2223[2:]
M2324 = ['2023-12','2024-01','2024-02','2024-03','2024-04','2024-05','2024-06','2024-07','2024-08','2024-09','2024-10']
# chiave: (pagina, fascia verticale del grafico, y dello zero, pt per tacca, valore per tacca, mesi)
CHARTS = {
    'od2324':  (11, (80, 326),  325.0,  29.76, 2,    M2324),
    'cond2223':(13, (100, 205), 200.8,  18.57, 500,  M2223),
    'cond2324':(13, (335, 455), 451.2,  21.55, 500,  M2324),
    'n2223':   (15, (190, 282), 279.8,  21.0,  2,    M2223B),
    'n2324':   (15, (420, 530), 526.6,  12.39, .5,   M2324),
    'p2223':   (17, (160, 345), 343.07, 22.07, .1,   M2223),
    'p2324':   (17, (450, 692), 688.9,  28.8,  .1,   M2324),
    'nh2223':  (20, (250, 436), 434.2,  29.32, .5,   M2223B),
    'nh2324':  (20, (545, 710), 708.2,  31.45, .5,   M2324),
}
ECOLI_X = {114:'2022-04',350:'2022-10',390:'2022-11',429:'2022-12',468:'2023-01',469:'2023-01',508:'2023-03'}
ECOLI_COLORS = [(0.31,0.51,0.74),(0.75,0.31,0.3),(0.61,0.73,0.35),(0.5,0.39,0.63),(0.29,0.68,0.78)]

def series(doc, page, band, y0, dy, dv, months):
    lines = []
    for item in doc[page-1].get_drawings():
        seg = [i for i in item['items'] if i[0] == 'l']
        color, width = item.get('color'), item.get('width') or 0
        if not color or not seg or width < 1.5:
            continue
        pts = [(seg[0][1].x, seg[0][1].y)] + [(i[2].x, i[2].y) for i in seg]
        legend_key = len(pts) == 2 and abs(pts[0][1]-pts[1][1]) < .01
        if band[0] <= pts[0][1] <= band[1] and not legend_key:
            lines.append((tuple(round(v, 2) for v in color), pts))
    colors = []
    for c, _ in lines:
        if c not in colors:
            colors.append(c)
    xs = []
    for x in sorted({round(x) for _, pts in lines for x, _ in pts}):
        if not xs or x - xs[-1] > 5:
            xs.append(x)
    assert len(xs) == len(months), (page, xs)
    out = {}
    for c, pts in lines:
        st = colors.index(c) + 1          # l'ordine delle serie è quello delle stazioni 1..9
        for x, y in pts:
            i = min(range(len(xs)), key=lambda k: abs(xs[k]-x))
            out[f'{st}|{months[i]}'] = round((y0-y)/dy*dv, 4)
    return out

def ecoli(doc):
    out = {}
    for item in doc[22].get_drawings():
        if not any(i[0] == 'c' for i in item['items']):
            continue
        r = item['rect']
        if r.width >= 9 or r.height >= 9 or (r.y0+r.y1)/2 >= 288:
            continue
        color = tuple(round(v, 2) for v in item.get('fill') or ())
        x = round((r.x0+r.x1)/2)
        if color in ECOLI_COLORS and x in ECOLI_X:
            out[f'{ECOLI_COLORS.index(color)+1}|{ECOLI_X[x]}'] = round((284.4-(r.y0+r.y1)/2)/35.3*5000, 4)
    return out

def main(path):
    doc = fitz.open(path)
    data = {k: series(doc, *v) for k, v in CHARTS.items()}
    data['ec2223'] = ecoli(doc)
    target = Path(__file__).resolve().parent.parent/'data'/'grafici_relazione.json'
    target.write_text(json.dumps(data, indent=0))
    print({k: len(v) for k, v in data.items()})

if __name__ == '__main__':
    main(sys.argv[1])
