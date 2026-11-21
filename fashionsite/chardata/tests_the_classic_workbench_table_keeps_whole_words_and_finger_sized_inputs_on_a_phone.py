# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a phone the Classic designs keep the smithmagic workbench stat names whole and its number inputs finger-sized, the table scrolling inside its wrapper, while the simulator table and the Atelier design are left out."""
import io
import os

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import chain_of, declared, matching, stylesheet, winning

PHONE = '(max-width: 600px)'
DESIGNS = ('html:not(.fm-modern, .fm-enhanced)', 'html.fm-enhanced')
TABLES = tuple(design + ' .fm-table.fm-workbench-table' for design in DESIGNS)
INPUTS = tuple(design + ' body .fm-table.fm-workbench-table input[type="number"]' for design in DESIGNS)
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'forgemagie.html')


SHEETS = [(name, stylesheet(name)) for name in ('forms.css', 'responsive.css', 'forgemagie.css', 'enhanced.css')]
INPUT_ATTRS = {'class': 'pretty-input fm-input', 'type': 'number'}


def input_chain(table_class, html_classes):
    ancestors = (('html', {}), ('body', {}), ('table', {'class': table_class}), ('tbody', {}), ('tr', {}), ('td', {}))
    return chain_of(ancestors, 'input', INPUT_ATTRS, html_classes)


def phone_rules():
    return stylesheet('responsive.css')


class TheClassicWorkbenchTableKeepsWholeWordsAndFingerSizedInputsOnAPhone(SimpleTestCase):

    def test_the_workbench_table_carries_its_own_class(self):
        with io.open(TEMPLATE, encoding='utf-8') as handle:
            source = handle.read()
        head = source.index('<tbody id="fm-rows">')
        self.assertIn('<table class="fm-table fm-workbench-table">', source[:head])
        self.assertEqual(source.count('fm-workbench-table'), 1)

    def test_the_columns_size_to_their_content_instead_of_sharing_the_width_equally(self):
        rules = phone_rules()
        for table in TABLES:
            with self.subTest(table=table):
                self.assertEqual(declared(rules, table, 'table-layout', PHONE), ('auto', False))
                self.assertEqual(declared(rules, table, 'width', PHONE), ('auto', True))
                minimum = int(declared(rules, table, 'min-width', PHONE)[0].replace('px', ''))
                self.assertGreaterEqual(minimum, 700)

    def test_a_stat_name_breaks_between_words_only(self):
        rules = phone_rules()
        cells = [rule for rule in matching(rules, TABLES[0] + ' th', PHONE)
                 if rule['selectors'] == [table + ' ' + cell for table in TABLES for cell in ('th', 'td')]]
        self.assertEqual(len(cells), 1)
        declarations = cells[0]['declarations']
        self.assertEqual(declarations['overflow-wrap'][0], 'normal')
        self.assertEqual(declarations['word-break'][0], 'normal')
        for table in TABLES:
            with self.subTest(table=table):
                self.assertTrue(matching(rules, table + ' td:first-child', PHONE))

    def test_the_number_inputs_show_four_digits_and_a_sign_and_stay_44_pixels_tall(self):
        rules = phone_rules()
        for inputs in INPUTS:
            with self.subTest(inputs=inputs):
                found = matching(rules, inputs, PHONE)
                self.assertEqual(len(found), 1)
                declarations = found[0]['declarations']
                self.assertGreaterEqual(int(declarations['width'][0].replace('px', '')), 72)
                self.assertEqual(declarations['min-height'][0], '44px')
                self.assertEqual(declarations['box-sizing'][0], 'border-box')

    def test_the_forced_width_wins_the_cascade_in_both_classic_designs(self):
        for classes in (('fm-light',), ('fm-dark',), ('fm-enhanced', 'fm-light'), ('fm-enhanced', 'fm-dark')):
            for width in (360, 390, 600):
                with self.subTest(classes=classes, width=width):
                    chain = input_chain('fm-table fm-workbench-table', classes)
                    self.assertEqual('76px', winning(SHEETS, chain, 'width', width)[0])

    def test_the_simulator_table_keeps_the_width_its_cells_give_it(self):
        for classes in (('fm-light',), ('fm-enhanced', 'fm-light')):
            with self.subTest(classes=classes):
                chain = input_chain('fm-table', classes)
                self.assertNotEqual('76px', winning(SHEETS, chain, 'width', 390)[0])

    def test_every_phone_rule_for_the_table_leaves_the_modern_design_out(self):
        for rule in phone_rules():
            if rule['media'] != PHONE:
                continue
            for selector in rule['selectors']:
                if 'fm-workbench-table' in selector or 'input[type="number"]' in selector:
                    self.assertTrue(selector.startswith(tuple(design + ' ' for design in DESIGNS)), selector)

    def test_the_atelier_rules_for_the_workbench_are_still_in_the_modern_sheet(self):
        modern = stylesheet('modern.css')
        key = 'html.fm-modern .fm-page.tools-atelier .fm-table:has(#fm-rows)'
        self.assertEqual(declared(modern, key, 'min-width', _media_of(modern, key)), ('980px', False))


def _media_of(rules, selector):
    for rule in rules:
        if selector in rule['selectors'] and 'min-width' in rule['declarations']:
            return rule['media']
    return None
