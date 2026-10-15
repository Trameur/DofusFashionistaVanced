# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A side rail is hidden or sits wholly outside the 1920px shell at every width, the guard comes after the pinned rail rules, and long text keeps its measure."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, chain_of, declared, parse, read_css, rule_order, stylesheet, winning

MODERN = stylesheet('modern.css')
SHELL = 1920
WIDTHS = (1280, 1440, 1559, 1560, 1859, 1860, 1920, 2000, 2299, 2300, 2400, 2559, 2560, 3000, 3840)
ANCESTORS = (('html', {}), ('body', {'class': 'body-base'}))
TALL = re.compile(r'\s+and\s+\(min-height:700px\)')


def tall(rules):
    return [dict(rule, media=TALL.sub('', rule['media']) if rule['media'] else None) for rule in rules]


TALL_MODERN = tall(MODERN)
SHEETS = [('modern.css', TALL_MODERN)]


SCROLLBAR = 17


def rail(side, width):
    chain = chain_of(ANCESTORS, 'div', {'class': 'fm-ad fm-ad-rail fm-ad-rail-%s' % side}, ('fm-modern', 'fm-light'))
    if winning(SHEETS, chain, 'display', width)[0] == 'none':
        return None
    size = int(winning(SHEETS, chain, 'width', width)[0].rstrip('px'))
    prop = 'left' if side == 'left' else 'right'
    offset = int(re.fullmatch(r'calc\(50% - (\d+)px\)', winning(SHEETS, chain, prop, width)[0]).group(1))
    layout = width - SCROLLBAR
    near = layout / 2.0 - offset
    return (near, near + size) if side == 'left' else (layout - near - size, layout - near)


class NoRailOverlapsTheShellTests(SimpleTestCase):

    def test_at_every_width_a_visible_rail_lies_between_the_window_edge_and_the_shell(self):
        for width in WIDTHS:
            layout = width - SCROLLBAR
            shell_left = (layout - min(layout, SHELL)) / 2.0
            for side in ('left', 'right'):
                with self.subTest(width=width, side=side):
                    found = rail(side, width)
                    if found is None:
                        continue
                    near, far = found
                    if side == 'left':
                        self.assertGreaterEqual(near, 0)
                        self.assertLessEqual(far, shell_left)
                    else:
                        self.assertGreaterEqual(near, layout - shell_left)
                        self.assertLessEqual(far, layout)

    def test_the_rails_are_hidden_below_2300_and_shown_from_2300_up(self):
        self.assertEqual([None, None, None, None], [rail('left', width) for width in (1560, 1860, 2000, 2299)])
        self.assertEqual([True, True, True], [rail('left', width) is not None for width in (2300, 2560, 3840)])

    def test_a_rail_is_narrower_than_the_room_beside_the_shell(self):
        for width in (2300, 2400, 2559, 2560, 3000):
            near, far = rail('left', width)
            self.assertGreater(far - near, 0)
            self.assertGreaterEqual((width - SCROLLBAR - SHELL) / 2.0 - far, 8)

    def test_the_guard_comes_after_the_pinned_rail_rules(self):
        raw = read_css('modern.css')
        pinned = raw.index('@media (min-width:1860px) and (min-height:700px)')
        guard = raw.index('@media (max-width:2299px)')
        self.assertLess(pinned, guard)
        self.assertLess(raw.index('\n.fm-ad-rail{ display:none; }'), raw.index('@media (min-width:1560px) and (min-height:700px)'))

    def test_the_pinned_rail_rules_are_not_rewritten(self):
        raw = read_css('modern.css')
        for text in ('left:calc(50% - 776px)', 'right:calc(50% - 776px)', 'left:calc(50% - 920px)', 'right:calc(50% - 920px)',
                     'display:block; position:fixed; top:96px; width:160px; margin:0; z-index:0;'):
            self.assertEqual(1, raw.count(text), text)

    def test_every_guard_selector_is_prefixed(self):
        guard = [rule for rule in MODERN if rule['media'] and ('2299px' in rule['media'] or '2300px' in rule['media']
                                                                or '2560px' in rule['media'])]
        self.assertTrue(guard)
        for rule in guard:
            for selector in rule['selectors']:
                self.assertTrue(selector.startswith('html.fm-modern '), selector)


class LongTextKeepsItsMeasureTests(SimpleTestCase):

    def test_the_measure_token_is_72ch(self):
        self.assertEqual('72ch', declared(MODERN, 'html.fm-modern', '--fm-measure')[0])

    def test_long_text_is_held_to_the_measure_in_a_wide_main_column(self):
        base = ANCESTORS + (('div', {'class': 'add-banner'}), ('div', {'class': 'maincontent'}))
        cases = (('p', {'class': 'big-text'}, base), ('p', {}, base + (('div', {'class': 'big-text'}),)),
                 ('li', {}, base + (('div', {'class': 'big-text'}), ('ul', {}))))
        for tag, attrs, ancestors in cases:
            with self.subTest(tag=tag, attrs=attrs):
                chain = chain_of(ancestors, tag, attrs, ('fm-modern', 'fm-light'))
                self.assertEqual('var(--fm-measure)', winning([('modern.css', MODERN)], chain, 'max-width', 1920)[0])

    def test_the_home_introduction_is_centred_within_its_measure(self):
        chain = chain_of(ANCESTORS + (('div', {'class': 'main-div'}),), 'p', {'class': 'home-intro'}, ('fm-modern', 'fm-light'))
        self.assertEqual('var(--fm-measure)', winning([('modern.css', MODERN)], chain, 'max-width', 1920)[0])
        self.assertEqual('auto', winning([('modern.css', MODERN)], chain, 'margin-left', 1920)[0])
