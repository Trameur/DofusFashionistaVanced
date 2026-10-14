var SETUP_PREVIEW = {
    debounceMs: 250,
    highlightMs: 5000,
    namesShown: 3,
    memoLimit: 64,
    minLevel: 1,
    maxLevel: 200
};

function setupPreviewQuery(fields) {
    var level = String(fields.level === undefined || fields.level === null ? '' : fields.level);
    if (!fields.className || !/^[0-9]{1,3}$/.test(level)
            || Number(level) < SETUP_PREVIEW.minLevel || Number(level) > SETUP_PREVIEW.maxLevel) {
        return null;
    }
    var pairs = [['class', fields.className], ['level', level]];
    var boxes = (fields.boxes || []).slice().sort();
    for (var i = 0; i < boxes.length; i++) {
        pairs.push(['check_' + boxes[i], 'on']);
    }
    if (fields.priority) {
        pairs.push(['priority', fields.priority]);
    }
    if (fields.playMode) {
        pairs.push(['play_mode', fields.playMode]);
    }
    if (fields.temporix === true || fields.temporix === false) {
        pairs.push(['temporix', fields.temporix ? 'on' : 'off']);
    }
    var parts = [];
    for (var j = 0; j < pairs.length; j++) {
        parts.push(encodeURIComponent(pairs[j][0]) + '=' + encodeURIComponent(pairs[j][1]));
    }
    return parts.join('&');
}

function setupPreviewChanges(before, after) {
    var changes = {};
    for (var key in after) {
        if (!Object.prototype.hasOwnProperty.call(after, key) || !before
                || !Object.prototype.hasOwnProperty.call(before, key)) {
            continue;
        }
        var was = before[key];
        var now = after[key];
        var weight = now.weight !== undefined && now.weight !== was.weight;
        var minimum = now.min !== undefined && now.min !== was.min;
        if (weight || minimum) {
            changes[key] = {weight: weight, min: minimum, weightWas: was.weight, minWas: was.min};
        }
    }
    return changes;
}

function setupPreviewSummary(names, total) {
    if (total === 0) {
        return gettext('Your last choice left the weights and minimums unchanged.');
    }
    var shown = names.slice(0, SETUP_PREVIEW.namesShown).join(', ');
    var more = total - SETUP_PREVIEW.namesShown;
    if (more > 0) {
        shown += ' ' + interpolate(ngettext('and %s more', 'and %s more', more), [more]);
    }
    return interpolate(ngettext(
        'Your last choice changed %(count)s characteristic: %(names)s.',
        'Your last choice changed %(count)s characteristics: %(names)s.', total),
        {count: total, names: shown}, true);
}

function setupPreviewBadge(count) {
    return interpolate(ngettext('%s changed', '%s changed', count), [count]);
}

function setupPreviewTitle(change) {
    var lines = [];
    if (change.weight) {
        lines.push(interpolate(gettext('Weight was %s'), [change.weightWas]));
    }
    if (change.min) {
        lines.push(change.minWas === '' ? gettext('There was no minimum')
                                         : interpolate(gettext('Minimum was %s'), [change.minWas]));
    }
    return lines.join('\n');
}

function setupPreviewGuard(priority, percent, kinds) {
    var kind = kinds && Object.prototype.hasOwnProperty.call(kinds, priority) ? kinds[priority] : null;
    var lost = percent === undefined || percent === null || percent === '' ? NaN : Number(percent);
    if (!kind || !isFinite(lost) || lost < 0 || lost > 100) {
        return null;
    }
    var values = {share: (100 - lost) + '%'};
    if (kind === 'effective_hp') {
        return interpolate(gettext('Safeguard: effective HP, AP, MP, Range and the other stats the priority does not aim for keep at least %(share)s of their value in the balanced build. The exact values are computed at launch.'), values, true);
    }
    if (kind === 'turn') {
        return interpolate(gettext('Safeguard: damage stats, AP, MP, Range and the other stats the priority does not aim for keep at least %(share)s of their value in the balanced build. The exact values are computed at launch.'), values, true);
    }
    return null;
}

function setupSameValue(a, b) {
    var left = String(a === undefined || a === null ? '' : a).replace(/^\s+|\s+$/g, '');
    var right = String(b === undefined || b === null ? '' : b).replace(/^\s+|\s+$/g, '');
    if (left === right) {
        return true;
    }
    if (left === '' || right === '') {
        return false;
    }
    return isFinite(Number(left)) && isFinite(Number(right)) && Number(left) === Number(right);
}

function setupBlank(value) {
    return String(value === undefined || value === null ? '' : value).replace(/^\s+|\s+$/g, '') === '';
}

function setupWhole(value) {
    return setupBlank(value) || !isFinite(Number(value)) ? null : Math.round(Number(value));
}

function setupSameState(first, second) {
    if (!first || !second) {
        return false;
    }
    return JSON.stringify([first.weights, first.minimums, first.caps])
        === JSON.stringify([second.weights, second.minimums, second.caps]);
}

function setupEdits(baseline, current) {
    var edits = {};
    for (var key in current) {
        if (!Object.prototype.hasOwnProperty.call(current, key) || !baseline
                || !Object.prototype.hasOwnProperty.call(baseline, key)) {
            continue;
        }
        var was = baseline[key];
        var now = current[key];
        var wholeWeight = setupWhole(now.weight);
        var wholeMin = setupWhole(now.min);
        var cleared = now.min !== undefined && setupBlank(now.min) && !setupBlank(was.min);
        var weight = wholeWeight !== null && !setupSameValue(was.weight, wholeWeight);
        var minimum = cleared || (wholeMin !== null && !setupSameValue(was.min, wholeMin));
        if (weight || minimum) {
            edits[key] = {weight: weight, min: minimum, aggregate: !!now.aggregate,
                          now: {weight: weight ? wholeWeight : now.weight,
                                min: minimum && !cleared ? wholeMin : now.min,
                                aggregate: now.aggregate}};
        }
    }
    return edits;
}

function setupTouchedFields(edits) {
    var fields = [];
    var keys = Object.keys(edits).sort();
    for (var i = 0; i < keys.length; i++) {
        var edit = edits[keys[i]];
        if (edit.aggregate) {
            continue;
        }
        if (edit.weight) {
            fields.push(['weight_' + keys[i], String(edit.now.weight)]);
        }
        if (edit.min) {
            fields.push(['min_' + keys[i], String(edit.now.min)]);
        }
    }
    return fields;
}

