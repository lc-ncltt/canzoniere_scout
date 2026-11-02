/* Canzoniere - Vanilla JS, nessuna dipendenza. Il testo viene sempre inserito con
   textContent (mai innerHTML), quindi il contenuto del JSON non può iniettare HTML. */
(function () {
  'use strict';

  var canti = [];
  var perId = {};
  var corrente = null;
  var accordiVisibili = true;

  function $(id) { return document.getElementById(id); }
  function el(tag, classe, testo) {
    var e = document.createElement(tag);
    if (classe) e.className = classe;
    if (testo !== undefined) e.textContent = testo;
    return e;
  }
  function salva(chiave, valore) { try { localStorage.setItem(chiave, valore); } catch (e) {} }
  function leggi(chiave) { try { return localStorage.getItem(chiave); } catch (e) { return null; } }

  /* ---------- Tema ---------- */
  function temaAttuale() {
    var t = document.documentElement.getAttribute('data-tema');
    if (t) return t;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'scuro' : 'chiaro';
  }
  function applicaTema(t) {
    document.documentElement.setAttribute('data-tema', t);
    $('tema').textContent = t === 'scuro' ? 'Chiaro' : 'Scuro';
    $('tema').setAttribute('aria-pressed', String(t === 'scuro'));
  }

  /* ---------- Home ---------- */
  function disegnaElenco() {
    var ul = $('elenco');
    ul.textContent = '';
    canti.forEach(function (c) {
      var li = el('li');
      var a = el('a');
      a.href = '#/' + c.id;
      a.appendChild(el('span', 'n', String(c.id)));
      a.appendChild(el('span', 'tit', c.titolo));
      if ((c.branche || []).length) a.appendChild(quadratini(c));
      li.appendChild(a);
      ul.appendChild(li);
    });
  }

  function anteprima() {
    var q = $('codice').value.trim();
    var p = $('anteprima');
    p.textContent = '';
    if (!q) return;
    var c = perId[q];
    if (!c) { p.textContent = 'Nessun canto con questo codice.'; return; }
    var a = el('a', '', c.id + ' · ' + c.titolo);
    a.href = '#/' + c.id;
    p.appendChild(a);
  }

  /* ---------- Testo ChordPro ---------- */
  var RE_DIRETTIVA = /^\{\s*([A-Za-z_]+)\s*(?::\s*(.*?))?\s*\}$/;

  /* Una riga diventa una sequenza di "parole"; l'accordo si aggancia alla prima
     parola/sillaba che segue, così può stare sopra metà parola senza spezzarla. */
  function disegnaRiga(riga, conAccordi) {
    var parti = riga.split(/\[([^\]]*)\]/); // testo, accordo, testo, accordo, ...
    var pezzi = []; // {accordo, testo} oppure {spazio:true}
    var i;

    function pushTesto(accordo, testo) {
      var usato = false;
      testo.split(/(\s+)/).forEach(function (t) {
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

    if (parti[0]) pushTesto(null, parti[0]);
    for (i = 1; i < parti.length; i += 2) pushTesto(parti[i].trim(), parti[i + 1]);

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
    var box = $('testo');
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

  /* ---------- Pagina del canto ---------- */
  function quadratini(c) {
    var box = el('span', 'quadratini');
    (c.branche || []).forEach(function (b) { box.appendChild(el('span', 'q ' + b)); });
    return box;
  }

  function disegnaInfo(c) {
    var dl = $('info');
    dl.textContent = '';
    function riga(nome, valore, id) {
      var dt = el('dt', '', nome);
      var dd = el('dd', '', valore);
      if (id) dd.id = id;
      dl.appendChild(dt);
      dl.appendChild(dd);
    }
    if (c.autore) riga('Autore', c.autore);
    if (c.anno) riga('Anno', String(c.anno));
    if (c.url_audio) riga('Durata', c.durata || '—', 'info-durata');
    riga('Sezione', c.categoria);
    if (c.branche && c.branche.length) {
      riga('Branca', '');
      dl.lastChild.appendChild(quadratini(c));
    }
    if (c.intensita) riga('Intensità', c.intensita + ' su 5');
    if (c.pagina) riga('Pagina', String(c.pagina));
    if (c.note) riga('Note', c.note);
  }

  function mostraCanto(c) {
    corrente = c;
    $('home').hidden = true;
    $('canto').hidden = false;
    document.title = c.id + '. ' + c.titolo + ' - Canzoniere';
    $('c-num').textContent = c.id;
    $('c-titolo').textContent = c.titolo;
    disegnaInfo(c);

    var audio = $('audio');
    audio.pause();
    $('audio-err').hidden = true;
    if (c.url_audio) {
      audio.src = c.url_audio;
      $('audio-box').hidden = false;
    } else {
      audio.removeAttribute('src');
      $('audio-box').hidden = true;
    }

    var sp = $('spartito');
    if (c.url_spartito) { sp.href = c.url_spartito; $('spartito-box').hidden = false; }
    else { $('spartito-box').hidden = true; }

    vaiA($('prec'), perId[c.id - 1]);
    vaiA($('succ'), perId[c.id + 1]);
    disegnaTesto(c.testo_accordi);
    window.scrollTo(0, 0);
  }

  function vaiA(a, canto) {
    a.href = canto ? '#/' + canto.id : '#/';
    a.setAttribute('aria-disabled', String(!canto));
    a.tabIndex = canto ? 0 : -1;
  }

  function mostraHome() {
    corrente = null;
    $('audio').pause();
    $('canto').hidden = true;
    $('home').hidden = false;
    document.title = 'Canzoniere';
    $('codice').value = '';
    anteprima();
  }

  function route() {
    var m = /^#\/(\d+)$/.exec(location.hash);
    var c = m && perId[m[1]];
    if (c) mostraCanto(c); else mostraHome();
  }

  /* ---------- Avvio ---------- */
  function dimensioneTesto(delta) {
    var cur = parseFloat(leggi('fs')) || 1.1;
    var nuova = Math.min(2, Math.max(0.85, cur + delta));
    document.documentElement.style.setProperty('--fs', nuova + 'rem');
    salva('fs', String(nuova));
  }

  function init() {
    applicaTema(temaAttuale());
    $('tema').addEventListener('click', function () {
      var t = temaAttuale() === 'scuro' ? 'chiaro' : 'scuro';
      applicaTema(t);
      salva('tema', t);
    });

    var fs = parseFloat(leggi('fs'));
    if (fs) document.documentElement.style.setProperty('--fs', fs + 'rem');
    $('b-meno').addEventListener('click', function () { dimensioneTesto(-0.1); });
    $('b-piu').addEventListener('click', function () { dimensioneTesto(0.1); });

    accordiVisibili = leggi('accordi') !== '0';
    $('b-accordi').setAttribute('aria-pressed', String(accordiVisibili));
    $('b-accordi').addEventListener('click', function () {
      accordiVisibili = !accordiVisibili;
      $('b-accordi').setAttribute('aria-pressed', String(accordiVisibili));
      salva('accordi', accordiVisibili ? '1' : '0');
      if (corrente) disegnaTesto(corrente.testo_accordi);
    });

    $('audio').addEventListener('error', function () { $('audio-err').hidden = false; });
    // Se la durata non è nel JSON, la si legge dal file audio appena ne arrivano i metadati.
    $('audio').addEventListener('loadedmetadata', function () {
      var d = $('info-durata');
      var s = this.duration;
      if (d && corrente && !corrente.durata && isFinite(s)) {
        var sec = Math.round(s);
        d.textContent = Math.floor(sec / 60) + ':' + ('0' + (sec % 60)).slice(-2);
      }
    });

    $('codice').addEventListener('input', function () {
      this.value = this.value.replace(/\D/g, '');
      anteprima();
    });
    $('form').addEventListener('submit', function (ev) {
      ev.preventDefault();
      var q = $('codice').value.trim();
      if (perId[q]) location.hash = '#/' + q; else anteprima();
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
        disegnaElenco();
        route();
      })
      .catch(function () {
        $('anteprima').textContent = 'Impossibile caricare i canti. Controlla la connessione e ricarica.';
      });

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js').catch(function () {});
    }
  }

  avvia();
})();
