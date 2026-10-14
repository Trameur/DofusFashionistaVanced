# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The preset chips and the share and saved controls of /setup/ are at least 32px tall on desktop and 44px below 768px, wrap their label, and read against the page in the four design and theme combinations."""
import re

from django.test import SimpleTestCase, TestCase

from chardata.tests_the_setup_page_draws_the_live_weights_panel import _Versioned, setup_page
from chardata.tests_the_setup_stylesheet_support import (
    DESIGNS, chain_of, contrast, declared, flatten, matching, rgb, rule_order, setup_sheets,
    stylesheet, winning)

SETUP = stylesheet('setup.css')
MODERN = stylesheet('modern.css')
LIGHT_SITE = stylesheet('common_lighttheme.css')
DARK_SITE = stylesheet('common_darktheme.css')
PHONE = '(max-width: 767px)'
WIDTHS = (375, 768, 1024, 1920)
TOUCH_TARGETS = ('.setup-chip', '.setup-action', '.setup-saved-summary')
OWN = re.compile(r'\.setup-(recipes|chip|action|share|saved)')
MODERN_LIGHT = 'html.fm-modern.fm-light'
MODERN_DARK = 'html.fm-modern.fm-dark'
MODERN_AUTO = 'html.fm-modern:not(.fm-light):not(.fm-dark)'
VAR = re.compile(r'var\((--[\w-]+)\)')


def pixels(value):
    assert value[0].endswith('px'), value
    return int(value[0][:-2])


def own_rules():
    return [rule for rule in SETUP if any(OWN.search(selector) for selector in rule['selectors'])]


def token(selector, name):
    found = declared(MODERN, selector, name)
    return found[0] if found else None


def resolved(value, tokens):
    """The colour a custom property comes to once the modern token it names is read."""
    named = VAR.fullmatch(value)
    return tokens(named.group(1)) if named else value


class TheTouchTargetSizesTests(SimpleTestCase):

    def test_the_desktop_height_is_at_least_32_pixels(self):
        for selector in TOUCH_TARGETS:
            with self.subTest(selector=selector):
                self.assertGreaterEqual(pixels(declared(SETUP, selector, 'min-height')), 32)

    def test_the_phone_height_is_at_least_44_pixels(self):
        for selector in TOUCH_TARGETS:
            with self.subTest(selector=selector):
                self.assertGreaterEqual(pixels(declared(SETUP, selector, 'min-height', PHONE)), 44)

    def test_the_phone_rule_comes_after_the_base_rule_so_it_wins_at_equal_specificity(self):
        for selector in TOUCH_TARGETS:
            with self.subTest(selector=selector):
                self.assertLess(rule_order(SETUP, selector)[-1], rule_order(SETUP, selector, PHONE)[0])

    def test_the_phone_rule_for_a_target_sets_only_the_height(self):
        for rule in SETUP:
            if rule['media'] == PHONE and any(selector in TOUCH_TARGETS for selector in rule['selectors']):
                self.assertEqual({'min-height'}, set(rule['declarations']), rule['selectors'])

    def test_a_chip_and_an_action_wrap_a_long_translation_instead_of_overflowing(self):
        for selector in ('.setup-chip', '.setup-action'):
            with self.subTest(selector=selector):
                self.assertEqual(('normal', False), declared(SETUP, selector, 'white-space'))
                self.assertEqual(('100%', False), declared(SETUP, selector, 'max-width'))

    def test_the_chips_sit_in_a_wrapping_row(self):
        self.assertEqual(('flex', False), declared(SETUP, '.setup-chips', 'display'))
        self.assertEqual(('wrap', False), declared(SETUP, '.setup-chips', 'flex-wrap'))


class TheCascadeGivesEveryTargetItsSizeInEveryDesignTests(_Versioned, TestCase):

    def chains(self, page, design):
        """The chains of one chip, the copy and save buttons and the saved summary."""
        targets = {'chip': page.find('button', data_recipe='balanced')[0],
                   'copy': page.find('button', id='setup-share-copy')[0],
                   'save': page.find('button', id='setup-saved-save')[0],
                   'summary': [(attrs, ancestors) for attrs, ancestors in page.find('summary')
                               if 'setup-saved-summary' in attrs.get('class', '').split()][0]}
        return {name: chain_of(ancestors, 'summary' if name == 'summary' else 'button', attrs, DESIGNS[design])
                for name, (attrs, ancestors) in targets.items()}

    def test_the_height_is_32_pixels_from_768_up_and_44_below(self):
        sheets = setup_sheets()
        _html, page = setup_page(self.client, 'dofus3')
        for design in DESIGNS:
            for name, chain in self.chains(page, design).items():
                for width in WIDTHS:
                    with self.subTest(design=design, target=name, width=width):
                        value, sheet, selector = winning(sheets, chain, 'min-height', width)
                        self.assertEqual('setup.css', sheet)
                        self.assertGreaterEqual(pixels((value,)), 44 if width < 768 else 32, selector)

    def test_no_other_sheet_changes_the_look_of_a_chip_or_an_action(self):
        sheets = setup_sheets()
        _html, page = setup_page(self.client, 'dofus3')
        for design in DESIGNS:
            chains = self.chains(page, design)
            for name in ('chip', 'copy', 'save'):
                for prop in ('white-space', 'background', 'background-color', 'border', 'color', 'font-size',
                             'padding', 'text-transform'):
                    for width in (375, 1024):
                        found = winning(sheets, chains[name], prop, width)
                        with self.subTest(design=design, target=name, prop=prop, width=width):
                            self.assertTrue(found is None or found[1] == 'setup.css', found)


