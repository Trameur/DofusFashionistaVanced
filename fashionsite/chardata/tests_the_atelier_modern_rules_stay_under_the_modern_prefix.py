# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every rule in modern.css starts with html.fm-modern, so the classic design never sees it, except the frozen list below."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import chain_of, declared, stylesheet, winning

FROZEN_UNPREFIXED = frozenset((
    '.builds-grid > .fm-ad-feed',
    '.cc-toast',
    '.cc-toast-show',
    '.compare-cart',
    '.compare-cart .cc-count',
    '.compare-cart .cc-icon',
    '.compare-cart .cc-icon svg',
    '.compare-cart-panel',
    '.compare-cart-panel .cc-actions',
    '.compare-cart-panel .cc-av',
    '.compare-cart-panel .cc-clear',
    '.compare-cart-panel .cc-clear:hover',
    '.compare-cart-panel .cc-go',
    '.compare-cart-panel .cc-go[disabled]',
    '.compare-cart-panel .cc-lvl',
    '.compare-cart-panel .cc-name',
    '.compare-cart-panel .cc-row',
    '.compare-cart-panel .cc-rows',
    '.compare-cart-panel .cc-title',
    '.compare-cart-panel .cc-x',
    '.compare-cart-panel .cc-x:hover',
    '.compare-cart-panel::before',
    '.compare-cart-toggle',
    '.compare-cart-toggle:hover',
    '.compare-cart.cc-open .compare-cart-panel',
    '.compare-cart:hover .compare-cart-panel',
    '.compare-cart[hidden]',
    '.encyclopedia-grid > .fm-ad-feed',
    '.encyclopedia-monsters-grid > .fm-ad-feed',
    '.encyclopedia-sets-grid > .fm-ad-feed',
    '.fm-ad-rail',
    '.fm-design-toggle',
    '.fm-design-toggle:active',
    '.fm-design-toggle:hover',
    '.fm-guides-grid > .fm-ad-feed',
    '.fm-ico',
    '.fm-ico[hidden]',
    '.fm-ico-bag',
    '.fm-ico-camera',
    '.fm-ico-check',
    '.fm-ico-close',
    '.fm-ico-cut',
    '.fm-ico-forge',
    '.fm-ico-warn',
    '.fm-st',
    '.fm-st-builds',
    '.fm-st-fav',
    '.fm-st-like',
    '.fm-st-view',
    '.menu_link .mi',
    '.menu_link .mi svg',
    '.solution-stat-summary-name.spell-tip',
    '.spell-line',
    '.spell-tip',
    '.spell-tip-mark',
    '.spell-tip-mark svg',
    '.spell-tip-name',
    '.spell-tip-panel',
    '.spell-tip-text',
    '.spell-tip.st-flip .spell-tip-panel',
    '.spell-tip.st-open .spell-tip-mark',
    '.spell-tip.st-open .spell-tip-panel',
    '.spell-tip:focus-visible .spell-tip-mark',
    '.spell-tip:focus-visible .spell-tip-panel',
    '.spell-tip:hover .spell-tip-mark',
    '.spell-tip:hover .spell-tip-panel',
    '.stat-tip-row',
    '.transcendence-tip',
    '.transcendence-tip .spell-tip-mark',
    '.transcendence-tip .spell-tip-text + .spell-tip-text',
    'html.fm-dark .spell-line',
    'html.fm-dark .spell-tip-mark',
    'html.fm-dark .spell-tip.st-open .spell-tip-mark',
    'html.fm-dark .spell-tip:focus-visible .spell-tip-mark',
    'html.fm-dark .spell-tip:hover .spell-tip-mark',
    'html.fm-dark:not(.fm-modern) .compare-cart-toggle',
    'html:not(.fm-modern) .compare-cart',
    'html:not(.fm-modern) .compare-cart-panel',
    'html:not(.fm-modern) .compare-cart-toggle',
    'html:not(.fm-modern) .space.header-controls',
    'html:not(.fm-modern) .fm-design-toggle svg',
    'html:not(.fm-modern) .space.header-controls .fm-design-toggle',
))

