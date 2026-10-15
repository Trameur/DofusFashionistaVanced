# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Atelier palette and tokens are declared under the three modern selectors, in the forms the stylesheet readers understand, and every text and interface pair clears its WCAG threshold on every surface."""
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import contrast, declared, rgb, stylesheet

MODERN = stylesheet('modern.css')

COMMON = 'html.fm-modern'
LIGHT = 'html.fm-modern.fm-light'
DARK = 'html.fm-modern.fm-dark'
FALLBACK = 'html.fm-modern:not(.fm-light):not(.fm-dark)'

PER_THEME = ('--fm-bg', '--fm-bg-2', '--fm-surface', '--fm-surface-2', '--fm-surface-3', '--fm-text', '--fm-head',
             '--fm-muted', '--fm-accent-text', '--fm-seam', '--fm-frame-gold', '--fm-link-hover')
SHARED = ('--fm-tape', '--fm-tape-tick', '--fm-tape-text', '--fm-btn-gold', '--fm-accent', '--fm-font-display',
          '--fm-font-body', '--fm-font', '--fm-measure') + tuple('--fm-space-%d' % step for step in range(1, 9))
SURFACES = ('--fm-bg', '--fm-bg-2', '--fm-surface', '--fm-surface-2', '--fm-surface-3')
TEXT = ('--fm-text', '--fm-head', '--fm-muted', '--fm-accent-text', '--fm-link-hover')
COLOUR = re.compile(r'#[0-9a-fA-F]{6}|rgba?\([^)]*\)')

EXPECTED_LIGHT = {'--fm-bg': '#ece3cf', '--fm-surface': '#f7f0e1', '--fm-text': '#2a2017', '--fm-accent-text': '#7a5212',
                  '--fm-seam': '#8f6f45', '--fm-frame-gold': '#8c671c', '--fm-link-hover': '#5c3d0a'}
EXPECTED_DARK = {'--fm-bg': '#14100c', '--fm-surface': '#1e1913', '--fm-text': '#ece3d0', '--fm-accent-text': '#e0bd5f',
                 '--fm-seam': '#a88a4e', '--fm-frame-gold': '#c9a24a'}


def value(selector, name):
    found = declared(MODERN, selector, name)
    return found[0] if found else None


def colour(selector, name):
    raw = value(selector, name)
    reference = re.fullmatch(r'var\((--[\w-]+)\)', raw or '')
    if reference:
        return colour(selector, reference.group(1))
    return rgb(raw)[0]


class EveryAtelierTokenIsDeclaredTests(SimpleTestCase):

    def test_each_per_theme_token_exists_under_the_light_the_dark_and_the_fallback_selectors(self):
        for selector in (LIGHT, DARK, FALLBACK):
            with self.subTest(selector=selector):
                missing = [name for name in PER_THEME if value(selector, name) is None]
                self.assertEqual([], missing)

    def test_each_shared_token_exists_under_the_modern_selector(self):
        self.assertEqual([], [name for name in SHARED if value(COMMON, name) is None])

    def test_the_colour_tokens_are_hex_or_rgb_the_way_the_stylesheet_readers_need(self):
        for selector in (LIGHT, DARK, FALLBACK, COMMON):
            for name in PER_THEME + SHARED:
                raw = value(selector, name)
                if raw is None or not name.startswith(('--fm-bg', '--fm-surface', '--fm-text', '--fm-head', '--fm-muted',
                                                       '--fm-accent-text', '--fm-seam', '--fm-frame', '--fm-tape',
                                                       '--fm-btn')):
                    continue
                with self.subTest(selector=selector, name=name):
                    self.assertRegex(raw, COLOUR)

    def test_the_palette_tokens_hold_the_atelier_colours(self):
        for expected, selector in ((EXPECTED_LIGHT, LIGHT), (EXPECTED_DARK, DARK)):
            for name, wanted in expected.items():
                with self.subTest(selector=selector, name=name):
                    self.assertEqual(wanted, value(selector, name))

    def test_the_fallback_selector_carries_the_light_palette(self):
        for name in EXPECTED_LIGHT:
            with self.subTest(name=name):
                self.assertEqual(value(LIGHT, name), value(FALLBACK, name))

    def test_the_accent_stays_where_the_setup_tests_pin_it(self):
        self.assertEqual('#e3bf4d', value(COMMON, '--fm-accent'))
        self.assertEqual('rgba(227,191,77,.45)', value(COMMON, '--fm-accent-line'))

    def test_the_gap_token_equals_the_fourth_spacing_step(self):
        self.assertEqual(value(COMMON, '--fm-gap'), value(COMMON, '--fm-space-4'))

    def test_the_spacing_steps_are_the_atelier_pixel_sizes(self):
        self.assertEqual(['4px', '8px', '12px', '16px', '24px', '32px', '48px', '64px'],
                         [value(COMMON, '--fm-space-%d' % step) for step in range(1, 9)])

    def test_the_font_stacks_name_the_self_hosted_families_first_and_a_system_fallback_last(self):
        self.assertTrue(value(COMMON, '--fm-font-display').startswith('"IM Fell English SC",'))
        self.assertTrue(value(COMMON, '--fm-font-display').endswith('serif'))
        self.assertTrue(value(COMMON, '--fm-font-body').startswith('Barlow,'))
        self.assertTrue(value(COMMON, '--fm-font-body').endswith('sans-serif'))
        self.assertEqual('var(--fm-font-body)', value(COMMON, '--fm-font'))


class EveryPairClearsItsThresholdTests(SimpleTestCase):

    def test_text_tokens_reach_4_5_to_1_on_every_surface_in_both_themes(self):
        for selector in (LIGHT, DARK, FALLBACK):
            for name in TEXT:
                for surface in SURFACES:
                    with self.subTest(selector=selector, name=name, surface=surface):
                        self.assertGreaterEqual(contrast(colour(selector, name), colour(selector, surface)), 4.5)

    def test_the_seam_and_the_frame_gold_reach_3_to_1_on_every_surface_in_both_themes(self):
        for selector in (LIGHT, DARK, FALLBACK):
            for name in ('--fm-seam', '--fm-frame-gold'):
                for surface in SURFACES:
                    with self.subTest(selector=selector, name=name, surface=surface):
                        self.assertGreaterEqual(contrast(colour(selector, name), colour(selector, surface)), 3.0)

    def test_the_tape_text_reads_on_the_tape_and_on_the_gold_button(self):
        text = rgb(value(COMMON, '--fm-tape-text'))[0]
        for background in ('--fm-tape', '--fm-btn-gold'):
            with self.subTest(background=background):
                self.assertGreaterEqual(contrast(text, rgb(value(COMMON, background))[0]), 7.0)

    def test_the_tick_marks_stand_out_from_the_tape(self):
        self.assertGreaterEqual(contrast(rgb(value(COMMON, '--fm-tape-tick'))[0], rgb(value(COMMON, '--fm-tape'))[0]), 7.0)

    def test_the_link_hover_is_darker_than_the_link_in_the_light_theme_and_lighter_in_the_dark_one(self):
        self.assertLess(sum(colour(LIGHT, '--fm-link-hover')), sum(colour(LIGHT, '--fm-accent-text')))
        self.assertGreater(sum(colour(DARK, '--fm-link-hover')), sum(colour(DARK, '--fm-accent-text')))
