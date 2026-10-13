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
    var timer = null;
    var fadeTimer = null;
    var hasBaseline = false;
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
        $changes.text(setupPreviewSummary(names, names.length));
        $panelBadge.text(names.length ? setupPreviewBadge(names.length) : '')
            .prop('hidden', !names.length);
        fadeTimer = window.setTimeout(fadeHighlights, SETUP_PREVIEW.highlightMs);
    }

    function showGuard() {
        var text = hasBaseline ? setupPreviewGuard(
            $form.find('input[name="priority"]:checked').val(), $('#guard-percent').val(),
            guardKinds) : null;
        $guard.text(text || '').prop('hidden', !text);
    }

    function syncTemporixNote() {
        var $temporix = $('#temporix-cb');
        $block.find('.wm-note').prop('hidden', !($temporix.length && $temporix.prop('checked')));
    }

    function show(state) {
        var before = hasBaseline ? readRows() : null;
        api.applyState(state);
        syncTemporixNote();
        if (before) {
            showChanges(before);
        } else {
            hasBaseline = true;
            $block.prop('hidden', false);
            $empty.prop('hidden', true);
            $body.attr('aria-busy', 'false');
        }
        $notice.prop('hidden', true);
        showGuard();
    }

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
        failed: function() {
            $notice.prop('hidden', false);
            $body.attr('aria-busy', 'false');
        }
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
    $(window).on('load pageshow', function() {
        showGuard();
        schedule();
    });
    schedule();
});
