# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""From 1280px the control row stays on one line, the banner band is 132px from 761px and follows the window on a phone, and the band plus one row of the navigation bar stay under 220px."""
import re

from django.test import SimpleTestCase

from chardata.tests_the_phone_band_is_the_right_part_of_the_band import band_height
from chardata.tests_the_setup_stylesheet_support import chain_of, declared, read_css, stylesheet, winning

MODERN = stylesheet('modern.css')
NAV = stylesheet('modern-nav.css')
SHEETS = [('home.css', stylesheet('home.css')), ('responsive.css', stylesheet('responsive.css')), ('modern.css', MODERN),
          ('modern-nav.css', NAV)]
ROOT = 'html.fm-modern'
ANCESTORS = (('html', {}), ('body', {'class': 'body-base'}), ('div', {'class': 'add-banner'}), ('div', {'class': 'everything'}))
CLASSES = ('fm-modern', 'fm-light')


def row_chain():
    return chain_of(ANCESTORS, 'div', {'class': 'space header-controls'}, CLASSES)


def banner_chain():
    return chain_of(ANCESTORS, 'div', {'class': 'banner'}, CLASSES)


def pixels(found):
    return int(re.fullmatch(r'(\d+)px', found).group(1))


def nav_row_height(width):
    bar = chain_of(ANCESTORS, 'nav', {'class': 'fm-topnav'}, CLASSES)
    row = chain_of(ANCESTORS + (('nav', {'class': 'fm-topnav'}),), 'div', {'class': 'fm-topnav-in'}, CLASSES)
    border = winning(SHEETS, bar, 'border-bottom', width)[0].split()[0]
    return pixels(winning(SHEETS, row, 'min-height', width)[0]) + pixels(border)


def row_height():
    padding = [int(part.rstrip('px')) for part in winning(SHEETS, row_chain(), 'padding', 1920)[0].split()]
    pill = int(declared(MODERN, 'html.fm-modern .version-selector', 'height')[0].rstrip('px'))
    return padding[0] + pill + padding[2]


class TheControlRowIsOneLineFrom1280Tests(SimpleTestCase):

    def test_the_row_wraps_below_1280_and_never_wraps_from_1280_up(self):
        self.assertEqual(['wrap', 'wrap', 'nowrap', 'nowrap', 'nowrap', 'nowrap'],
                         [winning(SHEETS, row_chain(), 'flex-wrap', width)[0] for width in (601, 1279, 1280, 1440, 1920, 2560)])

    def test_the_row_does_not_break_its_labels_from_1280_up(self):
        self.assertEqual('nowrap', winning(SHEETS, row_chain(), 'white-space', 1280)[0])
        self.assertIsNone(winning(SHEETS, row_chain(), 'white-space', 1279))

    def test_an_overlong_row_cannot_overflow_off_the_left_edge(self):
        self.assertEqual('safe flex-end', winning(SHEETS, row_chain(), 'justify-content', 1280)[0])
        login = chain_of(ANCESTORS + (('div', {'class': 'space header-controls'}),), 'div', {'class': 'login'}, CLASSES)
        self.assertEqual('0', winning(SHEETS, login, 'min-width', 1280)[0])
        self.assertEqual('ellipsis', winning(SHEETS, login, 'text-overflow', 1280)[0])

    def test_the_banner_home_link_has_an_inset_focus_ring_the_band_cannot_clip(self):
        raw = read_css('modern.css')
        self.assertIn('html.fm-modern .banner a:focus-visible{ box-shadow:inset 0 0 0 3px var(--fm-accent-text); }', raw)
        self.assertIn('html.fm-modern .version-link:focus-visible{ box-shadow:inset 0 0 0 2px var(--fm-accent-text); }', raw)
        self.assertIn('html.fm-modern .version-link.active:focus-visible{ box-shadow:inset 0 0 0 2px #2a2010; }', raw)

    def test_the_row_is_a_flex_row_at_those_widths(self):
        for width in (1280, 1920, 2560):
            self.assertEqual('flex', winning(SHEETS, row_chain(), 'display', width)[0])


class TheBannerBandIsLowTests(SimpleTestCase):

    def test_the_band_is_132_pixels_from_761_up(self):
        for width in (761, 901, 1280, 1440, 1536, 1920, 2560):
            with self.subTest(width=width):
                self.assertEqual(132, band_height(width))

    def test_on_a_phone_the_band_follows_the_window_between_84_and_132_pixels(self):
        heights = [band_height(width) for width in range(320, 761)]
        self.assertEqual(84, min(heights))
        self.assertLess(max(heights), 132)
        self.assertEqual(sorted(heights), heights)

    def test_the_banner_takes_the_band_height_at_every_width(self):
        for width in (375, 760, 761, 900, 901, 1920, 2560):
            with self.subTest(width=width):
                self.assertEqual('var(--fm-band-h)', winning(SHEETS, banner_chain(), 'height', width)[0])

    def test_the_banner_has_no_margin_at_every_width(self):
        for width in (375, 760, 901, 1920, 2560):
            with self.subTest(width=width):
                self.assertEqual('0', winning(SHEETS, banner_chain(), 'margin', width)[0])

    def test_the_band_and_one_row_of_the_navigation_bar_stay_under_220_pixels(self):
        self.assertEqual(59, nav_row_height(1920))
        for width in (1280, 1440, 1536, 1920, 2560):
            with self.subTest(width=width):
                self.assertLessEqual(band_height(width) + nav_row_height(width), 220)

    def test_the_row_height_is_what_the_stylesheet_gives_it(self):
        self.assertEqual(54, row_height())
