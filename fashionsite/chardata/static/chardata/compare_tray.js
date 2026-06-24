// Comparison cart: collect builds from any page (localStorage) and compare them
// in one click. Shown as a small cart in the header -- hovering previews the
// builds, clicking compares them. Lightweight alternative to the old flow.
(function () {
    'use strict';

    var KEY = 'ffCompareTray';
    var MAX = 4;
    var cfg = window.COMPARE_TRAY_CONFIG || {apiBase: '', i18n: {}};
    var t = cfg.i18n || {};
    var hoverCapable = !(window.matchMedia && window.matchMedia('(hover: none)').matches);

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

    function rowHtml(b) {
        var av = b.avatar
            ? '<img src="' + esc(b.avatar) + '" alt="" class="cc-av">' : '';
        var lvl = b.level
            ? ' <span class="cc-lvl">' + esc(b.level) + '</span>' : '';
        return '<div class="cc-row">' + av +
            '<span class="cc-name">' + esc(b.name || ('#' + b.id)) + lvl + '</span>' +
            '<button type="button" class="cc-x" data-ct-remove="' + esc(b.id) +
            '" aria-label="remove">&times;</button></div>';
    }

    function render() {
        var cart = document.getElementById('compare-cart');
        var panel = document.getElementById('compare-cart-panel');
        if (!cart || !panel) {
            return;
        }
        var arr = load();
        var count = cart.querySelector('.cc-count');
        if (count) {
            count.textContent = arr.length;
        }
        if (!arr.length) {
            cart.hidden = true;
            cart.classList.remove('cc-open');
            panel.innerHTML = '';
            return;
        }
        cart.hidden = false;
        var canGo = arr.length >= 2;
        panel.innerHTML =
            '<div class="cc-title">' + esc(t.label || 'Comparison') + '</div>' +
            '<div class="cc-rows">' + arr.map(rowHtml).join('') + '</div>' +
            '<div class="cc-actions">' +
                '<button type="button" class="cc-go button-generic"' +
                    (canGo ? '' : ' disabled') + '>' +
                    esc(t.compare || 'Compare') + ' (' + arr.length + ')</button>' +
                '<button type="button" class="cc-clear">' +
                    esc(t.clear || 'Clear') + '</button>' +
            '</div>';
    }

    function flash(msg) {
        var f = document.getElementById('cc-toast');
        if (!f) {
            f = document.createElement('div');
            f.id = 'cc-toast';
            f.className = 'cc-toast';
            document.body.appendChild(f);
        }
        f.textContent = msg;
        f.classList.add('cc-toast-show');
        clearTimeout(f._t);
        f._t = setTimeout(function () {
            f.classList.remove('cc-toast-show');
        }, 1600);
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
            e.preventDefault();
            remove(rm.getAttribute('data-ct-remove'));
            return;
        }
        if (e.target.closest('.cc-go')) {
            go();
            return;
        }
        if (e.target.closest('.cc-clear')) {
            clear();
            return;
        }
        if (e.target.closest('.compare-cart-toggle')) {
            var cart = document.getElementById('compare-cart');
            if (hoverCapable) {
                go();
            } else if (cart) {
                cart.classList.toggle('cc-open');
            }
            return;
        }
        var openCart = document.getElementById('compare-cart');
        if (openCart && !e.target.closest('#compare-cart')) {
            openCart.classList.remove('cc-open');
        }
    });

    // Keep the cart in sync when builds are added from another tab.
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
