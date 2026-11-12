# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The seam goes on containers only, the data tape is a pale track with a fill and its ticks, the loading bar keeps the gold stripe, the page title has no rule under it, and the loot frame is a gilded double border that forced colours turn into a plain one."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, declared, matching, stylesheet

MODERN = stylesheet('modern.css')
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
CONTROLS = ('a', 'button', 'input', 'select', 'summary', 'textarea')
TAG = re.compile(r'<(\w+)\b([^>]*)>', re.S)
SEAMED = re.compile(r'class\s*=\s*["\'][^"\']*\b(fm-seam|brown-box)\b')


def last_compound(selector):
    return re.split(r'[\s>+~]+', selector.strip())[-1]


def seam_selectors():
    return [selector for rule in MODERN for selector in rule['selectors']
            if 'outline' in rule['declarations'] and '--fm-seam' in rule['declarations']['outline'][0]]


class TheSeamIsStitchedOnContainersOnlyTests(SimpleTestCase):

    def test_the_seam_is_a_dashed_outline_pulled_inside_the_edge(self):
        found = declared(MODERN, 'html.fm-modern .fm-seam', 'outline')
        self.assertEqual(('1.5px dashed var(--fm-seam)', False), found)
        self.assertEqual(('-7px', False), declared(MODERN, 'html.fm-modern .fm-seam', 'outline-offset'))
        self.assertEqual(('-7px', False), declared(MODERN, 'html.fm-modern .fm-card', 'outline-offset'))

    def test_the_seam_sits_on_the_brown_box_and_on_the_seam_class(self):
        self.assertEqual({'html.fm-modern .fm-seam', 'html.fm-modern .brown-box', 'html.fm-modern .fm-card',
                          'html.fm-modern .maincontent:is(:has(.setup-new),:has(> .solution-table),:has(.wm-section),:has(> .main-div)) .brown-box',
                          'html.fm-modern .tunnel-atelier .wm-section',
                          'html.fm-modern .tunnel-exclusions .exclusions-types-cell',
                          'html.fm-modern .tunnel-options > table > tbody > tr > td', 'html.fm-modern .tunnel-inclusions .small-brown-box',
                          'html.fm-modern .tunnel-atelier .tunnel-card', 'html.fm-modern .tunnel-infeasible .solver-why',
                          'html.fm-modern .setup-atelier .setup-recipes', 'html.fm-modern .setup-atelier .setup-zone-form',
                          'html.fm-modern .setup-atelier .setup-zone-options', 'html.fm-modern .setup-atelier .setup-preview'}, set(seam_selectors()))

    def test_no_seam_selector_ends_on_a_control(self):
        for selector in seam_selectors():
            with self.subTest(selector=selector):
                tail = last_compound(selector)
                self.assertFalse(re.match(r'(%s)\b' % '|'.join(CONTROLS), tail), tail)
                self.assertNotIn('tabindex', tail)

    def test_no_template_puts_a_seamed_class_on_a_control_or_on_something_focusable(self):
        offenders = []
        for root, _, names in os.walk(TEMPLATES):
            for name in names:
                if not name.endswith('.html'):
                    continue
                with open(os.path.join(root, name), encoding='utf-8', errors='replace') as handle:
                    source = handle.read()
                for tag, attributes in TAG.findall(source):
                    if SEAMED.search(attributes) and (tag.lower() in CONTROLS or 'tabindex' in attributes):
                        offenders.append((name, tag))
        self.assertEqual([], offenders)

    def test_the_focus_ring_is_a_box_shadow_so_the_seam_never_stands_in_for_it(self):
        self.assertNotIn('--fm-seam', declared(MODERN, 'html.fm-modern', '--fm-ring')[0])
        focus = declared(MODERN, 'html.fm-modern button:focus-visible', 'box-shadow')
        self.assertEqual(('var(--fm-ring)', False), focus)


