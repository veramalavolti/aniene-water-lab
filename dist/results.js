import {LEVELS, PERIOD_COLORS, PERIOD_LABELS, STATION_COLORS, chartDefaults, classify, fmt, fmtMonth, loadData, logTick, referenceLines, stationMean, unit} from './model.js';

const $ = id => document.getElementById(id);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function riverStrip(data) {
  const lim = data.paramById.lim;
  $('riverStrip').replaceChildren(...data.stations.map(station => {
    const mean = stationMean(data, 'lim', station.id, '23/24').mean;
    const band = classify(lim, mean);
    const cell = el('a', 'river-cell');
    cell.href = 'dashboard.html?param=lim&view=river';
    cell.style.background = LEVELS[band.level].bg;
    cell.style.color = LEVELS[band.level].fg;
    cell.append(el('b', '', fmt(mean, lim)), el('span', '', `${station.id} · ${station.name}`), el('em', '', band.label));
    return cell;
  }));
}

function options(param, {log = false, lines = referenceLines(param), legend = true} = {}) {
  return {
    responsive: true, maintainAspectRatio: false, interaction: {mode: 'nearest', intersect: false},
    plugins: {
      legend: {display: legend, position: 'bottom', labels: {usePointStyle: true, boxWidth: 8, boxHeight: 8, padding: 12}},
      tooltip: {callbacks: {label: c => `${c.dataset.label ? `${c.dataset.label}: ` : ''}${fmt(c.parsed.y, param)}${unit(param)}`}},
      referenceLines: {lines},
    },
    scales: {
      x: {grid: {display: false}, ticks: {maxRotation: 45, minRotation: 0, autoSkip: false, font: {size: 11}}},
      y: {type: log ? 'logarithmic' : 'linear', beginAtZero: !log, ticks: {callback: v => (log ? logTick(v) : fmt(Number(v), {digits: 3}))}},
    },
  };
}

function riverChart(data, canvas, paramId, {periods = ['22/23', '23/24'], byClass = false, lines} = {}) {
  const param = data.paramById[paramId];
  const stations = data.stations;
  const datasets = periods.map(period => {
    const means = stations.map(s => stationMean(data, paramId, s.id, period)?.mean ?? null);
    return {
      label: PERIOD_LABELS[period], data: means, borderRadius: 2, maxBarThickness: 40,
      backgroundColor: byClass ? means.map(m => LEVELS[classify(param, m)?.level ?? 2].bg) : PERIOD_COLORS[period],
    };
  });
  return new Chart($(canvas), {
    type: 'bar',
    data: {labels: stations.map(s => s.name), datasets},
    options: options(param, {legend: periods.length > 1, lines}),
  });
}

function ecoliChart(data) {
  const param = data.paramById.ec;
  const rows = data.samples.filter(s => s.period === '23/24');
  const months = [...new Set(rows.map(r => r.month))].sort();
  const datasets = data.stations.map(s => ({
    label: `${s.id} · ${s.name}`,
    data: months.map(m => rows.find(r => r.st === s.id && r.month === m)?.v.ec ?? null),
    borderColor: STATION_COLORS[s.id], backgroundColor: STATION_COLORS[s.id], borderWidth: 2, pointRadius: 2.5, tension: .15, spanGaps: true,
  }));
  const config = options(param, {log: true, lines: [{value: 20000, level: 5, label: 'Oltre 20.000: cattivo'}]});
  config.scales.x.ticks.autoSkip = true;
  config.plugins.legend.labels.font = {size: 11};
  return new Chart($('figEc'), {type: 'line', data: {labels: months.map(fmtMonth), datasets}, options: config});
}

function extras(data) {
  const fmtV = (value, id) => (value === null || value === undefined ? '—' : fmt(value, data.paramById[id]));
  const date = {'2024-06-08': '8 giu 2024', '2024-09-20': '20 set 2024'};
  $('extraRows').replaceChildren(...data.extras.map(e => {
    const row = el('tr');
    row.append(el('td', 'name', `${e.id} · ${e.name}`), el('td', '', date[e.date]), ...['od', 'nh', 'p', 'n', 'ec'].map(id => el('td', 'num', fmtV(e.v[id], id))));
    return row;
  }));
}

function init() {
  chartDefaults(Chart);
  loadData().then(data => {
    riverStrip(data);
    extras(data);
    riverChart(data, 'figT', 't', {periods: ['23/24']});
    riverChart(data, 'figOd', 'od', {periods: ['23/24'], byClass: true});
    riverChart(data, 'figCond', 'cond');
    riverChart(data, 'figN', 'n');
    riverChart(data, 'figP', 'p');
    riverChart(data, 'figNh', 'nh');
    ecoliChart(data);
  }).catch(error => {
    $('riverStrip').textContent = 'Non è stato possibile caricare i dati. Ricarica la pagina per riprovare.';
    console.error(error);
  });
}
if (document.readyState === 'complete') init(); else window.addEventListener('load', init);
