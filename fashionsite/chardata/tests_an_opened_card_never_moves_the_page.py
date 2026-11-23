# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Opening a card of the build page grows it in place: no rule widens it, spans columns or rearranges the grid, and the columns are real."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import read_css

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'solution.html')
SHEETS = ('modern.css', 'modern-solution.css', 'modern-rest.css', 'modern-solution-parts.css')


def page():
    with open(TEMPLATE, encoding='utf-8') as handle:
        return handle.read()


class AnOpenedCardTests(SimpleTestCase):

    def test_no_rule_reacts_to_an_open_card_by_spanning_or_moving_the_grid(self):
        for name in SHEETS:
            for rule in re.findall(r'[^{}]*fm-open[^{}]*\{[^{}]*\}', read_css(name)):
                selector, body = rule.split('{', 1)
                if ':has(' in selector or 'fm-sol-doll' in selector or 'solution-item-section:not' in selector:
                    self.assertNotRegex(body, r'grid-(column|area|template|auto-flow|row)|order:', (name, rule))
                self.assertNotIn('span', body, (name, rule))

    def test_the_doll_sides_are_real_columns_beside_the_figure(self):
        css = read_css('modern.css')
        self.assertIn('grid-template-areas:"left fig right"', css)
        self.assertIn('.fm-sol-doll > .solution-item-section-column{ display:flex !important; flex-direction:column;', css.replace('html.fm-modern .solution-item-section.fm-sol-doll', '.fm-sol-doll'))
        self.assertNotIn('item-container-hat{ grid-area', css)

    def test_the_script_puts_the_doll_items_in_their_side_and_the_tiles_in_columns(self):
        source = page()
        self.assertIn("side=sides.length===2?sides[i<5?0:1]:doll", source)
        self.assertIn("col.className='fm-sol-col'", source)
        self.assertIn("window.matchMedia('(min-width:760px)').addEventListener('change',refit)", source)

    def test_the_tile_columns_stack_their_cards_and_do_not_stretch(self):
        css = read_css('modern-solution-parts.css')
        self.assertRegex(css, r'> \.fm-sol-col\{ display:flex; flex-direction:column;[^}]*align-self:start')

    def test_the_tiles_keep_the_three_and_six_closed_columns(self):
        css = read_css('modern-solution-parts.css')
        self.assertIn('grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; align-items:start;', css)
        self.assertIn('grid-template-columns:repeat(6,minmax(0,1fr))', css)

    def test_the_script_equalises_the_closed_tiles_and_the_doll_rows(self):
        source = page()
        self.assertIn("card.style.minHeight=tall+'px'", source)
        self.assertIn("card.dataset.fmOrder", source)
        self.assertIn("left[j].style.minHeight=natural[j]+'px';right[j].style.minHeight=natural[j]+'px'", source)
        self.assertIn("figure.style.height=tall+'px'", source)

    def test_the_closed_sizes_stay_frozen_while_a_card_is_open(self):
        source = page()
        self.assertIn("if(section.querySelector('.expand-container.fm-open')){section.dataset.fmStale='1';return;}", source)
        self.assertIn("document.querySelector('.solution-item-section[data-fm-stale]')", source)

    def test_the_opened_tile_swaps_the_wrapping_button_for_an_icon_with_the_full_label(self):
        css = read_css('modern-solution-parts.css')
        self.assertRegex(css, r'fm-open \[id\^="stat-override-btn-sol-"\]\{[^}]*width:40px[^}]*font-size:0 !important')
        self.assertIn('[id^="stat-override-btn-sol-"].fm-editing::before', css)
        with open(os.path.join(os.path.dirname(TEMPLATE), 'solution_item.html'), encoding='utf-8') as handle:
            self.assertIn('class="button-generic" title="{% trans "Customize stats" %}"', handle.read())


class TheExchangePopupKeepsItsEnhancedSurfaceTests(SimpleTestCase):

    def test_the_exchange_rows_share_the_enhanced_surface_rule(self):
        css = read_css('enhanced.css')
        rule = re.search(r'html\.fm-enhanced \.item-exchange-stats[^{]*\{[^}]*\}', css).group(0)
        self.assertIn('html.fm-enhanced .item-exchange-comparison', rule)
        self.assertIn('html.fm-enhanced .item-exchange-violations', rule)
        self.assertIn('background:var(--fm-surface)', rule)
        self.assertNotIn('min-width:100%', rule)
