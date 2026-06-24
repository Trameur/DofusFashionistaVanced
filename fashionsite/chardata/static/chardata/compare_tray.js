// Comparison tray: collect builds from any page (localStorage) and compare them
// in one click. Lightweight alternative to the old per-page compare flow.
(function () {
    'use strict';

    var KEY = 'ffCompareTray';
    var MAX = 4;
    var cfg = window.COMPARE_TRAY_CONFIG || {apiBase: '', i18n: {}};
    var t = cfg.i18n || {};

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function load() {
        try {
            var arr = JSON.parse(localStorage.getItem(KEY) || '[]');
            return Array.isArray(arr) ? arr : [];
        } catch (e) {
            return [];
        }
    }

    function save(arr) {
        try {
            localStorage.setItem(KEY, JSON.stringify(arr));
        } catch (e) {}
    }

    function has(arr, id) {
        for (var i = 0; i < arr.length; i++) {
            if (String(arr[i].id) === String(id)) {
                return true;
            }
        }
        return false;
    }

    function add(build) {
        if (!build || !build.id) {
            return;
        }
        var arr = load();
        if (has(arr, build.id)) {
            render();
            flash(t.already || 'Already in comparison');
            return;
        }
        if (arr.length >= MAX) {
            flash(t.full || 'You can compare up to 4 builds');
            return;
        }
        arr.push(build);
        save(arr);
        render();
        flash(t.added || 'Added to comparison');
    }

    function remove(id) {
        save(load().filter(function (b) {
            return String(b.id) !== String(id);
        }));
        render();
    }

    function clear() {
        save([]);
        render();
    }

    function go() {
        var arr = load();
        if (arr.length < 2) {
            flash(t.needTwo || 'Add at least 2 builds to compare');
            return;
        }
        var base = arr[0].base != null ? arr[0].base : (cfg.apiBase || '');
        var ids = arr.map(function (b) { return encodeURIComponent(b.id); });
        window.location.href = base + '/compare_sets/' + ids.join('/');
    }

    function chipHtml(b) {
        var av = b.avatar
            ? '<img src="' + esc(b.avatar) + '" alt="" class="ct-chip-av">' : '';
        var lvl = b.level
            ? ' <span class="ct-chip-lvl">' + esc(b.level) + '</span>' : '';
        return '<span class="ct-chip">' + av +
            '<span class="ct-chip-txt">' + esc(b.name || ('#' + b.id)) + lvl + '</span>' +
            '<button type="button" class="ct-chip-x" data-ct-remove="' + esc(b.id) +
            '" aria-label="remove">×</button></span>';
    }

    function render() {
        var el = document.getElementById('compare-tray');
        if (!el) {
            return;
        }
        var arr = load();
        if (!arr.length) {
            el.hidden = true;
            el.innerHTML = '';
            return;
        }
        var canGo = arr.length >= 2;
        el.hidden = false;
        el.innerHTML =
            '<div class="ct-inner">' +
                '<span class="ct-label">' + esc(t.label || 'Compare') + '</span>' +
                '<div class="ct-chips">' + arr.map(chipHtml).join('') + '</div>' +
                '<div class="ct-actions">' +
                    '<button type="button" class="ct-go button-generic"' +
                        (canGo ? '' : ' disabled') + '>' +
                        esc(t.compare || 'Compare') + ' (' + arr.length + ')</button>' +
                    '<button type="button" class="ct-clear">' +
                        esc(t.clear || 'Clear') + '</button>' +
                '</div>' +
            '</div>';
    }

    function flash(msg) {
        var el = document.getElementById('compare-tray');
        if (!el || el.hidden) {
            return;
        }
        var f = el.querySelector('.ct-flash');
        if (!f) {
            f = document.createElement('div');
            f.className = 'ct-flash';
            el.appendChild(f);
        }
        f.textContent = msg;
        f.classList.add('ct-flash-show');
        clearTimeout(f._timer);
        f._timer = setTimeout(function () {
            f.classList.remove('ct-flash-show');
        }, 1800);
    }

    document.addEventListener('click', function (e) {
        var addBtn = e.target.closest('[data-compare-add]');
        if (addBtn) {
            e.preventDefault();
            add({
                id: addBtn.getAttribute('data-build-id'),
                name: addBtn.getAttribute('data-build-name'),
                cls: addBtn.getAttribute('data-build-cls'),
                level: addBtn.getAttribute('data-build-level'),
                avatar: addBtn.getAttribute('data-build-avatar'),
                base: addBtn.getAttribute('data-build-base')
            });
            return;
        }
        var rm = e.target.closest('[data-ct-remove]');
        if (rm) {
            remove(rm.getAttribute('data-ct-remove'));
            return;
        }
        if (e.target.closest('.ct-go')) {
            go();
        } else if (e.target.closest('.ct-clear')) {
            clear();
        }
    });

    // Keep the tray in sync when builds are added from another tab.
    window.addEventListener('storage', function (e) {
        if (e.key === KEY) {
            render();
        }
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', render);
    } else {
        render();
    }

    window.FashionCompareTray = {add: add, remove: remove, clear: clear};
})();
