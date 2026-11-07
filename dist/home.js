import {LEVELS, classify, fmt, fmtInt, loadData, stationMean} from './model.js';
const $ = id => document.getElementById(id);
const CORRECTION_TEXT = {
  arrotondamento: "Valore arrotondato a una cifra nell'Excel, ripreso per intero dal grafico della relazione.",
  'estremo di classe': "L'Excel riporta il limite della classe del kit. Usato il punto medio, come nella relazione.",
  discrepanza: 'Excel e relazione non coincidono: usato il grafico della relazione. Da verificare.',
  refuso: 'Errore di battitura o cella convertita da Excel, corretta.',
  integrazione: 'Valore assente nel foglio Dati e presente nel foglio Dataset dello stesso file.',
  esclusione: "Misura scartata: ossigeno preso accanto a una pianta acquatica (nota di campo) oppure E. coli di Vicovaro 2025, con etichette invertite nel file e da verificare.",
  'limite strumento': 'Valore oltre il fondo scala dello strumento: nel calcolo vale il limite.',
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function riverStrip(data) {
  const lim = data.paramById.lim;
  $('riverStrip').replaceChildren(...data.stations.map(station => {
    const stats = stationMean(data, 'lim', station.id, '23/24');
    if (!stats) return null;
    const band = classify(lim, stats.mean);
    const cell = el('a', 'river-cell');
    cell.href = `dashboard.html?param=lim&view=river`;
    cell.style.background = LEVELS[band.level].bg;
    cell.style.color = LEVELS[band.level].fg;
    cell.title = `${station.name}: LIMeco indicativo ${fmt(stats.mean, lim)}, ${band.label}`;
    cell.append(el('b', '', String(station.id)), el('span', '', station.name), el('em', '', band.label));
    return cell;
  }).filter(Boolean));
}

function paramCards(data) {
  const order = ['ec', 'nh', 'p', 'n', 'od', 'cond', 'lim', 't', 'ph', 'turb'];
  $('paramCards').replaceChildren(...order.map(id => {
    const p = data.paramById[id];
    const n = data.samples.filter(s => s.v[id] !== null && s.v[id] !== undefined).length;
    const card = el('a', 'param-card');
    card.href = `dashboard.html?param=${id}`;
    const top = el('div', 'param-top');
    const count = el('span', '', `${fmtInt(n)} ${p.derived ? 'calcoli' : 'misure'}`);
    count.style.cssText = 'color:var(--teal-light);font-weight:800;font-size:.85rem';
    top.append(el('span', 'param-tag', p.group), count);
    const body = el('div');
    body.append(top, el('h3', 'param-name', p.name), el('p', 'param-desc', p.what), el('p', 'param-desc', p.why));
    card.append(body, el('div', 'param-cta', 'Vedi nella dashboard →'));
    return card;
  }));
}

function corrections(data) {
  const counts = {};
  data.corrections.forEach(c => { counts[c.tipo] = (counts[c.tipo] || 0) + 1; });
  $('corrCount').textContent = `(${fmtInt(data.corrections.length)} valori)`;
  $('corrRows').replaceChildren(...Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([kind, n]) => {
    const row = el('tr');
    row.append(el('td', '', kind[0].toUpperCase() + kind.slice(1)), el('td', '', fmtInt(n)), el('td', '', CORRECTION_TEXT[kind]));
    return row;
  }));
}

loadData().then(data => {
  if ($('riverStrip')) riverStrip(data);
  if ($('paramCards')) paramCards(data);
  if ($('corrRows')) corrections(data);
}).catch(error => {
  if ($('paramCards')) $('paramCards').textContent = 'Non è stato possibile caricare i dati. Ricarica la pagina per riprovare.';
  console.error(error);
});
