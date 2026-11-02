/* Service worker: rende testi e accordi disponibili offline (l'audio resta online).
   __BUILD__ viene sostituito da scripts/build_site.py: ogni modifica invalida la cache vecchia. */
var CACHE = 'canzoniere-__BUILD__';
var FILE = ['./', 'index.html', 'style.css', 'app.js', 'manifest.webmanifest', 'canti.json'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(FILE); }).then(function () {
    return self.skipWaiting();
  }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (nomi) {
    return Promise.all(nomi.filter(function (n) { return n !== CACHE; }).map(function (n) { return caches.delete(n); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return; // audio/PDF: rete

  // Rete prima, cache come ripiego: online si vede sempre la versione aggiornata.
  e.respondWith(fetch(req).then(function (r) {
    var copia = r.clone();
    caches.open(CACHE).then(function (c) { c.put(req, copia); });
    return r;
  }).catch(function () {
    return caches.match(req, { ignoreSearch: true }).then(function (r) { return r || caches.match('index.html'); });
  }));
});
