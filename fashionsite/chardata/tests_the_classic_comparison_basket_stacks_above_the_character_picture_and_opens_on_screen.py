# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On desktop widths the classic design stacks the comparison toggle above the character picture overlay and opens its panel rightward, and the new design keeps both as they were."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import DESIGNS, chain_of, contrast, rgb, stylesheet, winning

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


CONTROLS = ('html', {}), ('body', {}), ('div', {'class': 'space header-controls'})
CART = ('div', {'id': 'compare-cart', 'class': 'compare-cart'})


def cart_panel_chain(design):
    return chain_of(CONTROLS + (CART,), 'div', {'id': 'compare-cart-panel', 'class': 'compare-cart-panel'}, DESIGNS[design])


def cart_chain(design):
    return chain_of(CONTROLS, 'div', {'id': 'compare-cart', 'class': 'compare-cart'}, DESIGNS[design])


def controls_chain(design):
    return chain_of(CONTROLS[:2], 'div', {'class': 'space header-controls'}, DESIGNS[design])


def hover_bridge_height():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata', 'modern.css')
    with io.open(path, encoding='utf-8') as handle:
        return re.search(r'\.compare-cart-panel::before\{[^}]*height:\s*(\d+px)', handle.read()).group(1)


class TheClassicComparisonPanelStaysInsideTheViewportOnNarrowScreensTests(SimpleTestCase):

    def test_the_classic_panel_is_centred_on_the_header_row_at_600_and_below(self):
        for design in ('classic light', 'classic dark'):
            for width in (320, 375, 560, 600):
                with self.subTest(design=design, width=width):
                    self.assertEqual('50%', winning(MODERN, cart_panel_chain(design), 'left', width)[0])
                    self.assertEqual('auto', winning(MODERN, cart_panel_chain(design), 'right', width)[0])
                    self.assertEqual('translateX(-50%)', winning(MODERN, cart_panel_chain(design), 'transform', width)[0])

    def test_the_classic_panel_has_no_transform_above_600_and_the_new_design_never_has_one(self):
        for design in ('classic light', 'classic dark'):
            for width in (601, 768, 900, 1280):
                with self.subTest(design=design, width=width):
                    self.assertIsNone(winning(MODERN, cart_panel_chain(design), 'transform', width))
        for design in ('modern light', 'modern dark'):
            for width in (375, 600, 768, 1280):
                with self.subTest(design=design, width=width):
                    self.assertIsNone(winning(MODERN, cart_panel_chain(design), 'transform', width))

    def test_the_classic_panel_is_anchored_to_the_header_row_not_to_the_toggle_at_600_and_below(self):
        for design in ('classic light', 'classic dark'):
            with self.subTest(design=design):
                self.assertEqual('static', winning(MODERN, cart_chain(design), 'position', 600)[0])
                self.assertEqual('relative', winning(MODERN, controls_chain(design), 'position', 600)[0])

    def test_the_classic_panel_stays_under_the_toggle_from_601_to_900(self):
        for design in ('classic light', 'classic dark'):
            for width in (601, 768, 900):
                with self.subTest(design=design, width=width):
                    self.assertEqual('0', winning(MODERN, cart_panel_chain(design), 'left', width)[0])
                    self.assertEqual('relative', winning(MODERN, cart_chain(design), 'position', width)[0])
                    self.assertIsNone(winning(MODERN, controls_chain(design), 'position', width))

    def test_the_classic_panel_never_grows_wider_than_the_viewport_at_600_and_below(self):
        for design in ('classic light', 'classic dark'):
            with self.subTest(design=design):
                self.assertEqual('calc(100vw - 12px)', winning(MODERN, cart_panel_chain(design), 'max-width', 360)[0])

    def test_the_classic_panel_opens_one_hover_bridge_under_the_toggle_not_under_the_header_row_at_600_and_below(self):
        bridge = hover_bridge_height()
        for design in ('classic light', 'classic dark'):
            for width in (320, 360, 375, 480, 600):
                with self.subTest(design=design, width=width):
                    self.assertEqual('auto', winning(MODERN, cart_panel_chain(design), 'top', width)[0])
                    self.assertEqual(bridge, winning(MODERN, cart_panel_chain(design), 'margin-top', width)[0])

    def test_the_classic_panel_keeps_its_offset_from_the_toggle_above_600(self):
        for design in ('classic light', 'classic dark'):
            for width in (601, 768, 900, 1280):
                with self.subTest(design=design, width=width):
                    self.assertEqual('calc(100% + 8px)', winning(MODERN, cart_panel_chain(design), 'top', width)[0])
                    self.assertIsNone(winning(MODERN, cart_panel_chain(design), 'margin-top', width))

    def test_the_classic_narrow_rule_stops_at_901_where_the_desktop_rule_takes_over(self):
        for design in ('classic light', 'classic dark'):
            with self.subTest(design=design):
                self.assertEqual('0', winning(MODERN, cart_panel_chain(design), 'left', 901)[0])
                self.assertEqual('relative', winning(MODERN, cart_chain(design), 'position', 901)[0])
                self.assertIsNone(winning(MODERN, controls_chain(design), 'position', 901))

    def test_the_narrow_classic_rule_does_not_match_the_new_design(self):
        for design in ('modern light', 'modern dark'):
            with self.subTest(design=design):
                self.assertEqual('relative', winning(MODERN, cart_chain(design), 'position', 768)[0])
                self.assertIsNone(winning(MODERN, controls_chain(design), 'position', 768))
                self.assertEqual('0', winning(MODERN, cart_panel_chain(design), 'left', 768)[0])
                self.assertEqual('80vw', winning(MODERN, cart_panel_chain(design), 'max-width', 768)[0])


class TheClassicDarkComparisonToggleIsReadableTests(SimpleTestCase):

    def test_the_classic_dark_toggle_icon_has_three_to_one_against_the_dark_page(self):
        colour = winning(MODERN, toggle_chain('classic dark'), 'color', 768)[0]
        self.assertGreaterEqual(contrast(rgb(colour)[0], rgb('#212121')[0]), 3)

    def test_the_classic_light_toggle_keeps_the_inherited_colour(self):
        self.assertEqual('inherit', winning(MODERN, toggle_chain('classic light'), 'color', 768)[0])

    def test_the_dark_toggle_rule_does_not_match_the_new_design(self):
        for design in ('modern light', 'modern dark'):
            with self.subTest(design=design):
                self.assertEqual('inherit', winning(MODERN, toggle_chain(design), 'color', 768)[0])
