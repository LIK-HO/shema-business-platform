const CACHE_VERSION = "shema-pwa-v1";
const PUBLIC_ASSETS = [
  "/",
  "/request",
  "/max",
  "/web/style.css",
  "/web/app.js",
  "/web/manifest.webmanifest",
  "/web/icon-192.svg",
  "/web/icon-512.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(PUBLIC_ASSETS))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key.startsWith("shema-pwa-") && key !== CACHE_VERSION)
          .map((key) => caches.delete(key))
      )
    )
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

function isForbidden(pathname) {
  return pathname.startsWith("/v1/") ||
    pathname.startsWith("/health/") ||
    pathname === "/docs" ||
    pathname === "/redoc" ||
    pathname === "/openapi.json";
}

function isCacheablePublicAsset(request) {
  const url = new URL(request.url);
  return url.origin === self.location.origin &&
    request.method === "GET" &&
    PUBLIC_ASSETS.includes(url.pathname);
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (url.origin !== self.location.origin) return;
  if (isForbidden(url.pathname)) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/"))
    );
    return;
  }

  if (!isCacheablePublicAsset(request)) return;

  event.respondWith(
    caches.match(request).then((cached) =>
      cached || fetch(request).then((response) => {
        if (response.ok) {
          return caches.open(CACHE_VERSION).then((cache) => {
            cache.put(request, response.clone());
            return response;
          });
        }
        return response;
      })
    )
  );
});
