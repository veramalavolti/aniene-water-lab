import {LEVELS, PERIODS, PERIOD_COLORS, PERIOD_LABELS, SOURCE_LABELS, STATION_COLORS, ZONES, chartDefaults, classify, fmt, fmtDate, fmtInt, fmtMonth, isGap, loadData, logTick, referenceLines, summarize, unit} from './model.js';

const $ = id => document.getElementById(id);
const PAGE_SIZE = 20;
const VIEWS = ['map', 'river', 'trend', 'matrix', 'stats'];
const state = {param: 'ec', view: 'map', period: 'all', zone: 'all', off: new Set(), log: true, page: 0, frame: 0, selected: null};
let data, chart, map, markers = {}, timer = null;

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};
const param = () => data.paramById[state.param];
const levelStyle = (node, band) => {
  const level = band ? LEVELS[band.level] : null;
  node.style.background = level ? level.bg : '#2D586E';
  node.style.color = level ? level.fg : '#FFFFFF';
};
const visibleStations = () => data.stations.filter(s => !state.off.has(s.id) && (state.zone === 'all' || s.zone === state.zone));
const inPeriod = sample => state.period === 'all' || sample.period === state.period;
function selection() {
  const ids = new Set(visibleStations().map(s => s.id));
  return data.samples.filter(s => ids.has(s.st) && inPeriod(s) && s.v[state.param] !== null && s.v[state.param] !== undefined);
}
const campaigns = rows => [...new Set(rows.map(r => r.month))].sort();
const nameOf = id => data.stationById[id].name;

/* Intestazione e riepilogo */
function renderHeader(rows) {
  const p = param();
  $('heroTitle').textContent = p.name;
  $('heroGroup').textContent = p.group;
  $('unitBadge').textContent = p.unit ? `Unità di misura: ${p.unit}` : 'Scala da 0 a 14';
  $('paramSelect').value = p.id;
  document.title = `${p.name} · Dashboard · Aniene Water Lab`;
  const stats = summarize(rows.map(r => r.v[p.id]));
  const lowest = stats && rows.find(r => r.v[p.id] === stats.min);
  const highest = stats && rows.find(r => r.v[p.id] === stats.max);
  const band = stats && classify(p, stats.mean);
  $('mCount').textContent = stats ? fmtInt(stats.n) : '0';
  $('mCountSub').textContent = `in ${campaigns(rows).length} campagne`;
  $('mMean').textContent = stats ? fmt(stats.mean, p) : '—';
  $('mMeanSub').textContent = stats ? `${p.unit}${band ? ` · ${band.label}` : ''}` : '—';
  $('mMedian').textContent = stats ? fmt(stats.median, p) : '—';
  $('mMin').textContent = stats ? fmt(stats.min, p) : '—';
  $('mMinSub').textContent = lowest ? `${nameOf(lowest.st)}, ${fmtMonth(lowest.month)}` : '—';
  $('mMax').textContent = stats ? fmt(stats.max, p) : '—';
  $('mMaxSub').textContent = highest ? `${nameOf(highest.st)}, ${fmtMonth(highest.month)}` : '—';
  const guide = $('guide');
  guide.replaceChildren(el('p', '', p.what), el('p', '', p.why), el('p', 'ref', p.ref));
  const notes = [];
  if (p.proxy) notes.push('Le classi riguardano il fosforo totale: per l’ortofosfato il confronto è solo indicativo.');
  if (p.id === 'lim') notes.push('Stima non ufficiale, non disponibile per il 2022/23.');
  if (['t', 'od', 'sat', 'ph', 'turb'].includes(p.id) && ['all', '22/23'].includes(state.period)) notes.push('Questo parametro non è stato rilevato con costanza nel 2022/23.');
  if (['cond', 'n', 'p', 'nh', 'ec'].includes(p.id) && ['all', '22/23'].includes(state.period)) notes.push('I valori 2022/23 sono ricostruiti dai grafici della relazione.');
  if (['all', '25'].includes(state.period)) notes.push('Il 2025 comprende solo tre campagne autunnali: le sue medie non equivalgono a quelle di un anno intero.');
  if (p.id === 'ec' && ['all', '25'].includes(state.period)) notes.push('Per Vicovaro E. coli 2025 manca: nel file le etichette sono invertite ed è da verificare.');
  if (p.range) notes.push('Il kit restituisce un intervallo: il valore mostrato ne è il punto medio.');
  if (p.id === 'turb') notes.push('Il tubo di Secchi non distingue i valori sotto 14 NTU: valgono 14, quindi le medie sono un valore massimo.');
  $('warn').textContent = notes.join(' ');
  $('logLabel').hidden = !['river', 'trend'].includes(state.view);
  $('log').checked = state.log;
  $('coverage').textContent = stats ? `Selezione: ${visibleStations().length} stazioni · ${campaigns(rows).map(fmtMonth).slice(0, 1)} – ${campaigns(rows).map(fmtMonth).slice(-1)}` : '';
  $('methodNote').textContent = 'Le stazioni sono numerate da valle (1) a monte (9). La stazione 10, Tenuta del Cavaliere, si è aggiunta nel 2025 tra Ponte Lucano e Casale Caletto. Le medie sono aritmetiche e confrontano le campagne disponibili, che non sono uguali per tutte le stazioni.';
}

