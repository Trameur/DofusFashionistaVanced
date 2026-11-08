/* Staff page shell: lazy tabs, filters without a reload, one tooltip, sortable tables. */
(function () {
    'use strict';
    var root = document.getElementById('admin-root');
    if (!root) { return; }

    var csrf = root.dataset.csrf || '';
    var tabsForm = document.getElementById('admin-tabs');
    var filtersBar = document.getElementById('admin-filters');
    var refreshLink = document.getElementById('admin-refresh');
    var generatedEl = document.getElementById('admin-generated');
    var NO_FILTER = {history: true, moderation: true, ads: true};
    var CLIENT_TTL = 10 * 60 * 1000;
    var listeners = [];
    var cache = {};
    var token = 0;
    var refreshes = 0;

    var wholeFormat = new Intl.NumberFormat('en-US', {maximumFractionDigits: 0});
    var compactFormat = new Intl.NumberFormat('en-US', {notation: 'compact', maximumFractionDigits: 1});
    var percentFormat = new Intl.NumberFormat('en-US', {maximumFractionDigits: 1});
    var fmt = {
        whole: function (n) { return wholeFormat.format(Math.round(n)); },
        compact: function (n) { return Math.abs(n) < 1000 ? wholeFormat.format(Math.round(n)) : compactFormat.format(n); },
        percent: function (ratio) { return percentFormat.format(ratio * 100) + '%'; }
    };

    function enc(v) { return encodeURIComponent(v); }

    function query(st) {
        var parts = ['tab=' + enc(st.tab)];
        if (st.from && st.to) {
            parts.push('from=' + enc(st.from), 'to=' + enc(st.to));
        } else if (st.period) {
            parts.push('period=' + enc(st.period));
        }
        if (st.version) { parts.push('version=' + enc(st.version)); }
        return parts.join('&');
    }

    function keyOf(st) { return NO_FILTER[st.tab] ? 'tab=' + enc(st.tab) : query(st); }

    function hiddenValue(name) {
        var el = tabsForm && tabsForm.querySelector('input[name="' + name + '"]');
        return el ? el.value : '';
    }

    function tabNames() {
        return [].map.call(root.querySelectorAll('.admin-panel'), function (p) { return p.dataset.panel; });
    }

    var firstFilters = {period: hiddenValue('period'), from: hiddenValue('from'), to: hiddenValue('to'),
                        version: hiddenValue('version')};
    var state = {tab: root.dataset.tab, period: firstFilters.period, from: firstFilters.from,
                 to: firstFilters.to, version: firstFilters.version};

    function stateFromUrl() {
        var q = new URLSearchParams(location.search);
        var tab = q.get('tab');
        if (!tab && tabNames().indexOf(location.hash.slice(1)) >= 0) { tab = location.hash.slice(1); }
        if (tabNames().indexOf(tab) < 0) { tab = 'history'; }
        var from = q.get('from') || '', to = q.get('to') || '', period = q.get('period') || '';
        if (!from && !to && !period) {
            from = firstFilters.from; to = firstFilters.to; period = firstFilters.period;
        }
        var version = q.has('version') ? q.get('version') : (q.has('tab') || q.has('period') ? '' : firstFilters.version);
        return {tab: tab, period: from && to ? '' : period, from: from, to: to, version: version};
    }

    function panelOf(tab) { return root.querySelector('.admin-panel[data-panel="' + tab + '"]'); }

    function announce(panel, info) {
        listeners.forEach(function (fn) { fn(panel, info || {}); });
    }

    var LABEL_PX = 11;

    function fitLabels(scope) {
        [].forEach.call(scope.querySelectorAll('svg.admin-chart'), function (svg) {
            var box = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
            if (!box.width || !vb || !vb.width) { return; }
            var k = box.width / vb.width, size = LABEL_PX / k, right = -1e9;
            var base = vb.height - 18 + size + 1;
            [].forEach.call(svg.querySelectorAll('.admin-chart-label'), function (label) {
                label.style.fontSize = size + 'px';
                label.style.display = '';
                label.setAttribute('y', base);
                var x = parseFloat(label.getAttribute('x')), w = label.getComputedTextLength();
                if (x - w / 2 < right + 8 / k) { label.style.display = 'none'; return; }
                right = x + w / 2;
            });
        });
    }

    var fitTimer = null;
    window.addEventListener('resize', function () {
        clearTimeout(fitTimer);
        fitTimer = setTimeout(function () { fitLabels(root); }, 120);
    });

    function enhance(panel) {
        fitLabels(panel);
        [].forEach.call(panel.querySelectorAll('.admin-table'), function (table) {
            if (table.dataset.enhanced) { return; }
            table.dataset.enhanced = '1';
            var keep = parseInt(table.dataset.more, 10);
            var more = null;
            if (keep) {
                var rows = dataRows(table);
                if (rows.length > keep) {
                    var button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'admin-more';
                    more = {keep: keep, open: false, button: button, table: table};
                    button.addEventListener('click', function () { more.open = !more.open; redrawMore(more); });
                    table.parentNode.insertBefore(button, table.nextSibling);
                    redrawMore(more);
                }
            }
            table._more = more;
            makeSortable(table);
        });
    }

    function dataRows(table) {
        return [].filter.call(table.rows, function (r) { return !r.querySelector('th'); });
    }

    function redrawMore(more) {
        var rows = dataRows(more.table);
        var hidden = Math.max(0, rows.length - more.keep);
        rows.forEach(function (r, i) { r.hidden = !more.open && i >= more.keep; });
        more.button.textContent = more.open ? 'show less' : 'show ' + hidden + ' more';
    }

    function cellValue(row, idx) {
        var cell = row.cells[idx];
        if (!cell) { return ''; }
        return cell.dataset.sort !== undefined ? cell.dataset.sort : cell.textContent.trim();
    }

    function makeSortable(table) {
        var head = table.rows[0];
        if (!head || !head.querySelector('th') || dataRows(table).length < 2) { return; }
        [].forEach.call(head.cells, function (th, idx) {
            th.setAttribute('aria-sort', 'none');
            th.tabIndex = 0;
            function go() {
                var dir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
                [].forEach.call(head.cells, function (other) { other.setAttribute('aria-sort', 'none'); });
                th.setAttribute('aria-sort', dir);
                sortRows(table, idx, dir === 'ascending' ? 1 : -1);
            }
            th.addEventListener('click', go);
            th.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); }
            });
        });
    }

    function numberOf(text) {
        var n = parseFloat(String(text).replace(/[,%\s]/g, ''));
        return isFinite(n) ? n : null;
    }

    function sortRows(table, idx, sign) {
        var rows = dataRows(table);
        var parent = rows[0].parentNode;
        rows.sort(function (a, b) {
            var x = cellValue(a, idx), y = cellValue(b, idx);
            var nx = numberOf(x), ny = numberOf(y);
            if (nx !== null && ny !== null) { return (nx - ny) * sign; }
            if (nx !== null) { return -1; }
            if (ny !== null) { return 1; }
            return x.localeCompare(y) * sign;
        });
        rows.forEach(function (r) { parent.appendChild(r); });
        if (table._more) { redrawMore(table._more); }
    }

    function drawTabs() {
        if (!tabsForm) { return; }
        [].forEach.call(tabsForm.querySelectorAll('.admin-tab'), function (b) {
            var on = b.dataset.tab === state.tab;
            b.classList.toggle('admin-tab-on', on);
            if (on) { b.setAttribute('aria-current', 'page'); } else { b.removeAttribute('aria-current'); }
        });
        [].forEach.call(tabsForm.querySelectorAll('input[type="hidden"]'), function (i) { i.remove(); });
        [['period', state.period], ['from', state.from], ['to', state.to], ['version', state.version]]
            .forEach(function (pair) {
                if (!pair[1] || (pair[0] === 'period' && state.from && state.to)) { return; }
                if ((pair[0] === 'from' || pair[0] === 'to') && !(state.from && state.to)) { return; }
                var input = document.createElement('input');
                input.type = 'hidden'; input.name = pair[0]; input.value = pair[1];
                tabsForm.insertBefore(input, tabsForm.firstChild);
            });
    }

    function paramsOf(a) {
        var q = new URL(a.getAttribute('href'), location.href).searchParams;
        return {period: q.get('period') || '', version: q.get('version') || ''};
    }

    var chips = [];
    if (filtersBar) {
        [].forEach.call(filtersBar.querySelectorAll('a.admin-chip'), function (a, i) {
            var rows = [].indexOf.call(filtersBar.querySelectorAll('.admin-filter-row'), a.closest('.admin-filter-row'));
            var p = paramsOf(a);
            chips.push({el: a, kind: rows === 0 ? 'period' : 'version', period: p.period, version: p.version});
        });
    }

    function drawFilters(note) {
        if (!filtersBar) { return; }
        filtersBar.hidden = !!NO_FILTER[state.tab];
        var custom = !!(state.from && state.to);
        chips.forEach(function (c) {
            var on, next;
            if (c.kind === 'period') {
                on = !custom && c.period === state.period;
                next = {tab: state.tab, period: c.period, from: '', to: '', version: state.version};
            } else {
                on = c.version === state.version;
                next = {tab: state.tab, period: state.period, from: state.from, to: state.to, version: c.version};
            }
            c.el.classList.toggle('admin-chip-on', on);
            c.el.setAttribute('href', '?' + query(next));
        });
        var form = filtersBar.querySelector('.admin-range');
        if (form) {
            var start = note ? note.dataset.start : null, end = note ? note.dataset.end : null;
            if (start !== null) { form.elements.from.value = start; }
            if (end !== null) { form.elements.to.value = end; }
            form.querySelector('button').classList.toggle('admin-chip-on', custom);
        }
    }

    function drawBadge(count) {
        var tab = tabsForm && tabsForm.querySelector('.admin-tab[data-tab="moderation"]');
        if (!tab) { return; }
        var badge = tab.querySelector('.admin-badge');
        if (!count) { if (badge) { badge.remove(); } return; }
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'admin-badge';
            tab.appendChild(document.createTextNode(' '));
            tab.appendChild(badge);
        }
        badge.textContent = count;
    }

    function fetchUrl(st, refresh) {
        return location.pathname + '?' + query(st) + '&fragment=1' + (refresh ? '&refresh=1' : '');
    }

    function parsePanel(html) {
        var t = document.createElement('template');
        t.innerHTML = html.trim();
        var node = t.content.firstElementChild;
        return node && node.classList.contains('admin-panel') ? node : null;
    }

    function failed(panel, st) {
        panel.classList.remove('admin-panel-busy');
        var kept = panel.dataset.loaded === '1';
        var old = panel.querySelector('.admin-failed');
        if (old) { old.remove(); }
        if (!kept) { panel.textContent = ''; }
        var p = document.createElement('p');
        p.className = 'admin-note admin-failed';
        p.setAttribute('role', 'alert');
        p.appendChild(document.createTextNode(kept ? 'The update failed, so what is shown may not match the filters. ' : 'This tab could not be loaded. '));
        var a = document.createElement('a');
        a.href = '?' + query(st);
        a.textContent = 'Retry';
        a.dataset.retry = '1';
        p.appendChild(a);
        panel.insertBefore(p, panel.firstChild);
        var note = kept ? panel.querySelector('.admin-filters-note') : null;
        if (note && state.tab === panel.dataset.panel) {
            state.period = note.dataset.custom ? '' : note.dataset.period;
            state.from = note.dataset.custom ? note.dataset.start : '';
            state.to = note.dataset.custom ? note.dataset.end : '';
            state.version = note.dataset.version || '';
            history.replaceState({}, '', location.pathname + '?' + query(state));
            drawTabs();
            drawFilters(note);
        }
    }

    function swapIn(st, key, html, refresh) {
        var old = panelOf(st.tab);
        var node = parsePanel(html);
        if (!node) { failed(old, st); return; }
        cache[key] = {html: html, at: Date.now()};
        place(old, node, st, key, refresh);
    }

    function place(old, node, st, key, refresh) {
        node.dataset.key = key;
        node.classList.toggle('admin-panel-off', state.tab !== st.tab);
        old.replaceWith(node);
        enhance(node);
        afterShow(node, refresh);
    }

    function afterShow(panel, refresh) {
        if (panel.dataset.generated && generatedEl) { generatedEl.textContent = panel.dataset.generated; }
        if (panel.dataset.pending !== undefined) { drawBadge(parseInt(panel.dataset.pending, 10) || 0); }
        var note = panel.querySelector('.admin-filters-note');
        if (note && state.tab === panel.dataset.panel) {
            state.period = note.dataset.custom ? '' : note.dataset.period;
            state.from = note.dataset.custom ? note.dataset.start : '';
            state.to = note.dataset.custom ? note.dataset.end : '';
            state.version = note.dataset.version || '';
            drawTabs();
        }
        drawFilters(note);
        fitLabels(panel);
        if (state.tab === panel.dataset.panel) { announce(panel, {refresh: !!refresh, refreshes: refreshes}); }
    }

    function load(st, force) {
        var key = keyOf(st);
        var panel = panelOf(st.tab);
        var mine = ++token;
        if (panel.dataset.loaded === '1') {
            panel.classList.add('admin-panel-busy');
        } else if (!panel.firstChild) {
            var wait = document.createElement('p');
            wait.className = 'admin-loading';
            wait.textContent = 'Loading';
            panel.appendChild(wait);
        }
        fetch(fetchUrl(st, force), {credentials: 'same-origin', headers: {'X-Requested-With': 'fetch'}})
            .then(function (r) {
                if (!r.ok) { throw new Error('status ' + r.status); }
                return r.text();
            })
            .then(function (html) {
                if (mine !== token) { return; }
                swapIn(st, key, html, force);
            })
            .catch(function () {
                if (mine === token) { failed(panelOf(st.tab), st); }
            });
    }

    function show(st, mode, force) {
        token++;
        state = {tab: st.tab, period: st.period, from: st.from, to: st.to, version: st.version};
        var panels = root.querySelectorAll('.admin-panel');
        var key = keyOf(state);
        [].forEach.call(panels, function (p) {
            p.classList.remove('admin-panel-busy');
            p.classList.toggle('admin-panel-off', p.dataset.panel !== state.tab);
        });
        drawTabs();
        drawFilters(null);
        if (mode) {
            var url = location.pathname + '?' + query(state);
            history[mode === 'push' ? 'pushState' : 'replaceState']({}, '', url);
        }
        var panel = panelOf(state.tab);
        if (force) {
            refreshes++;
            Object.keys(cache).forEach(function (k) { delete cache[k]; });
            [].forEach.call(panels, function (p) { if (p !== panel) { delete p.dataset.key; } });
            load(state, true);
            return;
        }
        if (panel.dataset.loaded === '1' && panel.dataset.key === key) {
            afterShow(panel, false);
            return;
        }
        var entry = cache[key];
        if (entry && Date.now() - entry.at < CLIENT_TTL) {
            var node = parsePanel(entry.html);
            if (node) { place(panel, node, state, key, false); return; }
        }
        load(state, false);
    }

    if (tabsForm) {
        tabsForm.addEventListener('submit', function (e) {
            var tab = e.submitter && e.submitter.dataset.tab;
            if (!tab) { return; }
            e.preventDefault();
            show({tab: tab, period: state.period, from: state.from, to: state.to, version: state.version}, 'push');
        });
    }

    if (filtersBar) {
        filtersBar.addEventListener('click', function (e) {
            var a = e.target.closest('a.admin-chip');
            if (!a || e.ctrlKey || e.metaKey || e.shiftKey) { return; }
            e.preventDefault();
            var chip = chips.filter(function (c) { return c.el === a; })[0];
            if (!chip) { return; }
            var next = {tab: state.tab, period: state.period, from: state.from, to: state.to, version: state.version};
            if (chip.kind === 'period') { next.period = chip.period; next.from = ''; next.to = ''; }
            else { next.version = chip.version; }
            show(next, 'replace');
        });
        var rangeForm = filtersBar.querySelector('.admin-range');
        if (rangeForm) {
            rangeForm.addEventListener('submit', function (e) {
                e.preventDefault();
                var from = rangeForm.elements.from.value, to = rangeForm.elements.to.value;
                if (!from && !to) { return; }
                show({tab: state.tab, period: '', from: from || '2000-01-01', to: to || rangeForm.elements.to.max,
                      version: state.version}, 'replace');
            });
        }
    }

    if (refreshLink) {
        refreshLink.addEventListener('click', function (e) {
            e.preventDefault();
            show(state, null, true);
        });
    }

    window.addEventListener('popstate', function () { show(stateFromUrl(), null); });

    root.addEventListener('click', function (e) {
        var retry = e.target.closest('a[data-retry]');
        if (retry) { e.preventDefault(); load(state, false); return; }
        var btn = e.target.closest('.admin-card-actions .admin-btn');
        if (btn) { moderate(btn); }
    });

    root.addEventListener('submit', function (e) {
        if (e.target.id === 'admin-ads-form') { e.preventDefault(); saveAds(e.target); }
    });

    function moderate(btn) {
        var card = btn.closest('.admin-card');
        var body = new URLSearchParams();
        body.append('comment_id', card.getAttribute('data-comment-id'));
        body.append('action', btn.getAttribute('data-action'));
        body.append('csrfmiddlewaretoken', csrf);
        btn.disabled = true;
        fetch(root.dataset.commentUrl, {method: 'POST', headers: {'X-CSRFToken': csrf}, body: body,
                                         credentials: 'same-origin'})
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data && data.success) {
                    delete cache[keyOf(state)];
                    load(state, false);
                } else {
                    window.alert((data && data.error) || 'Action failed');
                    btn.disabled = false;
                }
            })
            .catch(function () { window.alert('Action failed'); btn.disabled = false; });
    }

    function saveAds(form) {
        var status = document.getElementById('admin-ads-status');
        var body = new URLSearchParams(new FormData(form));
        body.append('csrfmiddlewaretoken', csrf);
        status.textContent = 'saving';
        fetch(root.dataset.adsUrl, {method: 'POST', headers: {'X-CSRFToken': csrf}, body: body,
                                     credentials: 'same-origin'})
            .then(function (r) { return r.json(); })
            .then(function (data) {
                status.textContent = (data && data.success) ? 'saved, live within 30 seconds'
                    : ((data && data.error) || 'save failed');
            })
            .catch(function () { status.textContent = 'save failed'; });
    }

    var tipEl = document.createElement('div');
    tipEl.className = 'admin-tip';
    tipEl.id = 'admin-tip';
    tipEl.setAttribute('role', 'tooltip');
    tipEl.hidden = true;
    root.appendChild(tipEl);

    function textEl(tag, cls, text) {
        var el = document.createElement(tag);
        if (cls) { el.className = cls; }
        el.textContent = text;
        return el;
    }

    function tipShow(x, y, spec) {
        tipEl.textContent = '';
        if (spec.title) { tipEl.appendChild(textEl('div', 'admin-tip-title', spec.title)); }
        (spec.rows || []).forEach(function (row) {
            var line = document.createElement('div');
            line.className = 'admin-tip-row';
            if (row.color) {
                var key = document.createElement('span');
                key.className = 'admin-tip-key';
                key.style.background = row.color;
                line.appendChild(key);
            }
            line.appendChild(textEl('span', 'admin-tip-val', row.value));
            if (row.name) { line.appendChild(textEl('span', 'admin-tip-name', row.name)); }
            tipEl.appendChild(line);
        });
        (spec.extra || []).forEach(function (t) { tipEl.appendChild(textEl('div', 'admin-tip-extra', t)); });
        tipEl.hidden = false;
        var w = tipEl.offsetWidth, h = tipEl.offsetHeight;
        var left = x + 14, top = y + 14;
        if (left + w > window.innerWidth - 8) { left = Math.max(8, x - w - 14); }
        if (top + h > window.innerHeight - 8) { top = Math.max(8, y - h - 14); }
        tipEl.style.left = left + 'px';
        tipEl.style.top = top + 'px';
    }

    function tipHide() { tipEl.hidden = true; }

    function fillOf(rect) {
        var f = rect.getAttribute('fill') || '';
        if (f.indexOf('url(') === 0) {
            var pattern = document.getElementById(f.slice(5, -1));
            var solid = pattern && pattern.querySelector('rect:last-child');
            f = solid ? solid.getAttribute('fill') : '';
        }
        return f;
    }

    function columnsOf(svg) {
        if (svg._cols) { return svg._cols; }
        var map = {}, cols = [];
        [].forEach.call(svg.querySelectorAll('rect[data-tip]'), function (r) {
            var x = r.getAttribute('x');
            if (!map[x]) {
                map[x] = {x: parseFloat(x) + parseFloat(r.getAttribute('width')) / 2, items: []};
                cols.push(map[x]);
            }
            map[x].items.push(r);
        });
        cols.sort(function (a, b) { return a.x - b.x; });
        svg._cols = cols;
        return cols;
    }

    function showColumn(svg, col, cx, cy) {
        [].forEach.call(svg.querySelectorAll('.is-hot'), function (r) { r.classList.remove('is-hot'); });
        col.items.forEach(function (r) { r.classList.add('is-hot'); });
        var rows = col.items.slice().reverse().map(function (r) {
            return {color: fillOf(r), value: fmt.whole(parseFloat(r.dataset.v)), name: r.dataset.s || ''};
        });
        tipShow(cx, cy, {title: col.items[0].dataset.tip, rows: rows});
    }

    function nearest(svg, event) {
        var cols = columnsOf(svg);
        if (!cols.length) { return null; }
        var box = svg.getBoundingClientRect();
        var vb = svg.viewBox.baseVal;
        var x = (event.clientX - box.left) * (vb.width / box.width);
        var best = cols[0];
        cols.forEach(function (c) { if (Math.abs(c.x - x) < Math.abs(best.x - x)) { best = c; } });
        return best;
    }

    root.addEventListener('pointermove', function (e) {
        var svg = e.target.closest && e.target.closest('svg.admin-chart');
        if (!svg) { return; }
        var col = nearest(svg, e);
        if (col) { showColumn(svg, col, e.clientX, e.clientY); }
    });
    root.addEventListener('pointerdown', function (e) {
        if (e.pointerType !== 'touch') { return; }
        var svg = e.target.closest && e.target.closest('svg.admin-chart');
        var col = svg && nearest(svg, e);
        if (col) { showColumn(svg, col, e.clientX, e.clientY); }
    });
    document.addEventListener('pointerdown', function (e) {
        if (e.pointerType === 'touch' && !(e.target.closest && e.target.closest('svg'))) { tipHide(); }
    });
    root.addEventListener('pointerout', function (e) {
        if (e.pointerType === 'touch') { return; }
        var svg = e.target.closest && e.target.closest('svg.admin-chart');
        if (svg && !svg.contains(e.relatedTarget)) {
            tipHide();
            [].forEach.call(svg.querySelectorAll('.is-hot'), function (r) { r.classList.remove('is-hot'); });
        }
    });
    root.addEventListener('keydown', function (e) {
        var svg = e.target.closest && e.target.closest('svg.admin-chart');
        if (!svg) { return; }
        var cols = columnsOf(svg);
        if (!cols.length) { return; }
        var i = svg._at === undefined ? -1 : svg._at;
        if (e.key === 'ArrowRight') { i = Math.min(cols.length - 1, i + 1); }
        else if (e.key === 'ArrowLeft') { i = Math.max(0, i - 1); }
        else if (e.key === 'Home') { i = 0; }
        else if (e.key === 'End') { i = cols.length - 1; }
        else if (e.key === 'Escape') { tipHide(); return; }
        else { return; }
        e.preventDefault();
        svg._at = i;
        var box = cols[i].items[0].getBoundingClientRect();
        showColumn(svg, cols[i], box.left + box.width / 2, box.top);
    });
    root.addEventListener('focusout', function (e) {
        if (e.target.matches && e.target.matches('svg.admin-chart')) { tipHide(); }
    });

    window.AdminTools = {
        root: root,
        fmt: fmt,
        tip: {show: tipShow, hide: tipHide},
        onPanel: function (fn) {
            listeners.push(fn);
            var current = panelOf(state.tab);
            if (current && current.dataset.loaded === '1') { fn(current, {}); }
        },
        enhance: enhance
    };

    var firstPanel = panelOf(state.tab);
    if (firstPanel) {
        firstPanel.dataset.key = keyOf(state);
        enhance(firstPanel);
        drawFilters(firstPanel.querySelector('.admin-filters-note'));
    }
    if (!new URLSearchParams(location.search).has('tab') && tabNames().indexOf(location.hash.slice(1)) >= 0) {
        show(stateFromUrl(), 'replace');
    }
}());
