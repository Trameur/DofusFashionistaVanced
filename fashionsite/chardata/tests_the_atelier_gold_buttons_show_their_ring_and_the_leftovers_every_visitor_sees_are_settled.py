# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The winning rule of the cascade in the modern design: every gold button shows the focus ring, the build bar buttons reach 44 pixels, the gallery label is left aligned, the preset chips are one scrolling row on a phone, the weights cards stretch to the row and a closed one does not, the basket panel stays on screen from 601 to 900, and the status tints are tokens declared for the light, dark and fallback themes."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, chain_of, declared, setup_sheets, stylesheet, winning

MODERN_SHEET = stylesheet('modern.css')
MODERN = ['fm-modern']
THEMES = (['fm-modern', 'fm-light'], ['fm-modern', 'fm-dark'])
FOCUSED = 'is-focus-visible'
HOVERED = 'is-hover'
TOKENS = ('--fm-ok', '--fm-warn', '--fm-bad', '--fm-info')
TOKEN_SELECTORS = ('html.fm-modern.fm-light', 'html.fm-modern.fm-dark', 'html.fm-modern:not(.fm-light):not(.fm-dark)')
TINTS = ('#2f6b2a', '#8bcb79', '#8a4e00', '#f0b45c', '#a8281f', '#ff8f86', '#1a5a85', '#6cb8ec')
RETIRED_TINTS = ('#1f6a26', '#86d68f')
PAGE = [('html', {}), ('div', {'class': 'maincontent'})]
GOLD = [('a', {'class': 'submit-button button-generic copy-action-link'}),
        ('input', {'type': 'submit', 'class': 'submit-button button-generic'}),
        ('input', {'type': 'submit'}),
        ('button', {'type': 'submit', 'class': 'button-generic'}),
        ('button', {'class': 'rerun-button'}),
        ('a', {'class': 'filter-button'}),
        ('a', {'class': 'button-generic-foreground'}),
        ('a', {'class': 'build-link'}),
        ('a', {'class': 'fm-btn-pri'})]
OUTLINES = GOLD[:4] + GOLD[5:7]
PRIMARIES = [('a', {'class': 'fm-btn-pri'}), ('button', {'class': 'rerun-button'}),
             ('input', {'type': 'submit', 'class': 'submit-button button-generic setup-primary'})]


def focus_state(rules):
    return [dict(rule, selectors=[selector.replace(':focus-visible', '.' + FOCUSED).replace(':hover', '.' + HOVERED)
                                  for selector in rule['selectors']])
            for rule in rules]


def sheets(focus=False):
    return [(name, focus_state(rules) if focus else rules) for name, rules in setup_sheets()]


def winner(ancestors, element, prop, width, classes=MODERN, focus=False, hover=False):
    attrs = dict(element[1])
    if focus:
        attrs['class'] = (attrs.get('class', '') + ' ' + FOCUSED).strip()
    if hover:
        attrs['class'] = (attrs.get('class', '') + ' ' + HOVERED).strip()
    return winning(sheets(focus or hover), chain_of(ancestors, element[0], attrs, classes), prop, width)


def modern_source():
    with io.open(os.path.join(STATIC, 'modern.css'), encoding='utf-8') as handle:
        return re.sub(r'/\*.*?\*/', '', handle.read(), flags=re.S)


