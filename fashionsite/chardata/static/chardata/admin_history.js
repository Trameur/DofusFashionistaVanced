/* History tab: charts drawn from /admin-tools/history.json, with plain SVG. Text goes in with textContent only. */
(function () {
    'use strict';
    var T = window.AdminTools;
    if (!T) { return; }
    var fmt = T.fmt, tip = T.tip;
    var NS = 'http://www.w3.org/2000/svg';
    var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var WORD = {M: 'Measured', C: 'Corrected, bots removed', E: 'Estimated', G: 'No data'};
    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var uid = 0;

    function h(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) { node.className = cls; }
        if (text !== undefined && text !== null) { node.textContent = text; }
        return node;
    }
    function num(v) { return isFinite(v) ? Math.round(v * 100) / 100 : 0; }
    function s(tag, attrs, parent) {
        var node = document.createElementNS(NS, tag);
        Object.keys(attrs || {}).forEach(function (k) {
            var v = attrs[k];
            node.setAttribute(k, typeof v === 'number' ? num(v) : v);
        });
        if (parent) { parent.appendChild(node); }
        return node;
    }
    function svgText(parent, x, y, text, cls, anchor) {
        var t = s('text', {x: x, y: y, 'class': cls || 'ah-axis-text'}, parent);
        if (anchor) { t.setAttribute('text-anchor', anchor); }
        t.textContent = text;
        return t;
    }
    function idx(month) { return parseInt(month.slice(0, 4), 10) * 12 + parseInt(month.slice(5, 7), 10) - 1; }
    function monthText(i) { return MON[((i % 12) + 12) % 12] + ' ' + Math.floor(i / 12); }
    function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
    function niceTicks(max) {
        if (!(max > 0)) { max = 1; }
        var raw = max / 4, mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), norm = raw / mag;
        var step = Math.max(1, (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag);
        var top = Math.ceil(max / step - 1e-9) * step, out = [];
        for (var v = 0; v <= top + step / 1000; v += step) { out.push(v); }
        return out;
    }
    function approx(row, text) { return row && row.st === 'E' ? 'about ' + text : text; }
    function hatch(defs, id, color) {
        var pat = s('pattern', {id: id, width: 9, height: 9, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)'}, defs);
        var a = s('rect', {width: 9, height: 9}, pat); a.style.fill = color; a.style.fillOpacity = '0.36';
        var b = s('rect', {width: 1.4, height: 9}, pat); b.style.fill = color; b.style.fillOpacity = '0.55';
    }
    function fitText(parent, x, y, text, cls, anchor, room) {
        var t = svgText(parent, x, y, text, cls, anchor);
        var w = t.getComputedTextLength ? t.getComputedTextLength() : 0;
        if (!w) { w = text.length * 6.2; }
        if (w + 10 > room) { parent.removeChild(t); return null; }
        return t;
    }
    function line(parent, x1, y1, x2, y2, cls) { return s('line', {x1: x1, y1: y1, x2: x2, y2: y2, 'class': cls}, parent); }

    function Model(p) {
        this.p = p;
        this.now = idx(p.now_month);
        this.S = {};
        var self = this;
        Object.keys(p.series).forEach(function (k) {
            var by = {}, list = [];
            p.series[k].forEach(function (r) {
                var o = {i: idx(r[0]), v: Number(r[1]) || 0, st: r[2], lo: r[3], hi: r[4]};
                by[o.i] = o;
                list.push(o);
            });
            var from = null;
            var keepsCounting = (p.live || []).indexOf(k) >= 0;
            for (var j = list.length - 1; keepsCounting && j >= 0 && (list[j].st === 'M' || list[j].st === 'C'); j--) { from = list[j].i; }
            self.S[k] = {by: by, list: list, zeroFrom: from};
        });
        this.eras = (p.eras || []).map(function (e) {
            return {id: e.id, name: e.name, story: e.story, from: idx(e.from), to: e.to ? idx(e.to) : self.now};
        });
        this.milestones = (p.milestones || []).slice().sort(function (a, b) {
            return a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
        });
        this.msByMonth = {};
        this.milestones.forEach(function (m) {
            var i = idx(m.month);
            (self.msByMonth[i] = self.msByMonth[i] || []).push(m);
        });
        var first = this.now;
        this.eras.forEach(function (e) { first = Math.min(first, e.from); });
        MAIN.forEach(function (d) {
            var list = (self.S[d.key] || {list: []}).list;
            if (list.length) { first = Math.min(first, list[0].i); }
        });
        this.first = first;
    }
    Model.prototype.row = function (k, i) {
        var s1 = this.S[k];
        if (!s1) { return null; }
        if (s1.by[i]) { return s1.by[i]; }
        if (s1.zeroFrom !== null && i >= s1.zeroFrom && i <= this.now) {
            return {i: i, v: 0, st: 'M', lo: null, hi: null};
        }
        return null;
    };
    Model.prototype.lo = function (r) { return r.lo === null || r.lo === undefined ? r.v : r.lo; };
    Model.prototype.hi = function (r) { return r.hi === null || r.hi === undefined ? r.v : r.hi; };
    Model.prototype.total = function (k, a, b) {
        var out = {sum: 0, measured: 0, lo: 0, hi: 0, estimated: false, any: false};
        var list = (this.S[k] || {list: []}).list;
        for (var j = 0; j < list.length; j++) {
            var r = list[j];
            if (r.i < a || r.i > b || r.st === 'G') { continue; }
            out.any = true;
            out.sum += r.v;
            out.lo += this.lo(r);
            out.hi += this.hi(r);
            if (r.st === 'E') { out.estimated = true; } else { out.measured += r.v; }
        }
        return out;
    };

    var MAIN = [
        {key: 'builds_real', label: 'Builds', color: 'var(--ad-s1)'},
        {key: 'solver', label: 'Solver runs', color: 'var(--ad-s2)'},
        {key: 'accounts_real', label: 'Accounts', color: 'var(--ad-s3)'},
        {key: 'visits', label: 'Visits', color: 'var(--ad-s4)'},
        {key: 'pages_real', label: 'Pages read', color: 'var(--ad-s5)'},
        {key: 'builds_robots', label: 'Bot copies filtered', color: 'var(--ad-bot)'}
    ];
    function mainDef(k) { return MAIN.filter(function (d) { return d.key === k; })[0]; }

    var payload = null, model = null, loadingFor = null, seenRefreshes = 0;
    var ui = {metric: 'builds_real', mode: 'month', range: null, rangeKey: 'all'};
    var ms = {lane: '', query: '', major: false};
    var parts = {};
    var redrawers = [];

    function fetchHistory(container, refresh) {
        var url = container.dataset.historyUrl + (refresh ? '?refresh=1' : '');
        container.textContent = '';
        container.appendChild(h('p', 'admin-loading', 'Loading'));
        loadingFor = container;
        fetch(url, {credentials: 'same-origin', headers: {'Accept': 'application/json'}})
            .then(function (r) { if (!r.ok) { throw new Error('status ' + r.status); } return r.json(); })
            .then(function (p) {
                if (loadingFor !== container) { return; }
                payload = p;
                build(container);
            })
            .catch(function () {
                if (loadingFor !== container) { return; }
                container.textContent = '';
                var note = h('p', 'admin-note', 'The history could not be loaded. ');
                var retry = h('a', null, 'Retry');
                retry.href = '#';
                retry.addEventListener('click', function (e) { e.preventDefault(); fetchHistory(container, false); });
                note.appendChild(retry);
                container.appendChild(note);
            });
    }

    function init(panel, info) {
        var container = panel.querySelector('#admin-history');
        if (!container) { return; }
        if (container._ready && !info.refresh) {
            redraw();
            return;
        }
        container._ready = true;
        if (info.refresh || !payload || seenRefreshes !== (info.refreshes || 0)) {
            seenRefreshes = info.refreshes || 0;
            fetchHistory(container, !!info.refresh);
        } else {
            build(container);
        }
    }

    function build(container) {
        container.textContent = '';
        if (!payload || !payload.loaded) {
            var empty = h('p', 'admin-note admin-history-empty', 'No history snapshot is loaded. Load one with the load_site_history command.');
            container.appendChild(empty);
            return;
        }
        model = new Model(payload);
        ui.range = [model.first, model.now];
        ui.rangeKey = 'all';
        redrawers = [];
        var root = h('div', 'ah');
        container.appendChild(root);
        parts = {};
        root.appendChild(lede());
        root.appendChild(tiles());
        root.appendChild(mainCard());
        root.appendChild(erasSection());
        root.appendChild(botsSection());
        root.appendChild(versionsSection());
        root.appendChild(communitySection());
        root.appendChild(workSection());
        root.appendChild(classesSection());
        root.appendChild(milestonesSection());
        root.appendChild(methodsSection());
        T.enhance(root);
        redraw();
    }

    var resizeTimer = null;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(redraw, 120);
    });

    function redraw() {
        if (!model || !parts.plot || !parts.plot.offsetWidth) { return; }
        drawMain();
        redrawers.forEach(function (fn) { fn(); });
    }

    function lede() {
        var wrap = h('div');
        var t = model.total('builds_real', model.first, model.now);
        var share = t.sum ? t.measured / t.sum : 0;
        var text = 'Data as of ' + payload.as_of + ', months after that date are counted live. ' +
            'Builds since the first record: ' + (t.estimated ? 'about ' : '') + fmt.compact(t.sum) +
            ', of which ' + fmt.percent(share) + ' measured. ' +
            'The figures before the measured months are estimates: they are drawn lighter, with a range.';
        wrap.appendChild(h('p', 'ah-lede', text));
        return wrap;
    }

    function tiles() {
        var grid = h('div', 'ah-tiles');
        MAIN.forEach(function (d) {
            var t = model.total(d.key, model.first, model.now);
            var b = h('button', 'ah-tile');
            b.type = 'button';
            b.dataset.metric = d.key;
            b.setAttribute('aria-pressed', ui.metric === d.key ? 'true' : 'false');
            b.appendChild(h('span', 'ah-tile-label', d.label));
            b.appendChild(h('span', 'ah-tile-num', (t.estimated ? '~' : '') + fmt.compact(t.sum)));
            var share = t.sum ? t.measured / t.sum : 0;
            var bar = h('span', 'ah-share');
            bar.style.setProperty('--ad-c', d.color);
            bar.setAttribute('role', 'img');
            bar.setAttribute('aria-label', fmt.percent(share) + ' measured');
            var m = h('span', 'ah-share-m'); m.style.width = (share * 100) + '%'; m.style.background = d.color;
            var e = h('span', 'ah-share-e'); e.style.width = ((1 - share) * 100) + '%';
            bar.appendChild(m); bar.appendChild(e);
            b.appendChild(bar);
            var lines = [];
            if (t.estimated) { lines.push('Range ' + fmt.compact(t.lo) + ' to ' + fmt.compact(t.hi)); }
            lines.push(fmt.percent(share) + ' measured');
            var cur = model.row(d.key, model.now);
            lines.push('This month so far: ' + (cur && cur.st !== 'G' ? approx(cur, fmt.whole(cur.v)) : '0'));
            lines.forEach(function (l) { b.appendChild(h('span', 'ah-tile-sub', l)); });
            b.addEventListener('click', function () {
                ui.metric = d.key;
                syncTiles();
                if (ui.rangeKey === 'first') { applyRange('first'); } else { drawMain(); }
                drawStrip();
            });
            grid.appendChild(b);
        });
        parts.tiles = grid;
        return grid;
    }

    function syncTiles() {
        [].forEach.call(parts.tiles.querySelectorAll('.ah-tile'), function (b) {
            b.setAttribute('aria-pressed', b.dataset.metric === ui.metric ? 'true' : 'false');
        });
        [].forEach.call(parts.metricChips.querySelectorAll('button'), function (b) {
            b.setAttribute('aria-pressed', b.dataset.metric === ui.metric ? 'true' : 'false');
        });
    }

    function chip(label, pressed, fn) {
        var b = h('button', 'admin-chip', label);
        b.type = 'button';
        b.setAttribute('aria-pressed', pressed ? 'true' : 'false');
        b.addEventListener('click', fn);
        return b;
    }

    function mainCard() {
        var card = h('div', 'ah-card');
        card.appendChild(h('h2', null, 'Month by month'));
        var c1 = h('div', 'ah-controls');
        parts.metricChips = c1;
        MAIN.forEach(function (d) {
            var b = chip(d.label, ui.metric === d.key, function () {
                ui.metric = d.key;
                syncTiles();
                if (ui.rangeKey === 'first') { applyRange('first'); } else { drawMain(); }
                drawStrip();
            });
            b.dataset.metric = d.key;
            c1.appendChild(b);
        });
        card.appendChild(c1);

        var c2 = h('div', 'ah-controls');
        parts.modeChips = [];
        [['month', 'Per month'], ['cum', 'Cumulative']].forEach(function (pair) {
            var b = chip(pair[1], ui.mode === pair[0], function () {
                ui.mode = pair[0];
                parts.modeChips.forEach(function (x) { x.setAttribute('aria-pressed', x.dataset.mode === ui.mode ? 'true' : 'false'); });
                drawMain();
            });
            b.dataset.mode = pair[0];
            parts.modeChips.push(b);
            c2.appendChild(b);
        });
        c2.appendChild(h('span', 'ah-sep'));
        parts.rangeChips = [];
        [['all', 'All'], ['first', 'First site'], ['2023', 'Since 2023'], ['12', 'Last 12 months']].forEach(function (pair) {
            var b = chip(pair[1], ui.rangeKey === pair[0], function () { applyRange(pair[0]); });
            b.dataset.range = pair[0];
            parts.rangeChips.push(b);
            c2.appendChild(b);
        });
        var reset = h('button', 'admin-chip ah-grow', 'Reset zoom');
        reset.type = 'button';
        reset.hidden = true;
        reset.addEventListener('click', function () { applyRange('all'); });
        parts.reset = reset;
        c2.appendChild(reset);
        card.appendChild(c2);

        parts.strip = h('div', 'ah-strip');
        card.appendChild(parts.strip);
        var plot = h('div', 'ah-plot');
        parts.plot = plot;
        card.appendChild(plot);
        parts.legend = h('div', 'ah-legend');
        card.appendChild(parts.legend);
        card.appendChild(h('p', 'admin-note', 'Drag across the chart to zoom, or click an era above it. The dots under the axis are milestones. With the chart focused, the arrow keys move from month to month.'));
        parts.msNote = h('p', 'admin-note');
        card.appendChild(parts.msNote);

        var det = h('details', 'ah-details');
        det.appendChild(h('summary', null, 'Show the numbers'));
        var holder = h('div', 'ah-scroll');
        det.appendChild(holder);
        det.addEventListener('toggle', function () { if (det.open) { drawNumbers(holder); } });
        parts.numbers = {det: det, holder: holder};
        card.appendChild(det);
        drawStrip();
        return card;
    }

    function drawStrip() {
        var k = ui.metric, d = mainDef(k);
        var box = parts.strip;
        box.textContent = '';
        [['This month so far', model.now, true], ['Last full month', model.now - 1, false],
         ['Same month last year', model.now - 12, false]].forEach(function (c) {
            var r = model.row(k, c[1]);
            var cell = h('div', c[2] ? 'ah-strip-now' : '');
            cell.appendChild(h('span', 'ah-strip-label', c[0] + ', ' + monthText(c[1])));
            var none = !r || r.st === 'G';
            cell.appendChild(h('span', 'ah-strip-val', none ? 'No data' : approx(r, fmt.whole(r.v))));
            cell.appendChild(h('span', 'ah-strip-st', none ? '' : WORD[r.st] + ' - ' + d.label.toLowerCase()));
            box.appendChild(cell);
        });
    }

    function rangeFor(key) {
        var k = ui.metric, a = model.first, b = model.now;
        if (key === '2023') { a = Math.max(a, 2023 * 12); }
        else if (key === '12') { a = Math.max(a, model.now - 11); }
        else if (key === 'first') {
            var list = (model.S[k] || {list: []}).list;
            if (!list.length) { return null; }
            var start = list[0].i, end = start, gap = 0, last = start;
            for (var j = 0; j < list.length; j++) {
                var r = list[j];
                if (r.st === 'G') { continue; }
                if (r.i - last > 6) { break; }
                end = r.i; last = r.i;
            }
            var firstGap = list.filter(function (r) { return r.st === 'G'; })[0];
            if (firstGap && firstGap.i > start) { end = Math.min(end, firstGap.i - 1); }
            if (!firstGap || end >= model.now - 1) { return null; }
            gap = end;
            a = start; b = gap;
        }
        return [a, b];
    }

    function applyRange(key) {
        var r = rangeFor(key);
        if (!r) { key = 'all'; r = rangeFor('all'); }
        ui.range = r;
        ui.rangeKey = key;
        drawMain();
    }

    function syncRangeUi() {
        parts.rangeChips.forEach(function (b) {
            b.setAttribute('aria-pressed', b.dataset.range === ui.rangeKey ? 'true' : 'false');
            if (b.dataset.range === 'first') { b.hidden = !rangeFor('first'); }
        });
        var hideReset = ui.rangeKey === 'all' || ui.rangeKey === '2023' || ui.rangeKey === '12' || ui.rangeKey === 'first';
        if (hideReset && document.activeElement === parts.reset) {
            var target = parts.rangeChips.filter(function (b) { return b.dataset.range === ui.rangeKey && !b.hidden; })[0] || parts.rangeChips[0];
            target.focus({preventScroll: true});
        }
        parts.reset.hidden = hideReset;
    }

    function drawLegend(d) {
        var lg = parts.legend;
        lg.textContent = '';
        lg.style.setProperty('--ad-c', d.color);
        function item(swCls, text) {
            var span = h('span');
            var sw = h('i', 'ah-sw ' + swCls);
            span.appendChild(sw);
            span.appendChild(document.createTextNode(text));
            lg.appendChild(span);
        }
        if (ui.mode === 'cum') {
            item('ah-sw-line', 'Total made only of measured or corrected months');
            item('ah-sw-line ah-sw-e', 'Total that includes estimates or months with no data, with its range as a band');
        } else {
            item('', 'Measured or corrected');
            item('ah-sw-e', 'Estimated, lighter, with its range as a soft band');
            item('ah-sw-dot ah-sw-dot-major', 'Major milestone');
            item('ah-sw-dot', 'Milestone');
            item('ah-sw-dot ah-sw-dot-group', 'Several milestones close together, with their count');
        }
        item('ah-sw-void', 'Months with no data are left empty');
    }

    function drawMain() {
        if (!model || !parts.plot) { return; }
        var plotBox = parts.plot;
        var W = Math.max(300, Math.floor(plotBox.clientWidth));
        if (!plotBox.clientWidth) { return; }
        var k = ui.metric, d = mainDef(k);
        var small = W < 520;
        var H = small ? 320 : 380, L = small ? 44 : 54, R = 8, ESH = 22, PT = ESH + 18, PB = H - 76;
        var plotW = W - L - R, plotH = PB - PT;
        var i0 = ui.range[0], i1 = ui.range[1], n = i1 - i0 + 1, band = plotW / n;
        var cum = ui.mode === 'cum';
        syncRangeUi();
        drawLegend(d);

        var vals = [], cumV = [], cumLo = [], cumHi = [], cumEst = [], run = 0, runLo = 0, runHi = 0, runEst = false;
        var list = (model.S[k] || {list: []}).list;
        list.forEach(function (r) { if (r.i < i0 && r.st !== 'G') { run += r.v; runLo += model.lo(r); runHi += model.hi(r); if (r.st === 'E') { runEst = true; } } });
        var maxV = 0;
        for (var i = i0; i <= i1; i++) {
            var r = model.row(k, i);
            var real = r && r.st !== 'G' ? r : null;
            vals.push(real);
            if (real) { run += real.v; runLo += model.lo(real); runHi += model.hi(real); if (real.st === 'E') { runEst = true; } }
            cumV.push(run); cumLo.push(runLo); cumHi.push(runHi); cumEst.push(runEst || runLo !== runHi);
            maxV = Math.max(maxV, cum ? runHi : (real ? model.hi(real) : 0));
        }
        var ticks = niceTicks(maxV), top = ticks[ticks.length - 1] || 1;
        function X(j) { return L + (j + 0.5) * band; }
        function Y(v) { return PB - (v / top) * plotH; }

        var focusKey = null;
        if (plotBox.contains(document.activeElement) && document.activeElement.dataset) { focusKey = document.activeElement.dataset.fk || null; }
        var focusIds = focusKey === 'ms' ? (document.activeElement.dataset.ids || '').split(',') : null;
        plotBox.textContent = '';
        var svg = s('svg', {viewBox: '0 0 ' + W + ' ' + H, 'class': 'ah-svg', role: 'group', tabindex: 0,
                            'aria-label': d.label + (cum ? ', cumulative' : ' per month') + ', ' + monthText(i0) + ' to ' + monthText(i1)});
        svg.dataset.fk = 'svg';
        svg.style.setProperty('--ad-c', d.color);
        svg.style.color = 'inherit';
        plotBox.appendChild(svg);
        var defs = s('defs', {}, svg);
        var pid = 'ah-hatch-' + (++uid);
        hatch(defs, pid, 'var(--ad-c)');

        ticks.forEach(function (v) {
            var y = Y(v);
            line(svg, L, y, W - R, y, v === 0 ? 'ah-axis-line' : 'ah-tick-line');
            svgText(svg, L - 6, y + 4, fmt.compact(v), 'ah-axis-text', 'end');
        });

        var runStart = null;
        function voidRun(a, b) {
            var w = (b - a + 1) * band;
            s('rect', {x: L + a * band, y: PT, width: w, height: plotH, 'class': 'ah-void-rect'}, svg);
            fitText(svg, L + a * band + w / 2, PT + plotH / 2, 'No data', 'ah-void', 'middle', w);
        }
        for (var j = 0; j < vals.length; j++) {
            if (!vals[j]) { if (runStart === null) { runStart = j; } }
            else if (runStart !== null) { voidRun(runStart, j - 1); runStart = null; }
        }
        if (runStart !== null) { voidRun(runStart, vals.length - 1); }

        var bw = Math.min(Math.max(band * 0.78, 1), 24);
        if (!cum) {
            var runE = [];
            function flushBand() {
                if (!runE.length) { return; }
                var half = runE.length === 1 ? Math.max(bw / 2, 2) : band / 2, first = runE[0], last = runE[runE.length - 1];
                var top = runE.map(function (q) { return num(q.x) + ' ' + num(Y(q.hi)); });
                var bot = runE.map(function (q) { return num(q.x) + ' ' + num(Y(q.lo)); }).reverse();
                var d0 = 'M' + num(first.x - half) + ' ' + num(Y(first.hi)) + 'L' + top.join('L') + 'L' + num(last.x + half) + ' ' + num(Y(last.hi)) +
                    'L' + num(last.x + half) + ' ' + num(Y(last.lo)) + 'L' + bot.join('L') + 'L' + num(first.x - half) + ' ' + num(Y(first.lo)) + 'Z';
                s('path', {d: d0, 'class': 'ah-est-band'}, svg);
                runE = [];
            }
            vals.forEach(function (r, j) {
                if (r && r.st === 'E' && r.lo !== null && r.lo !== undefined) { runE.push({x: X(j), lo: model.lo(r), hi: model.hi(r)}); }
                else { flushBand(); }
            });
            flushBand();
            vals.forEach(function (r, j) {
                if (!r) { return; }
                var hgt = (r.v / top) * plotH;
                var rect = s('rect', {x: X(j) - bw / 2, y: PB - hgt, width: bw, height: Math.max(hgt, 0), 'class': 'ah-bar'}, svg);
                if (r.st === 'E') { rect.setAttribute('fill', 'url(#' + pid + ')'); }
                else { rect.style.fill = 'var(--ad-c)'; }
                if (i0 + j === model.now) {
                    s('rect', {x: X(j) - bw / 2 - 2, y: PB - hgt - 2, width: bw + 4, height: hgt + 2, 'class': 'ah-now'}, svg);
                    svgText(svg, X(j) + bw / 2 + 2, Math.max(PT + 8, PB - hgt - 8), 'so far', 'ah-now-text', 'end');
                }
            });
        } else {
            var pts = cumV.map(function (v, j) { return [X(j), Y(v)]; });
            var bandTop = cumHi.map(function (v, j) { return num(X(j)) + ' ' + num(Y(v)); });
            var bandBottom = cumLo.map(function (v, j) { return num(X(j)) + ' ' + num(Y(v)); }).reverse();
            s('path', {d: 'M' + bandTop.join('L') + 'L' + bandBottom.join('L') + 'Z', 'class': 'ah-band'}, svg);
            var area = 'M' + num(pts[0][0]) + ' ' + PB + 'L' + pts.map(function (p) { return num(p[0]) + ' ' + num(p[1]); }).join('L') +
                'L' + num(pts[pts.length - 1][0]) + ' ' + PB + 'Z';
            s('path', {d: area, 'class': 'ah-area'}, svg);
            var seg = null, segEst = null;
            for (j = 1; j < pts.length; j++) {
                if (!cumV[j] && !cumV[j - 1]) {
                    if (seg !== null) { drawSeg(svg, seg, segEst); seg = null; }
                    continue;
                }
                var est = cumEst[j] || !vals[j];
                if (seg === null || est !== segEst) {
                    if (seg !== null) { drawSeg(svg, seg, segEst); }
                    seg = [pts[j - 1]]; segEst = est;
                }
                seg.push(pts[j]);
            }
            if (seg) { drawSeg(svg, seg, segEst); }
            var lastP = pts[pts.length - 1];
            if (i1 === model.now || true) {
                s('circle', {cx: lastP[0], cy: lastP[1], r: 4.5, 'class': 'ah-dot'}, svg);
                var lbl = fmt.compact(cumV[cumV.length - 1]);
                svgText(svg, Math.min(lastP[0] + 6, W - R), Math.max(PT + 8, lastP[1] - 10), (i1 === model.now ? 'so far, ' : '') + (cumEst[cumEst.length - 1] ? '~' : '') + lbl, 'ah-now-text', 'end');
            }
        }

        line(svg, L, PB, W - R, PB, 'ah-axis-line');
        var yearly = n > 40, stepM;
        if (yearly) {
            var yrs = Math.max(1, Math.ceil(46 / (12 * band)));
            for (var y = Math.ceil(i0 / 12); y * 12 <= i1; y++) {
                if (y % yrs) { continue; }
                var jj = y * 12 - i0;
                line(svg, X(jj), PB, X(jj), PB + 4, 'ah-axis-line');
                svgText(svg, X(jj), PB + 17, String(y), 'ah-axis-text', 'middle');
            }
        } else {
            stepM = Math.max(1, Math.ceil(64 / band));
            [1, 2, 3, 6, 12].some(function (v) { if (v >= stepM) { stepM = v; return true; } return false; });
            for (var mi = i0; mi <= i1; mi++) {
                if (mi % 12 % stepM) { continue; }
                line(svg, X(mi - i0), PB, X(mi - i0), PB + 4, 'ah-axis-line');
                svgText(svg, X(mi - i0), PB + 17, monthText(mi), 'ah-axis-text', 'middle');
            }
        }

        model.eras.forEach(function (e) {
            var a = Math.max(e.from, i0), b = Math.min(e.to, i1);
            if (b < a) { return; }
            var x0 = L + (a - i0) * band, w = (b - a + 1) * band;
            var g = s('g', {'class': 'ah-era', tabindex: -1, role: 'button', 'aria-label': 'Zoom to ' + e.name}, svg);
            g.dataset.fk = 'era:' + e.id;
            s('rect', {x: x0 + 0.5, y: 0, width: Math.max(w - 1, 1), height: ESH}, g);
            fitText(g, x0 + w / 2, 15, e.name, '', 'middle', w);
            g.addEventListener('pointerdown', function (ev) { ev.stopPropagation(); });
            g.addEventListener('click', function () { zoomTo(e.from, e.to); });
            g.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); zoomTo(e.from, e.to); } });
            g.addEventListener('pointermove', function (ev) {
                ev.stopPropagation();
                tip.show(ev.clientX, ev.clientY, {title: e.name, rows: [], extra: [monthText(e.from) + ' to ' + (e.to === model.now && !payloadEraEnds(e) ? 'now' : monthText(e.to)), 'Click to zoom']});
            });
            g.addEventListener('pointerleave', tip.hide);
        });

        var showAll = n <= 48, my = PB + 40, hiddenMs = 0, MSR = 7, PITCH = 15;
        var cells = [];
        for (var mm = i0; mm <= i1; mm++) {
            var every = model.msByMonth[mm] || [];
            var shownMs = every.filter(function (m) { return showAll || m.major; });
            hiddenMs += every.length - shownMs.length;
            if (shownMs.length) { cells.push({x: X(mm - i0), items: shownMs, mm: mm}); }
        }
        var groups = [];
        cells.forEach(function (c) {
            var g0 = groups[groups.length - 1];
            if (g0 && c.x - g0.x0 < 2 * MSR + 6) { g0.items = g0.items.concat(c.items); g0.sum += c.x; g0.cnt += 1; g0.last = c.mm; }
            else { groups.push({x0: c.x, sum: c.x, cnt: 1, items: c.items.slice(), first: c.mm, last: c.mm}); }
        });
        var minX = L + MSR, maxX = W - R - MSR;
        groups.forEach(function (g0) { g0.x = clamp(g0.sum / g0.cnt, minX, maxX); });
        for (var gi = 1; gi < groups.length; gi++) { groups[gi].x = Math.max(groups[gi].x, groups[gi - 1].x + PITCH); }
        for (gi = groups.length - 1; gi >= 0; gi--) {
            var cap = gi === groups.length - 1 ? maxX : groups[gi + 1].x - PITCH;
            groups[gi].x = Math.min(groups[gi].x, cap);
        }
        groups.forEach(function (g0) {
            var items = g0.items, cx = g0.x, count = items.length, major = items.some(function (m) { return m.major; });
            var ids = items.map(function (m) { return m.id; });
            var span = monthText(g0.first) + (g0.last !== g0.first ? ' to ' + monthText(g0.last) : '');
            var label = count === 1 ? items[0].title + ', ' + span : count + ' milestones, ' + span;
            var node = s('g', {tabindex: 0, role: 'button', 'aria-label': label}, svg);
            node.dataset.fk = 'ms';
            node.dataset.ids = ids.join(',');
            s('circle', {cx: cx, cy: my, r: MSR, fill: 'transparent'}, node);
            if (count === 1) {
                s('circle', {cx: cx, cy: my, r: major ? 5 : 3.5, 'class': 'ah-ms' + (major ? ' ah-ms-major' : '')}, node);
            } else {
                s('circle', {cx: cx, cy: my, r: MSR - 0.5, 'class': 'ah-ms ah-ms-group' + (major ? ' ah-ms-major' : '')}, node);
                svgText(node, cx, my + 3.5, count > 99 ? '99+' : String(count), 'ah-ms-count', 'middle');
            }
            function go() { tip.hide(); scrollToMilestones(ids); }
            node.addEventListener('pointerdown', function (ev) { ev.stopPropagation(); });
            node.addEventListener('click', go);
            node.addEventListener('keydown', function (ev) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); go(); } });
            function over(ev) {
                ev.stopPropagation();
                var rc = node.getBoundingClientRect();
                var x = ev.clientX || rc.left, y = ev.clientY || rc.top;
                var lines = items.slice(0, 5).map(function (m) { return m.title; });
                if (count > 5) { lines.push('and ' + (count - 5) + ' more'); }
                lines.push(count > 1 ? 'Click to read them' : 'Click to read it');
                tip.show(x, y, {title: span, rows: [], extra: lines});
            }
            node.addEventListener('pointermove', over);
            node.addEventListener('focus', over);
            node.addEventListener('pointerleave', tip.hide);
            node.addEventListener('blur', tip.hide);
        });
        if (parts.msNote) {
            parts.msNote.textContent = hiddenMs ? 'This wide view shows major milestones only. Zoom in to see the other ' + hiddenMs + '.' : '';
            parts.msNote.hidden = !hiddenMs;
        }

        var cross = s('line', {x1: 0, y1: PT, x2: 0, y2: PB, 'class': 'ah-cross'}, svg);
        cross.style.display = 'none';
        var sel = s('rect', {x: 0, y: PT, width: 0, height: plotH, 'class': 'ah-sel'}, svg);
        sel.style.display = 'none';
        var drag = null, at = null;

        function sx(ev) {
            var box = svg.getBoundingClientRect();
            return (ev.clientX - box.left) * (W / box.width);
        }
        function indexAt(x) { return clamp(Math.floor((x - L) / band), 0, n - 1); }
        function describe(j, px, py) {
            var r = vals[j], mi = i0 + j;
            cross.setAttribute('x1', num(X(j))); cross.setAttribute('x2', num(X(j)));
            cross.style.display = '';
            var rows = [], extra = [];
            if (!r) {
                rows.push({value: 'No data', name: '', color: ''});
            } else {
                rows.push({color: d.color, value: approx(r, fmt.whole(r.v)), name: d.label.toLowerCase() + ', ' + WORD[r.st].toLowerCase()});
                if (r.st === 'E' && r.lo !== null && r.lo !== undefined) { extra.push('Range ' + fmt.whole(r.lo) + ' to ' + fmt.whole(r.hi)); }
            }
            if (cum) {
                rows.push({color: d.color, value: (cumEst[j] ? 'about ' : '') + fmt.whole(cumV[j]), name: 'total since the start'});
                if (cumLo[j] !== cumHi[j]) { extra.push('Range of the total ' + fmt.whole(cumLo[j]) + ' to ' + fmt.whole(cumHi[j])); }
            }
            if (mi === model.now) { extra.push('Month not over yet'); }
            (model.msByMonth[mi] || []).slice(0, 3).forEach(function (m) { extra.push('Milestone: ' + m.title); });
            tip.show(px, py, {title: monthText(mi), rows: rows, extra: extra});
        }
        svg.addEventListener('pointerdown', function (ev) {
            var x = sx(ev);
            if (x < L || x > L + plotW) { return; }
            drag = {x0: x, moved: false};
            if (ev.pointerType === 'touch') { at = indexAt(x); describe(at, ev.clientX, ev.clientY); }
            try { svg.setPointerCapture(ev.pointerId); } catch (err) { /* pointer already released */ }
        });
        svg.addEventListener('pointermove', function (ev) {
            var x = sx(ev);
            if (drag) {
                if (Math.abs(x - drag.x0) > 6) { drag.moved = true; }
                if (drag.moved) {
                    var a = clamp(Math.min(x, drag.x0), L, L + plotW), b = clamp(Math.max(x, drag.x0), L, L + plotW);
                    sel.setAttribute('x', num(a)); sel.setAttribute('width', num(b - a)); sel.style.display = '';
                    tip.hide();
                    return;
                }
            }
            if (x < L || x > L + plotW || ev.clientY === undefined) { return; }
            at = indexAt(x);
            describe(at, ev.clientX, ev.clientY);
        });
        svg.addEventListener('pointerup', function (ev) {
            if (!drag) { return; }
            var x = sx(ev), was = drag;
            drag = null;
            sel.style.display = 'none';
            if (was.moved) {
                var a = indexAt(Math.min(x, was.x0)) + i0, b = indexAt(Math.max(x, was.x0)) + i0;
                if (b > a) { zoomTo(a, b); }
            }
        });
        svg.addEventListener('pointerleave', function (ev) { if (!drag && ev.pointerType !== 'touch') { cross.style.display = 'none'; tip.hide(); } });
        svg.addEventListener('pointercancel', function () {
            drag = null;
            sel.style.display = 'none';
        });
        svg.addEventListener('keydown', function (ev) {
            if (ev.target !== svg) { return; }
            var move = ev.key === 'ArrowRight' ? 1 : ev.key === 'ArrowLeft' ? -1 : ev.key === 'Home' ? -n : ev.key === 'End' ? n : 0;
            if (ev.key === 'Escape') { cross.style.display = 'none'; tip.hide(); return; }
            if (!move) { return; }
            ev.preventDefault();
            at = clamp((at === null ? (move > 0 ? -1 : n) : at) + move, 0, n - 1);
            var box = svg.getBoundingClientRect();
            describe(at, box.left + X(at) * (box.width / W), box.top + PT);
        });
        svg.addEventListener('blur', function () { cross.style.display = 'none'; tip.hide(); });
        parts.svg = svg;
        restoreFocus(focusKey, focusIds, svg);
        if (parts.numbers.det.open) { drawNumbers(parts.numbers.holder); }
    }

    function restoreFocus(key, ids, svg) {
        if (!key) { return; }
        var target = null;
        if (key === 'ms') {
            [].forEach.call(svg.querySelectorAll('[data-fk="ms"]'), function (g0) {
                if (!target && (g0.dataset.ids || '').split(',').some(function (id) { return ids.indexOf(id) >= 0; })) { target = g0; }
            });
        } else {
            [].forEach.call(svg.querySelectorAll('[data-fk]'), function (g0) { if (g0.dataset.fk === key) { target = g0; } });
        }
        (target || svg).focus({preventScroll: true});
    }

    function payloadEraEnds(e) {
        var src = (payload.eras || []).filter(function (x) { return x.id === e.id; })[0];
        return !!(src && src.to);
    }

    function drawSeg(svg, pts, est) {
        var dPath = 'M' + pts.map(function (p) { return num(p[0]) + ' ' + num(p[1]); }).join('L');
        var path = s('path', {d: dPath, 'class': 'ah-line' + (est ? ' ah-line-e' : '')}, svg);
        if (est) { path.setAttribute('stroke-dasharray', '5 4'); }
    }

    function zoomTo(a, b) {
        if (b <= a) { b = a + 1; }
        ui.range = [Math.max(a, model.first), Math.min(b, model.now)];
        ui.rangeKey = 'zoom';
        drawMain();
        if (parts.plot.scrollIntoView) { parts.plot.scrollIntoView({block: 'nearest', behavior: reduceMotion ? 'auto' : 'smooth'}); }
    }

    function drawNumbers(holder) {
        holder.textContent = '';
        var k = ui.metric, table = h('table', 'admin-table');
        var head = table.insertRow();
        ['Month', 'Value', 'Status', 'Low', 'High'].forEach(function (t) { head.appendChild(h('th', null, t)); });
        for (var i = ui.range[0]; i <= ui.range[1]; i++) {
            var r = model.row(k, i), tr = table.insertRow();
            var c0 = tr.insertCell(); c0.textContent = monthText(i); c0.dataset.sort = i;
            var c1 = tr.insertCell(); c1.className = 'admin-num'; c1.textContent = r && r.st !== 'G' ? fmt.whole(r.v) : '';
            c1.dataset.sort = r && r.st !== 'G' ? r.v : '';
            tr.insertCell().textContent = r ? WORD[r.st] : WORD.G;
            var c3 = tr.insertCell(); c3.className = 'admin-num'; c3.textContent = r && r.lo !== null && r.lo !== undefined ? fmt.whole(r.lo) : '';
            var c4 = tr.insertCell(); c4.className = 'admin-num'; c4.textContent = r && r.hi !== null && r.hi !== undefined ? fmt.whole(r.hi) : '';
        }
        table.dataset.more = '24';
        holder.appendChild(table);
        T.enhance(holder);
    }

    function erasSection() {
        var wrap = h('div');
        wrap.appendChild(h('h2', null, 'Eras'));
        var grid = h('div', 'ah-eras');
        model.eras.forEach(function (e) {
            var card = h('div', 'ah-card ah-era-card');
            card.appendChild(h('h3', null, e.name));
            var endText = payloadEraEnds(e) ? monthText(e.to) : 'now';
            card.appendChild(h('div', 'ah-era-dates', monthText(e.from) + ' to ' + endText));
            var spark = sparkline(e);
            if (spark) { card.appendChild(spark); }
            card.appendChild(h('p', 'ah-era-story', e.story));
            var totals = h('p', 'ah-era-totals');
            var any = false;
            [['builds_real', 'builds'], ['visits', 'visits'], ['solver', 'solver runs'], ['accounts_real', 'accounts']].forEach(function (pair) {
                var t = model.total(pair[0], e.from, e.to);
                if (!t.any || !t.sum) { return; }
                any = true;
                var span = h('span');
                span.appendChild(h('b', null, (t.estimated ? 'about ' : '') + fmt.compact(t.sum)));
                span.appendChild(document.createTextNode(' ' + pair[1]));
                totals.appendChild(span);
            });
            if (!any) { totals.textContent = 'No figures were kept for this period.'; }
            card.appendChild(totals);
            var b = h('button', 'admin-chip', 'Show on the chart');
            b.type = 'button';
            b.style.alignSelf = 'flex-start';
            b.addEventListener('click', function () {
                zoomTo(e.from, e.to);
                var main = parts.plot.closest('.ah-card');
                if (main && main.scrollIntoView) { main.scrollIntoView({block: 'start', behavior: reduceMotion ? 'auto' : 'smooth'}); }
            });
            card.appendChild(b);
            grid.appendChild(card);
        });
        wrap.appendChild(grid);
        return wrap;
    }

    function sparkline(e) {
        var rows = [];
        for (var i = e.from; i <= e.to; i++) {
            var r = model.row('builds_real', i);
            if (r && r.st !== 'G') { rows.push(r); }
        }
        if (rows.length < 2) { return null; }
        var box = h('div', 'ah-spark-box');
        var max = Math.max.apply(null, rows.map(function (r) { return r.v; })) || 1;
        var span = Math.max(1, e.to - e.from);
        var done = rows.filter(function (r) { return r.i !== model.now; });
        var partial = rows.filter(function (r) { return r.i === model.now; })[0];
        function draw() {
            if (!box.clientWidth) { return; }
            box.textContent = '';
            var W = Math.floor(box.clientWidth), H = 44;
            var svg = s('svg', {viewBox: '0 0 ' + W + ' ' + H, 'class': 'ah-spark', 'aria-hidden': 'true'}, box);
            svg.setAttribute('width', '100%');
            function P(r) { return [4 + ((r.i - e.from) / span) * (W - 8), H - 3 - (r.v / max) * (H - 8), r.st === 'E']; }
            var pts = done.map(P);
            if (pts.length > 1) {
                s('path', {d: 'M' + num(pts[0][0]) + ' ' + H + 'L' + pts.map(function (p) { return num(p[0]) + ' ' + num(p[1]); }).join('L') + 'L' + num(pts[pts.length - 1][0]) + ' ' + H + 'Z', 'class': 'ah-spark-a'}, svg);
                var cur = null, est = null;
                var flush = function () {
                    if (!cur) { return; }
                    var p = s('path', {d: 'M' + cur.map(function (q) { return num(q[0]) + ' ' + num(q[1]); }).join('L')}, svg);
                    if (est) { p.setAttribute('class', 'ah-spark-e'); p.setAttribute('stroke-dasharray', '4 3'); }
                };
                for (var j = 1; j < pts.length; j++) {
                    var e1 = pts[j][2];
                    if (!cur || e1 !== est) { flush(); cur = [pts[j - 1]]; est = e1; }
                    cur.push(pts[j]);
                }
                flush();
            }
            if (partial) {
                var q = P(partial);
                s('circle', {cx: Math.min(q[0], W - 5), cy: q[1], r: 3.5, 'class': 'ah-spark-now'}, svg);
            }
        }
        redrawers.push(draw);
        return box;
    }

    function miniChart(box, spec) {
        /* spec: {bars:[{key,label,color}], lines:[{key,label,color}], height, axis, ends} */
        var keys = spec.bars.concat(spec.lines || []);
        var a = model.now, b = model.now;
        keys.forEach(function (d) {
            var list = (model.S[d.key] || {list: []}).list.filter(function (r) { return r.st !== 'G'; });
            if (list.length) { a = Math.min(a, list[0].i); }
        });
        function draw() {
            if (!box.clientWidth) { return; }
            box.textContent = '';
            var W = Math.max(160, Math.floor(box.clientWidth)), H = spec.height || 150, axis = spec.axis !== false;
            var L = axis ? 38 : 4, R = 4, PT = spec.ends ? 16 : 6, PB = axis ? H - 20 : (spec.ends ? H - 18 : H - 4);
            var n = b - a + 1, band = (W - L - R) / n, plotH = PB - PT;
            var maxV = 0;
            for (var i = a; i <= b; i++) {
                var tot = 0;
                spec.bars.forEach(function (d) { var r = model.row(d.key, i); if (r && r.st !== 'G') { tot += model.hi(r); } });
                (spec.lines || []).forEach(function (d) { var r = model.row(d.key, i); if (r && r.st !== 'G') { maxV = Math.max(maxV, r.v); } });
                maxV = Math.max(maxV, tot);
            }
            var ticks = niceTicks(maxV), top = ticks[ticks.length - 1] || 1;
            function X(i2) { return L + (i2 - a + 0.5) * band; }
            function Y(v) { return PB - (v / top) * plotH; }
            var svg = s('svg', {viewBox: '0 0 ' + W + ' ' + H, 'class': 'ah-svg', role: 'img', tabindex: 0, 'aria-label': spec.label});
            svg.style.touchAction = 'pan-y';
            box.appendChild(svg);
            var defs = s('defs', {}, svg);
            var ids = {};
            spec.bars.forEach(function (d) {
                var pid = 'ah-hatch-' + (++uid);
                ids[d.key] = pid;
                hatch(defs, pid, d.color);
            });
            var t0 = axis ? ticks : [0];
            t0.forEach(function (v) {
                line(svg, L, Y(v), W - R, Y(v), v === 0 ? 'ah-axis-line' : 'ah-tick-line');
                if (axis) { svgText(svg, L - 5, Y(v) + 4, fmt.compact(v), 'ah-axis-text', 'end'); }
            });
            var bw = Math.min(Math.max(band * 0.78, 1), 20), peak = null;
            for (var m = a; m <= b; m++) {
                var base = PB, sum = 0;
                spec.bars.forEach(function (d) {
                    var r = model.row(d.key, m);
                    if (!r || r.st === 'G') { return; }
                    sum += r.v;
                    var live = m === model.now;
                    if (!r.v && !live) { return; }
                    var hgt = Math.max((r.v / top) * plotH - (spec.bars.length > 1 ? 1 : 0), live ? 2 : 0.5);
                    base -= hgt + (spec.bars.length > 1 ? 1 : 0);
                    var rect = s('rect', {x: X(m) - bw / 2, y: base, width: bw, height: hgt}, svg);
                    if (r.st === 'E') { rect.setAttribute('fill', 'url(#' + ids[d.key] + ')'); } else { rect.style.fill = d.color; }
                    if (live) { rect.setAttribute('class', 'ah-bar-now'); rect.style.fillOpacity = r.v ? '0.55' : '0'; }
                });
                if (spec.ends && sum > 0 && m !== model.now && (!peak || sum > peak.v)) { peak = {m: m, v: sum}; }
            }
            (spec.lines || []).forEach(function (d) {
                var pts = [], live = null;
                for (var m2 = a; m2 <= b; m2++) {
                    var r = model.row(d.key, m2);
                    if (!r || r.st === 'G') { continue; }
                    if (m2 === model.now) { live = [X(m2), Y(r.v)]; } else { pts.push(num(X(m2)) + ' ' + num(Y(r.v))); }
                }
                if (pts.length) {
                    var path = s('path', {d: 'M' + pts.join('L'), 'class': 'ah-line'}, svg);
                    path.style.stroke = d.color;
                }
                if (live) {
                    var dot = s('circle', {cx: live[0], cy: live[1], r: 3.5, 'class': 'ah-spark-now'}, svg);
                    dot.style.stroke = d.color;
                }
            });
            if (axis) {
                var yrs = Math.max(1, Math.ceil(46 / (12 * band)));
                if (n <= 30) {
                    var st = Math.max(1, Math.ceil(54 / band));
                    for (var m3 = a; m3 <= b; m3++) {
                        if ((m3 - a) % st) { continue; }
                        svgText(svg, X(m3), H - 5, monthText(m3), 'ah-axis-text', 'middle');
                    }
                } else {
                    for (var y = Math.ceil(a / 12); y * 12 <= b; y++) {
                        if (y % yrs) { continue; }
                        svgText(svg, X(y * 12), H - 5, String(y), 'ah-axis-text', 'middle');
                    }
                }
            }
            if (spec.ends) {
                svgText(svg, L, H - 4, monthText(a), 'ah-axis-text', 'start');
                svgText(svg, W - R, H - 4, monthText(b), 'ah-axis-text', 'end');
                if (peak) {
                    var px = clamp(X(peak.m), L + 30, W - R - 30), py = Math.max(11, Y(peak.v) - 4);
                    svgText(svg, px, py, 'max ' + fmt.compact(peak.v), 'ah-axis-text', 'middle');
                }
            }
            var cross = s('line', {x1: 0, y1: PT, x2: 0, y2: PB, 'class': 'ah-cross'}, svg);
            cross.style.display = 'none';
            var at = null;
            function describe(j, px, py) {
                var mi = a + j;
                cross.setAttribute('x1', num(X(mi))); cross.setAttribute('x2', num(X(mi))); cross.style.display = '';
                var rows = [];
                spec.bars.concat(spec.lines || []).forEach(function (d) {
                    var r = model.row(d.key, mi);
                    rows.push({color: d.color, value: r && r.st !== 'G' ? approx(r, fmt.whole(r.v)) : 'No data', name: d.label});
                });
                tip.show(px, py, {title: monthText(mi), rows: rows.reverse(), extra: mi === model.now ? ['Month not over yet'] : []});
            }
            function pointAt(ev) {
                var box2 = svg.getBoundingClientRect();
                var x = (ev.clientX - box2.left) * (W / box2.width);
                at = clamp(Math.floor((x - L) / band), 0, n - 1);
                describe(at, ev.clientX, ev.clientY);
            }
            svg.addEventListener('pointermove', pointAt);
            svg.addEventListener('pointerdown', function (ev) { if (ev.pointerType === 'touch') { pointAt(ev); } });
            svg.addEventListener('pointerleave', function (ev) { if (ev.pointerType !== 'touch') { cross.style.display = 'none'; tip.hide(); } });
            svg.addEventListener('keydown', function (ev) {
                var mv = ev.key === 'ArrowRight' ? 1 : ev.key === 'ArrowLeft' ? -1 : 0;
                if (ev.key === 'Escape') { cross.style.display = 'none'; tip.hide(); return; }
                if (!mv) { return; }
                ev.preventDefault();
                at = clamp((at === null ? (mv > 0 ? -1 : n) : at) + mv, 0, n - 1);
                var bx = svg.getBoundingClientRect();
                describe(at, bx.left + X(a + at) * (bx.width / W), bx.top + PT);
            });
            svg.addEventListener('blur', function () { cross.style.display = 'none'; tip.hide(); });
        }
        redrawers.push(draw);
        draw();
    }

    function keyLegend(items) {
        var lg = h('div', 'ah-legend');
        items.forEach(function (d) {
            var span = h('span');
            var sw = h('i', 'ah-sw' + (d.line ? ' ah-sw-line' : ''));
            sw.style.setProperty('--ad-c', d.color);
            sw.style.background = d.color;
            span.appendChild(sw);
            span.appendChild(document.createTextNode(d.label));
            lg.appendChild(span);
        });
        return lg;
    }

    function miniCard(title, note, spec, legendItems, total) {
        var card = h('div', 'ah-card');
        card.appendChild(h('h3', null, title));
        if (total) { card.appendChild(h('p', 'ah-total', total)); }
        if (note) { card.appendChild(h('p', 'admin-note', note)); }
        if (legendItems) { card.appendChild(keyLegend(legendItems)); }
        var box = h('div', 'ah-plot');
        box.style.marginTop = '8px';
        card.appendChild(box);
        card._draw = function () { miniChart(box, spec); };
        return card;
    }

    var DRAW_LATER = [];
    function later(card) {
        DRAW_LATER.push(card);
        return card;
    }

    function sectionOf(title, intro) {
        var wrap = h('div');
        wrap.appendChild(h('h2', null, title));
        if (intro) { wrap.appendChild(h('p', 'admin-note', intro)); wrap.lastChild.style.marginBottom = '8px'; }
        return wrap;
    }

    function drawDeferred() {
        DRAW_LATER.splice(0).forEach(function (card) { card._draw(); });
    }

    function botsSection() {
        var wrap = sectionOf('Bots and the figures', 'Bars are the figures once bot traffic is taken out, drawn lighter where estimated. Each card says what its line is.');
        var grid = h('div', 'ah-minis');
        [['Pages', 'pages_real', 'pages_counted', 'Pages read', 'The line is the pages as counted, bots included.'],
         ['Builds', 'builds_real', 'builds_robots', 'Builds', 'The line is the number of bot copies that were filtered out.'],
         ['Accounts', 'accounts_real', 'accounts_raw', 'Accounts', 'The line is the accounts as counted, bots included.']].forEach(function (c) {
            var bar = {key: c[1], label: c[3] + ', bots removed', color: 'var(--ad-s1)'};
            var ln = {key: c[2], label: c[2] === 'builds_robots' ? 'Bot copies filtered' : 'As counted', color: 'var(--ad-s2)'};
            grid.appendChild(later(miniCard(c[0], c[4], {bars: [bar], lines: [ln], label: c[0] + ', per month'},
                [{label: bar.label, color: bar.color}, {label: ln.label, color: ln.color, line: true}])));
        });
        wrap.appendChild(grid);
        return wrap;
    }

    function versionsSection() {
        var wrap = sectionOf('Game versions and traffic channels', 'Versions are measured, bot copies removed. Channels are estimated, so look only at the general shape.');
        var grid = h('div', 'ah-minis');
        var versions = [['v_dofus3', 'Dofus 3', 'var(--ad-s1)'], ['v_dofus2', 'Dofus 2', 'var(--ad-s2)'], ['v_touch', 'Dofus Touch', 'var(--ad-s3)'],
                        ['v_retro', 'Dofus Retro', 'var(--ad-s4)'], ['v_beta', 'Dofus 3 Beta', 'var(--ad-s5)']];
        var channels = [['ch_organic', 'Search engines', 'var(--ad-s2)'], ['ch_direct', 'Direct', 'var(--ad-s1)'], ['ch_ai', 'AI assistants', 'var(--ad-s4)'],
                        ['ch_other', 'Other', 'var(--ad-s3)']];
        function conv(list) { return list.map(function (x) { return {key: x[0], label: x[1], color: x[2]}; }); }
        grid.appendChild(later(miniCard('Builds per game version', '', {bars: conv(versions), label: 'Builds per game version'}, conv(versions))));
        grid.appendChild(later(miniCard('Visits per channel', '', {bars: conv(channels), label: 'Visits per channel'}, conv(channels))));
        wrap.appendChild(grid);
        return wrap;
    }

    function communitySection() {
        var wrap = sectionOf('What players do on the site', 'Each card has its own scale. The big number is the total since the start.');
        var grid = h('div', 'ah-minis ah-minis-s');
        [['shared', 'Shared builds'], ['views_real', 'Build views, estimated'], ['votes', 'Votes'],
         ['comments', 'Comments'], ['tags', 'Tags'], ['workshop', 'Workshop'],
         ['inventory', 'Inventory'], ['imports', 'Imports'], ['exports', 'Exports'],
         ['support', 'Support clicks']].forEach(function (c) {
            if (!model.S[c[0]] || !model.S[c[0]].list.length) { return; }
            var t = model.total(c[0], model.first, model.now);
            var months = model.S[c[0]].list.filter(function (r) { return r.st !== 'G' && r.v > 0; }).length;
            var total = (t.estimated ? 'about ' : '') + fmt.compact(t.sum);
            if (months < 3) {
                var card = h('div', 'ah-card');
                card.appendChild(h('h3', null, c[1]));
                card.appendChild(h('p', 'ah-total', total));
                card.appendChild(h('p', 'ah-mini-note', 'Active in only ' + months + (months === 1 ? ' month' : ' months') + ', too few for a chart.'));
                grid.appendChild(card);
                return;
            }
            grid.appendChild(later(miniCard(c[1], '', {bars: [{key: c[0], label: c[1], color: 'var(--ad-s1)'}], label: c[1] + ', per month', height: 118, axis: false, ends: true},
                null, total)));
        });
        wrap.appendChild(grid);
        return wrap;
    }

    function workSection() {
        var wrap = sectionOf('The work behind');
        var grid = h('div', 'ah-minis');
        var commits = [{key: 'commits_owner', label: 'Site owner', color: 'var(--ad-s1)'}, {key: 'commits_original', label: 'Original creators', color: 'var(--ad-s2)'},
                       {key: 'commits_other', label: 'Contributors', color: 'var(--ad-s3)'}];
        var all = 0;
        commits.forEach(function (c) { all += model.total(c.key, model.first, model.now).sum; });
        grid.appendChild(later(miniCard('Commits per month', 'Measured, on the main branch. Total: ' + fmt.whole(all) + '.', {bars: commits, label: 'Commits per month'}, commits)));
        var upd = model.total('data_updates', model.first, model.now);
        grid.appendChild(later(miniCard('Item database updates', fmt.whole(upd.sum) + ' recorded. The log can stop before the updates do.',
            {bars: [{key: 'data_updates', label: 'Updates', color: 'var(--ad-s1)'}], label: 'Item database updates per month'})));
        wrap.appendChild(grid);
        return wrap;
    }

    function classesSection() {
        var wrap = sectionOf('Classes and levels');
        var grid = h('div', 'ah-minis');
        var rows = payload.classes || [], levels = payload.levels || [];
        var cardC = h('div', 'ah-card');
        cardC.appendChild(h('h3', null, 'Share of each class per year'));
        cardC.appendChild(h('p', 'admin-note', 'Bot copies are taken out. Sorted by the most recent year. Hover or focus a cell for the number of builds.'));
        var years = [], by = {}, max = 0;
        rows.forEach(function (r) {
            if (years.indexOf(r.year) < 0) { years.push(r.year); }
            by[r.class] = by[r.class] || {};
            by[r.class][r.year] = r;
            max = Math.max(max, Number(r.share) || 0);
        });
        years.sort();
        var last = years[years.length - 1];
        var names = Object.keys(by).sort(function (a, b) {
            return ((by[b][last] || {}).share || 0) - ((by[a][last] || {}).share || 0) || (a < b ? -1 : 1);
        });
        var wrapT = h('div', 'ah-scroll');
        var table = h('table', 'admin-table ah-heat');
        var head = table.insertRow();
        head.appendChild(h('th', null, 'Class'));
        years.forEach(function (y) { head.appendChild(h('th', null, y)); });
        names.forEach(function (name) {
            var tr = table.insertRow();
            tr.insertCell().textContent = name;
            years.forEach(function (y) {
                var r = by[name][y], td = tr.insertCell();
                td.className = 'ah-cell';
                if (!r) { td.textContent = '-'; td.dataset.sort = ''; return; }
                var share = Number(r.share) || 0;
                td.textContent = fmt.percent(share);
                td.dataset.sort = share;
                td.title = fmt.whole(r.builds) + ' builds';
                td.style.background = 'color-mix(in srgb, var(--ad-s1) ' + Math.round(clamp(share / (max || 1), 0, 1) * 55) + '%, transparent)';
            });
        });
        wrapT.appendChild(table);
        cardC.appendChild(wrapT);
        grid.appendChild(cardC);

        var cardL = h('div', 'ah-card');
        cardL.appendChild(h('h3', null, 'Build levels per year'));
        cardL.appendChild(h('p', 'admin-note', 'Share of the builds of each year, bot copies taken out.'));
        var wl = h('div', 'ah-scroll');
        var tl = h('table', 'admin-table');
        var hl = tl.insertRow();
        ['Year', 'Builds', 'Level 1 to 50', '51 to 100', '101 to 199', '200'].forEach(function (t) { hl.appendChild(h('th', null, t)); });
        levels.forEach(function (r) {
            var tr = tl.insertRow();
            tr.insertCell().textContent = r.year;
            [r.builds, r.low, r.mid, r.high, r.top].forEach(function (v, i) {
                var td = tr.insertCell();
                td.className = 'admin-num';
                td.textContent = i === 0 ? fmt.whole(v) : fmt.whole(v) + '%';
                td.dataset.sort = v;
            });
        });
        wl.appendChild(tl);
        cardL.appendChild(wl);
        grid.appendChild(cardL);
        wrap.appendChild(grid);
        return wrap;
    }

    function milestonesSection() {
        var card = h('div', 'ah-card');
        card.appendChild(h('h2', null, 'All milestones'));
        var f = h('div', 'ah-filters');
        var search = h('input', 'ah-search');
        search.type = 'search'; search.placeholder = 'Search a milestone'; search.setAttribute('aria-label', 'Search a milestone');
        f.appendChild(search);
        var lanes = [], laneNames = {};
        model.milestones.forEach(function (m) { if (lanes.indexOf(m.lane) < 0) { lanes.push(m.lane); laneNames[m.lane] = m.lane_name; } });
        var chipEls = [];
        [['', 'All']].concat(lanes.map(function (l) { return [l, laneNames[l]]; })).forEach(function (pair) {
            var b = chip(pair[1], pair[0] === ms.lane, function () { ms.lane = pair[0]; drawMilestones(); });
            b.dataset.lane = pair[0];
            chipEls.push(b);
            f.appendChild(b);
        });
        var label = h('label', 'ah-check');
        var cb = h('input'); cb.type = 'checkbox'; cb.checked = ms.major;
        label.appendChild(cb); label.appendChild(document.createTextNode('Major milestones only'));
        f.appendChild(label);
        card.appendChild(f);
        var count = h('p', 'admin-note');
        card.appendChild(count);
        var list = h('ul', 'ah-ms-list');
        card.appendChild(list);
        search.value = ms.query;
        parts.ms = {search: search, cb: cb, chips: chipEls, count: count, list: list};
        search.addEventListener('input', function () { ms.query = search.value.trim().toLowerCase(); drawMilestones(); });
        cb.addEventListener('change', function () { ms.major = cb.checked; drawMilestones(); });
        drawMilestones();
        return card;
    }

    function drawMilestones() {
        var p = parts.ms;
        p.chips.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.lane === ms.lane ? 'true' : 'false'); });
        p.list.textContent = '';
        var shown = 0;
        model.milestones.forEach(function (m) {
            if (ms.lane && m.lane !== ms.lane) { return; }
            if (ms.major && !m.major) { return; }
            if (ms.query && (m.title + ' ' + m.detail).toLowerCase().indexOf(ms.query) < 0) { return; }
            shown++;
            var li = h('li', 'ah-ms-item');
            li.id = 'ah-ms-' + m.id;
            li.tabIndex = -1;
            li.appendChild(h('div', 'ah-ms-date', m.shown));
            var title = h('div');
            title.appendChild(h('span', 'ah-ms-title', m.title));
            if (m.major) { title.appendChild(h('span', 'ah-ms-major-flag', 'Major')); }
            title.appendChild(h('span', 'ah-ms-lane', m.lane_name));
            li.appendChild(title);
            li.appendChild(h('p', 'ah-ms-detail', m.detail));
            p.list.appendChild(li);
        });
        p.count.textContent = shown + ' of ' + model.milestones.length + ' milestones shown.';
        if (!shown) { p.list.appendChild(h('li', 'admin-empty', 'No milestone matches.')); }
    }

    function scrollToMilestones(ids) {
        ms.lane = ''; ms.query = ''; ms.major = false;
        parts.ms.search.value = ''; parts.ms.cb.checked = false;
        drawMilestones();
        var items = ids.map(function (id) { return document.getElementById('ah-ms-' + id); }).filter(Boolean);
        if (!items.length) { return; }
        items[0].scrollIntoView({block: 'center', behavior: reduceMotion ? 'auto' : 'smooth'});
        items[0].focus({preventScroll: true});
        items.forEach(function (li) { li.classList.add('is-hot'); });
        setTimeout(function () { items.forEach(function (li) { li.classList.remove('is-hot'); }); }, 2600);
    }

    function methodsSection() {
        var card = h('div', 'ah-card');
        var det = h('details', 'ah-details');
        det.appendChild(h('summary', null, 'How each figure is obtained'));
        det.appendChild(h('p', 'admin-note', 'Measured means read from the database or the logs. Corrected means measured, then cleaned of bot traffic. Estimated means computed from another figure, always with a range. Data as of ' + payload.as_of + ': later months are counted live. The figures before the measured months are estimates.'));
        var lg = h('div', 'ah-legend');
        [['M', ''], ['C', ''], ['E', 'ah-sw-e'], ['G', '']].forEach(function (pair) {
            var span = h('span');
            var sw = h('i', 'ah-sw ' + pair[1]);
            sw.style.setProperty('--ad-c', 'var(--ad-s1)');
            if (pair[0] === 'G') { sw.style.background = 'transparent'; sw.style.border = '1px solid currentColor'; }
            span.appendChild(sw);
            span.appendChild(document.createTextNode(WORD[pair[0]]));
            lg.appendChild(span);
        });
        det.appendChild(lg);
        var holder = h('div', 'ah-scroll');
        var table = h('table', 'admin-table');
        var head = table.insertRow();
        ['Figure', 'Period', 'Status', 'Confidence', 'Method'].forEach(function (t) { head.appendChild(h('th', null, t)); });
        (payload.methods || []).forEach(function (m) {
            var tr = table.insertRow();
            [m.metric, m.period, m.status, m.confidence, m.method].forEach(function (v) { tr.insertCell().textContent = v; });
        });
        holder.appendChild(table);
        det.appendChild(holder);
        card.appendChild(det);
        return card;
    }

    var origBuild = build;
    build = function (container) {
        DRAW_LATER = [];
        origBuild(container);
        drawDeferred();
    };

    T.onPanel(function (panel, info) {
        if (panel.dataset.panel === 'history') { init(panel, info || {}); }
    });
}());
