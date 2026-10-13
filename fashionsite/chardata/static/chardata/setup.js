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
        restoreEdits(kept);
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

    var actions = setupPanelActions(gate, {
        focusSummary: function() { $details.children('summary').first().trigger('focus'); },
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
        settled: function() { $notice.prop('hidden', true); },
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
    $(window).on('load pageshow', function() {
        $form.find('input.setup-touched').remove();
        showGuard();
        schedule();
    });
    schedule();
});
