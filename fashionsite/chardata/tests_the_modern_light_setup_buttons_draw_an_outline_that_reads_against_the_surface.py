# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""In the modern design the secondary doors and the panel buttons of /setup/ draw an outline of at least 3:1 against their surface in the light theme, and the dark theme and the shared accent line stay as they were."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import (
    contrast, declared, flatten, matching, rgb, stylesheet)

MODERN = stylesheet('modern.css')
SETUP = stylesheet('setup.css')

DOORS = '.setup-doors input.setup-secondary'
PANEL = '.setup-preview button.button-thin-foreground'
LIGHT_TOKENS = ('html.fm-modern.fm-light', 'html.fm-modern:not(.fm-light):not(.fm-dark)')
DARK_TOKENS = 'html.fm-modern.fm-dark'


def token(selector, name):
    value = declared(MODERN, selector, name)
    return value[0] if value else None


class TheLightOutlineReadsAgainstTheSurfaceTests(SimpleTestCase):

    def test_the_outline_of_both_button_kinds_is_the_text_accent_token(self):
        for button in (DOORS, PANEL):
            with self.subTest(button=button):
                self.assertEqual(('var(--fm-accent-text)', True),
                                 declared(SETUP, 'html.fm-modern:not(.fm-dark) ' + button,
                                          'border-color'))

    def test_the_outline_is_at_least_3_to_1_on_the_surface_and_on_the_page_in_both_light_states(self):
        for selector in LIGHT_TOKENS:
            outline = rgb(token(selector, '--fm-accent-text'))[0]
            for backdrop in ('--fm-surface', '--fm-bg'):
                with self.subTest(selector=selector, backdrop=backdrop):
                    ratio = contrast(outline, rgb(token(selector, backdrop))[0])
                    self.assertGreaterEqual(ratio, 3.0, ratio)

    def test_both_button_kinds_fill_with_the_surface_so_the_outline_is_read_against_it(self):
        self.assertEqual(('var(--fm-surface)', True),
                         declared(SETUP, 'html.fm-modern ' + DOORS, 'background'))
        self.assertEqual(('var(--fm-surface)', True),
                         declared(MODERN, 'html.fm-modern .button-thin-foreground', 'background'))
        self.assertEqual(('var(--fm-surface)', False),
                         declared(SETUP, 'html.fm-modern .setup-preview', 'background'))

    def test_the_text_of_both_button_kinds_is_the_outline_colour(self):
        self.assertEqual(('var(--fm-accent-text)', True),
                         declared(SETUP, 'html.fm-modern ' + DOORS, 'color'))
        self.assertEqual(('var(--fm-accent-text)', True),
                         declared(MODERN, 'html.fm-modern .button-thin-foreground', 'color'))

    def test_the_light_override_names_only_the_two_button_kinds_and_sets_only_the_border_colour(self):
        overrides = [rule for rule in SETUP if rule['media'] is None
                     and any(selector.startswith('html.fm-modern:not(.fm-dark)')
                             for selector in rule['selectors'])]
        self.assertEqual(1, len(overrides))
        self.assertEqual({'html.fm-modern:not(.fm-dark) ' + DOORS,
                          'html.fm-modern:not(.fm-dark) ' + PANEL},
                         set(overrides[0]['selectors']))
        self.assertEqual({'border-color'}, set(overrides[0]['declarations']))


class TheDarkThemeAndTheSharedLineStayAsTheyWereTests(SimpleTestCase):

    def test_the_accent_line_token_is_the_one_every_other_modern_page_uses(self):
        self.assertEqual('rgba(227,191,77,.45)', token('html.fm-modern', '--fm-accent-line'))

    def test_the_setup_stylesheet_does_not_redefine_a_modern_token(self):
        redefined = sorted(prop for rule in SETUP for prop in rule['declarations']
                           if prop.startswith('--fm-'))
        self.assertEqual([], redefined)

    def test_the_secondary_door_keeps_the_accent_line_as_its_outline_in_the_dark_theme(self):
        self.assertEqual(('1px solid var(--fm-accent-line)', True),
                         declared(SETUP, 'html.fm-modern ' + DOORS, 'border'))

    def test_no_selector_restyles_the_dark_outline(self):
        self.assertEqual([], matching(SETUP, 'html.fm-modern.fm-dark ' + DOORS))
        self.assertEqual([], matching(SETUP, 'html.fm-modern.fm-dark ' + PANEL))

    def test_the_dark_outline_stays_at_least_3_to_1_on_the_dark_surface(self):
        surface = token(DARK_TOKENS, '--fm-surface')
        line = token('html.fm-modern', '--fm-accent-line')
        self.assertGreaterEqual(contrast(flatten(line, surface), rgb(surface)[0]), 3.0)