function setupPreviewEdits(count) {
    return interpolate(ngettext('You edited %s value.', 'You edited %s values.', count), [count]);
}

function setupEditGate(env) {
    var held = null;

    function arrive(state) {
        if (!env.hasBaseline() || env.edited() === 0) {
            held = null;
            env.ask(false);
            env.apply(state, false);
        } else if (env.same(state)) {
            held = null;
            env.ask(false);
        } else {
            held = state;
            env.ask(true);
        }
    }

    function settle(keep) {
        var state = held;
        held = null;
        env.ask(false);
        if (state) {
            env.apply(state, keep);
        }
    }

    function drop() {
        held = null;
        env.ask(false);
    }

    function cleaned() {
        if (held !== null && env.edited() === 0) {
            settle(false);
        }
    }

    return {
        arrive: arrive,
        keep: function() { settle(true); },
        recompute: function() { settle(false); },
        drop: drop,
        cleaned: cleaned,
        holding: function() { return held !== null; }
    };
}

function setupWriteLive(node, text) {
    if (node.text() === text) {
        return false;
    }
    node.text(text);
    return true;
}

function setupRestoredValues(edit, cap) {
    var values = {};
    if (!edit || edit.aggregate) {
        return values;
    }
    if (edit.weight) {
        values.weight = edit.now.weight;
    }
    if (edit.min) {
        var value = edit.now.min;
        if (cap !== undefined && value !== '' && Number(value) > Number(cap)) {
            value = cap;
        }
        values.min = value;
    }
    return values;
}

function setupOutOfView(rect, panelRect, viewportHeight) {
    var top = Math.max(0, panelRect.top);
    var bottom = Math.min(viewportHeight, panelRect.bottom);
    return rect.bottom <= top || rect.top >= bottom;
}

function setupScrollOptions(reduceMotion) {
    return {block: 'nearest', behavior: reduceMotion ? 'auto' : 'smooth'};
}

function setupPanelActions(gate, env) {
    function settled(action) {
        return function() {
            action();
            env.focusSummary();
        };
    }

    return {
        failed: function() {
            gate.drop();
            env.showNotice();
        },
        clear: function() {
            env.forgetPending();
            gate.recompute();
            if (env.hasBaseline()) {
                env.restorePreset();
            }
        },
        keep: settled(gate.keep),
        recompute: settled(gate.recompute),
        reset: settled(function() {
            if (gate.holding()) {
                gate.recompute();
            } else {
                env.restorePreset();
            }
        }),
        submit: function(event) {
            env.clearTouched();
            if (event.isDefaultPrevented()) {
                return;
            }
            if (gate.holding() && env.edited() > 0) {
                event.preventDefault();
                env.showQuestion();
                return;
            }
            env.attach(setupTouchedFields(env.edits()));
        }
    };
}

function setupPreviewLoop(env) {
    var memo = {};
    var memoOrder = [];
    var sequence = 0;
    var controller = null;
    var shownQuery = null;
    var requestedQuery = null;

    function remember(query, state) {
        if (!Object.prototype.hasOwnProperty.call(memo, query)) {
            memoOrder.push(query);
            if (memoOrder.length > SETUP_PREVIEW.memoLimit) {
                delete memo[memoOrder.shift()];
            }
        }
        memo[query] = state;
    }

    function cancel() {
        sequence += 1;
        requestedQuery = null;
        if (controller) {
            controller.abort();
            controller = null;
        }
    }

    function show(state, query) {
        requestedQuery = null;
        shownQuery = query;
        env.show(state, query);
    }

    function request(query) {
        cancel();
        var mine = sequence;
        requestedQuery = query;
        controller = env.newController();
        env.load(query, controller ? controller.signal : undefined).then(function(state) {
            if (mine === sequence) {
                controller = null;
                remember(query, state);
                show(state, query);
            }
        }).catch(function(error) {
            if (mine !== sequence || (error && error.name === 'AbortError')) {
                return;
            }
            controller = null;
            requestedQuery = null;
            shownQuery = null;
            env.failed();
        });
    }

    function refresh() {
        var query = env.query();
        if (query === null) {
            return;
        }
        if (query === shownQuery) {
            cancel();
            env.settled();
        } else if (query === requestedQuery) {
            return;
        } else if (Object.prototype.hasOwnProperty.call(memo, query)) {
            cancel();
            show(memo[query], query);
        } else {
            request(query);
        }
    }

    return {refresh: refresh};
}

var SETUP_RECIPES = {
    focusLimit: 2,
    savedLimit: 5,
    nameLimit: 40,
    fragmentLimit: 2000,
    format: '1',
    storagePrefix: 'fashionista.setups.'
};

function setupRecipeFromData(data) {
    var focus = [];
    var words = String(data.focus || '').split(/\s+/);
    for (var i = 0; i < words.length; i++) {
        if (words[i] !== '') {
            focus.push(words[i]);
        }
    }
    var guard = setupBlank(data.guard) ? null : Number(data.guard);
    return {
        key: String(data.key || ''),
        focus: focus,
        priority: String(data.priority || ''),
        mode: String(data.mode || ''),
        guard: guard !== null && isFinite(guard) ? guard : null,
        mule: data.mule === 'true'
    };
}

function setupRecipeTarget(recipe, page) {
    var focus = [];
    for (var i = 0; i < recipe.focus.length; i++) {
        var aspect = recipe.focus[i];
        if (page.focus.indexOf(aspect) !== -1 && focus.indexOf(aspect) === -1
                && focus.length < SETUP_RECIPES.focusLimit) {
            focus.push(aspect);
        }
    }
    var guarded = recipe.guard !== null && page.guards.indexOf(recipe.guard) !== -1;
    return {
        focus: focus,
        priority: page.priorities.indexOf(recipe.priority) !== -1 ? recipe.priority : page.priorities[0],
        mode: page.modes.indexOf(recipe.mode) !== -1 ? recipe.mode : page.modes[0],
        guard: guarded ? recipe.guard : page.guardDefault
    };
}

function setupRecipeMatches(target, current) {
    return JSON.stringify([target.focus.slice().sort(), target.priority, target.mode, String(target.guard)])
        === JSON.stringify([current.focus.slice().sort(), current.priority, current.mode, String(current.guard)]);
}

function setupRecipeNote(recipe, hasElement) {
    if (!recipe) {
        return '';
    }
    if (recipe.mule) {
        return 'mule';
    }
    return hasElement ? '' : 'element';
}

