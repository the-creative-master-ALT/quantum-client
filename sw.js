/* ==========================================================================
   EaglerVault service worker
   Caches ONLY the launcher shell (HTML/CSS/JS/icons/covers) so the app opens
   instantly and works offline.  The game .html files are deliberately NOT
   cached -- they are 60 KB … 80 MB each and would blow past every quota.
   ========================================================================== */
const VERSION = 'eaglervault-v1';

const SHELL = [
  './',
  './index.html',
  './assets/css/launcher.css',
  './assets/js/app.js',
  './data/versions.json',
  './manifest.webmanifest',
  './assets/img/icon-192.png',
  './assets/img/icon-512.png',
  './assets/img/hero.jpg',
  './assets/img/cat-preclassic.jpg',
  './assets/img/cat-classic.jpg',
  './assets/img/cat-indev.jpg',
  './assets/img/cat-infdev.jpg',
  './assets/img/cat-alpha.jpg',
  './assets/img/cat-beta.jpg',
  './assets/img/cat-release.jpg',
  './assets/img/cat-client.jpg',
  './assets/img/cat-extras.jpg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(VERSION)
      .then((cache) => cache.addAll(SHELL).catch(() => {
        // one missing asset must not break the whole install
        return Promise.all(SHELL.map((u) => cache.add(u).catch(() => null)));
      }))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') self.skipWaiting();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;      // third party: leave alone
  if (url.pathname.endsWith('/sw.js')) return;

  const isCatalogue = url.pathname.endsWith('/data/versions.json');
  const isShell = SHELL.some((u) => {
    const p = new URL(u, self.location.href).pathname;
    return p === url.pathname;
  });
  if (!isCatalogue && !isShell) return;                 // games: normal network fetch

  // the catalogue must stay fresh so newly added builds show up
  if (isCatalogue) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match('./data/versions.json')))
    );
    return;
  }

  // static shell: cache first, quietly refresh in the background
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
