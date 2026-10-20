/*
 * Turns the opening times rendered by pretix_countdown into live countdowns.
 *
 * Targets have the class "pretix-countdown" plus "pretix-countdown-ts-<unix seconds>".
 * The ones inside the front page banner count down to the start of presale, all others
 * are products. pretix decides on its own server whether something can be bought, so
 * this is only a display: when a countdown reaches zero, the page reloads.
 *
 * Countdown templates are rendered like render_countdown() in formats.py. Keep the two
 * in sync.
 */
(function () {
    "use strict";

    var TS_PREFIX = "pretix-countdown-ts-";
    var PLACEHOLDER = /\{(\w+)\}/g;
    var OPTIONAL_PART = /\[([^\[\]]*)\]/g;
    var NUMBERS = ["days", "hours", "minutes", "seconds", "hh", "mm", "ss"];

    function pad(n) {
        return n < 10 ? "0" + n : String(n);
    }

    function uses(template, names) {
        for (var i = 0; i < names.length; i++) {
            if (template.indexOf("{" + names[i] + "}") !== -1) {
                return true;
            }
        }
        return false;
    }

    function countdownParts(template, seconds, labels) {
        var days = Math.floor(seconds / 86400);
        var hours = Math.floor(seconds % 86400 / 3600);
        var minutes = Math.floor(seconds % 3600 / 60);
        var secs = seconds % 60;
        // Units the template doesn't show are carried over into the next smaller one
        if (!uses(template, ["days"])) {
            hours += days * 24;
            days = 0;
        }
        if (!uses(template, ["hours", "hh"])) {
            minutes += hours * 60;
            hours = 0;
        }
        if (!uses(template, ["minutes", "mm"])) {
            secs += minutes * 60;
            minutes = 0;
        }
        var parts = {
            days: days,
            hours: hours,
            minutes: minutes,
            seconds: secs,
            hh: pad(hours),
            mm: pad(minutes),
            ss: pad(secs),
        };
        ["days", "hours", "minutes", "seconds"].forEach(function (unit) {
            var label = labels[unit + "_label"];
            parts[unit + "_label"] = parts[unit] === 1 ? label[0] : label[1];
        });
        return parts;
    }

    function fill(text, values) {
        return text.replace(PLACEHOLDER, function (match, name) {
            return Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match;
        });
    }

    function renderCountdown(template, seconds, labels) {
        var parts = countdownParts(template, seconds, labels);
        var text = template.replace(OPTIONAL_PART, function (match, inner) {
            var names = [];
            inner.replace(PLACEHOLDER, function (m, name) {
                if (NUMBERS.indexOf(name) !== -1) {
                    names.push(name);
                }
            });
            var allZero = names.length > 0 && names.every(function (name) {
                return parseInt(parts[name], 10) === 0;
            });
            return allZero ? "" : inner;
        });
        return fill(text, parts);
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
        // Server time minus the visitor's clock, so a wrong local clock doesn't matter
        var offset = config.now - Date.now();

        var countdowns = [];
        var elements = document.querySelectorAll(".pretix-countdown");
        for (var i = 0; i < elements.length; i++) {
            var el = elements[i];
            var target = targetTime(el);
            if (target === null) {
                continue;
            }
            var dateEl = el.querySelector(".pretix-countdown-date");
            countdowns.push({
                el: el,
                target: target,
                isEvent: !!el.closest(".pretix-countdown-banner"),
                date: dateEl ? dateEl.textContent : "",
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
                var remaining = Math.ceil((c.target - now) / 1000);
                if (remaining > 0) {
                    var text = renderCountdown(config.format, remaining, config.labels);
                    c.el.textContent = c.isEvent ? text : fill(config.product, {countdown: text, date: c.date});
                    continue;
                }
                c.running = false;
                c.el.textContent = c.isEvent ? config.event_open : config.product_open;
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
