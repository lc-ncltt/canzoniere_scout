/* Canzoniere - Vanilla JS, nessuna dipendenza. Il testo viene sempre inserito con
   textContent (mai innerHTML), quindi il contenuto del JSON non può iniettare HTML. */
(function () {
  'use strict';

  var canti = [];
  var perId = {};
  var categoriaAttiva = null;
  var corrente = null;
  var accordiVisibili = true;
  var wakeLock = null;

  function $(id) { return document.getElementById(id); }
  function el(tag, classe, testo) {
    var e = document.createElement(tag);
    if (classe) e.className = classe;
    if (testo !== undefined) e.textContent = testo;
    return e;
  }
  function normalizza(s) {
    return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }
  function salva(chiave, valore) { try { localStorage.setItem(chiave, valore); } catch (e) {} }
  function leggi(chiave) { try { return localStorage.getItem(chiave); } catch (e) { return null; } }

  /* ---------- Tema ---------- */
  function temaAttuale() {
    var t = document.documentElement.getAttribute('data-tema');
    if (t) return t;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'notte' : 'giorno';
  }
  function applicaTema(t) {
    document.documentElement.setAttribute('data-tema', t);
    var notte = t === 'notte';
    $('btn-tema').setAttribute('aria-pressed', String(notte));
    $('ico-tema').textContent = notte ? '☀' : '☾';
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', notte ? '#0e0b08' : '#f6f1e7');
  }

  /* ---------- Elenco e ricerca ---------- */
  function categorie() {
    var viste = [];
    canti.forEach(function (c) { if (viste.indexOf(c.categoria) < 0) viste.push(c.categoria); });
    return viste;
  }

  function disegnaFiltri() {
    var box = $('filtri');
    box.textContent = '';
    categorie().forEach(function (cat) {
      var b = el('button', 'chip', cat);
      b.type = 'button';
      b.setAttribute('aria-pressed', String(cat === categoriaAttiva));
      b.addEventListener('click', function () {
        categoriaAttiva = categoriaAttiva === cat ? null : cat;
        disegnaFiltri();
        disegnaElenco();
      });
      box.appendChild(b);
    });
  }

  function risultati() {
    var q = normalizza($('cerca').value.trim());
    return canti.filter(function (c) {
      if (categoriaAttiva && c.categoria !== categoriaAttiva) return false;
      if (!q) return true;
      if (/^\d+$/.test(q)) return String(c.id).indexOf(q) === 0;
      return normalizza(c.titolo).indexOf(q) >= 0;
    });
  }

  function disegnaElenco() {
    var lista = risultati();
    var ul = $('elenco');
    ul.textContent = '';
    lista.forEach(function (c) {
      var li = el('li');
      var a = el('a');
      a.href = '#/' + c.id;
      a.appendChild(el('span', 'num', String(c.id)));
      a.appendChild(el('span', 'tit', c.titolo));
      if (c.pagina) a.appendChild(el('span', 'pag', 'p. ' + c.pagina));
      li.appendChild(a);
      ul.appendChild(li);
    });
    $('stato').textContent = lista.length ? '' : 'Nessun canto trovato.';
  }

  /* ---------- Testo ChordPro ---------- */
  var RE_DIRETTIVA = /^\{\s*([A-Za-z_]+)\s*(?::\s*(.*?))?\s*\}$/;

  /* Una riga diventa una sequenza di "parole"; l'accordo si aggancia alla prima
     parola/sillaba che segue, così può stare sopra metà parola senza spezzarla. */
  function disegnaRiga(riga, conAccordi) {
    var parti = riga.split(/\[([^\]]*)\]/); // testo, accordo, testo, accordo, ...
    var pezzi = []; // {accordo, testo} oppure {spazio:true}
    var i;
    if (parti[0]) pushTesto(null, parti[0]);
    for (i = 1; i < parti.length; i += 2) pushTesto(parti[i].trim(), parti[i + 1]);

    function pushTesto(accordo, testo) {
      var token = testo.split(/(\s+)/);
      var usato = false;
      token.forEach(function (t) {
        if (t === '') return;
        if (/^\s+$/.test(t)) {
          if (accordo && !usato) { pezzi.push({ accordo: accordo, testo: '' }); usato = true; }
          pezzi.push({ spazio: true });
        } else {
          pezzi.push({ accordo: usato ? null : accordo, testo: t });
          usato = true;
        }
      });
      if (accordo && !usato) pezzi.push({ accordo: accordo, testo: '' });
    }

    var haAccordi = conAccordi && pezzi.some(function (p) { return p.accordo; });
    var div = el('div', 'riga' + (haAccordi ? ' con-accordi' : ''));
    var parola = null;
    pezzi.forEach(function (p) {
      if (p.spazio) { div.appendChild(document.createTextNode(' ')); parola = null; return; }
      if (!parola) { parola = el('span', 'parola'); div.appendChild(parola); }
      var seg = el('span', 'seg');
      if (haAccordi) seg.appendChild(el('span', 'ch', p.accordo || ''));
      seg.appendChild(el('span', 'tx', p.testo));
      parola.appendChild(seg);
    });
    return div;
  }

  function disegnaTesto(testo) {
    var box = $('c-testo');
    box.textContent = '';
    var strofa = null;
    var ritornello = false;
    testo.split(/\r?\n/).forEach(function (grezza) {
      var riga = grezza.trim();
      if (riga.charAt(0) === '#') return;
      if (!riga) { strofa = null; return; }
      var m = RE_DIRETTIVA.exec(riga);
      if (m) {
        var nome = m[1].toLowerCase();
        if (nome === 'soc' || nome === 'start_of_chorus') { ritornello = true; strofa = null; }
        else if (nome === 'eoc' || nome === 'end_of_chorus') { ritornello = false; strofa = null; }
        else if (nome === 'c' || nome === 'comment' || nome === 'ci' || nome === 'comment_italic') {
          box.appendChild(el('p', 'commento', m[2] || ''));
        }
        return;
      }
      if (!strofa) {
        strofa = el('div', 'strofa' + (ritornello ? ' ritornello' : ''));
        box.appendChild(strofa);
      }
      strofa.appendChild(disegnaRiga(riga, accordiVisibili));
    });
  }

  /* ---------- Vista canto ---------- */
  function mostraCanto(c) {
    corrente = c;
    $('vista-elenco').hidden = true;
    $('vista-canto').hidden = false;
    document.title = c.id + '. ' + c.titolo + ' - Canzoniere';
    $('c-titolo').textContent = c.id + '. ' + c.titolo;
    $('c-meta').textContent = [c.categoria, c.autore, c.pagina ? 'pagina ' + c.pagina : null]
      .filter(Boolean).join(' · ');
    $('c-note').textContent = '';

    var audio = $('c-audio');
    audio.pause();
    $('c-audio-err').hidden = true;
    if (c.url_audio) {
      audio.src = c.url_audio;
      $('c-audio-box').hidden = false;
    } else {
      audio.removeAttribute('src');
      $('c-audio-box').hidden = true;
    }

    var sp = $('c-spartito');
    if (c.url_spartito) { sp.href = c.url_spartito; sp.hidden = false; } else { sp.hidden = true; }

    var prec = perId[c.id - 1], succ = perId[c.id + 1];
    vaiA($('prec'), prec);
    vaiA($('succ'), succ);

    disegnaTesto(c.testo_accordi);
    window.scrollTo(0, 0);
  }

  function vaiA(a, canto) {
    a.href = canto ? '#/' + canto.id : '#/';
    a.setAttribute('aria-disabled', String(!canto));
    a.tabIndex = canto ? 0 : -1;
  }

  function mostraElenco() {
    corrente = null;
    $('c-audio').pause();
    $('vista-canto').hidden = true;
    $('vista-elenco').hidden = false;
    document.title = 'Canzoniere';
  }

  function route() {
    var m = /^#\/(\d+)$/.exec(location.hash);
    var c = m && perId[m[1]];
    if (c) mostraCanto(c); else mostraElenco();
  }

  /* ---------- Controlli del canto ---------- */
  function dimensioneTesto(delta) {
    var cur = parseFloat(leggi('fs')) || 1.1;
    var nuova = Math.min(2, Math.max(0.85, cur + delta));
    document.documentElement.style.setProperty('--fs', nuova + 'rem');
    salva('fs', String(nuova));
  }

  function schermoAcceso(attiva) {
    if (!attiva) {
      if (wakeLock) { wakeLock.release(); wakeLock = null; }
      return Promise.resolve();
    }
    return navigator.wakeLock.request('screen').then(function (l) {
      wakeLock = l;
      l.addEventListener('release', function () {
        wakeLock = null;
        $('btn-schermo').setAttribute('aria-pressed', 'false');
      });
    });
  }

  function init() {
    applicaTema(temaAttuale());
    $('btn-tema').addEventListener('click', function () {
      var t = temaAttuale() === 'notte' ? 'giorno' : 'notte';
      applicaTema(t);
      salva('tema', t);
    });

    var fs = parseFloat(leggi('fs'));
    if (fs) document.documentElement.style.setProperty('--fs', fs + 'rem');
    $('btn-meno').addEventListener('click', function () { dimensioneTesto(-0.1); });
    $('btn-piu').addEventListener('click', function () { dimensioneTesto(0.1); });

    accordiVisibili = leggi('accordi') !== '0';
    $('btn-accordi').setAttribute('aria-pressed', String(accordiVisibili));
    $('btn-accordi').addEventListener('click', function () {
      accordiVisibili = !accordiVisibili;
      $('btn-accordi').setAttribute('aria-pressed', String(accordiVisibili));
      salva('accordi', accordiVisibili ? '1' : '0');
      if (corrente) disegnaTesto(corrente.testo_accordi);
    });

    if ('wakeLock' in navigator) {
      var b = $('btn-schermo');
      b.hidden = false;
      b.addEventListener('click', function () {
        var attiva = b.getAttribute('aria-pressed') !== 'true';
        schermoAcceso(attiva).then(function () {
          b.setAttribute('aria-pressed', String(attiva));
        }, function () {});
      });
    }

    $('c-audio').addEventListener('error', function () { $('c-audio-err').hidden = false; });

    $('cerca').addEventListener('input', disegnaElenco);
    $('form-cerca').addEventListener('submit', function (ev) {
      ev.preventDefault();
      var lista = risultati();
      var q = $('cerca').value.trim();
      if (/^\d+$/.test(q) && perId[q]) location.hash = '#/' + q;
      else if (lista.length === 1) location.hash = '#/' + lista[0].id;
      $('cerca').blur();
    });
    window.addEventListener('hashchange', route);
  }

  function avvia() {
    init();
    fetch('canti.json', { cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (dati) {
        canti = dati.slice().sort(function (a, b) { return a.id - b.id; });
        canti.forEach(function (c) { perId[c.id] = c; });
        disegnaFiltri();
        disegnaElenco();
        route();
      })
      .catch(function () {
        $('stato').textContent = 'Impossibile caricare i canti. Controlla la connessione e ricarica la pagina.';
      });

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js').catch(function () {});
    }
  }

  avvia();
})();
