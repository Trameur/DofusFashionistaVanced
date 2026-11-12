# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The modern main column and the inner rows of the navigation bars stop at 1920px and sit in the middle of wider windows, the breakpoint grid widens their gutter at each breakpoint, the band and the bars behind them span the whole window, and the classic shell keeps its two widths."""
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import chain_of, declared, matching, media_applies, stylesheet, winning

HOME = stylesheet('home.css')
RESPONSIVE = stylesheet('responsive.css')
MODERN = stylesheet('modern.css')
NAV = stylesheet('modern-nav.css')
SHEETS = [('home.css', HOME), ('responsive.css', RESPONSIVE), ('modern.css', MODERN), ('modern-nav.css', NAV)]
ROOT = 'html.fm-modern'
CLASSES = ('fm-modern', 'fm-light')
WIDTHS = (375, 760, 761, 768, 901, 1099, 1280, 1439, 1440, 1919, 1920, 2560)
PAGE = (('html', {}), ('body', {'class': 'body-base'}), ('div', {'class': 'add-banner'}), ('div', {'class': 'everything'}))
ROWS = (('nav', 'fm-topnav', 'fm-topnav-in'), ('nav', 'fm-buildbar', 'fm-buildbar-in'))


def token(name, width=2560):
    found = None
    for sheet in (MODERN, NAV):
        for rule in sheet:
            if ROOT in rule['selectors'] and name in rule['declarations'] and media_applies(rule['media'], width):
                found = rule['declarations'][name][0]
    return found


def pixels(value):
    return int(re.fullmatch(r'(\d+)px', value).group(1))


def column():
    return chain_of(PAGE, 'div', {'class': 'maincolumn'}, CLASSES)


def row(bar, inner):
    return chain_of(PAGE + ((bar[0], {'class': bar[1]}),), 'div', {'class': inner}, CLASSES)


def value(chain, prop, width):
    found = winning(SHEETS, chain, prop, width)
    return None if found is None else found[0]


def column_width(width):
    cap = token(re.fullmatch(r'var\((--[\w-]+)\)', value(column(), 'max-width', width)).group(1), width)
    return min(width, pixels(cap))


class TheModernShellIsCappedAt1920Tests(SimpleTestCase):

    def test_the_shell_width_token_is_1920(self):
        self.assertEqual('1920px', token('--fm-maxw'))

    def test_the_main_column_takes_its_maximum_from_that_token_at_every_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                self.assertEqual('var(--fm-maxw)', value(column(), 'max-width', width))
                self.assertEqual('100%', value(column(), 'width', width))
                self.assertEqual('border-box', value(column(), 'box-sizing', width))

    def test_the_main_column_is_centred_by_automatic_margins_at_every_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                found = winning(SHEETS, column(), 'margin', width)
                self.assertEqual(('0 auto', 'modern.css'), found[:2])

    def test_the_main_column_is_exactly_1920_wide_from_1920_up_and_the_window_below(self):
        self.assertEqual([375, 760, 761, 768, 901, 1099, 1280, 1439, 1440, 1919, 1920, 1920],
                         [column_width(width) for width in WIDTHS])

    def test_at_2560_the_page_shows_on_both_sides_of_the_main_column(self):
        self.assertEqual(320, (2560 - column_width(2560)) / 2)

    def test_the_gutter_grows_with_the_breakpoint_grid(self):
        steps = [(width, token('--fm-gutter', width)) for width in (900, 1279, 1280, 1439, 1440, 1919, 1920)]
        self.assertEqual(['20px', '20px', '24px', '24px', '28px', '28px', '32px'], [found for _, found in steps])

    def test_the_gutter_pads_the_main_column_from_761_and_a_phone_gets_16px(self):
        for width in (761, 900, 901, 1280, 1920, 2560):
            with self.subTest(width=width):
                self.assertEqual('18px var(--fm-gutter) 0', value(column(), 'padding', width))
        for width in (375, 520, 760):
            with self.subTest(width=width):
                self.assertEqual('12px 16px 0', value(column(), 'padding', width))

    def test_the_rows_of_both_bars_share_the_cap_the_centring_and_the_gutter_of_the_main_column(self):
        for bar in ROWS:
            chain = row(bar, bar[2])
            for width in WIDTHS:
                with self.subTest(row=bar[2], width=width):
                    self.assertEqual('var(--fm-maxw)', value(chain, 'max-width', width))
                    self.assertEqual('0 auto', value(chain, 'margin', width))
                    self.assertEqual('border-box', value(chain, 'box-sizing', width))
                    padding = value(chain, 'padding', width).split()
                    self.assertEqual('16px' if width <= 760 else 'var(--fm-gutter)', padding[1])

    def test_the_band_and_the_bars_behind_the_rows_span_the_whole_window(self):
        band = chain_of(PAGE[:2], 'div', {'class': 'add-banner'}, CLASSES)
        everything = chain_of(PAGE[:3], 'div', {'class': 'everything'}, CLASSES)
        for width in WIDTHS:
            with self.subTest(width=width):
                self.assertEqual(('100%', 'none', '0'), tuple(value(band, prop, width) for prop in ('width', 'max-width', 'padding')))
                self.assertEqual(('100%', '100%', '0'), tuple(value(everything, prop, width) for prop in ('width', 'max-width', 'margin')))
                for bar in ROWS:
                    self.assertEqual([], [prop for prop in ('max-width', 'width', 'margin', 'padding')
                                          if value(chain_of(PAGE, bar[0], {'class': bar[1]}, CLASSES), prop, width) is not None])

    def test_the_pinned_breakpoints_are_still_there(self):
        medias = {rule['media'] for rule in MODERN}
        for pinned in ('(max-width: 900px)', '(max-width: 520px)',
                       '(min-width:1560px) and (min-height:700px)'):
            self.assertIn(pinned, medias)

    def test_the_classic_shell_keeps_its_two_widths(self):
        self.assertEqual(('1234px', False), declared(HOME, '.add-banner', 'width'))
        self.assertEqual(('1044px', False), declared(HOME, '.everything', 'width'))
        self.assertEqual([], [rule for rule in matching(HOME, '.add-banner') if 'max-width' in rule['declarations']])

    def test_the_modern_shell_does_not_paint_the_classic_theme_slab(self):
        chain = chain_of(PAGE[:3], 'div', {'class': 'everything'}, CLASSES)
        self.assertEqual('transparent', winning(SHEETS, chain, 'background-color', 1920)[0])
