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
assert (meta['samples'], meta['measures'], meta['campaigns']) == (146, 1041, 22), meta
assert meta['by_period'] == {'22/23': 55, '23/24': 91}
assert len({e['id'] for e in data['extras']}) == 6

# Valori che coincidono con la relazione
assert round(mean('cond', {7}, '23/24')) == 589
assert round(mean('cond', {6}, '23/24')) == 1301
assert min(values('t')) == 9.2 and max(values('t')) == 23
assert max(values('ph')) == 8.7 and round(min(values('ph')), 1) == 7.2
assert max(values('ec', period='22/23')) <= 20000
assert all(x <= 1000 for x in values('ec', {9}))

# Valori citati nella pagina dei risultati
assert round(mean('od', {8}, '23/24'), 1) == 9.6 and min(values('od', {4})) == 3.5
assert round(mean('od', {3}, '23/24'), 1) == 5.5 and round(mean('od', {4}, '23/24'), 1) == 5.4
assert sum(x < 6 for x in values('od', {3})) == 7
assert all(x >= 8 for x in values('od', {8, 9}))
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

# Il pH di 81 del foglio Dataset non deve mai comparire
assert all(0 < x < 14 for x in values('ph'))
print('ok')
