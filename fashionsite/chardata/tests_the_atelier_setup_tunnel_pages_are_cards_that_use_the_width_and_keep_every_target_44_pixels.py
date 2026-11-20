# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The setup tunnel pages of the modern design (weights and minimums, wizard, options, lock items, forbid items): each carries the opt-in class, the forms.css caps are loosened under that class only, the sections are cards whose columns grow with the width and never drop, the seam sits on the details and never on the summary, every control is a 44 pixel target, the static inline styles moved to classes with the same values, and every new rule is prefixed by the modern class."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, parse, stylesheet

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
MARKER = '/* ---------- Setup tunnel: weights, wizard, options, lock items, forbid items ---------- */'
PREFIX = 'html.fm-modern .tunnel-atelier'
PAGES = {
    'weights_minimums.html': 'tunnel-weights',
    'wizard.html': 'tunnel-wizard',
    'options.html': 'tunnel-options',
    'inclusions.html': 'tunnel-inclusions',
    'exclusions.html': 'tunnel-exclusions',
}


def read(directory, name):
    with io.open(os.path.join(directory, name), encoding='utf-8') as handle:
        return handle.read()


def tunnel_rules():
    source = read(STATIC, 'modern.css')
    return parse(re.sub(r'/\*.*?\*/', '', source[source.index(MARKER):], flags=re.S))


def declared(selector, prop, media=None):
    found = [rule['declarations'][prop][0] for rule in tunnel_rules()
             if rule['media'] == media and selector in rule['selectors'] and prop in rule['declarations']]
    return found[-1] if found else None


def compact(value):
    return None if value is None else value.replace(' ', '')


def min_width(media):
    return int(re.search(r'min-width:\s*(\d+)px', media).group(1))


class TheTunnelPagesOptInAndKeepTheirContentTests(SimpleTestCase):

    def test_every_page_carries_the_opt_in_class_and_its_own(self):
        for name, own in PAGES.items():
            self.assertRegex(read(TEMPLATES, name), r'class="[^"]*\btunnel-atelier %s\b' % own, name)

    def test_the_static_inline_styles_moved_to_classes_and_only_the_script_toggled_ones_stay(self):
        names = list(PAGES) + ['inclusions_row.html', 'wizard_options.html']
        for name in names:
            for style in re.findall(r'\sstyle="([^"]*)"', read(TEMPLATES, name)):
                self.assertIn('display:none', style.replace(' ', ''), '%s keeps a static inline style: %s' % (name, style))

    def test_the_classes_carry_the_values_the_inline_styles_had(self):
        values = {}
        for rule in stylesheet('forms.css'):
            for selector in rule['selectors']:
                values[selector] = {key: value[0] for key, value in rule['declarations'].items()}
        self.assertEqual('48px', values['.exo-count-input']['width'])
        self.assertEqual('top', values['.option-cell-top']['vertical-align'])
        self.assertEqual('0.9em', values['.lock-hint']['font-size'])
        self.assertEqual('4px', values['.lock-hint']['margin-top'])
        self.assertEqual('middle', values['td.solution-item-info.inclusion-info-cell']['vertical-align'])
        self.assertEqual('middle', values['img.button-remove.inclusion-remove-icon']['vertical-align'])
        self.assertEqual('0.8em', values['button.button-generic.inclusion-customize-button']['font-size'])
        self.assertEqual('2px 8px', values['button.button-generic.inclusion-customize-button']['padding'])


class TheFormsCapsAreLoosenedUnderTheOptInClassOnlyTests(SimpleTestCase):

    def test_the_boxes_and_the_page_are_not_held_to_a_fixed_width(self):
        for box in ('.wizard-div', '.brown-box', '.small-brown-box'):
            self.assertEqual('auto', declared('%s %s' % (PREFIX, box), 'width'), box)
            self.assertEqual('none', declared('%s %s' % (PREFIX, box), 'max-width'), box)
        self.assertEqual('none', declared(PREFIX + '.wm-page', 'max-width'))
        self.assertEqual('100%', declared(PREFIX + ' .compare-link-input', 'width'))

    def test_the_caps_of_forms_css_are_untouched_for_the_classic_design(self):
        sheet = {selector: rule['declarations'] for rule in stylesheet('forms.css') for selector in rule['selectors']}
        self.assertEqual('620px', sheet['.brown-box']['width'][0])
        self.assertEqual('636px', sheet['.wizard-div']['width'][0])
        self.assertEqual('780px', sheet['.wm-page']['max-width'][0])

    def test_every_rule_of_the_section_starts_with_the_modern_class(self):
        for rule in tunnel_rules():
            for selector in rule['selectors']:
                self.assertTrue(selector.startswith('html.fm-modern '), selector)
                self.assertIn('.tunnel-', selector)
            self.assertNotIn('print', rule['media'] or '')


