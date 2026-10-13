# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ panel buttons are at least 32px tall on desktop and 44px tall below 768px, and their label wraps instead of overflowing in every design and theme."""
import io
import os

from django.test import SimpleTestCase, TestCase

from chardata.tests_the_setup_page_draws_the_live_weights_panel import _Versioned, setup_page
from chardata.tests_the_setup_stylesheet_support import (
    DESIGNS, chain_of, declared, matching, parse, rule_order, setup_sheets, stylesheet,
    winning)

SETUP = stylesheet('setup.css')
BUTTON = '.setup-preview button.button-thin-foreground'
MODERN_BUTTON = 'html.fm-modern .setup-preview button.button-thin-foreground'
PHONE = '(max-width: 767px)'
PANEL_BUTTONS = ('setup-preview-reset', 'setup-preview-keep-yes', 'setup-preview-keep-no')
WIDTHS = (375, 768, 1024, 1920)
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')


def pixels(value):
    assert value[0].endswith('px'), value
    return int(value[0][:-2])


class ThePanelButtonSizesTests(SimpleTestCase):

    def test_the_desktop_height_is_at_least_32_pixels(self):
        self.assertGreaterEqual(pixels(declared(SETUP, BUTTON, 'min-height')), 32)

    def test_the_phone_height_is_at_least_44_pixels(self):
        self.assertGreaterEqual(pixels(declared(SETUP, BUTTON, 'min-height', PHONE)), 44)

    def test_the_phone_rule_is_the_only_media_rule_for_the_button_and_it_sets_only_the_height(self):
        rules = [rule for rule in SETUP if rule['media'] is not None and BUTTON in rule['selectors']]
        self.assertEqual([PHONE], [rule['media'] for rule in rules])
        self.assertEqual({'min-height'}, set(rules[0]['declarations']))

    def test_the_phone_rule_comes_after_the_base_rule_so_it_wins_at_equal_specificity(self):
        self.assertEqual(1, len(matching(SETUP, BUTTON)))
        self.assertLess(rule_order(SETUP, BUTTON)[0], rule_order(SETUP, BUTTON, PHONE)[0])

    def test_the_classic_label_wraps_so_a_long_translation_stays_inside_the_panel(self):
        self.assertEqual(('normal', False), declared(SETUP, BUTTON, 'white-space'))

    def test_the_modern_label_wraps_by_a_rule_scoped_to_the_design(self):
        self.assertEqual(('normal', False), declared(SETUP, MODERN_BUTTON, 'white-space'))


class TheLabelWrapsInEveryDesignAndThemeTests(_Versioned, TestCase):

    def chain(self, page, button_id, design):
        attrs, ancestors = page.find('button', id=button_id)[0]
        return chain_of(ancestors, 'button', attrs, DESIGNS[design])

    def test_the_cascade_gives_every_panel_button_a_wrapping_label_at_every_width(self):
        sheets = setup_sheets()
        _html, page = setup_page(self.client, 'dofus3')
        for design in DESIGNS:
            for button_id in PANEL_BUTTONS:
                chain = self.chain(page, button_id, design)
                for width in WIDTHS:
                    with self.subTest(design=design, button=button_id, width=width):
                        value, sheet, selector = winning(sheets, chain, 'white-space', width)
                        self.assertEqual('normal', value, '%s in %s' % (selector, sheet))

    def test_the_modern_rule_is_what_wins_in_the_modern_designs(self):
        sheets = setup_sheets()
        _html, page = setup_page(self.client, 'dofus3')
        for design in ('modern light', 'modern dark'):
            with self.subTest(design=design):
                chain = self.chain(page, 'setup-preview-keep-no', design)
                self.assertEqual(('normal', 'setup.css', MODERN_BUTTON),
                                 winning(sheets, chain, 'white-space', 1024))

    def test_the_guard_sees_the_label_stay_on_one_line_when_only_the_classic_rule_exists(self):
        sheets = [(name, rules) for name, rules in setup_sheets() if name != 'setup.css']
        sheets.insert(2, ('setup.css', parse('%s { white-space: normal; min-height: 32px; }' % BUTTON)))
        _html, page = setup_page(self.client, 'dofus3')
        chain = self.chain(page, 'setup-preview-keep-no', 'modern dark')
        value, sheet, _selector = winning(sheets, chain, 'white-space', 1024)
        self.assertEqual(('nowrap', 'modern.css'), (value, sheet))


class TheSheetsLoadInTheOrderTheCascadeCheckAssumesTests(SimpleTestCase):

    def test_the_page_loads_common_then_the_page_sheets_then_responsive_then_modern(self):
        base = io.open(os.path.join(TEMPLATES, 'base.html'), encoding='utf-8').read()
        order = [base.index(marker) for marker in ('chardata/common.css', '{% block css %}',
                                                    'chardata/responsive.css', 'chardata/modern.css')]
        self.assertEqual(sorted(order), order)

    def test_the_setup_page_adds_its_sheets_inside_the_css_block_after_the_forms_sheet(self):
        page = io.open(os.path.join(TEMPLATES, 'projdetails.html'), encoding='utf-8').read()
        block = page[page.index('{% block css %}'):]
        block = block[:block.index('{% endblock %}')]
        self.assertLess(block.index('chardata/forms.css'), block.index('chardata/setup.css'))
