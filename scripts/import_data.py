#!/usr/bin/env python3
"""Genera dist/data.json e dist/aniene_dati.csv.

Fonti
  1. Excel "Dataset definitivo dati monitoraggio AnieneWaterLab 23_24.xlsx", foglio Dati (2023/24).
     Il foglio Dataset serve solo per riempire i vuoti: è una copia appiattita con più errori.
  2. data/grafici_relazione.json: punti dei grafici della relazione (2022/23 e controllo 2023/24).
Uso: python3 scripts/import_data.py "percorso/del/file.xlsx"     (richiede openpyxl)
"""
import csv, datetime, json, math, re, sys
from collections import Counter
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parent.parent
CHARTS = json.loads((ROOT/'data'/'grafici_relazione.json').read_text())
M2324 = ['2023-12','2024-01','2024-02','2024-03','2024-04','2024-05','2024-06','2024-07','2024-08','2024-09','2024-10']
DATES = ['2023-12-12','2024-01-16','2024-02-21','2024-03-18','2024-04-15','2024-05-12','2024-06-08','2024-07-17','2024-08-26','2024-09-20','2024-10-23']

STATIONS = [
 dict(id=9,name='Subiaco',lat=41.923838,lon=13.097747,zone='alto',since='aprile 2024'),
 dict(id=8,name='Vicovaro',lat=42.013276,lon=12.893538,zone='medio',since='aprile 2024'),
 dict(id=7,name='Tivoli',full='Tivoli – lungoaniene Peppino Impastato',lat=41.956734,lon=12.807158,zone='medio',since='dicembre 2023'),
 dict(id=6,name='Ponte Lucano',lat=41.954809,lon=12.761799,zone='basso',since='dicembre 2023'),
 dict(id=5,name='Casale Caletto',lat=41.923756,lon=12.608191,zone='basso',since='aprile 2022'),
 dict(id=4,name='Ponte Mammolo',lat=41.923199,lon=12.567930,zone='basso',since='aprile 2022'),
 dict(id=3,name='Casa del Parco',full='Attracco Casa del Parco',lat=41.931552,lon=12.546583,zone='basso',since='aprile 2022'),
 dict(id=2,name='Ponte delle Valli',lat=41.935283,lon=12.524046,zone='basso',since='aprile 2022'),
 dict(id=1,name='Ponte Salario',lat=41.942530,lon=12.501150,zone='basso',since='aprile 2022'),
]
BLOCKS = {1:(4,15),2:(20,31),3:(35,46),4:(51,62),5:(66,77),6:(81,92),7:(96,107),8:(111,122),9:(126,137)}
EXTRA = {'A':(143,156,'Riva dx monte Lanificio / Acea Montenevoso'),'B':(162,173,'Vigna Mangani / Pietralata'),
         'C':(181,192,"Fosso Val Melaina – collettore Val D'Ala"),'D':(198,209,'Confluenza Poligrafico'),
         'E':(215,226,'Scolmatore Fosso Casal de Pazzi'),'F':(231,242,'Ponte Acea / via Benigni')}
LABELS = [('pres','Pressione'),('cond','Conducibilità'),('t','Temperatura'),('od','Ossigeno'),('turb','Torbidità'),
          ('p','Fosfato'),('n','Nitrato'),('nh','Ammonio'),('ph','PH'),('ec','Escherichia')]
DATASET_COL = {'cond':6,'t':7,'od':8,'turb':9,'p':10,'n':11,'ph':12,'nh':13,'ec':14}
P_CLASSES = [(.01,'< 0,02'),(.035,'0,02–0,05'),(.075,'0,05–0,1'),(.15,'0,1–0,2'),(.35,'0,2–0,5'),(.75,'0,5–1')]
N_CLASSES = [(.1,'< 0,2'),(.35,'0,2–0,5'),(.75,'0,5–1'),(1.5,'1–2'),(3.5,'2–5'),(7.5,'5–10')]

corrections = []
def log(kind, st, month, param, original, used, why):
    corrections.append(dict(tipo=kind, stazione=st, campagna=month, parametro=param, originale=str(original), usato=used, motivo=why))

def num(x):
    """Numero da una cella, oppure None. Gli intervalli diventano il punto medio."""
    if x is None or isinstance(x, (datetime.datetime, datetime.time)):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(',,', ',')
    if s.upper() in ('', 'NA', 'N/A'):
        return None
    m = re.fullmatch(r'([\d.,]+)\s*[-–]\s*([\d.,]+)', s)
    if m:
        a, b = (float(g.replace(',', '.')) for g in m.groups())
        return round((a+b)/2, 4)
    try:
        return float(s.replace(',', '.'))
    except ValueError:
        return None