function renderLegend() {
  const p = param(), legend = $('legend');
  if (!p.bands.length) {
    legend.replaceChildren(el('span', '', 'Questo parametro non ha classi di riferimento: il colore segnala solo la presenza del dato.'));
    return;
  }
  legend.replaceChildren(el('span', '', 'Classi:'), ...p.bands.map(b => {
    const chip = el('span', 'class-chip', b.label);
    levelStyle(chip, b);
    return chip;
  }));
}

/* Mappa */
function mapValues() {
  const rows = selection(), months = campaigns(rows);
  const month = state.frame > 0 ? months[state.frame - 1] : null;
  return visibleStations().map(station => {
    const own = rows.filter(r => r.st === station.id && (!month || r.month === month));
    const stats = summarize(own.map(r => r.v[state.param]));
    return {station, value: stats ? (month ? stats.max : stats.mean) : null, n: stats ? stats.n : 0};
  });
}
function initMap() {
  map = L.map('map', {scrollWheelZoom: false, attributionControl: true}).setView([41.96, 12.8], 10);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 16, className: 'basemap',
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);
  fetch('fiumi.geojson').then(r => r.json()).then(geo => {
    L.geoJSON(geo, {interactive: false, style: f => ({color: f.properties.name === 'Aniene' ? '#2D7A9A' : '#7FA8BA', weight: f.properties.name === 'Aniene' ? 3.5 : 3, opacity: .85})}).addTo(map);
  });
  map.fitBounds(data.stations.map(s => [s.lat, s.lon]), {padding: [34, 34]});
}
function renderMap() {
  if (!map) initMap();
  const p = param(), rows = selection(), months = campaigns(rows);
  const slider = $('timeline');
  slider.max = months.length;
  state.frame = Math.min(state.frame, months.length);
  slider.value = state.frame;
  const label = state.frame > 0 ? fmtMonth(months[state.frame - 1]) : 'Media del periodo';
  $('timelineLabel').textContent = label;
  slider.setAttribute('aria-valuetext', label);
  Object.values(markers).forEach(m => m.remove());
  markers = {};
  const values = mapValues();
  $('mapList').replaceChildren(...values.map(({station, value}) => {
    const band = value === null ? null : classify(p, value);
    const icon = el('span', value === null ? 'pin pin-empty' : 'pin', String(station.id));
    if (value !== null) levelStyle(icon, band);
    const text = value === null ? 'nessun dato' : `${fmt(value, p)}${unit(p)}${band ? ` · ${band.label}` : ''}`;
    markers[station.id] = L.marker([station.lat, station.lon], {
      icon: L.divIcon({html: icon.outerHTML, className: '', iconSize: [28, 28], iconAnchor: [14, 14]}),
      title: `Stazione ${station.id}, ${station.name}`, alt: `Stazione ${station.id}, ${station.name}: ${text}`, riseOnHover: true,
    }).bindTooltip(`<strong>${station.id} · ${station.name}</strong><br>${text}`).on('click', () => selectStation(station.id)).addTo(map);
    const li = el('li'), button = el('button');
    button.type = 'button';
    if (state.selected === station.id) button.classList.add('sel');
    const name = el('span', 'nm', station.name);
    name.append(el('small', '', band ? band.label : ZONES[station.zone]));
    button.append(icon.cloneNode(true), name, el('span', 'val', value === null ? '—' : fmt(value, p)));
    button.addEventListener('click', () => selectStation(station.id));
    li.append(button);
    return li;
  }));
  map.invalidateSize();
}
function selectStation(id) {
  state.selected = state.selected === id ? null : id;
  const station = data.stationById[id];
  if (state.selected) { map.panTo([station.lat, station.lon]); markers[id]?.openTooltip(); }
  document.querySelectorAll('#mapList button').forEach((b, i) => b.classList.toggle('sel', visibleStations()[i]?.id === state.selected));
}
function togglePlay(force) {
  const on = force ?? !timer;
  clearInterval(timer); timer = null;
  $('play').textContent = on ? '❚❚ Ferma' : '▶ Scorri';
  $('play').setAttribute('aria-pressed', String(on));
  if (!on) return;
  timer = setInterval(() => {
    const total = campaigns(selection()).length;
    state.frame = state.frame >= total ? 1 : state.frame + 1;
    renderMap();
  }, 1100);
}

