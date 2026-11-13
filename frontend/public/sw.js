// Service worker: makes the web app installable and lets it open without a network.
// It caches only the app itself (the page and its hashed /assets/). The API is never cached: chats,
// files and accounts always come from the server, and offline the app says so (App.tsx).
const CACHE = "acf-app-v1";
const SHELL = ["/", "/manifest.webmanifest", "/favicon.svg", "/icons/icon-192.png"];

const assetsIn = (html) => [...new Set(html.match(/\/assets\/[^"'\s)]+/g) ?? [])];

async function storeShell(cache, response) {
  const html = await response.clone().text();
  const old = await cache.match("/");
  await cache.put("/", response);
  const now = assetsIn(html);
  await cache.addAll(now.map((u) => new Request(u, { cache: "reload" }))).catch(() => {});
  // Drop the previous build's scripts and styles.
  if (old) for (const u of assetsIn(await old.text())) if (!now.includes(u)) await cache.delete(u);
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(SHELL.slice(1));
    const page = await fetch("/", { cache: "reload" });
    if (page.ok) await storeShell(cache, page);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) if (name !== CACHE) await caches.delete(name);
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  if (req.mode === "navigate") {
    // Every page is the same app: the newest from the network, the cached one when offline.
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      try {
        const res = await fetch(req);
        if (res.ok && (res.headers.get("content-type") ?? "").startsWith("text/html")) {
          event.waitUntil(storeShell(cache, res.clone()));
        }
        return res;
      } catch (err) {
        const cached = await cache.match("/");
        if (cached) return cached;
        throw err;
      }
    })());
    return;
  }

  if (url.pathname.startsWith("/assets/")) {
    // Hashed file names never change content: cache first.
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const hit = await cache.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok) event.waitUntil(cache.put(req, res.clone()));
      return res;
    })());
    return;
  }

  if (SHELL.includes(url.pathname)) {
    event.respondWith(fetch(req).catch(async () => (await caches.match(url.pathname)) ?? Response.error()));
  }
});