class EveryGoldButtonShowsTheFocusRingTests(SimpleTestCase):

    def test_the_winning_box_shadow_of_a_focused_gold_button_is_the_ring_in_both_themes(self):
        for classes in THEMES:
            for element in GOLD:
                with self.subTest(element=element, classes=classes):
                    found = winner(PAGE, element, 'box-shadow', 1440, classes, focus=True)
                    self.assertEqual('var(--fm-ring)', found[0])

    def test_the_active_version_link_keeps_an_inset_ring_because_its_bar_clips_an_outer_one(self):
        for classes in THEMES:
            found = winner(PAGE, ('a', {'class': 'version-link active'}), 'box-shadow', 1440, classes, focus=True)
            self.assertEqual('inset 0 0 0 2px #efcb63, inset 0 0 0 4px #2a2010', found[0])

    def test_an_unfocused_button_is_an_outline_with_no_shadow(self):
        expected = {'box-shadow': 'none', 'background': 'transparent', 'border': '1.5px solid var(--fm-btnline)', 'color': 'var(--fm-head)'}
        for classes in THEMES:
            for element in OUTLINES:
                with self.subTest(element=element, classes=classes):
                    self.assertEqual(expected, {prop: winner(PAGE, element, prop, 1440, classes)[0] for prop in expected})

    def test_an_unfocused_primary_is_plain_gold_with_no_shadow(self):
        expected = {'background': 'var(--fm-gold)', 'border-color': 'var(--fm-gold)', 'color': 'var(--fm-on-gold)'}
        for classes in THEMES:
            for element in PRIMARIES:
                with self.subTest(element=element, classes=classes):
                    self.assertEqual(expected, {prop: winner(PAGE, element, prop, 1440, classes)[0] for prop in expected})
                    shadow = winner(PAGE, element, 'box-shadow', 1440, classes)
                    self.assertIn(None if shadow is None else shadow[0], (None, 'none'))

    def test_the_build_bar_primary_is_plain_gold_and_its_focus_outline_sits_outside_the_gold(self):
        nav = stylesheet('modern-nav.css')
        button = 'html.fm-modern .fm-buildbar .fm-buildbar-end a.rerun-button'
        self.assertEqual(('var(--fm-gold)', True), declared(nav, button + ':link', 'background'))
        self.assertEqual(('var(--fm-on-gold)', True), declared(nav, button + ':link', 'color'))
        self.assertEqual(('var(--fm-gold-hover)', True), declared(nav, button + ':hover', 'background'))
        self.assertEqual(('2px solid var(--fm-accent-text)', False),
                         declared(nav, 'html.fm-modern .fm-buildbar .fm-buildbar-in :is(a,button):focus-visible', 'outline'))
        self.assertEqual(('2px', False), declared(nav, button + ':focus-visible', 'outline-offset'))

    def test_the_ring_rule_is_important_and_inside_the_screen_media_block(self):
        rules = [rule for rule in MODERN_SHEET
                 if 'html.fm-modern .submit-button:focus-visible' in rule['selectors'] and 'box-shadow' in rule['declarations']
                 and rule['declarations']['box-shadow'][1]]
        self.assertEqual(['screen'], [rule['media'] for rule in rules])

    def test_the_ring_reaches_every_setup_door_without_the_page_rule(self):
        ancestors = [('html', {}), ('div', {'class': 'setup-atelier'}), ('div', {'class': 'setup-doors', 'id': 'submit-mode'})]
        for element in (('input', {'type': 'submit', 'class': 'submit-button button-generic setup-primary', 'name': 'optimize'}),
                        ('input', {'type': 'submit', 'class': 'submit-button button-thin-foreground setup-secondary', 'name': 'wizard'})):
            found = winner(ancestors, element, 'box-shadow', 375, THEMES[0], focus=True)
            self.assertEqual('var(--fm-ring)', found[0])

    def test_a_focused_setup_door_keeps_its_ring_while_the_pointer_is_over_it(self):
        ancestors = [('html', {}), ('div', {'class': 'setup-atelier'}), ('div', {'class': 'setup-doors', 'id': 'submit-mode'})]
        door = ('input', {'type': 'submit', 'class': 'submit-button button-thin-foreground setup-secondary', 'name': 'wizard'})
        for classes in THEMES:
            with self.subTest(classes=classes):
                self.assertEqual('var(--fm-ring)', winner(ancestors, door, 'box-shadow', 1440, classes, focus=True, hover=True)[0])
                self.assertEqual('none', winner(ancestors, door, 'box-shadow', 1440, classes, hover=True)[0])


class TheBuildBarButtonsReach44PixelsTests(SimpleTestCase):

    def test_edit_duplicate_and_copy_have_a_44_pixel_minimum_at_every_width(self):
        ancestors = [('html', {}), ('div', {'class': 'proj_info'}), ('div', {'class': 'proj-info-side proj-info-side-owner'})]
        for width in (375, 768, 1280, 1440, 1920):
            for element in (('a', {'class': 'submit-button button-generic copy-action-link'}),
                            ('button', {'type': 'submit', 'class': 'submit-button button-generic'})):
                with self.subTest(width=width, tag=element[0]):
                    self.assertEqual('44px', winner(ancestors, element, 'min-height', width)[0])
                    self.assertEqual('border-box', winner(ancestors, element, 'box-sizing', width)[0])


class TheGalleryLabelIsLeftAlignedTests(SimpleTestCase):

    def test_the_text_of_the_gallery_checkbox_is_left_aligned_at_every_width(self):
        ancestors = [('html', {}), ('div', {'class': 'setup-atelier'}), ('form', {}),
                     ('div', {'id': 'publish-choice', 'class': 'setup-choice-box'}), ('label', {})]
        for width in (375, 1440):
            with self.subTest(width=width):
                found = winner(ancestors, ('span', {'class': 'input-name'}), 'text-align', width)
                self.assertEqual('left', found[0])


