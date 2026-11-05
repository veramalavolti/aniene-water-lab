#!/usr/bin/env python3
"""Controlla che i numeri citati nelle pagine corrispondano a dist/data.json. Uso: python3 scripts/test_data.py"""
import json, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
data = json.loads((ROOT/'dist'/'data.json').read_text())
S = data['samples']

def values(param, stations=None, period=None):
    return [s['v'][param] for s in S if s['v'].get(param) is not None
            and (stations is None or s['st'] in stations) and (period is None or s['period'] == period)]
def mean(*args, **kw):
    return st.mean(values(*args, **kw))

meta = data['meta']
assert (meta['samples'], meta['measures'], meta['campaigns'], meta['stations']) == (173, 1281, 25, 10), meta
assert meta['by_period'] == {'22/23': 55, '23/24': 91, '25': 27}
assert len(data['extras']) == 11

# Valori che coincidono con la relazione
assert round(mean('cond', {7}, '23/24')) == 589
assert round(mean('cond', {6}, '23/24')) == 1301
assert min(values('t', period='23/24')) == 9.2 and max(values('t', period='23/24')) == 23
assert max(values('ph', period='23/24')) == 8.7 and round(min(values('ph', period='23/24')), 1) == 7.2
assert max(values('ec', period='22/23')) <= 20000
assert all(x <= 1000 for x in values('ec', {9}, '23/24'))

# Valori citati nella pagina dei risultati
assert round(mean('od', {8}, '23/24'), 1) == 9.6 and min(values('od', {4}, '23/24')) == 3.5
assert round(mean('od', {3}, '23/24'), 1) == 5.5 and round(mean('od', {4}, '23/24'), 1) == 5.4
assert sum(x < 6 for x in values('od', {3}, '23/24')) == 7
assert all(x >= 8 for x in values('od', {8, 9}, '23/24'))
assert sum(x > 1500 for x in values('cond', period='23/24')) == 23
five = {1, 2, 3, 4, 5}
assert round(mean('n', five, '22/23'), 2) == 1.49 and round(mean('n', five, '23/24'), 2) == 1.10
assert round(mean('p', five, '22/23'), 2) == .24 and round(mean('p', five, '23/24'), 2) == .19
assert round(mean('nh', five, '22/23'), 2) == .52 and round(mean('nh', five, '23/24'), 2) == .31
assert round(mean('nh', {5}, '22/23'), 2) == .71 and round(mean('nh', {4}, '23/24'), 2) == .47
assert max(values('nh')) == 2.73 and max(values('ec')) == 154000
urban = [s for s in S if s['st'] <= 4 and s['period'] == '23/24' and s['v']['ec'] is not None]
assert st.median(s['v']['ec'] for s in urban if s['month'] < '2024-09') == 4300
late = [s['v']['ec'] for s in urban if s['month'] >= '2024-09']
assert (min(late), max(late)) == (61000, 154000)
assert [round(mean('lim', {i}, '23/24'), 2) for i in (9, 8, 7)] == [.88, .64, .57]
assert round(mean('lim', {6}, '23/24'), 2) == .52 and round(mean('lim', {1}, '23/24'), 2) == .26

# Autunno 2025
assert not values('cond', {3}, '25') and len(values('cond', {10}, '25')) == 3   # il punto 3 del file è Tenuta del Cavaliere
assert not values('ec', {8}, '25')
assert round(mean('cond', {10}, '25'), -1) == 1890 and round(mean('cond', {7}, '25')) == 641 and round(mean('cond', {6}, '25')) == 1386
assert max(values('ec', period='25')) == 39800
at = lambda station, month, p: next(s['v'][p] for s in S if s['st'] == station and s['month'] == month)
assert (at(1, '2024-10', 'ec'), at(1, '2025-10', 'ec'), at(2, '2024-10', 'ec'), at(2, '2025-10', 'ec')) == (120000, 32180, 100000, 15270)
assert sum(x > 20000 for x in values('ec', {1}, '25')) == 2 and sum(x > 20000 for x in values('ec', {2}, '25')) == 2
assert (at(4, '2025-11', 'nh'), at(5, '2025-11', 'nh')) == (2.08, 1.96)

# I punti di giugno hanno coordinate e nessun nome di luogo; il picco è del punto D di giugno
june = {e['id']: e for e in data['extras'] if e['date'] == '2024-06-08'}
assert set(june) == set('ABCDE') and all(e['lat'] and e['name'].startswith('Punto') for e in june.values())
assert (june['D']['v']['od'], june['D']['v']['nh'], june['D']['v']['ec']) == (1, 9.9, 200000)
assert next(e for e in data['extras'] if e['id'] == 'D' and e['date'] == '2024-09-20')['name'] == 'Confluenza Poligrafico'

# Il pH di 81 del foglio Dataset non deve mai comparire
assert all(0 < x < 14 for x in values('ph'))
print('ok')
