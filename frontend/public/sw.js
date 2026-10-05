self.addEventListener("push", (event) => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch { payload = {}; }
  const title = typeof payload.title === "string" ? payload.title.slice(0, 80) : "CLINI-CASE update";
  const body = typeof payload.body === "string" ? payload.body.slice(0, 180) : "Open CLINI-CASE to review your work.";
  event.waitUntil(self.registration.showNotification(title, {
    body,
    icon: "/favicon.ico",
    data: { url: typeof payload.url === "string" && payload.url.startsWith("/") && !payload.url.startsWith("//") ? payload.url : "/follow-up" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/follow-up", self.location.origin).href;
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
    const sameOrigin = clients.find((client) => new URL(client.url).origin === self.location.origin);
    if (sameOrigin) return sameOrigin.navigate(target).then(() => sameOrigin.focus());
    return self.clients.openWindow(target);
  }));
});
