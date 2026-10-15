# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The modern shell stops at 1920px and sits in the middle of wider windows, the breakpoint grid widens its gutter step by step, and the classic shell keeps its two widths."""
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import chain_of, declared, matching, media_applies, stylesheet, winning

HOME = stylesheet('home.css')
RESPONSIVE = stylesheet('responsive.css')
MODERN = stylesheet('modern.css')
SHEETS = [('home.css', HOME), ('responsive.css', RESPONSIVE), ('modern.css', MODERN)]
ROOT = 'html.fm-modern'
WIDTHS = (375, 768, 901, 1099, 1280, 1439, 1440, 1919, 1920, 2560)


def token(name, width=2560):
    found = None
    for rule in MODERN:
        if ROOT in rule['selectors'] and name in rule['declarations'] and media_applies(rule['media'], width):
            found = rule['declarations'][name][0]
    return found


def pixels(value):
    return int(re.fullmatch(r'(\d+)px', value).group(1))


def shell(width):
    classes = ('fm-modern', 'fm-light')
    chain = chain_of((('html', {}), ('body', {'class': 'body-base'})), 'div', {'class': 'add-banner'}, classes)
    limit = winning(SHEETS, chain, 'max-width', width)
    return limit, chain


def shell_width(width):
    limit, _ = shell(width)
    cap = token(re.fullmatch(r'var\((--[\w-]+)\)', limit[0]).group(1), width)
    return min(width, pixels(cap))


class TheModernShellIsCappedAt1920Tests(SimpleTestCase):

    def test_the_shell_width_token_is_1920(self):
        self.assertEqual('1920px', token('--fm-maxw'))

    def test_the_shell_takes_its_maximum_from_that_token_at_every_width(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                limit, _ = shell(width)
                self.assertEqual('var(--fm-maxw)', limit[0])

    def test_the_shell_is_centred_by_automatic_margins(self):
        _, chain = shell(2560)
        self.assertEqual('0 auto', winning(SHEETS, chain, 'margin', 2560)[0])

    def test_the_shell_is_exactly_1920_wide_from_1920_up_and_the_window_below(self):
        self.assertEqual([375, 768, 901, 1099, 1280, 1439, 1440, 1919, 1920, 1920],
                         [shell_width(width) for width in WIDTHS])

    def test_at_2560_the_page_shows_on_both_sides_of_the_shell(self):
        side = (2560 - shell_width(2560)) / 2
        self.assertEqual(320, side)

    def test_the_gutter_grows_with_the_breakpoint_grid(self):
        steps = [(width, token('--fm-gutter', width)) for width in (900, 1279, 1280, 1439, 1440, 1919, 1920)]
        self.assertEqual([('20px'), '20px', '24px', '24px', '28px', '28px', '32px'], [value for _, value in steps])

    def test_the_gutter_pads_the_shell_from_901_and_the_pinned_phone_padding_stays(self):
        _, chain = shell(901)
        self.assertEqual('0 var(--fm-gutter)', winning(SHEETS, chain, 'padding', 901)[0])
        self.assertEqual('0 12px', winning(SHEETS, chain, 'padding', 900)[0])
        self.assertEqual('0 8px', winning(SHEETS, chain, 'padding', 520)[0])

    def test_the_pinned_breakpoints_are_still_there(self):
        medias = {rule['media'] for rule in MODERN}
        for pinned in ('(max-width: 900px)', '(min-width: 901px) and (max-width: 1099px)', '(max-width: 520px)',
                       '(min-width:1560px) and (min-height:700px)'):
            self.assertIn(pinned, medias)

    def test_the_classic_shell_keeps_its_two_widths(self):
        self.assertEqual(('1234px', False), declared(HOME, '.add-banner', 'width'))
        self.assertEqual(('1044px', False), declared(HOME, '.everything', 'width'))
        self.assertEqual([], [rule for rule in matching(HOME, '.add-banner') if 'max-width' in rule['declarations']])

    def test_the_modern_shell_does_not_paint_the_classic_theme_slab(self):
        chain = chain_of((('html', {}), ('body', {'class': 'body-base'}), ('div', {'class': 'add-banner'})), 'div', {'class': 'everything'},
                         ('fm-modern', 'fm-light'))
        self.assertEqual('transparent', winning(SHEETS, chain, 'background-color', 1920)[0])