function setupRecipeNoteText(kind) {
    if (kind === 'mule') {
        return gettext('Mules need no element: leave the Elements column unchecked, or pick one if the character also fights.');
    }
    if (kind === 'element') {
        return gettext('Presets never choose an element: pick yours in the Elements column.');
    }
    return '';
}

function setupShareLevel(value) {
    if (!/^[0-9]{1,3}$/.test(value)) {
        return null;
    }
    var level = Number(value);
    return level >= SETUP_PREVIEW.minLevel && level <= SETUP_PREVIEW.maxLevel ? String(level) : null;
}

function setupShareItem(value) {
    return typeof value === 'string' && /^[0-9]{1,9}$/.test(value) ? value : null;
}

function setupShareFits(fragment) {
    return String(fragment).length <= SETUP_RECIPES.fragmentLimit;
}

function setupShareEncode(state) {
    var pairs = [['setup', SETUP_RECIPES.format], ['game', state.game]];
    if (state.className) {
        pairs.push(['class', state.className]);
    }
    var level = setupShareLevel(String(state.level === undefined || state.level === null ? '' : state.level));
    if (level !== null) {
        pairs.push(['level', level]);
    }
    pairs.push(['boxes', (state.boxes || []).slice().sort().join('.')]);
    if (state.priority) {
        pairs.push(['priority', state.priority]);
    }
    if (state.mode) {
        pairs.push(['mode', state.mode]);
    }
    if (state.guard !== undefined && state.guard !== null && state.guard !== '') {
        pairs.push(['guard', String(state.guard)]);
    }
    if (state.temporix === true || state.temporix === false) {
        pairs.push(['temporix', state.temporix ? 'on' : 'off']);
    }
    if (setupShareItem(state.item) !== null) {
        pairs.push(['item', state.item]);
    }
    var touched = state.touched || [];
    for (var i = 0; i < touched.length; i++) {
        pairs.push([touched[i][0], touched[i][1]]);
    }
    var parts = [];
    for (var j = 0; j < pairs.length; j++) {
        parts.push(encodeURIComponent(pairs[j][0]) + '=' + encodeURIComponent(pairs[j][1]));
    }
    return parts.join('&');
}

function setupShareBoxes(text, allowed) {
    if (text === '') {
        return [];
    }
    var boxes = text.split('.');
    var seen = {};
    var focus = 0;
    for (var i = 0; i < boxes.length; i++) {
        if (allowed.boxes.indexOf(boxes[i]) === -1 || seen[boxes[i]]) {
            return null;
        }
        seen[boxes[i]] = true;
        if (allowed.focus.indexOf(boxes[i]) !== -1) {
            focus += 1;
        }
    }
    if (focus > SETUP_RECIPES.focusLimit || (seen.crit && seen.noncrit)) {
        return null;
    }
    return boxes;
}

function setupShareParse(fragment, allowed) {
    var text = String(fragment === undefined || fragment === null ? '' : fragment);
    if (text.charAt(0) === '#') {
        text = text.substring(1);
    }
    if (text === '' || text.length > SETUP_RECIPES.fragmentLimit) {
        return null;
    }
    var fields = Object.create(null);
    var pieces = text.split('&');
    for (var i = 0; i < pieces.length; i++) {
        var at = pieces[i].indexOf('=');
        var field;
        var value;
        if (at < 1) {
            return null;
        }
        try {
            field = decodeURIComponent(pieces[i].substring(0, at));
            value = decodeURIComponent(pieces[i].substring(at + 1));
        } catch (error) {
            return null;
        }
        if (Object.prototype.hasOwnProperty.call(fields, field)) {
            return null;
        }
        fields[field] = value;
    }
    if (fields.setup !== SETUP_RECIPES.format || fields.game !== allowed.game) {
        return null;
    }
    var state = {className: null, level: null, boxes: null, priority: null, mode: null,
                 guard: null, temporix: null, item: null, touched: []};
    var names = Object.keys(fields).sort();
    for (var j = 0; j < names.length; j++) {
        var name = names[j];
        var given = fields[name];
        if (name === 'setup' || name === 'game') {
            continue;
        } else if (name === 'class') {
            if (allowed.classes.indexOf(given) === -1) {
                return null;
            }
            state.className = given;
        } else if (name === 'level') {
            state.level = setupShareLevel(given);
            if (state.level === null) {
                return null;
            }
        } else if (name === 'boxes') {
            state.boxes = setupShareBoxes(given, allowed);
            if (state.boxes === null) {
                return null;
            }
        } else if (name === 'priority') {
            if (allowed.priorities.indexOf(given) === -1) {
                return null;
            }
            state.priority = given;
        } else if (name === 'mode') {
            if (allowed.modes.indexOf(given) === -1) {
                return null;
            }
            state.mode = given;
        } else if (name === 'guard') {
            if (!/^[0-9]{1,3}$/.test(given) || allowed.guards.indexOf(Number(given)) === -1) {
                return null;
            }
            state.guard = Number(given);
        } else if (name === 'temporix') {
            if (given !== 'on' && given !== 'off') {
                return null;
            }
            state.temporix = given === 'on';
        } else if (name === 'item') {
            state.item = setupShareItem(given);
            if (state.item === null) {
                return null;
            }
        } else if (/^weight_[A-Za-z0-9_]{1,40}$/.test(name)) {
            if (!/^-?[0-9]{1,6}$/.test(given)) {
                return null;
            }
            state.touched.push([name, given]);
        } else if (/^min_[A-Za-z0-9_]{1,40}$/.test(name)) {
            if (given !== '' && !/^-?[0-9]{1,6}$/.test(given)) {
                return null;
            }
            state.touched.push([name, given]);
        } else {
            return null;
        }
    }
    return state;
}

function setupSharedEdits(touched) {
    var edits = {};
    for (var i = 0; i < touched.length; i++) {
        var weight = touched[i][0].indexOf('weight_') === 0;
        var key = touched[i][0].substring(weight ? 'weight_'.length : 'min_'.length);
        var edit = edits[key] || {weight: false, min: false, aggregate: false, now: {}};
        if (weight) {
            edit.weight = true;
            edit.now.weight = Number(touched[i][1]);
        } else {
            edit.min = true;
            edit.now.min = touched[i][1] === '' ? '' : Number(touched[i][1]);
        }
        edits[key] = edit;
    }
    return edits;
}