/* Grafici */
function baseOptions(p, logScale) {
  const canLog = logScale;
  return {
    responsive: true, maintainAspectRatio: false, interaction: {mode: 'nearest', intersect: false},
    plugins: {
      legend: {position: 'bottom', labels: {usePointStyle: true, boxWidth: 8, boxHeight: 8, padding: 14}},
      tooltip: {callbacks: {label: c => `${c.dataset.label}: ${fmt(c.parsed.y, p)}${unit(p)}`}},
      referenceLines: {lines: referenceLines(p)},
    },
    scales: {
      x: {grid: {display: false}, ticks: {autoSkip: true, maxRotation: 0, autoSkipPadding: 12}},
      y: {type: canLog ? 'logarithmic' : 'linear', beginAtZero: !canLog && !['ph', 't'].includes(p.id), title: {display: Boolean(p.unit), text: p.unit},
          ticks: {callback: value => (canLog ? logTick(value) : fmt(Number(value), {digits: 3}))}},
    },
  };
}
function drawChart(config) {
  if (chart) chart.destroy();
  chart = new Chart($('chart'), config);
}
function renderRiver() {
  const p = param(), rows = selection(), stations = visibleStations();
  const periods = PERIODS.filter(per => rows.some(r => r.period === per));
  const datasets = periods.map(per => ({
    label: PERIOD_LABELS[per],
    data: stations.map(s => summarize(rows.filter(r => r.st === s.id && r.period === per).map(r => r.v[p.id]))?.mean ?? null),
    backgroundColor: PERIOD_COLORS[per], borderRadius: 2, maxBarThickness: 44,
  }));
  drawChart({type: 'bar', data: {labels: stations.map(s => `${s.id} · ${s.name}`), datasets}, options: baseOptions(p, state.log && p.log)});
}
function renderTrend() {
  const p = param(), rows = selection(), months = campaigns(rows);
  const labels = [];
  months.forEach((m, i) => {
    if (i && isGap(months[i - 1], m)) labels.push(null);
    labels.push(m);
  });
  const datasets = visibleStations().filter(s => rows.some(r => r.st === s.id)).map(s => ({
    label: `${s.id} · ${s.name}`,
    data: labels.map(m => {
      const value = m ? rows.find(r => r.st === s.id && r.month === m)?.v[p.id] ?? null : null;
      return value === 0 && state.log && p.log ? null : value;       // lo zero non esiste su scala logaritmica
    }),
    borderColor: STATION_COLORS[s.id], backgroundColor: STATION_COLORS[s.id], borderWidth: 2, pointRadius: 2.5, pointHoverRadius: 5, tension: .15,
  }));
  drawChart({type: 'line', data: {labels: labels.map(m => m ? fmtMonth(m) : ''), datasets}, options: baseOptions(p, state.log && p.log)});
}

/* Matrice */
function renderMatrix() {
  const p = param(), rows = selection(), months = campaigns(rows);
  const table = el('table', 'matrix'), head = el('tr');
  head.append(el('th', 'row', 'Stazione'));
  months.forEach((m, i) => {
    if (i && isGap(months[i - 1], m)) head.append(el('th', 'gap'));
    head.append(el('th', '', fmtMonth(m)));
  });
  const thead = el('thead'), tbody = el('tbody');
  thead.append(head);
  const peak = summarize(rows.map(r => r.v[p.id]))?.max || 1;
  visibleStations().forEach(s => {
    const tr = el('tr');
    tr.append(el('th', 'row', `${s.id} · ${s.name}`));
    months.forEach((m, i) => {
      if (i && isGap(months[i - 1], m)) tr.append(el('td', 'gap'));
      const value = rows.find(r => r.st === s.id && r.month === m)?.v[p.id];
      const td = el('td');
      if (value === undefined) { td.className = 'none'; td.textContent = '·'; }
      else {
        const band = classify(p, value);
        td.textContent = fmt(value, p.id === 'ec' ? {digits: 0} : p);
        if (band) levelStyle(td, band);
        else { td.style.background = `rgba(45,88,110,${.12 + .6 * value / peak})`; td.style.color = value / peak > .6 ? '#fff' : '#14262F'; }
        td.title = `${s.name}, ${fmtMonth(m)}: ${fmt(value, p)}${unit(p)}${band ? `, ${band.label}` : ''}`;
      }
      tr.append(td);
    });
    tbody.append(tr);
  });
  table.append(thead, tbody);
  $('matrixView').replaceChildren(table);
}

