// Funzioni condivise da home, risultati e dashboard.
export const LEVELS = {
  1: {bg: '#2D7A9A', fg: '#FFFFFF'},
  2: {bg: '#8CA918', fg: '#14262F'},
  3: {bg: '#E9C23B', fg: '#14262F'},
  4: {bg: '#E0812E', fg: '#14262F'},
  5: {bg: '#B03A2E', fg: '#FFFFFF'},
};
// Ordine da monte a valle: il colore segue la posizione lungo il fiume.
export const STATION_COLORS = {9: '#8CA918', 8: '#5C9A3C', 7: '#2F8A5B', 6: '#1F7F78', 5: '#2D7A9A', 4: '#2D586E', 3: '#4A4F8C', 2: '#5E3F86', 1: '#2A1F45'};
export const PERIOD_COLORS = {'22/23': '#2D586E', '23/24': '#B8D432'};
export const PERIOD_LABELS = {'22/23': 'Aprile 2022 – marzo 2023', '23/24': 'Dicembre 2023 – ottobre 2024'};
export const ZONES = {alto: 'Alto corso', medio: 'Medio corso', basso: 'Basso corso'};
const MONTHS = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];

export async function loadData() {
  const response = await fetch('data.json');
  if (!response.ok) throw new Error('data.json non disponibile');
  const data = await response.json();
  data.stationById = Object.fromEntries(data.stations.map(s => [s.id, s]));
  data.paramById = Object.fromEntries(data.params.map(p => [p.id, p]));
  return data;
}

export function fmt(value, param) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const digits = param ? param.digits : 2;
  return new Intl.NumberFormat('it-IT', {maximumFractionDigits: digits, useGrouping: 'always'}).format(value);
}
export const fmtInt = value => new Intl.NumberFormat('it-IT', {useGrouping: 'always'}).format(value);
export function fmtMonth(month) {
  const [year, m] = month.split('-');
  return `${MONTHS[Number(m) - 1]} ${year.slice(2)}`;
}
export function fmtDate(sample) {
  if (!sample.date) return fmtMonth(sample.month);
  const [y, m, d] = sample.date.split('-');
  return `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`;
}
// Sulle scale logaritmiche basta etichettare 1, 2 e 5 di ogni decade.
export const logTick = value => {
  const lead = Number(value) / 10 ** Math.floor(Math.log10(Number(value)));
  return [1, 2, 5].some(n => Math.abs(lead - n) < 1e-6) ? fmt(Number(value), {digits: 3}) : '';
};
export const unit = param => (param.unit ? ` ${param.unit}` : '');

export function classify(param, value) {
  if (value === null || value === undefined || !param.bands.length) return null;
  if (param.scale === 'range') return value >= param.bands[0].lo && value <= param.bands[0].hi ? param.bands[0] : param.bands[1];
  if (param.scale === 'min') return param.bands.find(b => b.min === null || value >= b.min);
  const x = param.scale === 'dev' ? Math.abs(100 - value) : value;
  const strictFirst = param.id === 'nh' || param.id === 'n';
  return param.bands.find((b, i) => b.max === null || (strictFirst && i === 0 ? x < b.max : x <= b.max));
}

export function summarize(values) {
  const v = values.filter(x => x !== null && x !== undefined).sort((a, b) => a - b);
  if (!v.length) return null;
  const mid = Math.floor(v.length / 2);
  return {
    n: v.length,
    mean: v.reduce((a, b) => a + b, 0) / v.length,
    median: v.length % 2 ? v[mid] : (v[mid - 1] + v[mid]) / 2,
    min: v[0],
    max: v[v.length - 1],
  };
}

export function stationMean(data, paramId, stationId, period) {
  return summarize(data.samples.filter(s => s.st === stationId && (!period || s.period === period)).map(s => s.v[paramId]));
}

// Linee di riferimento da disegnare sui grafici.
export function referenceLines(param) {
  const label = (b, v) => `${b.label} ${v}`;
  if (param.scale === 'lim') return param.bands.filter(b => b.max !== null).map(b => ({value: b.max, level: b.level, label: label(b, `≤ ${fmt(b.max, {digits: 3})}`)}));
  if (param.scale === 'min') return param.bands.filter(b => b.min !== null).map(b => ({value: b.min, level: b.level, label: label(b, `≥ ${fmt(b.min, {digits: 2})}`)}));
  if (param.scale === 'range') return [{value: param.bands[0].lo, level: 5, label: 'Minimo 6,5'}, {value: param.bands[0].hi, level: 5, label: 'Massimo 9'}];
  if (param.scale === 'dev') return [{value: 100, level: 1, label: 'Saturazione 100%'}, {value: 80, level: 3, label: 'Scostamento 20'}, {value: 60, level: 4, label: 'Scostamento 40'}];
  return [];
}

export const referenceLinesPlugin = {
  id: 'referenceLines',
  afterDatasetsDraw(chart, _args, options) {
    const {ctx, chartArea: area, scales: {y}} = chart;
    (options.lines || []).forEach(line => {
      const py = y.getPixelForValue(line.value);
      if (py < area.top || py > area.bottom) return;
      const color = LEVELS[line.level].bg;
      ctx.save();
      ctx.strokeStyle = color; ctx.lineWidth = 1.25; ctx.setLineDash([6, 4]);
      ctx.beginPath(); ctx.moveTo(area.left, py); ctx.lineTo(area.right, py); ctx.stroke();
      ctx.setLineDash([]); ctx.font = '700 11px Barlow, sans-serif'; ctx.textAlign = 'right';
      const width = ctx.measureText(line.label).width;
      ctx.fillStyle = 'rgba(255,255,255,.86)'; ctx.fillRect(area.right - width - 7, py - 15, width + 6, 14);
      ctx.fillStyle = line.level === 3 ? '#7A6200' : (line.level === 2 ? '#5A6E0E' : color);
      ctx.fillText(line.label, area.right - 4, py - 4);
      ctx.restore();
    });
  },
};

export function chartDefaults(Chart) {
  Chart.defaults.font.family = "'Barlow', sans-serif";
  Chart.defaults.font.size = 13;
  Chart.defaults.color = '#4A5568';
  Chart.defaults.borderColor = 'rgba(26,51,64,.1)';
  Chart.defaults.animation.duration = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 350;
  Chart.register(referenceLinesPlugin);
}