function setupSavedRead(storage, game) {
    var kept = [];
    try {
        var list = JSON.parse(storage.getItem(SETUP_RECIPES.storagePrefix + game));
        if (!Array.isArray(list)) {
            return kept;
        }
        for (var i = 0; i < list.length && kept.length < SETUP_RECIPES.savedLimit; i++) {
            var item = list[i];
            var valid = !!item && typeof item.name === 'string' && typeof item.fragment === 'string'
                && item.name !== '' && item.name.length <= SETUP_RECIPES.nameLimit
                && item.fragment.length <= SETUP_RECIPES.fragmentLimit;
            var twice = false;
            for (var j = 0; valid && j < kept.length; j++) {
                twice = twice || kept[j].name === item.name;
            }
            if (valid && !twice) {
                kept.push({name: item.name, fragment: item.fragment});
            }
        }
    } catch (error) {
        return [];
    }
    return kept;
}

function setupSavedWrite(storage, game, list) {
    try {
        storage.setItem(SETUP_RECIPES.storagePrefix + game, JSON.stringify(list));
        return true;
    } catch (error) {
        return false;
    }
}

function setupSavedName(text) {
    return String(text === undefined || text === null ? '' : text).replace(/\s+/g, ' ')
        .replace(/^ /, '').substring(0, SETUP_RECIPES.nameLimit).replace(/ $/, '');
}

function setupSavedPut(list, text, fragment) {
    var name = setupSavedName(text);
    if (name === '') {
        return {result: 'blank', list: list};
    }
    if (!setupShareFits(fragment)) {
        return {result: 'long', list: list};
    }
    var next = list.slice();
    for (var i = 0; i < next.length; i++) {
        if (next[i].name === name) {
            next[i] = {name: name, fragment: fragment};
            return {result: 'saved', list: next};
        }
    }
    if (next.length >= SETUP_RECIPES.savedLimit) {
        return {result: 'full', list: list};
    }
    next.push({name: name, fragment: fragment});
    return {result: 'saved', list: next};
}

function setupSavedFind(list, name) {
    for (var i = 0; i < list.length; i++) {
        if (list[i].name === name) {
            return list[i];
        }
    }
    return null;
}

function setupSavedDrop(list, name) {
    var next = [];
    for (var i = 0; i < list.length; i++) {
        if (list[i].name !== name) {
            next.push(list[i]);
        }
    }
    return next;
}

function setupOpenStorage(host) {
    try {
        var storage = host.localStorage;
        storage.setItem('fashionista.probe', '1');
        storage.removeItem('fashionista.probe');
        return storage;
    } catch (error) {
        return null;
    }
}

function setupFillControls(fill, env) {
    if (fill.boxes) {
        for (var i = 0; i < fill.scope.length; i++) {
            if (fill.boxes.indexOf(fill.scope[i]) === -1) {
                env.tick(fill.scope[i], false);
            }
        }
        for (var j = 0; j < fill.boxes.length; j++) {
            if (fill.scope.indexOf(fill.boxes[j]) !== -1) {
                env.tick(fill.boxes[j], true);
            }
        }
    }
    if (fill.priority !== null && fill.priority !== undefined) {
        env.priority(fill.priority);
    }
    if (fill.mode !== null && fill.mode !== undefined) {
        env.mode(fill.mode);
    }
    if (fill.guard !== null && fill.guard !== undefined) {
        env.guard(fill.guard);
    }
}

function setupRestore(state, now, page, env) {
    env.clearPanel();
    if (state.level !== null && state.level !== undefined) {
        env.setLevel(state.level);
    }
    if (state.className !== null && state.className !== undefined) {
        env.setClass(state.className);
    }
    if (state.temporix === true || state.temporix === false) {
        env.setTemporix(state.temporix);
    }
    if (setupShareItem(state.item) !== null) {
        env.setItem(state.item);
    }
    setupFillControls({scope: page.boxes, boxes: state.boxes, priority: state.priority,
                       mode: state.mode, guard: state.guard}, env);
    env.restorePanel(setupSharedEdits(state.touched || []), now);
    env.finished();
}

function setupMoreOwn(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key);
}

function setupMoreDefaults(table, level) {
    var values = {};
    var key;
    for (key in table.base) {
        if (setupMoreOwn(table.base, key)) {
            values[key] = table.base[key];
        }
    }
    for (var i = 0; i < table.ladder.length && table.ladder[i][0] <= level; i++) {
        var row = table.ladder[i][1];
        for (key in row) {
            if (setupMoreOwn(row, key)) {
                values[key] = row[key];
            }
        }
    }
    for (key in table.levels) {
        if (setupMoreOwn(table.levels, key) && table.levels[key] > level) {
            values[key] = null;
        }
    }
    return values;
}

function setupMoreSame(wanted, found) {
    var blank = wanted === null || wanted === undefined;
    if (blank !== (found === null || found === undefined)) {
        return false;
    }
    return blank || setupSameValue(wanted, found);
}

function setupMoreChanged(groups, defaults, current) {
    var changed = [];
    for (var i = 0; i < groups.length; i++) {
        var fields = groups[i][1];
        for (var j = 0; j < fields.length; j++) {
            if (!setupMoreSame(defaults[fields[j]], current[fields[j]])) {
                changed.push(groups[i][0]);
                break;
            }
        }
    }
    return changed;
}

function setupMoreFollow(table, before, after, current, kept, touched) {
    var was = setupMoreDefaults(table, before);
    var next = setupMoreDefaults(table, after);
    var values = {};
    var stored = {};
    var set = touched || {};
    var key;
    for (key in kept || {}) {
        if (setupMoreOwn(kept, key)) {
            stored[key] = kept[key];
        }
    }
    for (var i = 0; i < table.groups.length; i++) {
        for (var j = 0; j < table.groups[i][1].length; j++) {
            key = table.groups[i][1][j];
            var needed = setupMoreOwn(table.levels, key) ? table.levels[key] : 0;
            if (needed > after) {
                if (needed <= before) {
                    stored[key] = current[key];
                }
                values[key] = null;
            } else if (needed > before) {
                values[key] = setupMoreOwn(stored, key) ? stored[key] : next[key];
                delete stored[key];
            } else if (!setupMoreOwn(set, key) && setupMoreSame(was[key], current[key])) {
                values[key] = next[key];
            }
        }
    }
    return {values: values, kept: stored};
}

