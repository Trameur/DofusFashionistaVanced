# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A classic-only rule skips the enhanced classic design as well as the new one, and only the rules that hide new markup still skip the new design alone."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import (
    CLASSIC_ONLY, STATIC, chain_of, enhanced_sheets, is_classic_only, parse, setup_sheets, winning)

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
HIDER = re.compile(r'^html:not\(\.fm-modern\) \.fm-[\w-]+$')
HIDING = ({'display': ('none', True)}, {'display': ('none', False)}, {'display': ('contents', False)})
DOOR = ((('html', {}), ('body', {'class': 'body-base'}), ('form', {'id': 'theform'}),
         ('div', {'id': 'submit-mode', 'class': 'setup-doors'}), ('div', {'class': 'setup-doors-secondary'})),
        'input', {'class': 'submit-button button-thin-foreground setup-secondary', 'type': 'submit'})


def sheet_rules():
    for folder, _, names in os.walk(STATIC):
        for name in names:
            if name.endswith('.css'):
                with io.open(os.path.join(folder, name), encoding='utf-8', errors='replace') as handle:
                    text = handle.read()
                if 'fm-modern' in text:
                    yield name, parse(re.sub(r'/\*.*?\*/', '', text, flags=re.S))


def template_rules():
    for folder, _, names in os.walk(TEMPLATES):
        for name in names:
            if name.endswith('.html'):
                with io.open(os.path.join(folder, name), encoding='utf-8') as handle:
                    text = handle.read()
                for style in re.findall(r'<style[^>]*>(.*?)</style>', text, re.S):
                    if 'fm-modern' in style:
                        yield name, parse(re.sub(r'/\*.*?\*/', '', style, flags=re.S))


def negating(rules):
    return [(selector, rule['declarations']) for rule in rules for selector in rule['selectors'] if ':not(.fm-modern' in selector]


class EveryClassicOnlySelectorUsesTheListFormTests(SimpleTestCase):

    def check(self, found):
        seen = 0
        for name, rules in found:
            for selector, declarations in negating(rules):
                seen += 1
                with self.subTest(source=name, selector=selector):
                    if HIDER.match(selector):
                        self.assertIn(declarations, HIDING)
                    else:
                        self.assertTrue(is_classic_only(selector))
        return seen

    def test_every_sheet_selector_is_a_hider_or_skips_both_designs(self):
        self.assertGreater(self.check(sheet_rules()), 30)

    def test_every_inline_page_style_selector_is_a_hider_or_skips_both_designs(self):
        self.assertGreaterEqual(self.check(template_rules()), 1)

    def test_the_list_form_is_what_the_helper_recognises(self):
        self.assertEqual(':not(.fm-modern, .fm-enhanced)', CLASSIC_ONLY)
        self.assertFalse(is_classic_only('html:not(.fm-modern) .setup-preview'))


class TheEngineGivesEachDesignItsOwnDoorOutlineTests(SimpleTestCase):

    def door_border(self, classes, sheets):
        ancestors, tag, attrs = DOOR
        return winning(sheets, chain_of(ancestors, tag, attrs, classes), 'border', 1440)

    def test_the_classic_light_door_gets_the_classic_outline(self):
        value, sheet, selector = self.door_border(('fm-light',), enhanced_sheets())
        self.assertEqual(('setup.css', 'html.fm-light:not(.fm-modern, .fm-enhanced) .setup-doors .setup-secondary'), (sheet, selector))
        self.assertEqual('1px solid #3d200d', value.lower())

    def test_the_enhanced_light_door_gets_the_production_outline_twin(self):
        value, sheet, selector = self.door_border(('fm-enhanced', 'fm-light'), enhanced_sheets())
        self.assertEqual(('setup.css', 'html.fm-enhanced .setup-doors input.setup-secondary'), (sheet, selector))
        colour = winning(enhanced_sheets(), chain_of(DOOR[0], DOOR[1], DOOR[2], ('fm-enhanced', 'fm-light')), 'border-color', 1440)
        self.assertEqual(('setup.css', 'html.fm-enhanced:not(.fm-dark) .setup-doors input.setup-secondary'), colour[1:])

    def test_the_enhanced_door_never_gets_a_classic_only_rule(self):
        for classes in (('fm-enhanced', 'fm-light'), ('fm-enhanced', 'fm-dark')):
            for prop in ('border', 'background', 'color'):
                found = winning(enhanced_sheets(), chain_of(DOOR[0], DOOR[1], DOOR[2], classes), prop, 1440)
                self.assertIsNotNone(found, (classes, prop))
                self.assertFalse(is_classic_only(found[2]), (classes, prop, found))

    def test_the_new_design_door_is_unchanged_by_the_enhanced_sheet(self):
        for classes in (('fm-modern', 'fm-light'), ('fm-modern', 'fm-dark')):
            for prop in ('border', 'background', 'color'):
                chain = chain_of(DOOR[0], DOOR[1], DOOR[2], classes)
                self.assertEqual(winning(setup_sheets(), chain, prop, 1440), winning(enhanced_sheets(), chain, prop, 1440))