class TheTapeDrawsItsTicksTests(SimpleTestCase):

    STRIPE = 'repeating-linear-gradient(90deg,var(--fm-tape-tick) 0 1px,transparent 1px 8px),var(--fm-tape)'
    TICKS = ('repeating-linear-gradient(90deg,var(--fm-tick) 0 1px,transparent 1px 8px) top/100% 40% no-repeat,'
             'repeating-linear-gradient(90deg,var(--fm-tick) 0 1.5px,transparent 1.5px 40px)')

    def test_the_data_tape_is_a_pale_track_with_a_fill_as_wide_as_its_value(self):
        self.assertEqual(('var(--fm-track)', False), declared(MODERN, 'html.fm-modern .fm-tape', 'background'))
        self.assertEqual(('12px', False), declared(MODERN, 'html.fm-modern .fm-tape', 'height'))
        self.assertEqual(('var(--fm-fill)', False), declared(MODERN, 'html.fm-modern .fm-tape > i', 'background'))
        self.assertEqual(('var(--w,0%)', False), declared(MODERN, 'html.fm-modern .fm-tape > i', 'width'))

    def test_the_data_tape_draws_a_small_tick_every_8px_and_a_tall_one_every_40px_over_the_fill(self):
        self.assertEqual((self.TICKS, False), declared(MODERN, 'html.fm-modern .fm-tape::after', 'background'))
        self.assertEqual(('none', False), declared(MODERN, 'html.fm-modern .fm-tape::after', 'pointer-events'))

    def test_the_loading_fill_keeps_the_gold_stripe_and_the_page_title_has_no_rule(self):
        self.assertEqual(1, len([rule for rule in matching(MODERN, 'html.fm-modern .loading-progress > span')
                                 if rule['declarations'].get('background') == (self.STRIPE, False)]))
        self.assertEqual(('none', False), declared(MODERN, 'html.fm-modern h1::after', 'content'))
        self.assertEqual([], [rule for rule in matching(MODERN, 'html.fm-modern h1::after') if 'background' in rule['declarations']])

    def test_the_loading_bar_has_a_track_that_stands_out_from_the_page(self):
        self.assertEqual(('1px solid var(--fm-seam)', False), declared(MODERN, 'html.fm-modern .loading-progress', 'border'))

    def test_the_loading_fill_keeps_the_width_the_script_sets(self):
        self.assertIsNone(declared(MODERN, 'html.fm-modern .loading-progress > span', 'width'))


class TheLootFrameIsAGildedDoubleBorderTests(SimpleTestCase):

    FRAME = 'html.fm-modern .fm-frame'

    def test_the_frame_is_a_2px_gold_border_with_two_inset_rings(self):
        self.assertEqual(('2px solid var(--fm-frame-gold)', False), declared(MODERN, self.FRAME, 'border'))
        shadow = declared(MODERN, self.FRAME, 'box-shadow')[0]
        self.assertEqual('inset 0 0 0 2px var(--fm-surface), inset 0 0 0 3px var(--fm-frame-gold)', shadow)

    def test_the_frame_has_the_small_radius(self):
        self.assertEqual(('var(--fm-radius-xs)', False), declared(MODERN, self.FRAME, 'border-radius'))

    def test_the_frame_carries_no_game_data(self):
        for prop, (value, _) in matching(MODERN, self.FRAME)[0]['declarations'].items():
            with self.subTest(prop=prop):
                self.assertNotIn('content', prop)
                self.assertNotIn('url(', value)

    def test_forced_colours_get_a_plain_solid_border(self):
        media = '(forced-colors:active)'
        self.assertEqual(('CanvasText', False), declared(MODERN, self.FRAME, 'border-color', media))
        self.assertEqual(('none', False), declared(MODERN, self.FRAME, 'box-shadow', media))

    def test_the_shiny_slot_keeps_its_own_stylesheet_and_only_the_modern_prefix_restyles_it(self):
        with open(os.path.join(STATIC, 'solution.css'), encoding='utf-8') as handle:
            self.assertIn('.shiny-slot', handle.read())
        shiny = [selector for rule in MODERN for selector in rule['selectors'] if 'shiny' in selector]
        self.assertTrue(shiny)
        self.assertEqual([], [selector for selector in shiny if not selector.startswith('html.fm-modern ')])