def excel_date_range(x):
    """Excel ha trasformato l'intervallo '2-5' in 2 maggio (anche come seriale 45414)."""
    if isinstance(x, datetime.datetime) and x.month == 5 and x.day == 2:
        return True
    return isinstance(x, (int, float)) and int(x) == 45414

def snap(v, classes):
    return min((c for c, _ in classes), key=lambda c: abs(c-v))

def class_label(v, classes):
    return dict(classes).get(v)

def o2_saturation(od, temp, pres):
    """Solubilità dell'ossigeno in acqua dolce (Benson e Krause), corretta per la pressione."""
    k = temp + 273.15
    cs = math.exp(-139.34411 + 1.575701e5/k - 6.642308e7/k**2 + 1.243800e10/k**3 - 8.621949e11/k**4)
    return 100*od/(cs*(pres or 1013.25)/1013.25)

def level(v, cuts, strict_first=True):
    scores = [1, .5, .25, .125]
    for i, (cut, score) in enumerate(zip(cuts, scores)):
        if (v < cut if strict_first and i == 0 else v <= cut):
            return score
    return 0

def limeco(v):
    if None in (v.get('sat'), v.get('nh'), v.get('n'), v.get('p')):
        return None
    parts = [level(abs(100-v['sat']), (10,20,40,80), False), level(v['nh'], (.03,.06,.12,.24)),
             level(v['n'], (.6,1.2,2.4,4.8)), level(v['p'], (.05,.1,.2,.4), False)]
    return round(sum(parts)/4, 4)

def read_block(grid, a, b, cols):
    out = {}
    for r in range(a, b+1):
        row = grid[r-1]
        lab = str(row[0] or '').strip()
        for key, prefix in LABELS:
            if lab.startswith(prefix):
                out[key] = [row[c] for c in cols]
    return out

def harmonize(param, st, month, cell):
    """Fosfati, nitrati e ammonio: nei grafici della relazione il valore è intero, nell'Excel spesso no."""
    excel = num(cell)
    if excel_date_range(cell):
        excel = 3.5
    key = {'p':'p2324','n':'n2324','nh':'nh2324'}[param]
    chart = CHARTS[key].get(f'{st}|{month}')
    if param == 'n' and chart is not None and chart < .05:
        chart = None                                 # nel grafico un dato presente è disegnato a zero
    if excel is None and chart is None:
        return None, None
    if param == 'nh':
        used = round(max(chart, 0), 2) if chart is not None else excel
    else:
        classes = P_CLASSES if param == 'p' else N_CLASSES
        source = chart if chart is not None else (excel if excel > 0 else classes[0][0])
        used = snap(source, classes)
    if excel is None or abs(excel-used) > 1e-6:
        if excel is not None and abs(excel-used) <= .0501:
            log('arrotondamento', st, month, param, cell, used, "Valore arrotondato a una cifra nell'Excel; ripreso dal grafico della relazione")
        elif param != 'nh' and excel in (.05,.1,.2,.5,1,2,5,.02,0):
            log('estremo di classe', st, month, param, cell, used, 'Excel riporta un estremo della classe del kit; usato il punto medio, come nella relazione')
        else:
            log('discrepanza', st, month, param, cell, used, 'Excel e grafico della relazione non coincidono; usato il grafico')
    return used, excel

