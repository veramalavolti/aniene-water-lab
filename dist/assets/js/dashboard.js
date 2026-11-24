/* Dashboard interattive dei monitoraggi dell'Aniene.
 *
 * Ogni dashboard è un <div class="dashboard" data-dati="nome-del-file">.
 * Qui dentro non ci sono testi di contenuto: parametri, soglie, spiegazioni e
 * possibili cause arrivano da dati/parametri.json, che a sua volta viene da
 * contenuti/parametri.yml. Per cambiare una soglia o una spiegazione si
 * modifica quel file, non questo.
 */
(function () {
  'use strict';

  var COLORI_LIVELLO = { 1: '#2D7A9A', 2: '#8CA918', 3: '#E9C23B', 4: '#E0812E', 5: '#B03A2E' };
  var COLORI_SERIE = [
    '#1A3340', '#8CA918', '#B03A2E', '#2D7A9A', '#E0812E',
    '#6B4C9A', '#2D586E', '#C2185B', '#4E7A2A', '#8D6E1E'
  ];
  var SVGNS = 'http://www.w3.org/2000/svg';

  // ----------------------------------------------------------------- utilità

  function el(tag, attributi, testo) {
    var n = document.createElementNS(SVGNS, tag);
    for (var k in attributi) if (attributi[k] !== undefined && attributi[k] !== null) {
      n.setAttribute(k, attributi[k]);
    }
    if (testo !== undefined) n.textContent = testo;
    return n;
  }

  function html(tag, classe, testo) {
    var n = document.createElement(tag);
    if (classe) n.className = classe;
    if (testo !== undefined) n.textContent = testo;
    return n;
  }

  /* Un valore può essere un numero oppure {v: numero, lim: "<" | ">" | "~"}
     quando il kit di campo è andato fuori scala. */
  function valore(v) {
    if (v === null || v === undefined) return null;
    return typeof v === 'object' ? v.v : v;
  }

  function limite(v) {
    return (v && typeof v === 'object' && v.lim) ? v.lim : '';
  }

  function formatta(v, decimali) {
    var n = valore(v);
    if (n === null) return '—';
    var d = decimali === undefined ? (Math.abs(n) >= 100 ? 0 : Math.abs(n) >= 10 ? 1 : 2) : decimali;
    var t = n.toFixed(d).replace('.', ',');
    if (t.indexOf(',') > -1) t = t.replace(/,?0+$/, '');
    t = t.replace(/\B(?=(\d{3})+(?!\d))/, '');
    if (Math.abs(n) >= 10000) t = Math.round(n).toLocaleString('it-IT');
    var l = limite(v);
    return (l === '~' ? '≈ ' : l ? l + ' ' : '') + t;
  }

  function dataBreve(iso) {
    var p = String(iso).split('-');
    return p.length === 3 ? p[2] + '/' + p[1] + '/' + p[0].slice(2) : iso;
  }

  /* Classe di qualità di un valore, in base alle soglie del parametro. */
  function livello(parametro, v) {
    var n = valore(v);
    if (n === null || !parametro.soglie || !parametro.soglie.length) return 0;
    var verso = parametro.verso || 'alto_critico';
    var soglie = parametro.soglie.slice();
    /* Restituisce il livello della soglia peggiore superata, 0 se il valore
       sta entro tutte le soglie. Le soglie elencate non sono per forza una
       scala completa di qualità, quindi "nessuna soglia superata" non viene
       mai presentato come "elevato". */
    var peggiore = 0;
    soglie.forEach(function (s) {
      var superata =
        verso === 'alto_critico' ? n >= s.valore :
        verso === 'basso_critico' ? n <= s.valore :
        verso === 'intervallo' ? (s.valore >= 7.5 ? n > s.valore : n < s.valore) :
        false;
      if (superata && s.livello > peggiore) peggiore = s.livello;
    });
    return peggiore;
  }

  function colore(parametro, v) {
    var l = livello(parametro, v);
    return l ? COLORI_LIVELLO[l] : '#4E7A8C';
  }

  // ---------------------------------------------------------------- scale

  function scalaLineare(min, max, da, a) {
    if (max === min) max = min + 1;
    return function (v) { return da + (v - min) / (max - min) * (a - da); };
  }

  function scalaLog(min, max, da, a) {
    var lmin = Math.log10(Math.max(min, 0.5));
    var lmax = Math.log10(Math.max(max, lmin * 10 + 1));
    return function (v) {
      var l = Math.log10(Math.max(v, Math.pow(10, lmin)));
      return da + (l - lmin) / (lmax - lmin) * (a - da);
    };
  }

  function tacche(min, max, quante) {
    var passo = (max - min) / quante;
    var mag = Math.pow(10, Math.floor(Math.log10(passo || 1)));
    var norm = passo / mag;
    var buono = norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1;
    passo = buono * mag;
    var out = [], v = Math.ceil(min / passo) * passo;
    for (; v <= max + passo * 0.001 && out.length < 20; v += passo) out.push(Math.round(v / passo) * passo);
    return out;
  }

  function taccheLog(min, max) {
    var out = [];
    for (var e = Math.floor(Math.log10(Math.max(min, 1))); e <= Math.ceil(Math.log10(max)); e++) {
      out.push(Math.pow(10, e));
    }
    return out.filter(function (v) { return v <= max * 1.2; });
  }

  // ------------------------------------------------------------ costruzione

  function Dashboard(nodo, dati, schede) {
    this.nodo = nodo;
    this.dati = dati;
    this.schede = schede;
    this.parametriDisponibili = this.trovaParametri();
    this.parametro = this.parametriDisponibili[0];
    this.TUTTI = '__tutti__';
    this.vista = dati.stazioni.length > 12 ? 'profilo' : 'andamento';
    this.campagna = 'tutte';
    this.spente = {};
    this.costruisci();
    this.disegna();
  }

  Dashboard.prototype.trovaParametri = function () {
    var presenti = {};
    this.dati.misure.forEach(function (m) {
      for (var p in m.p) presenti[p] = true;
    });
    var ordine = Object.keys(this.schede.parametri);
    return ordine.filter(function (p) { return presenti[p]; });
  };

  Dashboard.prototype.scheda = function () {
    return this.schede.parametri[this.parametro] || {};
  };

  Dashboard.prototype.stazioniVisibili = function () {
    var spente = this.spente;
    return this.dati.stazioni.filter(function (s) { return !spente[s.id]; });
  };

  Dashboard.prototype.costruisci = function () {
    var self = this;
    this.nodo.textContent = '';

    // barra dei parametri
    var barra = html('div', 'dash-barra');
    barra.setAttribute('role', 'group');
    barra.setAttribute('aria-label', 'Scegli il parametro da esplorare');
    this.bottoniParametro = {};
    barra.appendChild(html('span', 'dash-barra-titolo', 'Parametro'));

    var tutti = html('button', 'dash-par tutti', 'Tutti insieme');
    tutti.type = 'button';
    tutti.setAttribute('aria-pressed', 'false');
    tutti.title = 'Mostra un grafico per ogni parametro';
    tutti.addEventListener('click', function () { self.scegliParametro(self.TUTTI); });
    this.bottoniParametro[this.TUTTI] = tutti;
    barra.appendChild(tutti);

    this.parametriDisponibili.forEach(function (p) {
      var b = html('button', 'dash-par', self.schede.parametri[p].nome);
      b.type = 'button';
      b.setAttribute('aria-pressed', p === self.parametro ? 'true' : 'false');
      b.addEventListener('click', function () { self.scegliParametro(p); });
      self.bottoniParametro[p] = b;
      barra.appendChild(b);
    });
    this.nodo.appendChild(barra);

    // controlli: vista, campagna, scarica
    var controlli = html('div', 'dash-controlli');

    var lVista = html('label');
    lVista.appendChild(html('span', null, 'Come guardare i dati'));
    this.selVista = html('select');
    [['andamento', 'Andamento nel tempo'], ['profilo', 'Profilo da monte a valle'],
     ['mappa', 'Mappa dei punti']]
      .forEach(function (o) {
        var opt = html('option', null, o[1]);
        opt.value = o[0];
        self.selVista.appendChild(opt);
      });
    this.selVista.value = this.vista;
    this.selVista.addEventListener('change', function () {
      self.vista = this.value;
      self.aggiornaControlli();
      self.disegna();
    });
    lVista.appendChild(this.selVista);
    controlli.appendChild(lVista);
    this.lVista = lVista;

    this.lCampagna = html('label');
    this.lCampagna.appendChild(html('span', null, 'Campagna'));
    this.selCampagna = html('select');
    var optTutte = html('option', null, 'Media di tutte le campagne');
    optTutte.value = 'tutte';
    this.selCampagna.appendChild(optTutte);
    this.dati.campagne.forEach(function (c) {
      var opt = html('option', null, c.etichetta + ' · ' + dataBreve(c.id));
      opt.value = c.id;
      self.selCampagna.appendChild(opt);
    });
    this.selCampagna.addEventListener('change', function () {
      self.campagna = this.value;
      self.disegna();
    });
    this.lCampagna.appendChild(this.selCampagna);
    controlli.appendChild(this.lCampagna);

    // scelta rapida dei punti: tutti insieme oppure uno solo
    var lPunti = html('label');
    lPunti.appendChild(html('span', null, 'Punti di monitoraggio'));
    this.selPunti = html('select');
    var optTutti = html('option', null, 'Tutti i punti');
    optTutti.value = 'tutti';
    this.selPunti.appendChild(optTutti);
    this.dati.stazioni.forEach(function (s) {
      var opt = html('option', null, 'Solo ' + self.etichettaStazione(s));
      opt.value = 'solo:' + s.id;
      self.selPunti.appendChild(opt);
    });
    this.optPersonalizzata = html('option', null, 'Selezione personalizzata');
    this.optPersonalizzata.value = 'misto';
    this.optPersonalizzata.hidden = true;
    this.selPunti.appendChild(this.optPersonalizzata);
    this.selPunti.addEventListener('change', function () {
      var v = this.value;
      self.spente = {};
      if (v.indexOf('solo:') === 0) {
        var scelto = v.slice(5);
        self.dati.stazioni.forEach(function (s) {
          if (s.id !== scelto) self.spente[s.id] = true;
        });
      }
      self.aggiornaChip();
      self.disegna();
    });
    lPunti.appendChild(this.selPunti);
    controlli.appendChild(lPunti);

    this.nodo.appendChild(controlli);

    // intestazione del parametro
    this.intestazione = html('div', 'dash-intestazione');
    this.nodo.appendChild(this.intestazione);

    // area del grafico
    this.areaGrafico = html('div', 'dash-grafico');
    this.suggerimento = html('div', 'suggerimento');
    this.suggerimento.setAttribute('role', 'status');
    this.areaGrafico.appendChild(this.suggerimento);
    this.nodo.appendChild(this.areaGrafico);

    this.legenda = html('div', 'dash-legenda');
    this.nodo.appendChild(this.legenda);

    this.spiegaSoglie = html('div', 'soglie-spiegate');
    this.nodo.appendChild(this.spiegaSoglie);

    this.barraStazioni = html('div', 'dash-stazioni');
    this.barraStazioni.setAttribute('role', 'group');
    this.barraStazioni.setAttribute('aria-label', 'Mostra o nascondi le stazioni');
    this.nodo.appendChild(this.barraStazioni);

    this.guida = html('div', 'dash-guida');
    this.nodo.appendChild(this.guida);

    // tabella dei dati
    var dettagli = html('details', 'dash-tabella');
    dettagli.appendChild(html('summary', null, 'Vedi i numeri in tabella'));
    this.tabella = html('div', 'tabella-scroll');
    dettagli.appendChild(this.tabella);
    dettagli.addEventListener('toggle', function () {
      if (dettagli.open) self.disegnaTabella();
    });
    this.dettagli = dettagli;
    this.nodo.appendChild(dettagli);

    var pie = html('div', 'dash-pie');
    pie.appendChild(html('span', null,
      this.dati.stazioni.length + ' punti · ' + this.dati.campagne.length + ' campagne · ' +
      this.dati.misure.length + ' prelievi'));
    if (this.dati.nota_fonte) pie.appendChild(html('span', null, this.dati.nota_fonte));
    var scarica = html('button', 'bottone bottone-chiaro', 'Scarica i dati (CSV)');
    scarica.type = 'button';
    scarica.addEventListener('click', function () { self.scaricaCsv(); });
    pie.appendChild(scarica);
    this.nodo.appendChild(pie);

    this.aggiornaControlli();
    this.disegnaStazioni();

    if (window.ResizeObserver) {
      var ultima = 0;
      new ResizeObserver(function () {
        var l = self.areaGrafico.clientWidth;
        if (Math.abs(l - ultima) > 12) { ultima = l; self.disegna(); }
      }).observe(this.areaGrafico);
    }
  };

  Dashboard.prototype.scegliParametro = function (nome) {
    this.parametro = nome;
    for (var k in this.bottoniParametro) {
      this.bottoniParametro[k].setAttribute('aria-pressed', k === nome ? 'true' : 'false');
    }
    this.aggiornaControlli();
    this.disegna();
  };

  Dashboard.prototype.aggiornaControlli = function () {
    // la scelta della campagna serve solo quando il grafico mostra un momento
    var serve = this.parametro === this.TUTTI || this.vista !== 'andamento';
    this.lCampagna.style.display = serve ? '' : 'none';
    // nella vista d'insieme la scelta della forma del grafico non si applica
    this.lVista.style.display = this.parametro === this.TUTTI ? 'none' : '';
  };

  Dashboard.prototype.disegnaStazioni = function () {
    var self = this;
    this.barraStazioni.textContent = '';

    var azioni = html('span', 'dash-punti-azioni');
    var bTutti = html('button', 'dash-mini', 'Mostra tutti');
    bTutti.type = 'button';
    bTutti.addEventListener('click', function () {
      self.spente = {};
      self.selPunti.value = 'tutti';
      self.aggiornaChip();
      self.disegna();
    });
    azioni.appendChild(bTutti);
    this.barraStazioni.appendChild(azioni);

    this.chip = {};
    this.dati.stazioni.forEach(function (s, i) {
      var b = html('button', 'stz');
      b.type = 'button';
      b.setAttribute('aria-pressed', 'true');
      var punto = html('span', 'punto-colore');
      punto.style.background = COLORI_SERIE[i % COLORI_SERIE.length];
      b.appendChild(punto);
      b.appendChild(document.createTextNode(self.etichettaStazione(s)));
      b.addEventListener('click', function (ev) {
        // con alt (o doppio clic) si isola il punto, altrimenti si aggiunge o si toglie
        if (ev.altKey) {
          self.spente = {};
          self.dati.stazioni.forEach(function (x) { if (x.id !== s.id) self.spente[x.id] = true; });
        } else {
          if (!self.spente[s.id] && self.stazioniVisibili().length === 1) return;
          self.spente[s.id] = !self.spente[s.id];
        }
        self.aggiornaChip();
        self.disegna();
      });
      b.addEventListener('dblclick', function () {
        self.spente = {};
        self.dati.stazioni.forEach(function (x) { if (x.id !== s.id) self.spente[x.id] = true; });
        self.aggiornaChip();
        self.disegna();
      });
      b.title = 'Clic per mostrare o nascondere · doppio clic per vedere solo questo punto';
      self.chip[s.id] = b;
      self.barraStazioni.appendChild(b);
    });
  };

  /* Tiene allineati i pulsanti dei punti e il menu a tendina. */
  Dashboard.prototype.aggiornaChip = function () {
    var self = this;
    this.dati.stazioni.forEach(function (s) {
      if (self.chip[s.id]) {
        self.chip[s.id].setAttribute('aria-pressed', self.spente[s.id] ? 'false' : 'true');
      }
    });
    var visibili = this.stazioniVisibili();
    if (!visibili.length || visibili.length === this.dati.stazioni.length) {
      this.selPunti.value = 'tutti';
    } else if (visibili.length === 1) {
      this.selPunti.value = 'solo:' + visibili[0].id;
    } else {
      this.optPersonalizzata.hidden = false;
      this.selPunti.value = 'misto';
    }
  };

  Dashboard.prototype.etichettaStazione = function (s) {
    if (/^\d/.test(s.id) || s.id.length <= 2) return s.id + ' · ' + s.nome;
    return s.nome;
  };

  // ------------------------------------------------------------- dati vista

  Dashboard.prototype.valoriPunto = function (stazioneId, campagnaId) {
    var p = this.parametro, out = [];
    this.dati.misure.forEach(function (m) {
      if (m.s !== stazioneId) return;
      if (campagnaId && campagnaId !== 'tutte' && m.c !== campagnaId) return;
      if (m.p[p] !== undefined) out.push(m.p[p]);
    });
    return out;
  };

  Dashboard.prototype.media = function (valori) {
    if (!valori.length) return null;
    var somma = 0;
    valori.forEach(function (v) { somma += valore(v); });
    return somma / valori.length;
  };

  Dashboard.prototype.estensione = function () {
    var self = this, min = Infinity, max = -Infinity;
    this.stazioniVisibili().forEach(function (s) {
      self.valoriPunto(s.id).forEach(function (v) {
        var n = valore(v);
        if (n === null) return;
        if (n < min) min = n;
        if (n > max) max = n;
      });
    });
    (this.scheda().soglie || []).forEach(function (s) {
      if (s.valore < min) min = s.valore;
      if (s.valore > max) max = s.valore;
    });
    if (min === Infinity) { min = 0; max = 1; }
    if (this.scheda().scala === 'log') return [Math.max(min, 1), max * 1.6];
    var margine = (max - min) * 0.12 || Math.abs(max) * 0.1 || 1;
    return [Math.max(0, min - margine), max + margine];
  };

  // ------------------------------------------------------------- disegno

  Dashboard.prototype.disegna = function () {
    if (this.parametro === this.TUTTI) return this.disegnaTuttiIParametri();
    var vecchiMultipli = this.nodo.querySelector('.piccoli-multipli');
    if (vecchiMultipli) vecchiMultipli.remove();
    this.areaGrafico.hidden = false;
    this.legenda.hidden = false;
    this.spiegaSoglie.hidden = false;
    this.guida.hidden = false;
    var p = this.scheda();
    this.intestazione.textContent = '';
    this.intestazione.appendChild(html('h3', null, p.nome + (p.unita ? ' · ' + p.unita : '')));
    this.intestazione.appendChild(html('p', null, p.cosa_misura || ''));

    this.guida.textContent = '';
    var g = html('p');
    g.appendChild(html('strong', null, 'Come leggerlo. '));
    g.appendChild(document.createTextNode(p.come_leggerlo || ''));
    this.guida.appendChild(g);
    if (p.soglie && p.soglie.length) {
      this.guida.appendChild(html('p', null,
        'Le linee tratteggiate nel grafico sono le soglie di qualità: passaci sopra con il ' +
        'mouse, o toccale, per leggere che cosa significa superarle e quali possono essere le cause.'));
    }

    this.disegnaLegenda();
    this.disegnaSpiegazioneSoglie();

    var vecchio = this.areaGrafico.querySelector('svg');
    if (vecchio) vecchio.remove();
    var svg = this.vista === 'andamento' ? this.grafiocoAndamento()
      : this.vista === 'mappa' ? this.graficoMappa()
      : this.graficoProfilo();
    this.areaGrafico.appendChild(svg);
    if (this.dettagli.open) this.disegnaTabella();
  };

  /* Tutti i parametri insieme: un grafico piccolo per ciascuno, da cliccare
     per aprirlo a tutta larghezza. */
  Dashboard.prototype.disegnaTuttiIParametri = function () {
    var self = this;
    this.areaGrafico.hidden = true;
    this.legenda.hidden = true;
    this.spiegaSoglie.hidden = true;
    this.guida.hidden = true;

    this.intestazione.textContent = '';
    this.intestazione.appendChild(html('h3', null, 'Tutti i parametri insieme'));
    this.intestazione.appendChild(html('p', null,
      'Il profilo del fiume da valle a monte per ogni parametro misurato. ' +
      'Il colore di ogni barra dice se quel valore supera una soglia. ' +
      'Tocca un grafico per aprirlo e leggerne la scheda.'));

    var vecchio = this.nodo.querySelector('.piccoli-multipli');
    if (vecchio) vecchio.remove();
    var griglia = html('div', 'piccoli-multipli');

    var parametroCorrente = this.parametro;
    this.parametriDisponibili.forEach(function (nome) {
      self.parametro = nome;
      var p = self.schede.parametri[nome];
      var riquadro = html('div', 'mini-grafico');
      var bottone = html('button');
      bottone.type = 'button';
      bottone.appendChild(html('h4', null, p.nome));
      bottone.appendChild(html('p', 'mini-unita', p.unita || ''));
      bottone.appendChild(self.graficoProfilo({ mini: true }));
      bottone.addEventListener('click', function () { self.scegliParametro(nome); });
      riquadro.appendChild(bottone);
      griglia.appendChild(riquadro);
    });
    this.parametro = parametroCorrente;

    this.areaGrafico.insertAdjacentElement('afterend', griglia);
  };

  Dashboard.prototype.disegnaLegenda = function () {
    var p = this.scheda();
    this.legenda.textContent = '';
    if (!p.soglie || !p.soglie.length) {
      this.legenda.appendChild(html('span', null,
        'Questo parametro non ha soglie di qualità: si legge confrontando stazioni e stagioni.'));
      return;
    }
    var self = this;
    this.legenda.appendChild(html('span', null, 'Soglie di questo parametro:'));
    var verso = p.verso === 'basso_critico' ? 'sotto ' : 'oltre ';
    p.soglie.slice().sort(function (a, b) { return a.livello - b.livello; }).forEach(function (s) {
      var pastiglia = html('span', 'pastiglia lvl-' + s.livello,
        verso + formatta(s.valore) + ' ' + (p.unita || ''));
      self.legenda.appendChild(pastiglia);
    });
    var entro = html('span', 'pastiglia', 'entro le soglie');
    entro.style.background = '#4E7A8C';
    entro.style.color = '#fff';
    this.legenda.appendChild(entro);
  };

  /* Dice a parole che cosa distingue una soglia dall'altra: il colore da solo
     non basta a capire quale delle due è quella grave. */
  Dashboard.prototype.disegnaSpiegazioneSoglie = function () {
    var p = this.scheda(), self = this;
    this.spiegaSoglie.textContent = '';
    if (!p.soglie || !p.soglie.length) return;

    var ordinate = p.soglie.slice().sort(function (a, b) { return a.livello - b.livello; });
    var quante = ordinate.length;
    ordinate.forEach(function (s, i) {
      var riga = html('div', 'soglia-riga');
      var tacca = html('span', 'soglia-tacca');
      tacca.style.background = COLORI_LIVELLO[s.livello] || '#B03A2E';
      riga.appendChild(tacca);
      var testo = html('div');
      var ruolo = quante === 1 ? 'Soglia di riferimento'
        : i === 0 ? 'Prima soglia, di attenzione'
        : i === quante - 1 ? 'Soglia più grave' : 'Soglia intermedia';
      testo.appendChild(html('b', null, ruolo + ': ' + s.etichetta + '. '));
      testo.appendChild(document.createTextNode(s.spiegazione || ''));
      riga.appendChild(testo);
      self.spiegaSoglie.appendChild(riga);
    });

    if (quante > 1) {
      var nota = html('div', 'soglia-riga');
      nota.appendChild(html('span', null, ''));
      var verso = p.verso === 'basso_critico' ? 'più si scende' : 'più si sale';
      nota.appendChild(html('div', null,
        'Le linee vanno lette in ordine: ' + verso + ' oltre le linee, peggiore è la ' +
        'condizione del fiume. La prima segnala che qualcosa non va, l\'ultima che la ' +
        'situazione è grave. Passando sopra una linea nel grafico compaiono anche le possibili cause.'));
      self.spiegaSoglie.appendChild(nota);
    }
  };

  /* Disegna le linee di soglia con l'etichetta sempre visibile e il riquadro
     di spiegazione al passaggio del mouse. */
  Dashboard.prototype.disegnaSoglie = function (svg, y, x0, x1, altezza, opzioni) {
    opzioni = opzioni || {};
    var self = this, p = this.scheda(), disegnate = 0;
    (p.soglie || []).forEach(function (s) {
      var py = y(s.valore);
      if (py < 6 || py > altezza - 6) return;
      var col = COLORI_LIVELLO[s.livello] || '#B03A2E';
      var gruppo = el('g', { class: 'soglia-gruppo', tabindex: '0', role: 'button',
        'aria-label': 'Soglia ' + s.etichetta + '. ' + s.spiegazione });

      gruppo.appendChild(el('line', {
        class: 'soglia-linea', x1: x0, x2: x1, y1: py, y2: py, stroke: col
      }));

      if (opzioni.mini) { svg.appendChild(gruppo); return; }

      var testo = s.etichetta;
      var larghezza = Math.min(testo.length * 5.6 + 14, Math.max(x1 - x0 - 4, 80));
      // alterna destra e sinistra: due soglie vicine non si coprono a vicenda
      var tx = (disegnate % 2 === 0)
        ? Math.max(x0 + 2, x1 - larghezza - 2)
        : x0 + 2;
      disegnate++;
      gruppo.appendChild(el('rect', {
        class: 'soglia-sfondo', x: tx, y: py - 16, width: larghezza, height: 15,
        rx: 2, fill: col
      }));
      gruppo.appendChild(el('text', {
        class: 'soglia-etichetta', x: tx + 7, y: py - 5, fill: s.livello === 3 ? '#14262F' : '#fff'
      }, testo));

      // area invisibile più alta della linea, per prenderla facilmente col mouse
      var presa = el('rect', {
        class: 'soglia-area', x: x0, y: py - 18, width: x1 - x0, height: 26
      });
      gruppo.appendChild(presa);

      function mostra(ev) {
        self.mostraSuggerimento(ev, {
          titolo: s.etichetta,
          righe: [s.spiegazione],
          cause: s.cause
        });
      }
      gruppo.addEventListener('mouseenter', mostra);
      gruppo.addEventListener('mousemove', mostra);
      gruppo.addEventListener('focus', mostra);
      gruppo.addEventListener('mouseleave', function () { self.nascondiSuggerimento(); });
      gruppo.addEventListener('blur', function () { self.nascondiSuggerimento(); });
      svg.appendChild(gruppo);
    });
  };

  Dashboard.prototype.mostraSuggerimento = function (ev, contenuto) {
    var s = this.suggerimento;
    s.textContent = '';
    s.appendChild(html('h4', null, contenuto.titolo));
    (contenuto.righe || []).forEach(function (r) {
      if (r) s.appendChild(html('p', null, r));
    });
    if (contenuto.cause) {
      s.appendChild(html('span', 'cause-titolo', 'Possibili cause'));
      s.appendChild(html('p', null, contenuto.cause));
    }
    s.setAttribute('data-visibile', 'si');

    var area = this.areaGrafico.getBoundingClientRect();
    var larghezza = s.offsetWidth || 320;
    var altezza = s.offsetHeight || 120;
    var x = (ev.clientX !== undefined ? ev.clientX - area.left : area.width / 2) + 16;
    var yy = (ev.clientY !== undefined ? ev.clientY - area.top : 20) - altezza - 10;
    if (x + larghezza > area.width) x = Math.max(8, area.width - larghezza - 8);
    if (yy < 4) yy = (ev.clientY !== undefined ? ev.clientY - area.top : 0) + 20;
    s.style.left = x + 'px';
    s.style.top = yy + 'px';
  };

  Dashboard.prototype.nascondiSuggerimento = function () {
    this.suggerimento.setAttribute('data-visibile', 'no');
  };

  Dashboard.prototype.misure = function (opzioni) {
    opzioni = opzioni || {};
    if (opzioni.mini) {
      return { l: 300, h: 160, sinistra: 34, destra: 8, sopra: 10, sotto: 26 };
    }
    var larghezza = Math.max(this.areaGrafico.clientWidth - 24, 320);
    var alta = this.vista === 'profilo' && this.dati.stazioni.length > 12;
    return {
      l: larghezza,
      h: alta ? 460 : 400,
      sinistra: 58,
      destra: 16,
      sopra: 16,
      sotto: alta ? 120 : 64
    };
  };

  Dashboard.prototype.assi = function (svg, m, y, etichetteX, posX, opzioni) {
    opzioni = opzioni || {};
    var p = this.scheda();
    var log = p.scala === 'log';
    var est = this.estensione();
    var valoriY = log ? taccheLog(est[0], est[1]) : tacche(est[0], est[1], 6);
    var griglia = el('g', { class: 'griglia' });
    var asse = el('g', { class: 'asse' });
    valoriY.forEach(function (v) {
      var py = y(v);
      griglia.appendChild(el('line', { x1: m.sinistra, x2: m.l - m.destra, y1: py, y2: py }));
      asse.appendChild(el('text', {
        x: m.sinistra - 8, y: py + 4, 'text-anchor': 'end'
      }, v >= 10000 ? (v / 1000) + 'k' : String(v).replace('.', ',')));
    });
    svg.appendChild(griglia);

    if (opzioni.mini) {
      asse.appendChild(el('line', {
        x1: m.sinistra, x2: m.l - m.destra, y1: m.h - m.sotto, y2: m.h - m.sotto
      }));
      svg.appendChild(asse);
      return;
    }
    var ruota = etichetteX.length > 9;
    etichetteX.forEach(function (t, i) {
      var px = posX(i);
      var nodo = el('text', {
        x: px, y: m.h - m.sotto + (ruota ? 14 : 18),
        'text-anchor': ruota ? 'end' : 'middle',
        transform: ruota ? 'rotate(-45 ' + px + ' ' + (m.h - m.sotto + 14) + ')' : null
      }, t);
      asse.appendChild(nodo);
    });
    asse.appendChild(el('line', {
      x1: m.sinistra, x2: m.l - m.destra, y1: m.h - m.sotto, y2: m.h - m.sotto
    }));
    svg.appendChild(asse);
  };

  Dashboard.prototype.creaSvg = function (m) {
    var svg = el('svg', {
      width: m.l, height: m.h, viewBox: '0 0 ' + m.l + ' ' + m.h,
      role: 'img',
      'aria-label': 'Grafico di ' + this.scheda().nome + ' nelle stazioni di monitoraggio'
    });
    return svg;
  };

  Dashboard.prototype.scalaY = function (m) {
    var est = this.estensione();
    var sotto = m.h - m.sotto, sopra = m.sopra;
    return this.scheda().scala === 'log'
      ? scalaLog(est[0], est[1], sotto, sopra)
      : scalaLineare(est[0], est[1], sotto, sopra);
  };

  /* Vista 1: andamento nel tempo, una linea per stazione. */
  Dashboard.prototype.grafiocoAndamento = function () {
    var self = this, m = this.misure(), svg = this.creaSvg(m);
    var y = this.scalaY(m);
    var campagne = this.dati.campagne;
    var larghezzaUtile = m.l - m.sinistra - m.destra;
    var passo = campagne.length > 1 ? larghezzaUtile / (campagne.length - 1) : 0;
    var posX = function (i) { return m.sinistra + (campagne.length > 1 ? i * passo : larghezzaUtile / 2); };

    this.assi(svg, m, y, campagne.map(function (c) { return c.etichetta; }), posX);

    var p = this.scheda();
    this.dati.stazioni.forEach(function (s, indice) {
      if (self.spente[s.id]) return;
      var col = COLORI_SERIE[indice % COLORI_SERIE.length];
      var punti = [];
      campagne.forEach(function (c, i) {
        var valori = self.valoriPunto(s.id, c.id);
        if (!valori.length) return;
        punti.push({ x: posX(i), y: y(self.media(valori)), v: valori[0], c: c });
      });
      if (!punti.length) return;
      var d = punti.map(function (pt, i) {
        return (i ? 'L' : 'M') + pt.x.toFixed(1) + ' ' + pt.y.toFixed(1);
      }).join(' ');
      svg.appendChild(el('path', { class: 'serie-linea', d: d, stroke: col }));
      punti.forEach(function (pt) {
        var cerchio = el('circle', {
          class: 'serie-punto', cx: pt.x, cy: pt.y, r: 4.2, fill: col, tabindex: '0',
          'aria-label': s.nome + ', ' + pt.c.etichetta + ': ' + formatta(pt.v) + ' ' + (p.unita || '')
        });
        function mostra(ev) {
          self.mostraSuggerimento(ev, {
            titolo: self.etichettaStazione(s),
            righe: [
              pt.c.etichetta + ' · ' + formatta(pt.v) + ' ' + (p.unita || ''),
              self.testoClasse(pt.v)
            ]
          });
        }
        cerchio.addEventListener('mouseenter', mostra);
        cerchio.addEventListener('mousemove', mostra);
        cerchio.addEventListener('focus', mostra);
        cerchio.addEventListener('mouseleave', function () { self.nascondiSuggerimento(); });
        cerchio.addEventListener('blur', function () { self.nascondiSuggerimento(); });
        svg.appendChild(cerchio);
      });
    });
    this.disegnaSoglie(svg, y, m.sinistra, m.l - m.destra, m.h - m.sotto);
    return svg;
  };

  /* Descrive il valore rispetto alle soglie, senza inventare una classe di
     qualità che le soglie elencate non permettono di stabilire. */
  Dashboard.prototype.testoClasse = function (v) {
    var p = this.scheda();
    if (!p.soglie || !p.soglie.length) return '';
    var l = livello(p, v);
    if (!l) return 'Entro tutte le soglie di questo parametro.';
    var peggiore = null;
    p.soglie.forEach(function (s) { if (s.livello === l) peggiore = s; });
    var verso = p.verso === 'basso_critico' ? 'Sotto' : 'Oltre';
    return verso + ' la soglia: ' + (peggiore ? peggiore.etichetta : '') + '.';
  };

  /* Vista 2: il profilo del fiume. Monte a destra e valle a sinistra, come
     si vede Roma guardandola dall'alto: l'Aniene arriva da est. */
  Dashboard.prototype.graficoProfilo = function (opzioni) {
    opzioni = opzioni || {};
    var self = this, m = this.misure(opzioni), svg = this.creaSvg(m);
    var y = this.scalaY(m);
    // da valle (sinistra) a monte (destra)
    var stazioni = this.stazioniVisibili().slice().reverse();
    var larghezzaUtile = m.l - m.sinistra - m.destra;
    var passo = larghezzaUtile / Math.max(stazioni.length, 1);
    var larghezzaBarra = Math.min(passo * 0.62, 46);
    var posX = function (i) { return m.sinistra + passo * (i + 0.5); };

    this.assi(svg, m, y, stazioni.map(function (s) {
      return stazioni.length > 12 || opzioni.mini ? s.id : s.nome;
    }), posX, opzioni);

    var p = this.scheda();
    var base = m.h - m.sotto;
    stazioni.forEach(function (s, i) {
      var valori = self.valoriPunto(s.id, self.campagna);
      if (!valori.length) return;
      var media = self.media(valori);
      var py = y(media);
      var col = colore(p, media);
      var barra = el('rect', {
        class: 'barra', x: posX(i) - larghezzaBarra / 2, y: Math.min(py, base),
        width: larghezzaBarra, height: Math.max(Math.abs(base - py), 1),
        fill: col, rx: 2, tabindex: opzioni.mini ? null : '0',
        'aria-label': s.nome + ': ' + formatta(media) + ' ' + (p.unita || '')
      });
      if (!opzioni.mini) {
        function mostra(ev) {
          var righe = [formatta(media) + ' ' + (p.unita || ''), self.testoClasse(media)];
          if (self.campagna === 'tutte' && valori.length > 1) {
            righe.unshift('Media di ' + valori.length + ' campagne');
          }
          if (s.tratto) righe.push('Tratto: ' + s.tratto + (s.bis ? ' · punto BIS, 500 m a valle' : ''));
          self.mostraSuggerimento(ev, { titolo: self.etichettaStazione(s), righe: righe });
        }
        barra.addEventListener('mouseenter', mostra);
        barra.addEventListener('mousemove', mostra);
        barra.addEventListener('focus', mostra);
        barra.addEventListener('mouseleave', function () { self.nascondiSuggerimento(); });
        barra.addEventListener('blur', function () { self.nascondiSuggerimento(); });
      }
      svg.appendChild(barra);
    });
    this.disegnaSoglie(svg, y, m.sinistra, m.l - m.destra, m.h - m.sotto, opzioni);

    svg.appendChild(el('text', { class: 'asse-titolo', x: m.sinistra, y: m.h - 6 }, '← valle'));
    svg.appendChild(el('text', {
      class: 'asse-titolo', x: m.l - m.destra, y: m.h - 6, 'text-anchor': 'end'
    }, 'monte →'));
    return svg;
  };

  /* Vista 3: mappa schematica dei punti di campionamento.
     Non usa mappe di sfondo né servizi esterni: posiziona i punti sulle loro
     coordinate reali e li unisce nell'ordine da monte a valle, così si legge
     il percorso del fiume senza dipendere da nessuno. */
  Dashboard.prototype.graficoMappa = function () {
    var self = this, p = this.scheda();
    var stazioni = this.stazioniVisibili().filter(function (s) {
      return typeof s.lat === 'number' && typeof s.lon === 'number';
    });
    var m = this.misure();
    m.h = 440;
    var svg = this.creaSvg(m);

    if (!stazioni.length) {
      svg.appendChild(el('text', { x: m.l / 2, y: m.h / 2, 'text-anchor': 'middle',
        class: 'asse-titolo' }, 'Per questi punti non abbiamo le coordinate.'));
      return svg;
    }

    var lat = stazioni.map(function (s) { return s.lat; });
    var lon = stazioni.map(function (s) { return s.lon; });
    var latMedia = (Math.min.apply(null, lat) + Math.max.apply(null, lat)) / 2;
    var k = Math.cos(latMedia * Math.PI / 180);
    var xs = lon.map(function (v) { return v * k; });
    var minX = Math.min.apply(null, xs), maxX = Math.max.apply(null, xs);
    var minY = Math.min.apply(null, lat), maxY = Math.max.apply(null, lat);
    var bordo = 46;
    var larghezza = m.l - bordo * 2, altezza = m.h - bordo * 2;
    var scala = Math.min(
      larghezza / Math.max(maxX - minX, 1e-6),
      altezza / Math.max(maxY - minY, 1e-6)
    );
    var offX = bordo + (larghezza - (maxX - minX) * scala) / 2;
    var offY = bordo + (altezza - (maxY - minY) * scala) / 2;
    var px = function (s) { return offX + (s.lon * k - minX) * scala; };
    var py = function (s) { return offY + (maxY - s.lat) * scala; };

    // il corso del fiume, come spezzata tra i punti in ordine
    var percorso = stazioni.slice().sort(function (a, b) { return a.ordine - b.ordine; });
    svg.appendChild(el('path', {
      d: percorso.map(function (s, i) {
        return (i ? 'L' : 'M') + px(s).toFixed(1) + ' ' + py(s).toFixed(1);
      }).join(' '),
      fill: 'none', stroke: '#9CC4D6', 'stroke-width': 6,
      'stroke-linejoin': 'round', 'stroke-linecap': 'round', opacity: .65
    }));

    stazioni.forEach(function (s) {
      var valori = self.valoriPunto(s.id, self.campagna);
      var media = valori.length ? self.media(valori) : null;
      var gruppo = el('g', { tabindex: '0', role: 'button',
        'aria-label': s.nome + (media === null ? ', nessun dato' : ': ' + formatta(media) + ' ' + (p.unita || '')) });
      gruppo.appendChild(el('circle', {
        cx: px(s), cy: py(s), r: 9,
        fill: media === null ? '#D8D4CB' : colore(p, media),
        stroke: '#fff', 'stroke-width': 2
      }));
      gruppo.appendChild(el('text', {
        x: px(s), y: py(s) - 14, 'text-anchor': 'middle',
        class: 'soglia-etichetta', fill: '#1A3340'
      }, s.id));
      function mostra(ev) {
        self.mostraSuggerimento(ev, {
          titolo: self.etichettaStazione(s),
          righe: media === null
            ? ['Nessun dato per questo parametro in questa campagna.']
            : [formatta(media) + ' ' + (p.unita || ''), self.testoClasse(media)]
        });
      }
      gruppo.addEventListener('mouseenter', mostra);
      gruppo.addEventListener('mousemove', mostra);
      gruppo.addEventListener('focus', mostra);
      gruppo.addEventListener('mouseleave', function () { self.nascondiSuggerimento(); });
      gruppo.addEventListener('blur', function () { self.nascondiSuggerimento(); });
      svg.appendChild(gruppo);
    });

    svg.appendChild(el('text', { class: 'asse-titolo', x: bordo, y: m.h - 8 },
      'Mappa schematica: i punti sono alle loro coordinate reali, uniti da monte a valle.'));
    return svg;
  };

  // ------------------------------------------------------------- tabella

  Dashboard.prototype.disegnaTabella = function () {
    var self = this, p = this.scheda();
    this.tabella.textContent = '';
    var tabella = html('table', 'dati');
    var thead = html('thead'), tr = html('tr');
    tr.appendChild(html('th', null, 'Stazione'));
    this.dati.campagne.forEach(function (c) {
      tr.appendChild(html('th', null, c.etichetta));
    });
    thead.appendChild(tr);
    tabella.appendChild(thead);

    var tbody = html('tbody');
    this.dati.stazioni.forEach(function (s) {
      var riga = html('tr');
      riga.appendChild(html('th', null, self.etichettaStazione(s)));
      self.dati.campagne.forEach(function (c) {
        var valori = self.valoriPunto(s.id, c.id);
        var cella = html('td', null, valori.length ? formatta(valori[0]) : '—');
        if (valori.length && livello(p, valori[0]) >= 4) {
          cella.className = 'oltre';
          cella.style.color = colore(p, valori[0]);
        }
        riga.appendChild(cella);
      });
      tbody.appendChild(riga);
    });
    tabella.appendChild(tbody);
    this.tabella.appendChild(html('p', null,
      'Valori di ' + p.nome.toLowerCase() + (p.unita ? ' in ' + p.unita : '') + '.'));
    this.tabella.appendChild(tabella);
  };

  Dashboard.prototype.scaricaCsv = function () {
    var self = this;
    var parametri = this.parametriDisponibili;
    var nomi = {};
    this.dati.stazioni.forEach(function (s) { nomi[s.id] = s.nome; });
    var righe = [['punto', 'nome', 'data', 'campagna'].concat(parametri).join(';')];
    this.dati.misure.forEach(function (m) {
      var riga = [m.s, '"' + (nomi[m.s] || '').replace(/"/g, '""') + '"', m.d, m.c];
      parametri.forEach(function (p) {
        var v = m.p[p];
        riga.push(v === undefined ? '' : (limite(v) + String(valore(v)).replace('.', ',')));
      });
      righe.push(riga.join(';'));
    });
    var blob = new Blob(['﻿' + righe.join('\n')], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'aniene-' + self.dati.id + '.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  // ------------------------------------------------------------------ avvio

  function avvia() {
    var nodi = document.querySelectorAll('.dashboard[data-dati]');
    if (!nodi.length) return;
    fetch('dati/parametri.json').then(function (r) { return r.json(); }).then(function (schede) {
      Array.prototype.forEach.call(nodi, function (nodo) {
        var nome = nodo.getAttribute('data-dati');
        fetch('dati/' + nome + '.json')
          .then(function (r) {
            if (!r.ok) throw new Error('dati non trovati');
            return r.json();
          })
          .then(function (dati) { new Dashboard(nodo, dati, schede); })
          .catch(function (e) {
            nodo.textContent = '';
            nodo.appendChild(html('div', 'dash-guida',
              'Non è stato possibile caricare i dati di questa campagna (' + e.message + ').'));
          });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', avvia);
  } else {
    avvia();
  }
})();
