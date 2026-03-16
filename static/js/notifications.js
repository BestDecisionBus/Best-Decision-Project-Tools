/**
 * BDBNotify — shared notification utilities for admin and employee bells.
 *
 * Usage:
 *   BDBNotify.withinHours(start, end)
 *   BDBNotify.relTime(isoString)
 *   BDBNotify.buildItem(notification, {useClasses: true})
 *   BDBNotify.setupPush(token, recipientType, recipientId)
 */
var BDBNotify = (function() {
    'use strict';

    function timeToMin(t) {
        var p = t.split(':');
        return parseInt(p[0]) * 60 + parseInt(p[1]);
    }

    function withinHours(start, end) {
        var now = new Date(), m = now.getHours() * 60 + now.getMinutes();
        return m >= timeToMin(start) && m <= timeToMin(end);
    }

    function relTime(iso) {
        var diff = Math.floor((new Date() - new Date(iso)) / 1000);
        if (diff < 60) return 'just now';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        return Math.floor(diff / 86400) + 'd ago';
    }

    /**
     * Build a notification dropdown item element.
     * @param {Object} n  — notification object with title, url, body, created_at
     * @param {Object} [opts] — options
     * @param {boolean} [opts.useClasses=false] — true = use CSS class names (admin),
     *                                            false = use inline styles (employee)
     */
    function buildItem(n, opts) {
        var cls = opts && opts.useClasses;
        var item = document.createElement('div');
        if (cls) {
            item.className = 'notif-item';
        } else {
            item.style.cssText = 'padding:10px 12px;border-bottom:1px solid var(--gray-100);';
        }

        var titleEl = n.url ? document.createElement('a') : (cls ? document.createElement('span') : document.createElement('div'));
        if (n.url) {
            titleEl.href = n.url;
            if (cls) {
                titleEl.className = 'notif-item-link';
            } else {
                titleEl.style.cssText = 'color:var(--blue);font-weight:600;font-size:14px;display:block;text-decoration:none;';
            }
        } else if (!cls) {
            titleEl.style.cssText = 'font-weight:600;font-size:14px;';
        }
        titleEl.textContent = n.title;
        item.appendChild(titleEl);

        if (n.body) {
            var b = document.createElement('div');
            if (cls) {
                b.className = 'notif-body';
            } else {
                b.style.cssText = 'font-size:13px;color:var(--gray-600);margin-top:2px;';
            }
            b.textContent = n.body;
            item.appendChild(b);
        }

        var t = document.createElement('div');
        if (cls) {
            t.className = 'notif-time';
        } else {
            t.style.cssText = 'font-size:11px;color:var(--gray-400);margin-top:4px;';
        }
        t.textContent = relTime(n.created_at);
        item.appendChild(t);
        return item;
    }

    function urlB64(b) {
        var p = '='.repeat((4 - b.length % 4) % 4);
        var r = atob((b + p).replace(/-/g, '+').replace(/_/g, '/'));
        var o = new Uint8Array(r.length);
        for (var i = 0; i < r.length; i++) o[i] = r.charCodeAt(i);
        return o;
    }

    /**
     * Register service worker and subscribe for push notifications.
     * @param {string} token — company token string
     * @param {string} recipientType — 'admin' or 'employee'
     * @param {number} recipientId — user/employee id
     */
    function setupPush(token, recipientType, recipientId) {
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
        navigator.serviceWorker.register('/sw.js', {scope: '/'}).then(function(reg) {
            return reg.pushManager.getSubscription().then(function(sub) {
                if (sub) return postSub(sub);
                if (Notification.permission === 'denied') return;
                return Notification.requestPermission().then(function(p) {
                    if (p !== 'granted') return;
                    return fetch('/api/push/vapid-public-key', {credentials: 'same-origin'})
                        .then(function(r) { return r.json(); })
                        .then(function(d) {
                            return reg.pushManager.subscribe({
                                userVisibleOnly: true,
                                applicationServerKey: urlB64(d.publicKey)
                            });
                        }).then(postSub);
                });
            });
        }).catch(function(e) { console.warn('SW setup failed:', e); });

        function postSub(sub) {
            return fetch('/api/push/subscribe', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    subscription: sub.toJSON(),
                    token: token,
                    recipient_type: recipientType,
                    recipient_id: recipientId
                })
            });
        }
    }

    return {
        timeToMin: timeToMin,
        withinHours: withinHours,
        relTime: relTime,
        buildItem: buildItem,
        urlB64: urlB64,
        setupPush: setupPush
    };
})();