class TheTunnelSectionsAreCardsWhoseColumnsGrowWithTheWidthTests(SimpleTestCase):

    def test_the_weights_sections_go_from_one_column_to_two_then_three(self):
        selector = PREFIX + '.wm-page'
        self.assertEqual('minmax(0,1fr)', compact(declared(selector, 'grid-template-columns', '(min-width:901px)')))
        self.assertEqual('repeat(2,minmax(0,1fr))', compact(declared(selector, 'grid-template-columns', '(min-width:1280px)')))
        self.assertEqual('repeat(3,minmax(0,1fr))', compact(declared(selector, 'grid-template-columns', '(min-width:1800px)')))

    def test_the_wizard_cards_pair_from_1280_and_the_dofus_card_spans_the_row(self):
        self.assertEqual('repeat(2,minmax(0,1fr))', compact(declared(
            'html.fm-modern .tunnel-wizard > table', 'grid-template-columns', '(min-width:1280px)')))
        self.assertEqual('1 / -1', declared(
            'html.fm-modern .tunnel-wizard > table .wizard-div:has(.dofus-box)', 'grid-column', '(min-width:901px)'))

    def test_the_lock_and_forbid_grids_never_drop_a_column_as_the_width_grows(self):
        self.assertEqual('repeat(2,minmax(0,1fr))', compact(declared(
            'html.fm-modern .tunnel-inclusions .columns-section', 'grid-template-columns', '(min-width:901px)')))
        self.assertEqual('repeat(auto-fill,minmax(min(100%,340px),1fr))', compact(declared(
            'html.fm-modern .tunnel-inclusions .columns-column', 'grid-template-columns')))
        self.assertEqual('repeat(auto-fill,minmax(320px,1fr))', compact(declared(
            'html.fm-modern .tunnel-exclusions .exclusions-types-section', 'grid-template-columns', '(min-width:901px)')))
        self.assertEqual('repeat(auto-fit,minmax(min(100%,300px),1fr))', compact(declared(
            'html.fm-modern .tunnel-options > table', 'grid-template-columns')))

    def test_no_fixed_multi_column_layout_starts_at_or_below_the_shared_responsive_breakpoint(self):
        for rule in tunnel_rules():
            columns = rule['declarations'].get('grid-template-columns')
            if columns and columns[0].startswith('repeat(') and 'auto-' not in columns[0]:
                self.assertIsNotNone(rule['media'], rule['selectors'])
                self.assertGreaterEqual(min_width(rule['media']), 901, rule['selectors'])

    def test_the_seam_sits_on_the_details_and_never_on_the_summary(self):
        self.assertEqual('1.5px dashed var(--fm-seam)', declared(PREFIX + ' .wm-section', 'outline'))
        for rule in tunnel_rules():
            for selector in rule['selectors']:
                if 'summary' in selector:
                    self.assertNotIn('outline', rule['declarations'])
                    self.assertNotIn('border', rule['declarations'])

    def test_the_section_titles_use_the_display_font_and_never_go_bold(self):
        for selector in (PREFIX + ' .wm-section-label', 'html.fm-modern .tunnel-wizard .wizard-div > b:first-child'):
            self.assertEqual('var(--fm-font-display)', declared(selector, 'font-family'))
            self.assertEqual('400', declared(selector, 'font-weight'))
            self.assertEqual('none', declared(selector, 'font-synthesis'))


class TheTunnelControlsAreFortyFourPixelTargetsTests(SimpleTestCase):

    def test_buttons_selects_inputs_summaries_and_labels_are_44_pixels_high(self):
        for selector in (PREFIX + ' .button-generic', PREFIX + ' select', PREFIX + ' input[type="number"]',
                         PREFIX + ' .white-pretty-input', PREFIX + ' .button-thin-foreground'):
            self.assertEqual('44px', declared(selector, 'min-height'), selector)
        self.assertEqual('44px', declared('html.fm-modern .tunnel-exclusions #input-item-to-forbid', 'min-height'))
        self.assertEqual('16px', declared('html.fm-modern .tunnel-exclusions #input-item-to-forbid', 'font-size'))
        self.assertEqual('44px', declared(PREFIX + ' label', 'min-height'))
        self.assertEqual('44px', declared(PREFIX + ' .wm-section > summary', 'min-height'))
        self.assertEqual('44px', declared(PREFIX + ' .wm-row .wm-input', 'min-height'))
        self.assertEqual('44px', declared('html.fm-modern .tunnel-inclusions button.inclusion-customize-button', 'min-height'))

    def test_every_input_of_the_five_pages_is_matched_by_a_44_pixel_selector(self):
        selectors = [selector for rule in tunnel_rules() if 'min-height' in rule['declarations'] and rule['declarations']['min-height'][0] == '44px'
                     for selector in rule['selectors']]
        for name in PAGES:
            for tag in re.findall(r'<input\b[^>]*>', read(TEMPLATES, name)):
                kind = re.search(r'\btype=([^ >]+)', tag)
                kind = kind.group(1).strip('"'+"'") if kind else None
                if kind in ('radio', 'checkbox', 'hidden', 'submit', 'button', 'range', 'image'):
                    continue
                if kind is None:
                    ident = re.search(r'\bid="([^"]*)"', tag)
                    self.assertTrue(ident and any(selector.endswith('#' + ident.group(1)) for selector in selectors), tag)
                else:
                    self.assertTrue(any('input[type="%s"]' % kind in selector for selector in selectors), tag)

    def test_the_small_icons_that_act_get_padding_up_to_44_pixels(self):
        self.assertEqual('14px', declared('html.fm-modern .tunnel-inclusions img.button-remove', 'padding'))
        self.assertEqual('14px', declared('html.fm-modern .tunnel-exclusions img.button-unforbid', 'padding'))
        self.assertEqual('content-box', declared('html.fm-modern .tunnel-exclusions img.button-unforbid', 'box-sizing'))
