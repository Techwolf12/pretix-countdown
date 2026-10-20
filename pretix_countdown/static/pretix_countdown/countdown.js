/*
 * Turns the opening times rendered by pretix_countdown into live countdowns.
 *
 * Targets have the class "pretix-countdown" plus "pretix-countdown-ts-<unix seconds>".
 * The ones inside the front page banner count down to the start of presale, all others
 * are products. pretix decides on its own server whether something can be bought, so
 * this is only a display: when a countdown reaches zero, the page reloads.
 */
(function () {
    "use strict";

    var TS_PREFIX = "pretix-countdown-ts-";

    function pad(n) {
        return n < 10 ? "0" + n : String(n);
    }

    function formatRemaining(ms, labels) {
        var total = Math.floor(ms / 1000);
        var days = Math.floor(total / 86400);
        var hours = Math.floor(total % 86400 / 3600);
        var minutes = Math.floor(total % 3600 / 60);
        var seconds = total % 60;
        var time = pad(hours) + ":" + pad(minutes) + ":" + pad(seconds);
        if (days > 0) {
            return days + " " + (days === 1 ? labels.day : labels.days) + " " + time;
        }
        return time;
    }

    function targetTime(el) {
        for (var i = 0; i < el.classList.length; i++) {
            var cls = el.classList[i];
            if (cls.indexOf(TS_PREFIX) === 0) {
                var seconds = parseInt(cls.substring(TS_PREFIX.length), 10);
                return isNaN(seconds) ? null : seconds * 1000;
            }
        }
        return null;
    }

    function init() {
        var configEl = document.getElementById("pretix-countdown-config");
        if (!configEl) {
            return;
        }
        var config = JSON.parse(configEl.textContent);
        var labels = config.labels;
        // Server time minus the visitor's clock, so a wrong local clock doesn't matter
        var offset = config.now - Date.now();

        var countdowns = [];
        var elements = document.querySelectorAll(".pretix-countdown");
        for (var i = 0; i < elements.length; i++) {
            var target = targetTime(elements[i]);
            if (target === null) {
                continue;
            }
            countdowns.push({
                el: elements[i],
                target: target,
                isEvent: !!elements[i].closest(".pretix-countdown-banner"),
                // Only reload for countdowns that run out while the page is open. If one
                // has already passed on load, reloading would not change anything.
                running: target > config.now,
            });
        }
        if (!countdowns.length) {
            return;
        }

        var reloading = false;

        function tick() {
            var now = Date.now() + offset;
            for (var i = 0; i < countdowns.length; i++) {
                var c = countdowns[i];
                if (!c.running) {
                    continue;
                }
                var remaining = c.target - now;
                if (remaining > 0) {
                    var text = formatRemaining(remaining, labels);
                    c.el.textContent = c.isEvent ? text : labels.product.replace("{countdown}", text);
                    continue;
                }
                c.running = false;
                c.el.textContent = c.isEvent ? labels.event_open : labels.product_open;
                if (!reloading) {
                    reloading = true;
                    // Spread out reloads a little so not every visitor hits the shop at once
                    window.setTimeout(function () {
                        window.location.reload();
                    }, 1000 + Math.random() * 2000);
                }
            }
        }

        tick();
        window.setInterval(tick, 1000);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
