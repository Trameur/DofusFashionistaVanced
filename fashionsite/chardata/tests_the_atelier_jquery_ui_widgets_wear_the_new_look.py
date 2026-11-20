# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""In the new look, the jQuery UI sliders and autocomplete menus are drawn by the site's stylesheet on every page that builds them, not by the library's theme."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, stylesheet

REST = stylesheet('modern-rest.css')
SETUP = stylesheet('modern-setup.css')
SLIDER = 'html.fm-modern .wm-page .wm-slider.ui-slider'
HANDLE = SLIDER + ' .ui-slider-handle'
MENU = 'html.fm-modern .ui-autocomplete.ui-menu'
ROW = MENU + ' .ui-menu-item-wrapper'
PHONE = '(max-width:760px)'
WIDGETS = ('ui-slider', 'ui-autocomplete', 'ui-menu')


def value(rules, selector, prop, media=None):
    found = declared(rules, selector, prop, media)
    return found[0] if found else None


def widget_selectors(rules):
    return [selector for rule in rules for selector in rule['selectors']
            if any(name in selector for name in WIDGETS)]


class TheSlidersTests(SimpleTestCase):

    def test_the_track_and_the_handle_are_drawn_for_every_block_of_weights(self):
        self.assertEqual('var(--fm-track)', value(REST, SLIDER, 'background'))
        self.assertEqual('0', value(REST, SLIDER, 'border'))
        self.assertEqual('12px', value(REST, SLIDER, 'height'))
        self.assertEqual('var(--fm-gold)', value(REST, HANDLE, 'background'))
        self.assertEqual('50%', value(REST, HANDLE, 'border-radius'))
        self.assertEqual(('20px', '20px'), (value(REST, HANDLE, 'width'), value(REST, HANDLE, 'height')))

    def test_the_handle_can_be_pressed_twelve_pixels_around_itself(self):
        self.assertEqual('-12px', value(REST, HANDLE + '::before', 'inset'))

    def test_the_weights_page_keeps_no_slider_rule_of_its_own(self):
        self.assertEqual([], widget_selectors(SETUP))

    def test_the_assistant_gives_the_slider_the_same_column_as_the_weights_page(self):
        for part in ('.wm-head', '.wm-row'):
            with self.subTest(part=part):
                weights = value(SETUP, 'html.fm-modern .tunnel-weights ' + part, 'grid-template-columns')
                self.assertIsNotNone(weights)
                self.assertEqual(weights, value(REST, 'html.fm-modern .tunnel-wizard ' + part, 'grid-template-columns'))


class TheAutocompleteMenuTests(SimpleTestCase):

    def test_the_menu_is_a_plain_surface_with_the_text_token(self):
        self.assertEqual('var(--fm-surface)', value(REST, MENU, 'background'))
        self.assertEqual('var(--fm-text)', value(REST, MENU, 'color'))
        self.assertEqual('1px solid var(--fm-border)', value(REST, MENU, 'border'))

    def test_a_row_drops_the_library_frame_and_texture(self):
        self.assertEqual('none', value(REST, ROW, 'background'))
        self.assertEqual('0', value(REST, ROW, 'border'))
        self.assertEqual('0', value(REST, ROW, 'margin'))

    def test_the_active_row_is_a_darker_surface_with_the_heading_token(self):
        active = ROW + '.ui-state-active'
        self.assertEqual('var(--fm-surface-3)', value(REST, active, 'background'))
        self.assertEqual('var(--fm-head)', value(REST, active, 'color'))

    def test_a_row_is_32_pixels_high_and_44_on_a_phone_padding_included(self):
        self.assertEqual('border-box', value(REST, ROW, 'box-sizing'))
        self.assertEqual('32px', value(REST, ROW, 'min-height'))
        self.assertEqual('44px', value(REST, ROW, 'min-height', PHONE))


class TheClassicLookKeepsTheLibraryThemeTests(SimpleTestCase):

    def test_every_widget_rule_applies_to_the_new_look_only(self):
        found = widget_selectors(REST)
        self.assertTrue(found)
        self.assertEqual([], [selector for selector in found if not selector.startswith('html.fm-modern ')])