$(document).ready(function() {
    var $panel = $('#setup-preview');
    var $form = $('#main_form');
    if (!$panel.length || !$form.length || !window.fetch || typeof wmInit !== 'function') {
        return;
    }
    var url = $panel.attr('data-preview-url');
    var $details = $('#setup-preview-details');
    var $body = $('#setup-preview-body');
    var $block = $('#setup-preview-block');
    var $changes = $('#setup-preview-changes');
    var $notice = $('#setup-preview-notice');
    var $empty = $('#setup-preview-empty');
    var $panelBadge = $('#setup-preview-badge');
    var $guard = $('#setup-preview-guard');
    var $reset = $('#setup-preview-reset');
    var $edited = $('#setup-preview-edited');
    var $keep = $('#setup-preview-keep');
    var timer = null;
    var fadeTimer = null;
    var hasBaseline = false;
    var baseline = null;
    var baselineState = null;
    var badgeBeforeAsking = null;
    var pendingEdits = null;
    var api = wmInit('', {form: '#main_form', mode: 'preview'});
    var guardKinds = {};
    try {
        guardKinds = JSON.parse($('#setup-guard-kinds').text()) || {};
    } catch (error) {
        guardKinds = {};
    }

    $block.find('.wm-section > summary .wm-section-label').after(
        '<span class="setup-badge" hidden></span>');

    function currentFields() {
        var boxes = [];
        $form.find('input[type="checkbox"][name^="check_"]:checked').each(function() {
            boxes.push(this.name.substring('check_'.length));
        });
        var $temporix = $('#temporix-cb');
        return {
            className: $('#select-char-class').val(),
            level: $.trim($('#input-char-level').val()),
            boxes: boxes,
            priority: $form.find('input[name="priority"]:checked').val(),
            playMode: $('#play-mode').val(),
            temporix: $temporix.length ? $temporix.prop('checked') : null
        };
    }

    function readRows() {
        var rows = {};
        $block.find('.wm-row').each(function() {
            var $row = $(this);
            rows[$row.attr('data-key')] = {
                weight: $row.find('.wm-weight input').val(),
                min: $row.find('.wm-min input').val()
            };
        });
        return rows;
    }

    function readFields() {
        var rows = {};
        $block.find('.wm-row').each(function() {
            var $row = $(this);
            if ($row.is('[data-sum]')) {
                return;
            }
            var $weight = $row.find('.wm-weight-input');
            var $min = $row.find('.wm-min-input');
            rows[$row.attr('data-key')] = {
                weight: $weight.length ? $weight.val() : undefined,
                min: $min.length ? $min.val() : undefined,
                aggregate: $row.hasClass('wm-aggregate')
            };
        });
        return rows;
    }

    function currentEdits() {
        return hasBaseline ? setupEdits(baseline, readFields()) : {};
    }

    function markEdits() {
        var edits = currentEdits();
        $block.find('.wm-row').each(function() {
            var edit = edits[$(this).attr('data-key')];
            $(this).find('.wm-weight-input').toggleClass('setup-edited', !!(edit && edit.weight));
            $(this).find('.wm-min-input').toggleClass('setup-edited', !!(edit && edit.min));
        });
        var count = setupTouchedFields(edits).length;
        setupWriteLive($edited, count ? setupPreviewEdits(count) : '');
        $reset.prop('hidden', !count);
    }

    function restoreEdits(edits) {
        $block.find('.wm-row').each(function() {
            var $min = $(this).find('.wm-min-input');
            var values = setupRestoredValues(edits[$(this).attr('data-key')], $min.attr('max'));
            if (values.weight !== undefined) {
                $(this).find('.wm-weight-input').val(values.weight);
            }
            if (values.min !== undefined) {
                $min.val(values.min);
            }
        });
        api.refresh();
    }

    function rowName($row) {
        var $name = $row.find('.wm-name').first().clone();
        $name.find('.small-explain, img').remove();
        return $.trim($name.text().replace(/\s+/g, ' '));
    }

    function fadeHighlights() {
        $block.find('.setup-changed').removeClass('setup-changed');
    }

    function showChanges(before) {
        window.clearTimeout(fadeTimer);
        fadeHighlights();
        $block.find('.wm-row').removeAttr('title').find('input').removeAttr('title');
        var changes = setupPreviewChanges(before, readRows());
        var names = [];
        var perSection = {};
        $block.find('.wm-row').each(function() {
            var $row = $(this);
            var change = changes[$row.attr('data-key')];
            if (!change) {
                return;
            }
            $row.addClass('setup-changed');
            if ($row.hasClass('wm-aggregate') || $row.is('[data-sum]')) {
                return;
            }
            names.push(rowName($row));
            var section = $row.closest('.wm-section').attr('data-section');
            perSection[section] = (perSection[section] || 0) + 1;
            $row.attr('title', setupPreviewTitle(change));
            if (change.weight) {
                $row.find('.wm-weight input').attr('title', setupPreviewTitle({weight: true, weightWas: change.weightWas}));
            }
            if (change.min) {
                $row.find('.wm-min input').attr('title', setupPreviewTitle({min: true, minWas: change.minWas}));
            }
        });
        $block.find('.wm-section').each(function() {
            var count = perSection[$(this).attr('data-section')] || 0;
            var $badge = $(this).children('summary').find('.setup-badge');
            $badge.text(count ? setupPreviewBadge(count) : '').prop('hidden', !count);
        });
        setupWriteLive($changes, setupPreviewSummary(names, names.length));
        $panelBadge.text(names.length ? setupPreviewBadge(names.length) : '')
            .prop('hidden', !names.length);
        fadeTimer = window.setTimeout(fadeHighlights, SETUP_PREVIEW.highlightMs);
    }

    function showGuard() {
        var text = hasBaseline ? setupPreviewGuard(
            $form.find('input[name="priority"]:checked').val(), $('#guard-percent').val(),
            guardKinds) : null;
        setupWriteLive($guard, text || '');
    }

    function syncTemporixNote() {
        var $temporix = $('#temporix-cb');
        $block.find('.wm-note').prop('hidden', !($temporix.length && $temporix.prop('checked')));
    }

    function applyPreset(state, keep) {
        var before = hasBaseline ? readRows() : null;
        var kept = keep ? currentEdits() : {};
        api.applyState(state);
        syncTemporixNote();
        baselineState = state;
        baseline = readFields();
        restoreEdits(pendingEdits || kept);
        pendingEdits = null;
        if (before) {
            showChanges(before);
        } else {
            hasBaseline = true;
            $block.prop('hidden', false);
            $empty.prop('hidden', true);
            $body.attr('aria-busy', 'false');
        }
        markEdits();
        $notice.prop('hidden', true);
        showGuard();
    }

    function revealQuestionOnce() {
        if (!$details.prop('open')) {
            return;
        }
        if (setupOutOfView($keep.get(0).getBoundingClientRect(),
                           $panel.get(0).getBoundingClientRect(), window.innerHeight)) {
            var still = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
            $keep.get(0).scrollIntoView(setupScrollOptions(still));
        }
    }

    function ask(on) {
        var opening = on && $keep.prop('hidden');
        if (opening) {
            badgeBeforeAsking = {text: $panelBadge.text(), hidden: $panelBadge.prop('hidden')};
            $panelBadge.text($.trim($('#setup-preview-keep-question').text()))
                .prop('hidden', false).addClass('setup-asking');
        } else if (!on && !$keep.prop('hidden') && badgeBeforeAsking) {
            $panelBadge.text(badgeBeforeAsking.text).prop('hidden', badgeBeforeAsking.hidden)
                .removeClass('setup-asking');
            badgeBeforeAsking = null;
        }
        $keep.prop('hidden', !on);
        if (opening) {
            revealQuestionOnce();
        }
    }

    var gate = setupEditGate({
        hasBaseline: function() { return hasBaseline; },
        edited: function() { return setupTouchedFields(currentEdits()).length; },
        same: function(state) { return setupSameState(state, baselineState); },
        apply: applyPreset,
        ask: ask
    });

    function show(state) {
        gate.arrive(state);
        $notice.prop('hidden', true);
    }

    function applyPending() {
        if (pendingEdits && hasBaseline) {
            restoreEdits(pendingEdits);
            pendingEdits = null;
            markEdits();
        }
    }

    var actions = setupPanelActions(gate, {
        focusSummary: function() { $details.children('summary').first().trigger('focus'); },
        forgetPending: function() { pendingEdits = null; },
        hasBaseline: function() { return hasBaseline; },
        restorePreset: function() {
            api.applyState(baselineState);
            syncTemporixNote();
            markEdits();
        },
        showNotice: function() {
            $notice.prop('hidden', false);
            $body.attr('aria-busy', 'false');
        },
        clearTouched: function() { $form.find('input.setup-touched').remove(); },
        edits: currentEdits,
        edited: function() { return setupTouchedFields(currentEdits()).length; },
        attach: function(fields) {
            $.each(fields, function(i, field) {
                $('<input type="hidden" class="setup-touched">').attr({name: field[0], value: field[1]})
                    .appendTo($form);
            });
        },
        showQuestion: function() {
            $details.prop('open', true);
            $keep.get(0).scrollIntoView({block: 'nearest'});
            $('#setup-preview-keep-yes').trigger('focus');
        }
    });

    var loop = setupPreviewLoop({
        query: function() { return setupPreviewQuery(currentFields()); },
        newController: function() { return window.AbortController ? new AbortController() : null; },
        load: function(query, signal) {
            var options = {credentials: 'same-origin', headers: {'Accept': 'application/json'}};
            if (signal) {
                options.signal = signal;
            }
            return window.fetch(url + '?' + query, options).then(function(response) {
                if (!response.ok) {
                    throw new Error('status ' + response.status);
                }
                return response.json();
            });
        },
        show: show,
        settled: function() {
            $notice.prop('hidden', true);
            applyPending();
        },
        failed: actions.failed
    });

    function schedule() {
        window.clearTimeout(timer);
        timer = window.setTimeout(loop.refresh, SETUP_PREVIEW.debounceMs);
    }

    if (window.matchMedia && window.matchMedia('(max-width: 900px)').matches) {
        $details.prop('open', false);
    }
    $panel.prop('hidden', false);
    $form.on('change input', schedule);
    $form.on('change input', showGuard);
    $block.on('change input', '.wm-input', function() {
        markEdits();
    });
    $block.on('change', '.wm-input', function() {
        gate.cleaned();
    });
    $('#setup-preview-reset').on('click', actions.reset);
    $('#setup-preview-keep-yes').on('click', actions.keep);
    $('#setup-preview-keep-no').on('click', actions.recompute);
    $form.on('submit', actions.submit);
    window.SETUP_PANEL = {
        touched: function() { return setupTouchedFields(currentEdits()); },
        clear: actions.clear,
        restore: function(edits, now) {
            pendingEdits = Object.keys(edits).length ? edits : null;
            if (now) {
                window.clearTimeout(timer);
                loop.refresh();
            }
        }
    };
    $(window).on('load pageshow', function() {
        $form.find('input.setup-touched').remove();
        showGuard();
        schedule();
    });
    schedule();
});

