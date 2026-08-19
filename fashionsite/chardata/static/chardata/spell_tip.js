// The info marker beside an item line that names a spell. CSS opens the panel
// on hover and on focus; this adds the tap, and keeps the panel inside the
// screen. Same shape as the comparison cart, which is the only other popover
// on the site that works with a finger.
(function () {
    'use strict';

    var OPEN = 'st-open';
    var MARGIN = 8;
    // The same info icon the sidebar uses, so the popups match the pages.
    var MARK = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none"'
             + ' stroke="currentColor" stroke-width="1.8" stroke-linecap="round"'
             + ' stroke-linejoin="round"><circle cx="12" cy="12" r="9"/>'
             + '<path d="M12 11v5"/><path d="M12 8h.01"/></svg>';
    var hoverCapable = !(window.matchMedia
                         && window.matchMedia('(hover: none)').matches);

    function closeAll(except) {
        var open = document.querySelectorAll('.spell-tip.' + OPEN);
        for (var i = 0; i < open.length; i++) {
            if (open[i] !== except) {
                open[i].classList.remove(OPEN);
            }
        }
    }

    // The switch popup clips what leaves it, so the panel has to stay inside
    // that box and not merely inside the screen.
    function room(tip) {
        var box = {left: 0, right: window.innerWidth};
        var node = tip.parentElement;
        while (node && node !== document.body && node !== document.documentElement) {
            var style = window.getComputedStyle(node);
            if (style.overflowX !== 'visible' || style.overflowY !== 'visible') {
                var rect = node.getBoundingClientRect();
                box.left = Math.max(box.left, rect.left);
                box.right = Math.min(box.right, rect.right);
                break;
            }
            node = node.parentElement;
        }
        return box;
    }

    function place(tip) {
        var panel = tip.querySelector('.spell-tip-panel');
        if (!panel) {
            return;
        }
        tip.classList.remove('st-flip');
        panel.style.left = '';
        panel.style.right = '';
        var rect = panel.getBoundingClientRect();
        if (!rect.width) {
            return;
        }
        var box = room(tip);
        if (rect.right > box.right - MARGIN) {
            tip.classList.add('st-flip');
            rect = panel.getBoundingClientRect();
        }
        if (rect.left < box.left + MARGIN) {
            // On a phone the panel is wider than the room on either side of the
            // mark, so neither edge fits: pin it to the margin instead.
            panel.style.left =
                (box.left + MARGIN - tip.getBoundingClientRect().left) + 'px';
            panel.style.right = 'auto';
        }
    }

    // The pinned offset is measured in pixels, so anything that moves the mark
    // afterwards leaves the panel behind.
    function placeOpen() {
        var open = document.querySelectorAll('.spell-tip.' + OPEN);
        for (var i = 0; i < open.length; i++) {
            place(open[i]);
        }
    }

    document.addEventListener('mouseover', function (event) {
        var tip = event.target.closest && event.target.closest('.spell-tip');
        if (tip) {
            place(tip);
        }
    });

    window.addEventListener('resize', placeOpen);
    document.addEventListener('scroll', placeOpen, true);

    document.addEventListener('click', function (event) {
        var tip = event.target.closest && event.target.closest('.spell-tip');
        if (!tip) {
            closeAll(null);
            return;
        }
        if (hoverCapable) {
            return;
        }
        // A tap toggles the panel, and must not reach what is underneath.
        event.stopPropagation();
        event.preventDefault();
        var wasOpen = tip.classList.contains(OPEN);
        closeAll(tip);
        if (wasOpen) {
            tip.classList.remove(OPEN);
        } else {
            tip.classList.add(OPEN);
            place(tip);
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            closeAll(null);
        }
    });

    function esc(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // The item popups build their lines as an HTML string instead of going
    // through a template, and that string is not escaped for them.
    window.spellTipHtml = function (statLine) {
        var tip = statLine && statLine.spell_tip;
        if (!tip || !tip.description) {
            return '';
        }
        var label = (typeof gettext === 'function')
            ? interpolate(gettext('What %(spell)s does'), {spell: tip.spell}, true)
            : '';
        return '<span class="spell-tip" tabindex="0" role="button"'
             + ' aria-label="' + esc(label) + '">'
             + '<span class="spell-tip-mark" aria-hidden="true">' + MARK + '</span>'
             + '<span class="spell-tip-panel" role="tooltip">'
             + '<b class="spell-tip-name">' + esc(tip.spell) + '</b>'
             + '<span class="spell-tip-text">' + esc(tip.description) + '</span>'
             + '</span></span>';
    };
    // The stats panel builds its lines the same way on the solution page and
    // on the comparison page.
    window.statTipPanelHtml = function (name, lines) {
        var html = '<span class="spell-tip-panel" role="tooltip">'
                 + '<b class="spell-tip-name">' + esc(name) + '</b>';
        for (var i = 0; i < lines.length; i++) {
            var value = lines[i].value;
            html += '<span class="stat-tip-row"><span>' + esc(lines[i].label)
                 + '</span><span>' + (value > 0 ? '+' : '') + value
                 + '</span></span>';
        }
        return html + '</span>';
    };
}());