class ThePresetChipsAreOneScrollingRowOnAPhoneTests(SimpleTestCase):
    ANCESTORS = [('html', {}), ('div', {'class': 'setup-atelier'}), ('section', {'class': 'setup-recipes'})]
    CHIPS = ('div', {'class': 'setup-chips'})
    CHIP = ('button', {'class': 'setup-chip'})

    def test_the_chip_list_scrolls_sideways_in_one_row_at_480_and_below(self):
        for width in (360, 375, 480):
            with self.subTest(width=width):
                self.assertEqual('auto', winner(self.ANCESTORS, self.CHIPS, 'overflow-x', width)[0])
                self.assertEqual('nowrap', winner(self.ANCESTORS, self.CHIPS, 'flex-wrap', width)[0])
                self.assertEqual('x proximity', winner(self.ANCESTORS, self.CHIPS, 'scroll-snap-type', width)[0])
                self.assertEqual('0 0 auto', winner(self.ANCESTORS + [self.CHIPS], self.CHIP, 'flex', width)[0])
                self.assertEqual('44px', winner(self.ANCESTORS + [self.CHIPS], self.CHIP, 'min-height', width)[0])
                self.assertEqual('inset 0 0 0 3px var(--fm-accent-text)',
                                 winner(self.ANCESTORS + [self.CHIPS], self.CHIP, 'box-shadow', width, THEMES[0], focus=True)[0])

    def test_the_chip_list_wraps_as_before_above_480(self):
        for width in (481, 900, 1440):
            with self.subTest(width=width):
                self.assertIsNone(winner(self.ANCESTORS, self.CHIPS, 'overflow-x', width))
                self.assertEqual('wrap', winner(self.ANCESTORS, self.CHIPS, 'flex-wrap', width)[0])


class TheWeightsCardsStretchToTheRowAndAClosedOneKeepsNoRowHeightTests(SimpleTestCase):
    PAGE = ('div', {'class': 'tunnel-atelier wm-page'})

    def test_an_open_card_shares_the_height_of_its_row_in_two_and_three_columns(self):
        for width in (901, 1280, 1440, 1920):
            with self.subTest(width=width):
                found = winner([('html', {})], self.PAGE, 'align-items', width)
                self.assertEqual('stretch', found[0])

    def test_a_closed_card_aligns_to_the_start_of_its_row_instead_of_keeping_the_row_height(self):
        for width in (901, 1280, 1920):
            with self.subTest(width=width):
                closed = winner([('html', {}), self.PAGE], ('details', {'class': 'wm-section'}), 'align-self', width)
                self.assertEqual('start', closed[0])

    def test_an_open_card_has_no_start_alignment_of_its_own(self):
        for width in (901, 1280, 1920):
            with self.subTest(width=width):
                found = winner([('html', {}), self.PAGE], ('details', {'class': 'wm-section', 'open': ''}), 'align-self', width)
                self.assertIsNone(found)

    def test_a_phone_keeps_the_single_column_without_the_row_rules(self):
        self.assertIsNone(winner([('html', {})], self.PAGE, 'align-items', 900))


class TheBasketPanelStaysOnScreenFrom601To900Tests(SimpleTestCase):

    def test_the_panel_hangs_from_the_left_edge_of_the_toggle_from_601_to_900(self):
        ancestors = [('html', {}), ('div', {'class': 'compare-cart'})]
        panel = ('div', {'class': 'compare-cart-panel'})
        for width in (601, 768, 900):
            with self.subTest(width=width):
                self.assertEqual('0', winner(ancestors, panel, 'left', width)[0])
                self.assertEqual('auto', winner(ancestors, panel, 'right', width)[0])


class TheStatusTintsAreTokensTests(SimpleTestCase):

    def test_each_status_token_exists_under_the_light_the_dark_and_the_fallback_selectors(self):
        for selector in TOKEN_SELECTORS:
            with self.subTest(selector=selector):
                self.assertEqual([], [name for name in TOKENS if declared(MODERN_SHEET, selector, name) is None])

    def test_the_token_values_are_the_status_tints_of_the_new_palette(self):
        light = {name: declared(MODERN_SHEET, TOKEN_SELECTORS[0], name)[0] for name in TOKENS}
        dark = {name: declared(MODERN_SHEET, TOKEN_SELECTORS[1], name)[0] for name in TOKENS}
        self.assertEqual({'--fm-ok': '#2f6b2a', '--fm-warn': '#8a4e00', '--fm-bad': '#a8281f', '--fm-info': '#1a5a85'}, light)
        self.assertEqual({'--fm-ok': '#8bcb79', '--fm-warn': '#f0b45c', '--fm-bad': '#ff8f86', '--fm-info': '#6cb8ec'}, dark)
        self.assertEqual(light, {name: declared(MODERN_SHEET, TOKEN_SELECTORS[2], name)[0] for name in TOKENS})

    def test_no_rule_outside_the_token_blocks_repeats_one_of_the_eight_tints_or_a_retired_one(self):
        repeated = []
        for rule in MODERN_SHEET:
            if any(selector in TOKEN_SELECTORS for selector in rule['selectors']):
                continue
            for prop, (found, _) in rule['declarations'].items():
                if any(tint in found.lower() for tint in TINTS + RETIRED_TINTS):
                    repeated.append((rule['selectors'][0], prop, found))
        self.assertEqual([], repeated)

    def test_the_rules_that_painted_a_status_now_read_a_token(self):
        source = modern_source()
        for name in ('inv-stat-over', 'inv-stat-under', 'inv-feedback', 'fm-ok', 'fm-bad', 'fm-warn', 'fm-sim-stop'):
            with self.subTest(name=name):
                self.assertRegex(source, r'\.%s[^{]*\{[^}]*var\(--fm-(ok|warn|bad|info)\)' % name)