$(document).ready(function() {
    var $section = $('#setup-recipes');
    var $form = $('#main_form');
    if (!$section.length || !$form.length || typeof aspectLayout === 'undefined'
            || typeof modeLayout === 'undefined') {
        return;
    }
    var $note = $('#setup-recipes-note');
    var $shareStatus = $('#setup-share-status');
    var $shareUrl = $('#setup-share-url');
    var $saved = $('#setup-saved');
    var $savedList = $('#setup-saved-list');
    var $savedStatus = $('#setup-saved-status');
    var $savedName = $('#setup-saved-name');
    var game = $section.attr('data-version') || '';
    var chips = [];
    var active = null;
    var storage = null;

    function aspectBox(aspect) {
        return $(document.getElementById('check_' + aspect));
    }

    function modeBox(mode) {
        return $(document.getElementById('mode_' + mode));
    }

    function describePage() {
        var focus = [];
        $.each(aspectLayout[2].concat(aspectLayout[3]), function(i, aspect) {
            if (aspect !== 'balanced') {
                focus.push(aspect);
            }
        });
        var boxes = [];
        $.each(aspectLayout[0].concat(focus), function(i, aspect) {
            if (aspectBox(aspect).length) {
                boxes.push(aspect);
            }
        });
        var classes = [];
        $('#select-char-class option').each(function() { classes.push(this.value); });
        var priorities = [];
        $form.find('input[name="priority"]').each(function() { priorities.push(this.value); });
        var modes = ['general'];
        $.each(modeLayout, function(i, mode) { modes.push(mode[0]); });
        var guards = [];
        $('#guard-percent option').each(function() { guards.push(Number(this.value)); });
        return {game: game, classes: classes, boxes: boxes, focus: focus, priorities: priorities,
                modes: modes, guards: guards, guardDefault: Number($section.attr('data-guard-default'))};
    }

    var page = describePage();

    function readControls() {
        var focus = [];
        $.each(page.focus, function(i, aspect) {
            if (aspectBox(aspect).prop('checked')) {
                focus.push(aspect);
            }
        });
        return {focus: focus, priority: $form.find('input[name="priority"]:checked').val(),
                mode: $('#play-mode').val(), guard: $('#guard-percent').val()};
    }

    function tick(aspect, on) {
        var $box = aspectBox(aspect);
        if ($box.length && $box.prop('checked') !== on) {
            $box.prop('checked', on).trigger('change');
        }
    }

    function setPriority(value) {
        var $radio = $form.find('input[name="priority"]').filter(function() { return this.value === value; });
        if ($radio.length && !$radio.prop('checked')) {
            $radio.prop('checked', true).trigger('change');
        }
    }

    function setMode(value) {
        if ($('#play-mode').val() === value) {
            return;
        }
        if (value === 'general') {
            $.each(modeLayout, function(i, mode) {
                var $box = modeBox(mode[0]);
                if ($box.prop('checked')) {
                    $box.prop('checked', false).trigger('change');
                }
            });
        } else {
            modeBox(value).prop('checked', true).trigger('change');
        }
    }

    function setGuard(value) {
        var $select = $('#guard-percent');
        if (String($select.val()) !== String(value) && page.guards.indexOf(Number(value)) !== -1) {
            $select.val(String(value)).trigger('change');
        }
    }

    function setTemporix(on) {
        var $box = $('#temporix-cb');
        if ($box.length && $box.prop('checked') !== on) {
            $box.prop('checked', on).trigger('change');
        }
    }

    function lockItem() {
        return setupShareItem($.trim($form.find('input[name="lock_item"]').val() || ''));
    }

    function setLockItem(item) {
        var $input = $form.find('input[name="lock_item"]');
        if (!$input.length) {
            $input = $('<input type="hidden" name="lock_item">').appendTo($form);
        }
        $input.val(item);
    }

    var formEnv = {
        tick: tick,
        priority: setPriority,
        mode: setMode,
        guard: setGuard,
        clearPanel: function() {
            if (window.SETUP_PANEL) {
                window.SETUP_PANEL.clear();
            }
        },
        setLevel: function(level) { $('#input-char-level').val(level).trigger('change'); },
        setClass: function(name) { $('#select-char-class').val(name).trigger('change'); },
        setTemporix: setTemporix,
        setItem: setLockItem,
        restorePanel: function(edits, now) {
            if (window.SETUP_PANEL) {
                window.SETUP_PANEL.restore(edits, now);
            }
        },
        finished: function() {
            active = null;
            refreshChips();
        }
    };

    function hasElement() {
        return typeof lacksElement === 'function' ? !lacksElement() : true;
    }

    function showNote() {
        setupWriteLive($note, setupRecipeNoteText(setupRecipeNote(active, hasElement())));
    }

    function refreshChips() {
        var current = readControls();
        var found = false;
        $.each(chips, function(i, chip) {
            var on = setupRecipeMatches(chip.target, current);
            chip.$chip.attr('aria-pressed', on ? 'true' : 'false');
            found = found || (on && !!active && active.key === chip.recipe.key);
        });
        if (!found) {
            active = null;
        }
        showNote();
    }

    function applyRecipe(chip) {
        setupFillControls({scope: page.focus, boxes: chip.target.focus, priority: chip.target.priority,
                           mode: chip.target.mode, guard: chip.target.guard}, formEnv);
        active = chip.recipe;
        refreshChips();
        if (!chip.recipe.mule && !hasElement() && typeof flashRed === 'function') {
            flashRed($('#element_title'));
        }
    }

    function collectState(withItem) {
        var controls = readControls();
        var boxes = [];
        $.each(page.boxes, function(i, aspect) {
            if (aspectBox(aspect).prop('checked')) {
                boxes.push(aspect);
            }
        });
        var $temporix = $('#temporix-cb');
        return {game: game, className: $('#select-char-class').val(), level: $.trim($('#input-char-level').val()),
                boxes: boxes, priority: controls.priority, mode: controls.mode, guard: controls.guard,
                temporix: $temporix.length ? $temporix.prop('checked') : null,
                item: withItem ? lockItem() : null,
                touched: window.SETUP_PANEL ? window.SETUP_PANEL.touched() : []};
    }

    function restoreSetup(state, now) {
        setupRestore(state, now, page, formEnv);
    }

    function shareAddress(fragment) {
        var origin = window.location.origin
            || window.location.protocol + '//' + window.location.host;
        return origin + window.location.pathname + '#' + fragment;
    }

    function selectAddress(address) {
        $shareUrl.val(address).prop('hidden', false);
        var field = $shareUrl.get(0);
        field.focus();
        field.select();
        var copied = false;
        try {
            copied = !!document.execCommand && document.execCommand('copy');
        } catch (error) {
            copied = false;
        }
        setupWriteLive($shareStatus, copied ? gettext('Link copied.') : gettext('Select the link and copy it.'));
    }

    function copyAddress() {
        var fragment = setupShareEncode(collectState(true));
        if (!setupShareFits(fragment)) {
            $shareUrl.prop('hidden', true);
            setupWriteLive($shareStatus, gettext('This setup has too many edited values to save or share. Reset some of them first.'));
            return;
        }
        var address = shareAddress(fragment);
        try {
            window.navigator.clipboard.writeText(address).then(function() {
                $shareUrl.prop('hidden', true);
                setupWriteLive($shareStatus, gettext('Link copied.'));
            }, function() {
                selectAddress(address);
            });
        } catch (error) {
            selectAddress(address);
        }
    }

    function renderSaved(list) {
        $savedList.empty();
        $.each(list, function(i, item) {
            var nameId = 'setup-saved-item-' + i;
            var $row = $('<li></li>');
            $('<span class="input-name setup-saved-label"></span>').attr('id', nameId).text(item.name)
                .appendTo($row);
            $('<button type="button" class="setup-action"></button>').attr({'data-load': item.name, 'aria-describedby': nameId})
                .text(gettext('Load')).appendTo($row);
            $('<button type="button" class="setup-action"></button>').attr({'data-delete': item.name, 'aria-describedby': nameId})
                .text(gettext('Delete')).appendTo($row);
            $row.appendTo($savedList);
        });
        if (!list.length) {
            $('<li class="small-explain setup-saved-empty"></li>').text(gettext('No saved setup yet.'))
                .appendTo($savedList);
        }
    }

    function saveSetup() {
        var put = setupSavedPut(setupSavedRead(storage, game), $savedName.val(), setupShareEncode(collectState(false)));
        if (put.result === 'blank') {
            setupWriteLive($savedStatus, gettext('Give the setup a name first.'));
        } else if (put.result === 'long') {
            setupWriteLive($savedStatus, gettext('This setup has too many edited values to save or share. Reset some of them first.'));
        } else if (put.result === 'full') {
            setupWriteLive($savedStatus, interpolate(
                gettext('You can keep up to %s setups. Delete one to save another.'), [SETUP_RECIPES.savedLimit]));
        } else if (!setupSavedWrite(storage, game, put.list)) {
            setupWriteLive($savedStatus, gettext('Your browser did not let this page save the setup.'));
        } else {
            renderSaved(put.list);
            $savedName.val('');
            setupWriteLive($savedStatus, gettext('Setup saved.'));
        }
    }

    function loadSetup(name) {
        var item = setupSavedFind(setupSavedRead(storage, game), name);
        var state = item ? setupShareParse(item.fragment, page) : null;
        if (!state) {
            setupWriteLive($savedStatus, gettext('This setup could not be loaded.'));
            return;
        }
        restoreSetup(state, true);
        setupWriteLive($savedStatus, gettext('Setup loaded.'));
    }

    function deleteSetup(name) {
        var list = setupSavedDrop(setupSavedRead(storage, game), name);
        var written = setupSavedWrite(storage, game, list);
        renderSaved(setupSavedRead(storage, game));
        setupWriteLive($savedStatus, written ? gettext('Setup deleted.')
                                             : gettext('Your browser did not let this page delete the setup.'));
    }

    function restoreFromAddress(now) {
        var state = setupShareParse(window.location.hash, page);
        if (state) {
            restoreSetup(state, now);
        }
    }

    $section.find('.setup-chip').each(function() {
        var $chip = $(this);
        var recipe = setupRecipeFromData({key: $chip.attr('data-recipe'), focus: $chip.attr('data-focus'),
                                          priority: $chip.attr('data-priority'), mode: $chip.attr('data-mode'),
                                          guard: $chip.attr('data-guard'), mule: $chip.attr('data-mule')});
        chips.push({$chip: $chip, recipe: recipe, target: setupRecipeTarget(recipe, page)});
    });
    $.each(chips, function(i, chip) {
        chip.$chip.on('click', function() { applyRecipe(chip); });
    });
    $('#setup-share-copy').on('click', copyAddress);
    $form.on('change', refreshChips);
    $(window).on('hashchange', function() { restoreFromAddress(true); });

    storage = setupOpenStorage(window);
    if (storage) {
        renderSaved(setupSavedRead(storage, game));
        $('#setup-saved-save').on('click', saveSetup);
        $savedName.on('keydown', function(event) {
            if (event.which === 13) {
                event.preventDefault();
                saveSetup();
            }
        });
        $savedList.on('click', '[data-load]', function() { loadSetup($(this).attr('data-load')); });
        $savedList.on('click', '[data-delete]', function() { deleteSetup($(this).attr('data-delete')); });
        $saved.prop('hidden', false);
    }

    restoreFromAddress(false);
    refreshChips();
    $section.prop('hidden', false);
});

