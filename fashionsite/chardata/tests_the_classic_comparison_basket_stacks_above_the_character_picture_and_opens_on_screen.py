# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On desktop widths the classic design stacks the comparison toggle above the character picture overlay and opens its panel rightward, and the new design keeps both as they were."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import DESIGNS, chain_of, stylesheet, winning

MODERN = [('modern.css', stylesheet('modern.css'))]
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'base.html')
TOGGLE = ('html', {}), ('body', {}), ('div', {'id': 'compare-cart', 'class': 'compare-cart'})


def toggle_chain(design):
    return chain_of(TOGGLE, 'button', {'class': 'compare-cart-toggle'}, DESIGNS[design])


def panel_chain(design):
    return chain_of(TOGGLE, 'div', {'id': 'compare-cart-panel', 'class': 'compare-cart-panel'}, DESIGNS[design])


def overlay_z_index():
    with io.open(TEMPLATE, encoding='utf-8') as handle:
        tag = re.search(r'<div class="char-overlay"[^>]*>', handle.read()).group(0)
    return int(re.search(r'z-index:\s*(\d+)', tag).group(1))


class TheClassicComparisonToggleStackingTests(SimpleTestCase):

    def test_the_classic_toggle_is_positioned_so_its_z_index_applies(self):
        for design in ('classic light', 'classic dark'):
            with self.subTest(design=design):
                self.assertEqual('relative', winning(MODERN, toggle_chain(design), 'position', 1920)[0])

    def test_the_classic_toggle_z_index_is_above_the_overlay_inline_z_index(self):
        for design in ('classic light', 'classic dark'):
            with self.subTest(design=design):
                self.assertGreater(int(winning(MODERN, toggle_chain(design), 'z-index', 1920)[0]), overlay_z_index())

    def test_the_new_design_toggle_has_no_z_index(self):
        for design in ('modern light', 'modern dark'):
            with self.subTest(design=design):
                self.assertIsNone(winning(MODERN, toggle_chain(design), 'z-index', 1920))

    def test_the_classic_toggle_is_left_alone_below_the_desktop_width(self):
        for design in ('classic light', 'classic dark'):
            with self.subTest(design=design):
                self.assertIsNone(winning(MODERN, toggle_chain(design), 'z-index', 768))

    def test_the_classic_panel_opens_rightward_from_the_toggle_on_desktop(self):
        for design in ('classic light', 'classic dark'):
            with self.subTest(design=design):
                self.assertEqual('0', winning(MODERN, panel_chain(design), 'left', 1280)[0])
                self.assertEqual('auto', winning(MODERN, panel_chain(design), 'right', 1280)[0])

    def test_the_new_design_panel_keeps_its_right_alignment(self):
        for design in ('modern light', 'modern dark'):
            with self.subTest(design=design):
                self.assertEqual('0', winning(MODERN, panel_chain(design), 'right', 1280)[0])