MODERN = stylesheet('modern.css')


def selectors():
    return [(selector, rule['media']) for rule in MODERN for selector in rule['selectors']]


class EveryModernRuleIsPrefixedTests(SimpleTestCase):

    def test_only_the_rules_that_were_already_unprefixed_lack_the_modern_prefix(self):
        added = sorted({selector for selector, _ in selectors()
                        if not selector.startswith('html.fm-modern') and selector not in FROZEN_UNPREFIXED})
        self.assertEqual([], added)

    def test_the_stylesheet_is_read_as_rules_and_not_as_nothing(self):
        self.assertGreater(len(selectors()), 300)

    def test_every_frozen_entry_is_still_a_selector_of_the_stylesheet(self):
        present = {selector for selector, _ in selectors()}
        self.assertEqual([], sorted(FROZEN_UNPREFIXED - present))

    def test_the_atelier_components_are_prefixed(self):
        found = {selector for selector, _ in selectors() if 'fm-seam' in selector or 'fm-tape' in selector
                 or 'fm-frame' in selector}
        self.assertTrue(found)
        self.assertEqual([], sorted(selector for selector in found if not selector.startswith('html.fm-modern ')))


PANEL = 'html.fm-modern .solution-stat-summary .spell-tip-panel'
ROW = PANEL + ' .stat-tip-row'


def stat_tip_chain(tag, attrs, design=('fm-modern', 'fm-light')):
    ancestors = (('html', {}), ('body', {'class': 'body-base'}), ('table', {}), ('tbody', {}), ('tr', {}),
                 ('td', {'class': 'solution-stat-summary'}), ('table', {'class': 'solution-stat-table'}), ('tbody', {}),
                 ('tr', {'class': 'solution-stat-summary-line'}),
                 ('td', {'class': 'solution-stat-summary-name spell-tip'}))
    if tag == 'row':
        return chain_of(ancestors + (('span', {'class': 'spell-tip-panel'}),), 'span', {'class': 'stat-tip-row'}, design)
    return chain_of(ancestors, tag, attrs, design)


def winner(prop, chain):
    found = winning([('modern.css', MODERN)], chain, prop, 1440)
    return found if found is not None else ('', '', '')


class StatTipPanelFitsTheStatsBoxTests(SimpleTestCase):

    def panel(self, design=('fm-modern', 'fm-light')):
        return stat_tip_chain('span', {'class': 'spell-tip-panel'}, design)

    def test_the_modern_rule_wins_the_panel_width_on_the_real_cell(self):
        self.assertIn(PANEL, {selector for selector, _ in selectors()})
        value, _, selector = winner('width', self.panel())
        self.assertEqual((PANEL, 'min(256px,78vw)'), (selector, value.replace(' ', '')))

    def test_the_modern_rule_wins_the_panel_box_sizing_on_the_real_cell(self):
        value, _, selector = winner('box-sizing', self.panel())
        self.assertEqual((PANEL, 'border-box'), (selector, value))

    def test_the_classic_design_keeps_the_wide_panel(self):
        self.assertNotEqual(PANEL, winner('width', self.panel(('fm-light',)))[2])
        self.assertNotEqual(PANEL, winner('box-sizing', self.panel(('fm-dark',)))[2])

    def test_the_label_of_a_row_wraps_and_the_value_stays_on_one_line(self):
        self.assertEqual((ROW, 'normal'), (winner('white-space', stat_tip_chain('row', {}))[2],
                                           winner('white-space', stat_tip_chain('row', {}))[0]))
        label = declared(MODERN, ROW + ' > :first-child', 'min-width')
        value = {prop: declared(MODERN, ROW + ' > :last-child', prop) for prop in ('white-space', 'flex-shrink')}
        self.assertEqual(('0', False), label)
        self.assertEqual({'white-space': ('nowrap', False), 'flex-shrink': ('0', False)}, value)

    def test_a_long_label_may_break_inside_a_word(self):
        self.assertEqual(('anywhere', False), declared(MODERN, ROW + ' > :first-child', 'overflow-wrap'))