$(document).ready(function() {
    var $section = $('#setup-more');
    var source = document.getElementById('setup-more-table');
    if (!$section.length || !source) {
        return;
    }
    var table = JSON.parse(source.textContent);
    var $badge = $('#setup-more-badge');
    var $level = $('#input-char-level');
    var shownLevel = Number($section.attr('data-level'));
    var kept = {};
    var touched = {};
    var $wisdom = $(document.getElementById('check_wis'));
    var $cawwot = $('#setup-more-cawwot');
    var names = [];
    $.each(table.groups, function(i, group) {
        names = names.concat(group[1]);
    });

    function field(name) {
        return $section.find('[name="' + name + '"]');
    }

    function read() {
        var values = {};
        $.each(names, function(i, name) {
            var value = null;
            field(name).each(function() {
                if (this.disabled) {
                    return;
                }
                if (this.type === 'radio' || this.type === 'checkbox') {
                    if (this.checked) {
                        value = this.value;
                    }
                } else {
                    value = this.value;
                }
            });
            values[name] = value;
        });
        return values;
    }

    function write(values) {
        $.each(values, function(name, value) {
            field(name).each(function() {
                if (this.type === 'radio') {
                    this.checked = this.value === value;
                } else if (this.type === 'checkbox') {
                    this.checked = value !== null && value !== undefined;
                } else {
                    this.value = value === null || value === undefined ? '' : value;
                }
            });
        });
    }

    function currentLevel() {
        var text = $.trim($level.val());
        if (!/^[0-9]{1,3}$/.test(text) || Number(text) < SETUP_PREVIEW.minLevel
                || Number(text) > SETUP_PREVIEW.maxLevel) {
            return null;
        }
        return Number(text);
    }

    function markUsable(level) {
        $.each(table.levels, function(key, needed) {
            var $box = field(key);
            var tooHigh = needed > level;
            $box.prop('disabled', tooHigh);
            $box.closest('.setup-more-box').toggleClass('setup-more-too-high', tooHigh);
        });
    }

    function changedGroups() {
        return setupMoreChanged(table.groups, setupMoreDefaults(table, shownLevel), read());
    }

    function showChanges() {
        var groups = changedGroups();
        $section.find('input.setup-more-group').remove();
        $.each(groups, function(i, group) {
            $('<input type="hidden" class="setup-more-group">').attr({name: 'setup_options', value: group})
                .appendTo($section);
        });
        $badge.text(groups.length ? setupPreviewBadge(groups.length) : '').prop('hidden', !groups.length);
    }

    function follow() {
        var level = currentLevel();
        if (level === null || level === shownLevel) {
            return;
        }
        var moved = setupMoreFollow(table, shownLevel, level, read(), kept, touched);
        kept = moved.kept;
        shownLevel = level;
        markUsable(level);
        write(moved.values);
        showChanges();
    }

    function showCawwot() {
        $cawwot.prop('hidden', !$wisdom.prop('checked'));
    }

    $section.on('click', '[data-check]', function() {
        var on = $(this).attr('data-check') === 'true';
        $section.find('.setup-more-grid input[type="checkbox"]').each(function() {
            if (!this.disabled) {
                this.checked = on;
                touched[this.name] = true;
            }
        });
        showChanges();
    });
    $section.on('change input', function(event) {
        if (event.target.name) {
            touched[event.target.name] = true;
        }
        showChanges();
    });
    $level.on('change', follow);
    $section.closest('form').on('change', showCawwot);
    markUsable(shownLevel);
    follow();
    showChanges();
    showCawwot();
});