def main(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    grid = [list(r) for r in wb['Dati'].iter_rows(values_only=True)]
    flat = [r for r in wb['Dataset'].iter_rows(min_row=2, values_only=True) if r[0]]
    flat_by = {(int(r[0]), r[4].strftime('%Y-%m')): r for r in flat if int(r[0]) <= 9}
    samples, excel_limeco = [], {}

    # 2023/24: i blocchi di Dati hanno una colonna per campagna (B..L)
    for st, (a, b) in BLOCKS.items():
        block = read_block(grid, a, b, range(1, 12))
        times = grid[a-1][1:12]
        for r in range(a, b+1):
            if str(grid[r-1][0] or '').startswith('LIMeco'):
                for i, c in enumerate(grid[r-1][1:12]):
                    m = re.match(r'[\d.,]+', str(c)) if c is not None else None
                    if m:
                        excel_limeco[f'{st}|{M2324[i]}'] = float(m.group().replace(',', '.'))
        for i, month in enumerate(M2324):
            cells = {k: block[k][i] for k in block}
            if all(num(c) is None and not isinstance(c, datetime.time) for c in cells.values()):
                continue
            v, raw, turb_cens = {}, {}, False
            for key in ('cond','t','od','ph','ec'):
                raw[key] = cells.get(key)
                v[key] = num(cells.get(key))
                if v[key] is None and (st, month) in flat_by:
                    other = num(flat_by[(st, month)][DATASET_COL[key]])
                    if other is not None and not (key == 'od' and st == 4 and month == '2024-03'):
                        v[key] = other
                        log('integrazione', st, month, key, cells.get(key), other, 'Vuoto nel foglio Dati, valore presente nel foglio Dataset')
            if isinstance(cells.get('ph'), str) and ',,' in cells['ph']:
                log('refuso', st, month, 'ph', cells['ph'], v['ph'], 'Doppia virgola nel valore')
            if v['ph'] is not None and v['ph'] > 14:
                fixed = v['ph']/10
                log('refuso', st, month, 'ph', v['ph'], fixed, 'Virgola mancante: il pH non può superare 14')
                v['ph'] = fixed
            if st == 4 and month == '2024-03':
                log('esclusione', st, month, 'od', cells.get('od'), None, "Nota di campo: misura presa accanto a una pianta acquatica. Assente anche nel foglio Dataset e nel grafico della relazione")
                v['od'] = None
            turb = cells.get('turb')
            raw['turb'] = turb
            if isinstance(turb, str) and '<' in turb:
                v['turb'], turb_cens = 14.0, True
            else:
                v['turb'] = num(turb)
            for key in ('p','n','nh'):
                raw[key] = cells.get(key)
                v[key], _ = harmonize(key, st, month, cells.get(key))
            pres = cells.get('pres')
            pressure = 1000 + pres.minute if isinstance(pres, datetime.time) else num(pres)
            if v['od'] is not None and v['t'] is not None:
                v['sat'] = round(o2_saturation(v['od'], v['t'], pressure), 1)
            else:
                v['sat'] = None
            v['lim'] = limeco(v)
            t = re.search(r'(\d{1,2})[.:](\d{2})\s*$', str(times[i] or ''))
            samples.append(dict(st=st, month=month, date=DATES[i], time=f'{int(t[1]):02d}:{t[2]}' if t else None, period='23/24',
                                v=v, raw={k: (None if c is None else str(c)) for k, c in raw.items()}, cens=['turb'] if turb_cens else [], src='excel'))

    # 2022/23: solo grafici della relazione
    months = sorted({k.split('|')[1] for name in ('cond2223','n2223','p2223','nh2223','ec2223') for k in CHARTS[name]})
    for st in range(1, 6):
        for month in months:
            g = lambda name: CHARTS[name].get(f'{st}|{month}')
            v = {k: None for k in ('t','od','sat','ph','turb','lim')}
            c = g('cond2223'); v['cond'] = round(c/5)*5 if c is not None else None
            n = g('n2223'); v['n'] = snap(n, N_CLASSES) if n is not None else None
            p = g('p2223'); v['p'] = snap(p, P_CLASSES) if p is not None else None
            h = g('nh2223'); v['nh'] = round(max(h, 0), 2) if h is not None else None
            e = g('ec2223'); v['ec'] = round(e, -2) if e is not None else None
            if any(x is not None for x in v.values()):
                samples.append(dict(st=st, month=month, date=None, time=None, period='22/23', v=v, raw={}, cens=[], src='relazione'))

    # Punti straordinari A–F (8 giugno e 20 settembre 2024)
    extras = []
    for pid, (a, b, name) in EXTRA.items():
        block = read_block(grid, a, b, (1, 2))
        for i, (date, month) in enumerate((('2024-06-08','2024-06'),('2024-09-20','2024-09'))):
            v, raw = {}, {}
            for key in ('cond','t','od','turb','p','n','nh','ph','ec'):
                cell = block.get(key, [None, None])[i]
                raw[key] = None if cell is None else str(cell)
                v[key] = 3.5 if excel_date_range(cell) else num(cell)
            if pid == 'C' and i == 0:
                v['ec'] = 17200.0
                log('refuso', pid, month, 'ec', block['ec'][i], 17200.0, 'Cella interpretata da Excel come orario; valore dal foglio Dataset')
            if any(x is not None for x in v.values()):
                extras.append(dict(id=pid, name=name, month=month, date=date, v=v, raw=raw))

    samples.sort(key=lambda s: (s['month'], -s['st']))
    data = dict(meta=meta(samples, extras), stations=STATIONS, params=PARAMS, samples=samples, extras=extras,
                corrections=corrections, excel_limeco=excel_limeco)
    (ROOT/'dist'/'data.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',',':')))
    write_csv(samples, extras)
    print(data['meta']); print(Counter(c['tipo'] for c in corrections))

def meta(samples, extras):
    measures = sum(1 for s in samples for k, x in s['v'].items() if x is not None and k not in ('sat','lim'))
    return dict(samples=len(samples), measures=measures, campaigns=len({s['month'] for s in samples}), stations=9,
                extras=len(extras), by_period={p: sum(1 for s in samples if s['period'] == p) for p in ('22/23','23/24')})

def write_csv(samples, extras):
    names = {s['id']: s['name'] for s in STATIONS}
    with open(ROOT/'dist'/'aniene_dati.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['periodo','campagna','data','stazione','nome','parametro','unita','valore','valore_excel','fonte','limite_strumento'])
        for s in samples:
            for p in PARAMS:
                x = s['v'].get(p['id'])
                if x is None:
                    continue
                source = 'calcolato' if p['id'] in ('sat','lim') else ('grafico relazione' if s['src'] == 'relazione' else 'excel 23/24')
                w.writerow([s['period'], s['month'], s['date'] or '', s['st'], names[s['st']], p['name'], p['unit'], str(x).replace('.', ','),
                            s['raw'].get(p['id']) or '', source, 'sì' if p['id'] in s['cens'] else ''])
        for e in extras:
            for p in PARAMS:
                x = e['v'].get(p['id'])
                if x is not None:
                    w.writerow(['23/24 straordinario', e['month'], e['date'], e['id'], e['name'], p['name'], p['unit'], str(x).replace('.', ','), e['raw'].get(p['id']) or '', 'excel 23/24', ''])

LIMECO_LABELS = ['Elevato','Buono','Sufficiente','Scarso','Cattivo']
def bands(cuts, labels=LIMECO_LABELS):
    return [dict(max=c, label=l, level=i+1) for i, (c, l) in enumerate(zip(cuts+[None], labels))]

PARAMS = [
 dict(id='ec',name='Escherichia coli',short='E. coli',unit='UFC/100 ml',group='Batteri',digits=0,log=True,tool='hyserve',
      what="Batterio che vive nell'intestino di persone e animali. Trovarlo in acqua indica un inquinamento fecale recente.",
      why="Non è un veleno in sé: segnala che possono esserci anche altri microrganismi patogeni.",
      ref='Classi del LIM: 100, 1.000, 5.000, 20.000 UFC/100 ml',bands=bands([100,1000,5000,20000]),scale='lim'),
 dict(id='nh',name='Ammonio',short='NH₄⁺',unit='mg/L',group='Nutrienti',digits=2,tool='checker',
      what="Forma dell'azoto legata a scarichi fognari, liquami e reflui. In un fiume ben ossigenato si trasforma rapidamente in nitrato.",
      why="È un campanello d'allarme: indica apporti organici recenti o carenza di ossigeno, ed è tossico per pesci e invertebrati.",
      ref='Classi LIMeco: 0,03, 0,06, 0,12, 0,24 mg/L',bands=bands([.03,.06,.12,.24]),scale='lim'),
 dict(id='p',name='Fosforo ortofosfato',short='P-PO₄',unit='mg/L',group='Nutrienti',digits=3,tool='fww',range=True,
      what="Il fosforo arriva da scarichi urbani e industriali, fertilizzanti e allevamenti. Si muove soprattutto legato alle particelle di suolo.",
      why="In eccesso nutre alghe e piante acquatiche: la loro decomposizione consuma ossigeno (eutrofizzazione).",
      ref='Classi LIMeco del fosforo totale, usate qui solo come confronto indicativo: 0,05, 0,10, 0,20, 0,40 mg/L',bands=bands([.05,.1,.2,.4]),scale='lim',proxy=True),
 dict(id='n',name='Azoto nitrico',short='N-NO₃',unit='mg/L',group='Nutrienti',digits=2,tool='fww',range=True,
      what="L'azoto contenuto nei nitrati, solubili e mobili: seguono l'acqua nei campi, nel suolo e nelle falde.",
      why="Con i fosfati favorisce la crescita eccessiva di alghe. Moltiplicando per 4,427 si ottiene la concentrazione dei nitrati.",
      ref='Classi LIMeco: 0,6, 1,2, 2,4, 4,8 mg/L',bands=bands([.6,1.2,2.4,4.8]),scale='lim'),
 dict(id='od',name='Ossigeno disciolto',short='O₂',unit='mg/L',group='Stato di base',digits=1,tool='winkler',
      what="L'ossigeno sciolto in acqua, che pesci, insetti e batteri aerobici respirano.",
      why="Sotto 6 mg/L molte specie soffrono, sotto 4 mg/L la situazione è critica per la maggior parte degli organismi.",
      ref='Riferimenti della relazione: ottimale 6–12 mg/L, trote oltre 8 mg/L',
      bands=[dict(min=8,label='Adatto ai salmonidi',level=1),dict(min=6,label='Ottimale',level=2),dict(min=4,label='Stress',level=4),dict(min=None,label='Critico',level=5)],scale='min'),
 dict(id='sat',name='Saturazione di ossigeno',short='O₂ %',unit='%',group='Stato di base',digits=0,derived=True,tool='winkler',
      what="Quanto ossigeno c'è rispetto a quello che l'acqua può contenere a quella temperatura e pressione. È calcolata da ossigeno, temperatura e pressione.",
      why="Il valore ideale è vicino al 100%. Molto sotto indica consumo di ossigeno; molto sopra può indicare fioriture algali.",
      ref='Scostamento da 100 secondo il LIMeco: 10, 20, 40, 80 punti',bands=bands([10,20,40,80]),scale='dev'),
 dict(id='cond',name='Conducibilità',short='EC',unit='µS/cm',group='Stato di base',digits=0,tool='dist3',
      what="Misura quanti sali sono disciolti in acqua. Ogni fiume ha un intervallo tipico, legato soprattutto alla geologia.",
      why="Un aumento improvviso può segnalare un apporto esterno di sali o contaminanti.",
      ref='In aree calcaree 250–800 µS/cm; oltre 1.000 attività antropica o forte evaporazione; oltre 1.500 da approfondire',
      bands=[dict(max=800,label='Tipico di area calcarea',level=1),dict(max=1000,label='Sopra il tipico',level=3),dict(max=1500,label='Alto',level=4),dict(max=None,label='Molto alto',level=5)],scale='lim'),
 dict(id='t',name='Temperatura',short='T',unit='°C',group='Stato di base',digits=1,tool='dist3',
      what="La temperatura dell'acqua segue le stagioni e cresce da monte a valle.",
      why="L'acqua calda trattiene meno ossigeno, e un salto anomalo può indicare un inquinamento termico.",
      ref='Nessuna soglia: si guarda la coerenza con la stagione',bands=[],scale='none'),
 dict(id='ph',name='pH',short='pH',unit='',group='Stato di base',digits=1,tool='lowcost',
      what="Indica quanto l'acqua è acida o basica. Nei fiumi di area calcarea tende a essere leggermente basica.",
      why="Valori alterati limitano la distribuzione delle specie negli habitat acquatici.",
      ref='Intervallo ottimale 6,5–9',bands=[dict(lo=6.5,hi=9,label='Nel range ottimale',level=1),dict(label='Fuori range',level=5)],scale='range'),
 dict(id='turb',name='Torbidità',short='NTU',unit='NTU',group='Stato di base',digits=0,tool='fww',
      what="Quanto l'acqua è opaca per fitoplancton o sedimenti. Si legge con il tubo di Secchi del kit FreshWater Watch.",
      why="I sedimenti possono arrivare con le piogge da cantieri, cave, campi e superfici asfaltate.",
      ref='Il tubo non distingue i valori sotto 14 NTU: nel calcolo valgono 14, quindi le medie sono un valore massimo',bands=[],scale='none'),
 dict(id='lim',name='LIMeco indicativo',short='LIMeco',unit='punteggio 0–1',group='Indice',digits=2,derived=True,tool=None,
      what="Punteggio da 0 a 1 che riassume ossigeno, ammonio, azoto nitrico e fosforo. Più è alto, meglio è.",
      why="È una stima, non una classificazione ufficiale: usa l'ortofosfato al posto del fosforo totale e misure di citizen science.",
      ref='Classi: Elevato ≥ 0,66, Buono ≥ 0,50, Sufficiente ≥ 0,33, Scarso ≥ 0,17, Cattivo sotto 0,17',
      bands=[dict(min=.66,label='Elevato',level=1),dict(min=.5,label='Buono',level=2),dict(min=.33,label='Sufficiente',level=3),dict(min=.17,label='Scarso',level=4),dict(min=None,label='Cattivo',level=5)],scale='min'),
]

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT.parent/'Dataset definitivo dati monitoraggio AnieneWaterLab 23_24.xlsx'))
