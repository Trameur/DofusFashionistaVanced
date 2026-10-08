function wmInit(postUrl, options) {
    var formMode = !!(options && options.mode === 'form');
    var $form = $((options && options.form) || '#main_form');
    var state = JSON.parse(document.getElementById('wm-state').textContent);
    var defaults = JSON.parse(document.getElementById('wm-defaults').textContent);
    var ranges = state.ranges || {};
    var STORE_KEY = 'fm_wm_sections';

    function media(query) {
        return window.matchMedia ? window.matchMedia(query).matches : true;
    }

    function rowOf(input) {
        return $(input).closest('.wm-row');
    }

    function column(input) {
        return $(input).hasClass('wm-min-input') ? 'min' : 'weight';
    }

    function boxOf(key, col) {
        return $('#' + (col === 'min' ? 'min_' : 'weight_') + key);
    }

    function members($row) {
        var list = ($row.attr('data-members') || '').split(' ');
        return $.grep(list, function(key) { return key !== ''; });
    }

    function widened(key, value) {
        var range = ranges[key] || [0, 100];
        var low = range[0];
        var high = range[1];
        if (value !== '' && !isNaN(value)) {
            value = Number(value);
            low = Math.min(low, Math.floor(value));
            high = Math.max(high, Math.ceil(value * 1.5));
        }
        return [low, high];
    }

    function refreshSlider($row) {
        var $slider = $row.find('.wm-slider');
        if (!$slider.length || !$slider.data('wm-built')) {
            return;
        }
        var key = $row.attr('data-key');
        var value = boxOf(key, 'weight').val();
        var range = widened(key, value);
        $slider.slider('option', 'min', range[0]);
        $slider.slider('option', 'max', range[1]);
        $slider.slider('value', value === '' ? range[0] : Number(value));
    }

    function refreshAggregates() {
        $('.wm-aggregate').each(function() {
            var $row = $(this);
            var key = $row.attr('data-key');
            $.each(['weight', 'min'], function(i, col) {
                var $box = boxOf(key, col);
                if (!$box.length) {
                    return;
                }
                var values = [];
                $.each(members($row), function(j, member) {
                    var $member = boxOf(member, col);
                    if ($member.length) {
                        values.push($member.val());
                    }
                });
                var common = values.length ? values[0] : '';
                $.each(values, function(j, value) {
                    if (value !== common) {
                        common = '';
                    }
                });
                $box.val(common);
            });
        });
        $('.wm-row[data-sum]').each(function() {
            var $row = $(this);
            var total = 0;
            $.each($row.attr('data-sum').split(' '), function(i, member) {
                var value = Number(boxOf(member, 'weight').val());
                total += isNaN(value) ? 0 : value;
            });
            boxOf($row.attr('data-key'), 'weight').val(total);
        });
    }

    function refreshRow($row) {
        var key = $row.attr('data-key');
        var $weight = $row.find('.wm-weight-input, .wm-weight input');
        var $min = $row.find('.wm-min-input');
        var weight = $weight.length ? $weight.val() : '';
        var hasMin = $min.length > 0 && $min.val() !== '';
        var noWeight = weight === '' || Number(weight) === 0;
        $row.toggleClass('wm-has-min', hasMin && !$row.hasClass('wm-aggregate'));
        $row.toggleClass('wm-idle', noWeight && !hasMin);
        refreshSlider($row);
        return key;
    }

    function refreshCounts() {
        $('.wm-section').each(function() {
            var n = $(this).find('.wm-row:not(.wm-aggregate) .wm-min-input').filter(function() {
                return this.value !== '';
            }).length;
            var text = n ? interpolate(ngettext('%s minimum', '%s minimums', n), [n]) : '';
            $(this).find('.wm-count').text(text);
        });
    }

    function refreshAll() {
        refreshAggregates();
        $('.wm-row').each(function() { refreshRow($(this)); });
        refreshCounts();
    }

    function applyState(newState) {
        ranges = newState.ranges || ranges;
        $('.wm-weight-input').each(function() {
            var key = rowOf(this).attr('data-key');
            var value = newState.weights[key];
            $(this).val(value === undefined || value === null ? 0 : value);
        });
        $('.wm-min-input').each(function() {
            var key = rowOf(this).attr('data-key');
            var value = newState.minimums[key];
            $(this).val(value === undefined || value === null ? '' : value);
        });
        $('#weights_reset').val('0');
        refreshAll();
    }

    function rememberFocus(input) {
        $(input).data('wm-at-focus', $(input).val());
    }

    function changedSinceFocus(input) {
        return $(input).val() !== $(input).data('wm-at-focus');
    }

    function mixedAndLeftBlank(input) {
        return rowOf(input).hasClass('wm-aggregate') && $(input).val() === ''
            && $(input).data('wm-at-focus') === '';
    }

    function clampToCap($input) {
        var max = $input.attr('max');
        if (max === undefined || $input.val() === '' || Number($input.val()) <= Number(max)) {
            return;
        }
        $input.val(max);
        var $row = rowOf($input);
        $row.addClass('wm-cap-hit');
        setTimeout(function() { $row.removeClass('wm-cap-hit'); }, 1200);
    }

    function afterEdit(input) {
        var $row = rowOf(input);
        var col = column(input);
        if ($row.hasClass('wm-aggregate') && !mixedAndLeftBlank(input)) {
            var value = $(input).val();
            $.each(members($row), function(i, member) {
                var $member = boxOf(member, col);
                $member.val(value);
                if (col === 'min') {
                    clampToCap($member);
                }
            });
        }
        refreshAll();
    }

    function buildSlider($row) {
        var $slider = $row.find('.wm-slider');
        if (!$slider.length || $slider.data('wm-built')) {
            return;
        }
        var key = $row.attr('data-key');
        var $box = boxOf(key, 'weight');
        var range = widened(key, $box.val());
        var onMove = function(event, ui) {
            if (!event.originalEvent) {
                return;
            }
            $box.val(ui.value);
            $box.trigger('change');
        };
        $slider.slider({min: range[0], max: range[1],
                        value: $box.val() === '' ? range[0] : Number($box.val()),
                        slide: onMove, change: onMove});
        $slider.find('.ui-slider-handle').attr('tabindex', '-1');
        $slider.data('wm-built', true);
    }

    function buildSliders($section) {
        if (!$.fn.slider || !media('(min-width: 481px)')) {
            return;
        }
        $section.find('.wm-row').each(function() { buildSlider($(this)); });
    }

    function storedSections() {
        try {
            var raw = window.localStorage.getItem(STORE_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    function storeSections() {
        var open = {};
        $('.wm-section').each(function() {
            open[$(this).attr('data-section')] = this.open;
        });
        try {
            window.localStorage.setItem(STORE_KEY, JSON.stringify(open));
        } catch (e) {
        }
    }

    function openSections() {
        var stored = storedSections();
        $('.wm-section').each(function() {
            var key = $(this).attr('data-section');
            if (stored && typeof stored[key] === 'boolean') {
                this.open = stored[key];
            } else if (!stored && media('(min-width: 901px)')) {
                this.open = true;
            }
        });
    }

    function openHash() {
        var hash = window.location.hash;
        if (!/^#row-[\w-]+$/.test(hash)) {
            return;
        }
        var $row = $(hash);
        if (!$row.length) {
            return;
        }
        var section = $row.closest('.wm-section').get(0);
        if (section && !section.open) {
            section.open = true;
        }
        $row.get(0).scrollIntoView({block: 'center'});
    }

    function visibleInputs(col) {
        return $('.wm-section[open] ' + (col === 'min' ? '.wm-min-input' : '.wm-weight-input'))
            .filter(':visible');
    }

    function selectOnFocus() {
        var input = this;
        rememberFocus(input);
        $(input).data('wm-focused', true);
        setTimeout(function() {
            if (document.activeElement === input) {
                try { input.select(); } catch (e) {}
            }
        }, 0);
    }

    function weightChanged() {
        if ($(this).val() === '' && !mixedAndLeftBlank(this)) {
            $(this).val(0);
        }
        afterEdit(this);
    }

    function minimumChanged() {
        clampToCap($(this));
        afterEdit(this);
    }

    function onEnter(event) {
        if (event.key !== 'Enter') {
            return;
        }
        event.preventDefault();
        if (changedSinceFocus(this)) {
            $(this).trigger('change');
            rememberFocus(this);
        }
        if (event.ctrlKey || event.metaKey) {
            if (typeof changesPendingStateEngine !== 'undefined' && changesPendingStateEngine) {
                $('#button-save').trigger('click');
            }
            return;
        }
        var inputs = visibleInputs(column(this));
        var at = inputs.index(this);
        if (at >= 0 && at + 1 < inputs.length) {
            inputs.eq(at + 1).trigger('focus');
        }
    }

    $('.wm-input').on('focus', selectOnFocus).on('mouseup', function(event) {
        if ($(this).data('wm-focused')) {
            $(this).data('wm-focused', false);
            event.preventDefault();
        }
    }).on('blur', function() {
        $(this).data('wm-focused', false);
    });
    $('.wm-weight-input').on('change', weightChanged);
    $('.wm-min-input').on('change', minimumChanged);
    $('.wm-input').on('keydown', onEnter);

    $('.wm-section').on('toggle', function() {
        if (this.open) {
            buildSliders($(this));
        }
    });
    $('.wm-section > summary').on('click', function() {
        setTimeout(storeSections, 0);
    });

    $('#button-reset-weights').on('click', function() {
        if (!confirm($form.attr('data-confirm-reset'))) {
            return;
        }
        $.each(defaults, function(key, value) {
            boxOf(key, 'weight').val(value);
        });
        refreshAll();
        $('#weights_reset').val('1');
        if (!formMode) {
            setChangesPendingStateEngine(true);
        }
    });

    function clearTheBar() {
        var bar = $('.wm-actions')[0];
        if (!bar) {
            return;
        }
        var fixed = $(bar).css('position') === 'fixed';
        $form[0].style.setProperty('padding-bottom', fixed ? (bar.offsetHeight + 12) + 'px' : '', fixed ? 'important' : '');
    }
    $(window).on('resize', clearTheBar);
    if (window.ResizeObserver && $('.wm-actions').length) {
        new ResizeObserver(clearTheBar).observe($('.wm-actions')[0]);
    }
    clearTheBar();

    openSections();
    if (formMode) {
        applyState(state);
    } else {
        setupStateEngine(applyState, postUrl, state, null, applyState);
    }
    $('.wm-section[open]').each(function() { buildSliders($(this)); });
    openHash();

    if ($form.attr('data-focus') === 'minimums' && media('(min-width: 901px)') && !window.location.hash) {
        $('#min_ap').trigger('focus');
    }
}
