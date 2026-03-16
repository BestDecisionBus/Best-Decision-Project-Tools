/* BDB Tools Service Worker — Push Notifications */

self.addEventListener('push', function(event) {
    var d = {};
    try { d = event.data ? event.data.json() : {}; } catch(e) {}
    var title = d.title || 'BDB Tools';
    var options = {
        body: d.body || '',
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/icon-192.png',
        data: { url: d.url || '/' },
        tag: d.category || 'general',
        renotify: true
    };
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    var url = (event.notification.data && event.notification.data.url) || '/';
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(list) {
            for (var i = 0; i < list.length; i++) {
                if (list[i].url.indexOf(url) !== -1 && 'focus' in list[i]) {
                    return list[i].focus();
                }
            }
            if (clients.openWindow) return clients.openWindow(url);
        })
    );
});