/* Statistiche */
function renderStats() {
  const p = param(), rows = selection();
  const table = el('table', 'stats-table'), thead = el('thead'), head = el('tr'), tbody = el('tbody');
  ['Stazione', 'Periodo', 'Misure', 'Media', 'Mediana', 'Minimo', 'Massimo', 'Classe della media'].forEach(t => head.append(el('th', '', t)));
  thead.append(head);
  visibleStations().forEach(s => PERIODS.forEach(per => {
    const stats = summarize(rows.filter(r => r.st === s.id && r.period === per).map(r => r.v[p.id]));
    if (!stats) return;
    const band = classify(p, stats.mean), tr = el('tr'), classCell = el('td');
    if (band) { const chip = el('span', 'class-chip', band.label); levelStyle(chip, band); classCell.append(chip); } else classCell.textContent = '—';
    tr.append(el('td', '', `${s.id} · ${s.name}`), el('td', '', per === '25' ? '2025' : per), el('td', 'num', fmtInt(stats.n)), el('td', 'num', fmt(stats.mean, p)), el('td', 'num', fmt(stats.median, p)), el('td', 'num', fmt(stats.min, p)), el('td', 'num', fmt(stats.max, p)), classCell);
    tbody.append(tr);
  }));
  table.append(thead, tbody);
  $('statsView').replaceChildren(table);
}

/* Tabella misure */
function renderRaw(rows) {
  const p = param(), pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  state.page = Math.min(state.page, pages - 1);
  const shown = rows.slice().reverse().slice(state.page * PAGE_SIZE, (state.page + 1) * PAGE_SIZE);
  $('rawBody').replaceChildren(...shown.map(r => {
    const tr = el('tr'), band = classify(p, r.v[p.id]);
    const original = p.derived ? 'calcolato' : (r.raw[p.id] ?? '—');
    tr.append(el('td', '', fmtDate(r)), el('td', '', `${r.st} · ${nameOf(r.st)}`), el('td', '', `${fmt(r.v[p.id], p)}${unit(p)}`), el('td', '', original), el('td', '', band ? band.label : '—'), el('td', '', SOURCE_LABELS[r.src]));
    return tr;
  }));
  $('rawCount').textContent = `(${fmtInt(rows.length)})`;
  $('pageInfo').textContent = `Pagina ${state.page + 1} di ${pages}`;
  $('prev').disabled = state.page === 0;
  $('next').disabled = state.page >= pages - 1;
}

