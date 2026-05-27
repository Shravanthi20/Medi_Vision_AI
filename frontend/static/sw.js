// MediVision AI — Service Worker v13
const CACHE = 'medivision-v13';
const PRECACHE = [
  '/offline',
  '/voice-billing',
  '/welcome',
];

// ── Install: precache key pages ────────────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: purge old caches ─────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch: network-first for API, cache-first for pages ───────────────────
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // API calls — network first, JSON error fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .catch(() => new Response(
          JSON.stringify({ error: 'offline', message: 'No internet connection' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        ))
    );
    return;
  }

  // Pages — cache first, update cache in background, fallback to offline
  event.respondWith(
    caches.open(CACHE).then(async cache => {
      const cached = await cache.match(event.request);
      const networkFetch = fetch(event.request)
        .then(res => {
          if (res.ok) cache.put(event.request, res.clone());
          return res;
        })
        .catch(() => cached || cache.match('/offline'));

      return cached || networkFetch;
    })
  );
});

// ── Background Sync: flush offline bill drafts ─────────────────────────────
self.addEventListener('sync', event => {
  if (event.tag === 'sync-offline-bills') {
    event.waitUntil(flushOfflineBills());
  }
});

async function flushOfflineBills() {
  try {
    const db = await openOfflineDB();
    const tx = db.transaction('offline_bills', 'readwrite');
    const store = tx.objectStore('offline_bills');
    const bills = await idbAll(store);

    for (const bill of bills) {
      try {
        const res = await fetch('/api/bills', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(bill),
        });
        if (res.ok) {
          const tx2 = db.transaction('offline_bills', 'readwrite');
          tx2.objectStore('offline_bills').delete(bill._id);
        }
      } catch (_) { /* retry next sync */ }
    }
  } catch (_) {}
}

function openOfflineDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('medivision-offline', 1);
    req.onupgradeneeded = e => e.target.result.createObjectStore('offline_bills', { keyPath: '_id', autoIncrement: true });
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = reject;
  });
}

function idbAll(store) {
  return new Promise((resolve, reject) => {
    const req = store.getAll();
    req.onsuccess = e => resolve(e.target.result);
    req.onerror = reject;
  });
}

// ── Push Notifications ─────────────────────────────────────────────────────
self.addEventListener('push', event => {
  if (!event.data) return;
  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || 'MediVision AI', {
      body: data.body || '',
      icon: '/static/images/icon-192.png',
      badge: '/static/images/icon-72.png',
      tag: data.tag || 'medivision',
      data: data.url || '/',
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data));
});