class TheChipsReadAgainstThePageInEveryDesignTests(SimpleTestCase):

    def colours(self, design):
        """(ink, line, on, page, surface, soft fill) of a design as flat colours, from the stylesheets alone."""
        ink = declared(SETUP, '.setup-recipes', '--setup-ink')[0]
        line = declared(SETUP, '.setup-recipes', '--setup-line')[0]
        on = declared(SETUP, '.setup-recipes', '--setup-on')[0]
        if design == 'classic light':
            ink, line, on = (declared(SETUP, 'html.fm-light .setup-recipes', prop)[0]
                             for prop in ('--setup-ink', '--setup-line', '--setup-on'))
            page = declared(LIGHT_SITE, '.body-base', 'background')[0]
            return ink, line, on, page, page, None
        if design == 'classic dark':
            page = declared(DARK_SITE, '.body-base', 'background')[0]
            return ink, line, on, page, page, None
        scope = MODERN_LIGHT if design == 'modern light' else MODERN_DARK

        def tokens(name):
            return token(scope, name) or token('html.fm-modern', name)
        ink, line, on = (resolved(declared(SETUP, 'html.fm-modern .setup-recipes', prop)[0], tokens)
                         for prop in ('--setup-ink', '--setup-line', '--setup-on'))
        page, surface = tokens('--fm-bg'), tokens('--fm-surface')
        return ink, line, on, page, surface, tokens('--fm-accent-soft')

    def test_the_label_reads_at_4_5_to_1_on_the_page(self):
        for design in DESIGNS:
            ink, _line, _on, page, surface, _soft = self.colours(design)
            for backdrop in (page, surface):
                with self.subTest(design=design, backdrop=backdrop):
                    self.assertGreaterEqual(contrast(rgb(ink)[0], rgb(backdrop)[0]), 4.5)

    def test_the_outline_and_the_pressed_dot_read_at_3_to_1_on_the_page(self):
        for design in DESIGNS:
            _ink, line, on, page, surface, _soft = self.colours(design)
            for name, colour in (('outline', line), ('pressed', on)):
                for backdrop in (page, surface):
                    with self.subTest(design=design, part=name, backdrop=backdrop):
                        self.assertGreaterEqual(contrast(rgb(colour)[0], rgb(backdrop)[0]), 3.0)

    def test_the_pressed_modern_chip_keeps_its_label_readable_on_its_soft_fill(self):
        for design in ('modern light', 'modern dark'):
            ink, _line, on, page, _surface, soft = self.colours(design)
            filled = tuple(round(channel) for channel in flatten(soft, page))
            with self.subTest(design=design):
                self.assertGreaterEqual(contrast(rgb(ink)[0], filled), 4.5)
                self.assertGreaterEqual(contrast(rgb(on)[0], filled), 3.0)

    def test_the_modern_pressed_fill_is_the_soft_accent_token_and_only_there(self):
        self.assertEqual(('var(--fm-accent-soft)', False),
                         declared(SETUP, 'html.fm-modern .setup-chip[aria-pressed="true"]', 'background'))
        self.assertEqual(('transparent', False), declared(SETUP, '.setup-chip', 'background'))
        self.assertEqual(('transparent', False), declared(SETUP, '.setup-action', 'background'))

    def test_the_light_tokens_of_the_auto_theme_are_the_ones_the_light_theme_uses(self):
        for name in ('--fm-bg', '--fm-text', '--fm-muted', '--fm-accent-text', '--fm-surface'):
            with self.subTest(token=name):
                self.assertEqual(token(MODERN_LIGHT, name), token(MODERN_AUTO, name))


class TheNewRulesKeepTheStylesTheOtherSetupTestsPinTests(SimpleTestCase):

    def test_no_new_rule_fills_a_classic_button(self):
        for rule in own_rules():
            if any(':not(.fm-modern)' in selector for selector in rule['selectors']):
                for prop in ('background', 'background-color', 'background-image'):
                    if prop in rule['declarations']:
                        self.assertEqual('transparent', rule['declarations'][prop][0], rule['selectors'])

    def test_no_new_rule_uses_the_light_override_selector_only_the_two_buttons_may_have(self):
        for rule in own_rules():
            for selector in rule['selectors']:
                self.assertFalse(selector.startswith('html.fm-modern:not(.fm-dark)'), selector)

    def test_no_new_rule_defines_a_modern_token(self):
        for rule in own_rules():
            self.assertEqual([], [prop for prop in rule['declarations'] if prop.startswith('--fm-')])

    def test_the_new_custom_properties_are_all_set_on_the_section_itself(self):
        for rule in own_rules():
            if '--setup-ink' in rule['declarations']:
                self.assertTrue(all(selector.endswith('.setup-recipes') for selector in rule['selectors']),
                                rule['selectors'])

    def test_nothing_hides_the_keyboard_focus_outline(self):
        for rule in own_rules():
            for prop in ('outline', 'outline-style', 'outline-width'):
                if prop in rule['declarations']:
                    self.assertNotIn(rule['declarations'][prop][0], ('none', '0'), rule['selectors'])

    def test_the_section_uses_no_grid_and_no_fixed_width_so_it_fits_a_375_pixel_phone(self):
        for rule in own_rules():
            self.assertNotIn('grid-template-columns', rule['declarations'])
        for selector in ('.setup-recipes', '.setup-chips', '.setup-chip', '.setup-action', '.setup-saved'):
            for rule in matching(SETUP, selector):
                width = rule['declarations'].get('width')
                self.assertTrue(width is None or not width[0].endswith('px'), (selector, width))

    def test_the_section_is_hidden_with_the_attribute_until_the_script_shows_it(self):
        self.assertEqual(('none', True), declared(SETUP, '.setup-recipes[hidden]', 'display'))
        self.assertEqual([], matching(SETUP, '.setup-recipes[hidden]', PHONE))
