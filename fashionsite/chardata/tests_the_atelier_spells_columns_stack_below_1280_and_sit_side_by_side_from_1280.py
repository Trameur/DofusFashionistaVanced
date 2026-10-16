# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The spells page of the modern design: one column below 1280, three side by side from 1280, the cards dealt into the first column alone while stacked, room reserved for the controls in the card headers, no scrolling box around the columns, and a classic design that keeps its table."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import media_applies, stylesheet

MODERN = stylesheet('modern.css')
SPELLS = stylesheet('spells.css')
ROOT = 'html.fm-modern'
TABLE = ROOT + ' #spells-table'
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'spells.html')
WIDTHS = [375, 768, 900, 901, 1279, 1280, 1440, 1920, 2560]


def at(selector, prop, width):
    found = None
    for rule in MODERN:
        if selector in rule['selectors'] and prop in rule['declarations'] and media_applies(rule['media'], width):
            found = rule['declarations'][prop][0]
    return found


def tracks(value):
    repeated = re.match(r'repeat\((\d+),', value)
    return int(repeated.group(1)) if repeated else len(re.sub(r'minmax\([^)]*\)', 'x', value).split())


class TheSpellColumnsTests(SimpleTestCase):

    def test_one_track_below_1280_and_three_from_1280(self):
        for width in WIDTHS:
            wanted = 3 if width >= 1280 else 1
            self.assertEqual(wanted, tracks(at(TABLE + ' > tbody > tr', 'grid-template-columns', width)), width)

    def test_the_three_cells_are_grid_items_that_may_shrink(self):
        for width in WIDTHS:
            self.assertEqual('block', at(TABLE + ' > tbody > tr > .spells-td', 'display', width).split()[0])
            self.assertEqual('auto', at(TABLE + ' > tbody > tr > .spells-td', 'width', width).split()[0])
            self.assertEqual('0', at(TABLE + ' > tbody > tr > .spells-td', 'min-width', width))

    def test_the_row_is_a_grid_at_every_width(self):
        for width in WIDTHS:
            self.assertEqual('grid', at(TABLE + ' > tbody > tr', 'display', width).split()[0])

    def test_no_rule_reaches_the_tables_inside_the_cards(self):
        for rule in MODERN:
            for selector in rule['selectors']:
                if '#spells-table ' in selector and ' > ' not in selector.split('#spells-table', 1)[1]:
                    self.assertNotRegex(selector, r'#spells-table (tbody|tr|td)(?![\w-])', selector)

    def test_no_scrolling_box_wraps_the_columns(self):
        for width in WIDTHS:
            self.assertEqual('visible', at(TABLE, 'overflow', width))

    def test_no_cell_keeps_a_fixed_width_below_901(self):
        for rule in MODERN:
            if any('.spells-td' in selector for selector in rule['selectors']):
                if 'width' in rule['declarations']:
                    self.assertEqual('auto', rule['declarations']['width'][0].split()[0], rule['selectors'])

    def test_the_header_reserves_a_strip_for_the_absolute_controls(self):
        found = [rule for rule in MODERN if ROOT + ' #spells-table .header-cell:has(.select-stack)' in rule['selectors']]
        self.assertEqual(1, len(found))
        self.assertIn(ROOT + ' #spells-table .header-cell:has(.circle-container)', found[0]['selectors'])
        self.assertGreaterEqual(int(found[0]['declarations']['padding-bottom'][0].rstrip('px')), 30)


class TheSpellDealingTests(SimpleTestCase):

    def setUp(self):
        with open(TEMPLATE, encoding='utf-8') as handle:
            self.html = handle.read()

    def test_the_stacked_condition_is_modern_and_below_the_grid_breakpoint(self):
        self.assertIn("var SIDE_BY_SIDE_QUERY = '(min-width: 1280px)';", self.html)
        self.assertRegex(self.html, r"classList\.contains\('fm-modern'\)\s*&&\s*!window\.matchMedia\(SIDE_BY_SIDE_QUERY\)\.matches")

    def test_create_lines_stops_looking_for_the_shortest_column_while_stacked(self):
        body = self.html[self.html.index('function createLines()'):self.html.index('function decideLevel')]
        self.assertIn('var stacked = spellsStacked();', body)
        self.assertIn('j < 3 && !stacked', body)

    def test_crossing_the_breakpoint_moves_the_cards_without_rebuilding_them(self):
        self.assertRegex(self.html, r"sideBySide\.addEventListener\('change', function\(\) \{\s*if \(document\.documentElement\.classList\.contains\('fm-modern'\)\) \{\s*redealSpells\(\);")
        body = self.html[self.html.index('function redealSpells()'):self.html.index('function decideLevel')]
        self.assertIn('.detach()', body)
        self.assertNotIn('createSpellPairOrSingle', body)
        self.assertNotIn('spellLevel', body)

    def test_each_card_carries_its_place_in_the_list(self):
        body = self.html[self.html.index('function createLines()'):self.html.index('function redealSpells()')]
        self.assertIn("$(new_cell).attr('data-deal', i);", body)

    def test_the_two_button_groups_wrap_instead_of_overflowing(self):
        for width in WIDTHS:
            self.assertEqual('flex', at(ROOT + ' #spell-buttons > table tr', 'display', width))
            self.assertEqual('wrap', at(ROOT + ' #spell-buttons > table tr', 'flex-wrap', width))

    def test_the_filters_line_up_left_when_stacked_and_right_otherwise(self):
        for width in WIDTHS:
            wanted = 'left' if width <= 900 else 'right'
            self.assertEqual(wanted, at(ROOT + ' #spell-buttons #right-buttons', 'text-align', width), width)


class TheClassicDesignKeepsItsTableTests(SimpleTestCase):

    def test_every_new_rule_sits_under_the_modern_prefix(self):
        for rule in MODERN:
            for selector in rule['selectors']:
                if 'spells-table' in selector or 'spell-buttons' in selector:
                    self.assertTrue(selector.startswith(ROOT), selector)

    def test_the_template_keeps_the_three_cells_in_order(self):
        with open(TEMPLATE, encoding='utf-8') as handle:
            html = handle.read()
        self.assertEqual(['spells0', 'spells1', 'spells2'], re.findall(r'<td class="spells-td"[^>]*>\s*<div id="(spells\d)">', html))

    def test_the_classic_sheet_declares_no_grid(self):
        for rule in SPELLS:
            self.assertNotIn('grid-template-columns', rule['declarations'])
