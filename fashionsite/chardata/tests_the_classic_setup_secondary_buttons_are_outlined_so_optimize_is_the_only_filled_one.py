# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""In the classic design the secondary doors and the panel buttons of /setup/ are outlined with no fill, and Optimize keeps the fill the site gives its main buttons in both themes."""
from django.test import SimpleTestCase, TestCase

from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import setup_page
from chardata.tests_the_setup_stylesheet_support import declared, stylesheet
from fashionistapulp.structure import set_current_game_version

SETUP = stylesheet('setup.css')
LIGHT_SITE = stylesheet('common_lighttheme.css')
DARK_SITE = stylesheet('common_darktheme.css')

DARK = 'html:not(.fm-modern):not(.fm-light)'
LIGHT = 'html.fm-light:not(.fm-modern)'
DOORS = '.setup-doors .setup-secondary'
PANEL = '.setup-preview button.button-thin-foreground'
FILL = ('background', 'background-color', 'background-image')


class TheSecondariesAreOutlinedWithNoFillTests(SimpleTestCase):

    def test_both_button_kinds_are_transparent_in_both_classic_themes(self):
        for theme in (DARK, LIGHT):
            for button in (DOORS, PANEL):
                with self.subTest(theme=theme, button=button):
                    self.assertEqual(('transparent', False),
                                     declared(SETUP, '%s %s' % (theme, button), 'background'))

    def test_both_button_kinds_draw_a_one_pixel_solid_outline_in_both_classic_themes(self):
        for theme in (DARK, LIGHT):
            for button in (DOORS, PANEL):
                with self.subTest(theme=theme, button=button):
                    border = declared(SETUP, '%s %s' % (theme, button), 'border')
                    self.assertIsNotNone(border)
                    self.assertTrue(border[0].startswith('1px solid #'), border)

    def test_the_light_outline_and_text_are_the_fill_the_site_gives_its_buttons(self):
        site = declared(LIGHT_SITE, '.button-generic', 'background')[0].lower()
        for button in (DOORS, PANEL):
            with self.subTest(button=button):
                rule = '%s %s' % (LIGHT, button)
                self.assertEqual(site, declared(SETUP, rule, 'color')[0].lower())
                self.assertEqual('1px solid ' + site, declared(SETUP, rule, 'border')[0].lower())

    def test_the_dark_text_is_the_text_the_site_gives_its_buttons(self):
        site = declared(DARK_SITE, '.button-generic', 'color')[0].lower()
        for button in (DOORS, PANEL):
            with self.subTest(button=button):
                self.assertEqual(site, declared(SETUP, '%s %s' % (DARK, button), 'color')[0].lower())

    def test_the_dark_outline_is_a_mid_grey_that_shows_on_the_dark_page(self):
        for button in (DOORS, PANEL):
            with self.subTest(button=button):
                self.assertEqual('1px solid #9a9a9a',
                                 declared(SETUP, '%s %s' % (DARK, button), 'border')[0].lower())


class OptimizeIsTheOnlyFilledButtonTests(SimpleTestCase):

    def test_no_setup_rule_gives_the_primary_door_a_colour_of_its_own(self):
        painted = [(rule['selectors'], prop) for rule in SETUP
                   if any('.setup-primary' in selector for selector in rule['selectors'])
                   for prop in rule['declarations']
                   if prop in FILL or prop in ('color', 'border', 'border-color')]
        self.assertEqual([], painted)

    def test_no_classic_setup_rule_fills_a_button(self):
        filled = [(rule['selectors'], prop, rule['declarations'][prop]) for rule in SETUP
                  for prop in FILL if prop in rule['declarations']
                  and any(':not(.fm-modern)' in selector for selector in rule['selectors'])
                  and rule['declarations'][prop][0] != 'transparent']
        self.assertEqual([], filled)

    def test_the_site_fills_the_primary_class_in_both_themes_and_it_reads_white_on_it(self):
        self.assertEqual('#3D200D', declared(LIGHT_SITE, '.button-generic', 'background')[0].upper())
        self.assertEqual('#333333', declared(DARK_SITE, '.button-generic', 'background')[0].upper())
        for site in (LIGHT_SITE, DARK_SITE):
            self.assertEqual('#FFFFFF', declared(site, '.button-generic', 'color')[0].upper())


class TheMarkupTheRulesTargetIsTheMarkupThePageDrawsTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_doors_and_the_panel_buttons_carry_the_classes_the_rules_select(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                submits = [(attrs, ancestors) for attrs, ancestors in page.find('input')
                           if attrs.get('type') == 'submit'
                           and page.inside(ancestors, 'div', 'submit-mode')]
                visible = [attrs for attrs, _ in submits
                           if 'setup-default-door' not in attrs.get('class', '').split()]
                primary = [attrs for attrs in visible if 'setup-primary' in attrs['class'].split()]
                secondary = [attrs for attrs in visible if 'setup-secondary' in attrs['class'].split()]
                self.assertEqual(['optimize'], [attrs['name'] for attrs in primary])
                self.assertIn('button-generic', primary[0]['class'].split())
                self.assertEqual(['byhand', 'wizard'], [attrs['name'] for attrs in secondary])
                panel = [attrs['id'] for attrs, ancestors in page.find('button')
                         if 'button-thin-foreground' in attrs.get('class', '').split()
                         and page.inside(ancestors, 'aside', 'setup-preview')]
                self.assertEqual(['setup-preview-reset', 'setup-preview-keep-yes',
                                  'setup-preview-keep-no'], panel)
