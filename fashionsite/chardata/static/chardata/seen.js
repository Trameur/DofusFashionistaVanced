// Tells the server this page reached someone: the tab is visible and was used,
// or stayed on screen a few seconds. Of the referrer it sends only the host.
// Whatever never runs a script is never counted.
(function () {
    'use strict';

    var script = document.currentScript;
    var token = script && script.getAttribute('data-seen');
    if (!token || !navigator.sendBeacon || navigator.webdriver) {
        return;
    }

    var ON_SCREEN_MS = 5000;
    var GESTURES = ['pointerdown', 'pointermove', 'keydown', 'scroll', 'touchstart'];
    var LISTENING = {capture: true, passive: true};
    var CAMPAIGN_FIELDS = {us: 'utm_source', um: 'utm_medium', uc: 'utm_campaign'};
    var timer = null;

    function onScreen() {
        return document.visibilityState === 'visible';
    }

    function referrerHost() {
        try {
            return new URL(document.referrer).hostname;
        } catch (e) {
            return '';
        }
    }

    function report() {
        if (!onScreen()) {
            return;
        }
        clearTimeout(timer);
        document.removeEventListener('visibilitychange', waitWhileOnScreen);
        GESTURES.forEach(function (name) {
            window.removeEventListener(name, report, LISTENING);
        });

        var fields = new URLSearchParams();
        var query = new URLSearchParams(location.search);
        fields.set('t', token);
        fields.set('r', referrerHost());
        Object.keys(CAMPAIGN_FIELDS).forEach(function (field) {
            fields.set(field, query.get(CAMPAIGN_FIELDS[field]) || '');
        });
        navigator.sendBeacon('/seen/', fields);
    }

    function waitWhileOnScreen() {
        clearTimeout(timer);
        if (onScreen()) {
            timer = setTimeout(report, ON_SCREEN_MS);
        }
    }

    document.addEventListener('visibilitychange', waitWhileOnScreen);
    GESTURES.forEach(function (name) {
        window.addEventListener(name, report, LISTENING);
    });
    waitWhileOnScreen();
})();
