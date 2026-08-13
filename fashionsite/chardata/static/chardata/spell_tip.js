// The info marker beside an item line that names a spell. CSS opens the panel
// on hover and on focus; this adds the tap, and keeps the panel inside the
// screen. Same shape as the comparison cart, which is the only other popover
// on the site that works with a finger.
(function () {
    'use strict';

    var OPEN = 'st-open';
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

    function place(tip) {
        var panel = tip.querySelector('.spell-tip-panel');
        if (!panel) {
            return;
        }
        tip.classList.remove('st-flip');
        var box = panel.getBoundingClientRect();
        if (box.right > window.innerWidth - 8) {
            tip.classList.add('st-flip');
        }
    }

    document.addEventListener('mouseover', function (event) {
        var tip = event.target.closest && event.target.closest('.spell-tip');
        if (tip) {
            place(tip);
        }
    });

    document.addEventListener('click', function (event) {
        var tip = event.target.closest && event.target.closest('.spell-tip');
        if (!tip) {
            closeAll(null);
            return;
        }
        // The lines sit inside the item card, which collapses when clicked.
        event.stopPropagation();
        event.preventDefault();
        if (hoverCapable) {
            return;
        }
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
        return '<span class="spell-tip" tabindex="0" role="button">'
             + '<span class="spell-tip-mark" aria-hidden="true">i</span>'
             + '<span class="spell-tip-panel" role="tooltip">'
             + '<b class="spell-tip-name">' + esc(tip.spell) + '</b>'
             + '<span class="spell-tip-text">' + esc(tip.description) + '</span>'
             + '</span></span>';
    };
}());