function downloadCsv() {
  const p = param();
  const lines = [['periodo', 'campagna', 'data', 'stazione', 'nome', 'parametro', 'unita', 'valore', 'valore_excel', 'classe', 'fonte'].join(';')];
  selection().forEach(r => {
    const band = classify(p, r.v[p.id]);
    lines.push([r.period, r.month, r.date || '', r.st, nameOf(r.st), p.name, p.unit, String(r.v[p.id]).replace('.', ','), r.raw[p.id] ?? '', band ? band.label : '', SOURCE_LABELS[r.src]].map(x => `"${String(x).replaceAll('"', '""')}"`).join(';'));
  });
  const link = el('a');
  link.href = URL.createObjectURL(new Blob(['﻿' + lines.join('\n')], {type: 'text/csv;charset=utf-8'}));
  link.download = `aniene_${p.id}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

const TITLES = {
  map: ['Le stazioni sulla mappa', 'All’inizio vedi la media del periodo. Sposta il cursore per scorrere le campagne una a una.'],
  river: ['Da monte a valle', 'Valore medio di ogni stazione. A sinistra Subiaco, a destra Ponte Salario, prima del Tevere.'],
  trend: ['Andamento nel tempo', 'Ogni linea è una stazione, ogni punto una campagna. Clicca sulla legenda per nascondere una linea.'],
  matrix: ['Stazioni e campagne', 'Ogni casella è una misura colorata con la sua classe. A colpo d’occhio si vedono i periodi critici.'],
  stats: ['Statistiche per stazione', 'Quante misure ci sono e come si distribuiscono, stazione per stazione.'],
};
function render() {
  const rows = selection(), view = state.view;
  renderHeader(rows);
  renderLegend();
  $('chartTitle').textContent = TITLES[view][0];
  $('chartDesc').textContent = TITLES[view][1];
  $('mapView').hidden = view !== 'map';
  $('chartView').hidden = !['river', 'trend'].includes(view);
  $('matrixView').hidden = view !== 'matrix';
  $('statsView').hidden = view !== 'stats';
  $('empty').hidden = rows.length > 0;
  if (view !== 'map') togglePlay(false);
  if (view === 'map') renderMap();
  if (view === 'river') renderRiver();
  if (view === 'trend') renderTrend();
  if (view === 'matrix') renderMatrix();
  if (view === 'stats') renderStats();
  renderRaw(rows);
  const url = new URL(location.href);
  url.search = new URLSearchParams({param: state.param, view}).toString();
  history.replaceState(null, '', url);
}

function setView(view) {
  state.view = view;
  document.querySelectorAll('.tab-btn').forEach(tab => {
    const active = tab.dataset.view === view;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  $('panel').setAttribute('aria-labelledby', `tab-${view}`);
  render();
}

function buildControls() {
  const select = $('paramSelect');
  const groups = [...new Set(data.params.map(p => p.group))];
  select.replaceChildren(...groups.map(group => {
    const og = el('optgroup');
    og.label = group;
    data.params.filter(p => p.group === group).forEach(p => {
      const option = el('option', '', p.name);
      option.value = p.id;
      og.append(option);
    });
    return og;
  }));
  const chips = $('stationChips');
  chips.replaceChildren(el('span', '', 'Stazioni:'), ...data.stations.map(s => {
    const chip = el('button', 'st-chip');
    chip.type = 'button';
    chip.dataset.station = s.id;
    chip.setAttribute('aria-pressed', 'true');
    chip.style.setProperty('--c', STATION_COLORS[s.id]);
    chip.append(el('i'), `${s.id} ${s.name}`);
    chip.addEventListener('click', () => {
      const id = s.id;
      state.off.has(id) ? state.off.delete(id) : state.off.add(id);
      chip.setAttribute('aria-pressed', String(!state.off.has(id)));
      state.page = 0;
      render();
    });
    return chip;
  }));
  select.addEventListener('change', () => { state.param = select.value; state.frame = 0; state.page = 0; state.log = Boolean(param().log); render(); });
  $('period').addEventListener('change', e => { state.period = e.target.value; state.frame = 0; state.page = 0; render(); });
  $('zone').addEventListener('change', e => { state.zone = e.target.value; state.page = 0; render(); });
  $('log').addEventListener('change', e => { state.log = e.target.checked; render(); });
  $('reset').addEventListener('click', () => {
    Object.assign(state, {period: 'all', zone: 'all', frame: 0, page: 0});
    state.off.clear();
    $('period').value = 'all'; $('zone').value = 'all';
    document.querySelectorAll('.st-chip').forEach(c => c.setAttribute('aria-pressed', 'true'));
    render();
  });
  $('download').addEventListener('click', downloadCsv);
  $('timeline').addEventListener('input', e => { togglePlay(false); state.frame = Number(e.target.value); renderMap(); });
  $('play').addEventListener('click', () => togglePlay());
  $('prev').addEventListener('click', () => { state.page -= 1; renderRaw(selection()); });
  $('next').addEventListener('click', () => { state.page += 1; renderRaw(selection()); });
  const tabs = [...document.querySelectorAll('.tab-btn')];
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => setView(tab.dataset.view));
    tab.addEventListener('keydown', e => {
      const step = {ArrowRight: 1, ArrowLeft: -1}[e.key];
      if (!step) return;
      e.preventDefault();
      const next = tabs[(i + step + tabs.length) % tabs.length];
      next.focus();
      setView(next.dataset.view);
    });
  });
  const dialog = $('infoDialog');
  $('info').addEventListener('click', () => dialog.showModal());
  $('sources').addEventListener('click', () => dialog.showModal());
  $('closeInfo').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });
}

async function init() {
  try {
    data = await loadData();
    chartDefaults(Chart);
    const query = new URLSearchParams(location.search);
    if (data.paramById[query.get('param')]) state.param = query.get('param');
    state.log = Boolean(param().log);
    buildControls();
    $('status').textContent = '';
    setView(VIEWS.includes(query.get('view')) ? query.get('view') : 'map');
  } catch (error) {
    $('status').textContent = 'Non è stato possibile caricare i dati. Ricarica la pagina per riprovare.';
    console.error(error);
  }
}
if (document.readyState === 'complete') init(); else window.addEventListener('load', init);
