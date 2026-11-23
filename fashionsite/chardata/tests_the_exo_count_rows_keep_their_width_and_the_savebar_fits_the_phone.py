# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The count inputs are capped in both Classic designs only, the Dracorune and transcendence rows alone align, and the Atelier save bar fits a phone."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import CLASSIC_ONLY, parse, read_css

ROW = '.setup-more-count:not(:has(.setup-more-icon))'


def rules_of(name):
    return parse(read_css(name))


class TheCountInputIsCappedInBothClassicDesignsOnlyTests(SimpleTestCase):

    def capping(self):
        return [rule for rule in rules_of('responsive.css')
                if rule['declarations'].get('width') and any('exo-count-input' in s for s in rule['selectors'])]

    def test_a_phone_rule_caps_the_count_input(self):
        self.assertTrue([r for r in self.capping() if r['media'] and 'max-width' in r['media']])

    def test_every_capping_selector_skips_the_atelier(self):
        for rule in self.capping():
            for selector in rule['selectors']:
                with self.subTest(selector=selector):
                    self.assertTrue(selector.startswith('html' + CLASSIC_ONLY) or selector.startswith('html.fm-enhanced'))


class OnlyTheDracoruneAndTranscendenceRowsAlignTests(SimpleTestCase):

    def aligning(self):
        return [(rule, selector) for rule in rules_of('setup.css') for selector in rule['selectors']
                if '.setup-more-count' in selector and ('align-items' in rule['declarations'] or 'flex' in rule['declarations'])
                and CLASSIC_ONLY in selector]

    def test_the_alignment_rules_exist(self):
        self.assertGreaterEqual(len(self.aligning()), 2)

    def test_they_leave_the_rows_that_carry_an_icon_alone(self):
        for _, selector in self.aligning():
            with self.subTest(selector=selector):
                self.assertIn(ROW, selector)

    def test_they_apply_from_a_desktop_width_only(self):
        for rule, selector in self.aligning():
            with self.subTest(selector=selector):
                self.assertIn('min-width', rule['media'] or '')


class TheAtelierSaveBarFitsAPhoneTests(SimpleTestCase):

    def test_both_atelier_sheets_pull_the_bar_back_inside_the_viewport(self):
        for name in ('modern.css', 'modern-rest.css'):
            found = [rule for rule in rules_of(name) if 'html.fm-modern .tunnel-atelier .fm-savebar' in rule['selectors']
                     and rule['media'] and 'max-width:760px' in rule['media'].replace(' ', '')]
            with self.subTest(sheet=name):
                self.assertTrue(found)
                self.assertEqual(found[-1]['declarations'].get('margin-inline'), ('-16px', False))
