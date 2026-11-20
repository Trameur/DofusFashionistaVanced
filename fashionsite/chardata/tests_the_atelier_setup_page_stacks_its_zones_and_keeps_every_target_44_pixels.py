# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The setup page of the modern design: the page carries the opt-in class, the static inline styles moved to classes with the values they had, every new rule is prefixed by the modern class and scoped to the page, the four zones are seamed panels, the media queries of the section are unique and ascending, and the winning rule of the cascade gives the fields, labels and summaries 44 pixels, the exo counts 5rem and the main buttons a focus ring at every width where a competing rule would take it away."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import (STATIC, chain_of, parse, setup_sheets, stylesheet, winning)

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
START = '/* ---------- Setup page: presets, build form, doors and live preview ---------- */'
END = '/* ---------- Setup tunnel: weights, wizard, options, lock items, forbid items ---------- */'
PANELS = ('.setup-recipes', '.setup-zone-form', '.setup-zone-options', '.setup-preview')
SCOPE = 'html.fm-modern .setup-atelier '
MODERN = ['fm-modern', 'fm-light']
CLASSIC = ['fm-light']
FOCUSED = 'is-focus-visible'
PHONE_BAND = (360, 480)
MIDDLE_BAND = (481, 900)
WIDE_BAND = (901, 1440, 1920)
EVERY_WIDTH = PHONE_BAND + MIDDLE_BAND + WIDE_BAND

SETUP = ('div', {'class': 'setup-atelier setup-new'})
PREVIEW = ('aside', {'id': 'setup-preview', 'class': 'setup-preview'})
BOXES = [('html', {}), SETUP, ('table', {'id': 'table-checkboxes', 'class': 'build-boxes-section'}), ('tbody', {}), ('tr', {}),
         ('td', {'id': 'table-checkboxes-column-0', 'class': 'build-boxes-column'})]


def read(directory, name):
    with io.open(os.path.join(directory, name), encoding='utf-8') as handle:
        return handle.read()


def section_source():
    source = read(STATIC, 'modern.css')
    start = source.index(START)
    return re.sub(r'/\*.*?\*/', '', source[start:source.index(END, start)], flags=re.S)


def page_rules():
    return parse(section_source())


def declared(selector, prop, media=None):
    found = [rule['declarations'][prop][0] for rule in page_rules()
             if rule['media'] == media and selector in rule['selectors'] and prop in rule['declarations']]
    return found[-1] if found else None


def values_of(name):
    values = {}
    for rule in stylesheet(name):
        for selector in rule['selectors']:
            values[selector] = {key: value[0] for key, value in rule['declarations'].items()}
    return values


def focus_state(rules):
    return [dict(rule, selectors=[selector.replace(':focus-visible', '.' + FOCUSED) for selector in rule['selectors']]) for rule in rules]


def sheets(focus=False):
    return [(name, focus_state(rules) if focus else rules) for name, rules in setup_sheets()]


def value(ancestors, element, prop, width, focus=False, classes=MODERN):
    attrs = dict(element[1])
    if focus:
        attrs['class'] = (attrs.get('class', '') + ' ' + FOCUSED).strip()
    found = winning(sheets(focus), chain_of(ancestors, element[0], attrs, classes), prop, width)
    return None if found is None else found[0]


def winner(ancestors, element, prop, width, classes=MODERN):
    return winning(sheets(), chain_of(ancestors, element[0], element[1], classes), prop, width)


def is_important(name, selector, prop):
    for sheet, rules in setup_sheets():
        if sheet == name:
            return any(selector in rule['selectors'] and rule['declarations'].get(prop, ('', False))[1] for rule in rules)
    return False


class TheSetupPageOptsInAndKeepsItsValuesTests(SimpleTestCase):

    def test_the_root_carries_the_opt_in_class_and_the_new_build_class(self):
        self.assertIn('class="setup-atelier{% if is_new_char %} setup-new{% endif %}"', read(TEMPLATES, 'projdetails.html'))

    def test_the_static_inline_styles_moved_to_classes(self):
        for style in re.findall(r'\sstyle="([^"]*)"', read(TEMPLATES, 'projdetails.html')):
            self.assertIn('display:none', style.replace(' ', ''), style)

    def test_the_header_classes_are_used_by_the_build_bar(self):
        header = read(TEMPLATES, 'main-header.html')
        self.assertIn('class="proj-info-main {% if is_guest', header)
        self.assertIn('class="proj-info-side"', header)
        self.assertIn('class="proj-info-side proj-info-side-owner"', header)

    def test_every_rule_is_under_the_modern_prefix_and_the_page_class(self):
        for rule in page_rules():
            for selector in rule['selectors']:
                self.assertTrue(selector.startswith('html.fm-modern '), selector)
                self.assertTrue('.setup-atelier' in selector or ':has(.setup-new)' in selector, selector)

    def test_no_selector_of_the_section_is_dead(self):
        source = section_source()
        self.assertNotIn('textarea', source)
        self.assertNotIn('.setup-zone-options > br', source)
        for template in ('projdetails.html', 'setup_more_options.html'):
            self.assertNotIn('<textarea', read(TEMPLATES, template))

    def test_the_media_queries_of_the_section_are_unique_and_ascending(self):
        found = [' '.join(prelude.split()) for prelude in re.findall(r'@media ([^{]+)\{', section_source())]
        found = [prelude for prelude in found if 'forced-colors' not in prelude]
        self.assertEqual(len(found), len(set(found)), found)
        firsts = [int(re.search(r'\d+', prelude).group()) if re.search(r'\d', prelude) else 0 for prelude in found]
        self.assertEqual(sorted(firsts), firsts, found)

    def test_the_section_uses_the_site_breakpoints(self):
        found = set(re.findall(r'(?:min|max)-width:\s*(\d+)px', ' '.join(re.findall(r'@media ([^{]+)\{', section_source()))))
        self.assertEqual({'480', '481', '900', '901', '1279', '1280', '1440', '1759', '1760'}, found)


class TheInlineStylesMovedToClassesWithTheValuesTheyHadTests(SimpleTestCase):
    ORIGINAL = {
        'level input': (('html', {}), SETUP, ('table', {'class': 'register'}), ('tr', {'class': 'register-line'}),
                        ('td', {'class': 'setup-level-cell'}),
                        ('input', {'class': 'input-value pretty-input change-modifies-state setup-level-input', 'type': 'number'}),
                        {'width': '40px'}),
        'level cell': (('html', {}), SETUP, ('table', {'class': 'register'}), ('tr', {'class': 'register-line'}),
                       ('td', {'class': 'setup-level-cell', 'align': 'left'}), None, {'padding': '0px 3px'}),
        'class guide': (('html', {}), SETUP, ('td', {}), ('div', {'class': 'setup-class-guide'}), None,
                        {'font-size': '0.85em', 'opacity': '0.9', 'margin-top': '3px'}),
        'last column': (('html', {}), SETUP, ('table', {'id': 'table-checkboxes', 'class': 'build-boxes-section'}), ('tr', {}),
                        ('td', {'id': 'table-checkboxes-column-3', 'class': 'build-boxes-column build-boxes-aspects-column build-boxes-last-column'}),
                        None, {'border-radius': '0px 0px 4px 0px'}),
        'choice box': (('html', {}), SETUP, ('form', {}), ('div', {'id': 'publish-choice', 'class': 'setup-choice-box'}), None,
                       {'margin-bottom': '10px'}),
        'bar main narrow': (('html', {}), ('div', {'class': 'proj_info'}), ('div', {'class': 'proj-info-main proj-info-main-narrow'}), None, None,
                            {'display': 'table-cell', 'width': '680px'}),
        'bar main wide': (('html', {}), ('div', {'class': 'proj_info'}), ('div', {'class': 'proj-info-main proj-info-main-wide'}), None, None,
                          {'display': 'table-cell', 'width': '840px'}),
        'bar side': (('html', {}), ('div', {'class': 'proj_info'}), ('div', {'class': 'proj-info-side'}), None, None,
                     {'display': 'table-cell', 'vertical-align': 'middle', 'width': '200px'}),
        'bar side owner': (('html', {}), ('div', {'class': 'proj_info'}), ('div', {'class': 'proj-info-side proj-info-side-owner'}), None, None,
                           {'display': 'table-cell', 'vertical-align': 'middle', 'width': '200px', 'text-align': 'right',
                            'padding-right': '14px'}),
    }

    def target(self, spec):
        chain = [item for item in spec[:-1] if item is not None]
        return chain[:-1], chain[-1], spec[-1]

    def test_every_moved_declaration_gives_its_original_value_in_the_classic_design(self):
        sheet_set = [('home.css', stylesheet('home.css'))] + setup_sheets()
        for label, spec in self.ORIGINAL.items():
            ancestors, element, expected = self.target(spec)
            for classes in (CLASSIC, ['fm-dark']):
                for prop, wanted in expected.items():
                    found = winning(sheet_set, chain_of(ancestors, element[0], element[1], classes), prop, 1920)
                    self.assertIsNotNone(found, (label, prop))
                    self.assertEqual(wanted, found[0], (label, prop, classes))

    def test_a_classic_phone_only_loses_a_moved_value_to_an_important_rule_as_the_inline_style_did(self):
        sheet_set = [('home.css', stylesheet('home.css'))] + setup_sheets()
        for label, spec in self.ORIGINAL.items():
            ancestors, element, expected = self.target(spec)
            for prop, wanted in expected.items():
                found = winning(sheet_set, chain_of(ancestors, element[0], element[1], CLASSIC), prop, 375)
                if found[0] != wanted:
                    rule_sheet = dict((name, rules) for name, rules in sheet_set)[found[1]]
                    self.assertTrue(any(found[2] in rule['selectors'] and rule['declarations'].get(prop, ('', False))[1]
                                        for rule in rule_sheet), (label, prop, found))

    def test_the_form_classes_carry_the_values_the_inline_styles_had(self):
        values = values_of('forms.css')
        self.assertEqual('40px', values['.register input.setup-level-input']['width'])
        self.assertEqual('0px 3px', values['.register td.setup-level-cell']['padding'])
        self.assertEqual('10px', values['div.setup-choice-box']['margin-bottom'])
        self.assertEqual('3px', values['div.setup-class-guide']['margin-top'])
        self.assertEqual('0.85em', values['div.setup-class-guide']['font-size'])
        self.assertEqual('0.9', values['div.setup-class-guide']['opacity'])
        self.assertEqual('0px 0px 4px 0px', values['td.build-boxes-column.build-boxes-last-column']['border-radius'])

    def test_the_build_bar_classes_carry_the_values_the_inline_styles_had(self):
        values = values_of('home.css')
        self.assertEqual('table-cell', values['.proj-info-main']['display'])
        self.assertEqual('680px', values['.proj-info-main-narrow']['width'])
        self.assertEqual('840px', values['.proj-info-main-wide']['width'])
        self.assertEqual('table-cell', values['.proj-info-side']['display'])
        self.assertEqual('middle', values['.proj-info-side']['vertical-align'])
        self.assertEqual('200px', values['.proj-info-side']['width'])
        self.assertEqual('right', values['.proj-info-side-owner']['text-align'])
        self.assertEqual('14px', values['.proj-info-side-owner']['padding-right'])


class TheSetupPageIsSeamedPanelsTests(SimpleTestCase):

    def test_the_four_zones_are_seamed_panels(self):
        for panel in PANELS:
            self.assertEqual('1.5px dashed var(--fm-seam)', declared(SCOPE + panel, 'outline'), panel)
            self.assertEqual('-6px', declared(SCOPE + panel, 'outline-offset'), panel)


class TheWinningRuleGivesEveryTargetItsFortyFourPixelsTests(SimpleTestCase):

    def test_a_preview_weight_input_is_44_pixels_and_16_pixels_at_every_width(self):
        element = ('input', {'class': 'white-pretty-input wm-input wm-min-input', 'type': 'number'})
        ancestors = [('html', {}), SETUP, PREVIEW, ('div', {'class': 'wm-row'})]
        for width in EVERY_WIDTH:
            self.assertEqual('44px', value(ancestors, element, 'min-height', width), width)
            self.assertEqual('16px', value(ancestors, element, 'font-size', width), width)

    def test_the_modern_rule_beats_the_important_phone_rule_of_the_preview_input(self):
        element = ('input', {'class': 'white-pretty-input wm-input wm-min-input', 'type': 'number'})
        ancestors = [('html', {}), SETUP, PREVIEW, ('div', {'class': 'wm-row'})]
        for width in PHONE_BAND:
            sheet, selector = winner(ancestors, element, 'min-height', width)[1:]
            self.assertEqual('modern.css', sheet, width)
            self.assertIn('.setup-atelier', selector)
            self.assertTrue(is_important('setup.css', '#setup-preview .wm-row .wm-input', 'min-height'))

    def test_a_checkbox_label_is_44_pixels_at_every_width(self):
        element = ('label', {})
        for width in EVERY_WIDTH:
            self.assertEqual('44px', value(BOXES, element, 'min-height', width), width)

    def test_the_modern_rule_beats_the_id_rule_of_the_phone_checkbox_labels(self):
        for width in PHONE_BAND:
            sheet, selector = winner(BOXES, ('label', {}), 'min-height', width)[1:]
            self.assertEqual('modern.css', sheet, width)
            self.assertIn('#table-checkboxes label', selector)

    def test_a_preview_section_summary_is_44_pixels_at_every_width(self):
        ancestors = [('html', {}), SETUP, PREVIEW, ('details', {'class': 'wm-section'})]
        for width in EVERY_WIDTH:
            self.assertEqual('44px', value(ancestors, ('summary', {}), 'min-height', width), width)
        for width in MIDDLE_BAND + WIDE_BAND:
            self.assertEqual('modern.css', winner(ancestors, ('summary', {}), 'min-height', width)[1], width)

    def test_a_field_without_a_type_attribute_is_44_pixels_and_16_pixels_up_to_900(self):
        ancestors = [('html', {}), SETUP, ('table', {'class': 'register'}), ('tr', {'class': 'register-line'}), ('td', {})]
        element = ('input', {'class': 'input-value pretty-input change-modifies-state', 'id': 'input-char-name', 'name': 'charname'})
        for width in EVERY_WIDTH:
            self.assertEqual('44px', value(ancestors, element, 'min-height', width), width)
        for width in PHONE_BAND + MIDDLE_BAND:
            self.assertEqual('16px', value(ancestors, element, 'font-size', width), width)

    def test_an_untyped_field_outside_the_register_is_still_44_pixels(self):
        found = winning(sheets(), chain_of([('html', {}), SETUP, ('div', {})], 'input', {'class': 'pretty-input'}, MODERN), 'min-height', 1440)
        self.assertEqual('44px', found[0])
        self.assertIn(':not([type])', found[2])

    def test_a_text_and_a_number_field_are_44_pixels_at_every_width(self):
        ancestors = [('html', {}), SETUP, ('div', {})]
        for kind in ('text', 'number'):
            for width in EVERY_WIDTH:
                self.assertEqual('44px', value(ancestors, ('input', {'type': kind, 'class': 'pretty-input'}), 'min-height', width), (kind, width))

    def test_a_retro_exo_count_stays_5rem_where_the_phone_rule_stretches_it(self):
        ancestors = [('html', {}), SETUP, ('div', {'class': 'setup-more'}), ('label', {'class': 'setup-more-count'})]
        element = ('input', {'class': 'pretty-input', 'type': 'number', 'name': 'ap_exo'})
        for width in EVERY_WIDTH:
            self.assertEqual('5rem', value(ancestors, element, 'width', width), width)
            self.assertEqual('44px', value(ancestors, element, 'min-height', width), width)
        self.assertEqual('modern.css', winner(ancestors, element, 'width', 900)[1])

    def test_a_preview_weight_name_breaks_between_words_before_it_breaks_a_word(self):
        ancestors = [('html', {}), SETUP, PREVIEW, ('div', {'class': 'wm-row'})]
        for width in EVERY_WIDTH:
            self.assertEqual('normal', value(ancestors, ('span', {'class': 'wm-name'}), 'word-break', width), width)
            self.assertEqual('break-word', value(ancestors, ('span', {'class': 'wm-name'}), 'overflow-wrap', width), width)


class TheMainButtonsKeepTheirFocusRingTests(SimpleTestCase):
    DOORS = [('html', {}), SETUP, ('form', {}), ('div', {'id': 'submit-mode', 'class': 'setup-doors'})]

    def test_the_optimize_button_shows_the_ring_at_every_width(self):
        element = ('input', {'class': 'submit-button button-generic setup-primary', 'type': 'submit', 'name': 'optimize'})
        for width in EVERY_WIDTH:
            self.assertEqual('var(--fm-ring)', value(self.DOORS, element, 'box-shadow', width, focus=True), width)

    def test_the_secondary_doors_show_the_ring_at_every_width(self):
        element = ('input', {'class': 'submit-button button-generic setup-secondary', 'type': 'submit'})
        for width in EVERY_WIDTH:
            self.assertEqual('var(--fm-ring)', value(self.DOORS, element, 'box-shadow', width, focus=True), width)

    def test_the_tailor_button_shows_the_ring_at_every_width(self):
        ancestors = [('html', {}), SETUP, ('form', {}), ('div', {'id': 'choices'})]
        element = ('button', {'id': 'button-save-and-tailor', 'class': 'button-generic', 'type': 'button'})
        for width in EVERY_WIDTH:
            self.assertEqual('var(--fm-ring)', value(ancestors, element, 'box-shadow', width, focus=True), width)

    def test_an_unfocused_button_keeps_the_gold_shadow(self):
        element = ('input', {'class': 'submit-button button-generic setup-primary', 'type': 'submit'})
        self.assertNotEqual('var(--fm-ring)', value(self.DOORS, element, 'box-shadow', 1440))

    def test_the_important_rules_of_the_targets_live_in_the_screen_block_so_print_keeps_none(self):
        marks = ('focus-visible', '.wm-input', '.setup-more-count input')
        for rule in page_rules():
            if any(marks_in in selector for selector in rule['selectors'] for marks_in in marks):
                if any(flag for _, flag in rule['declarations'].values()):
                    self.assertEqual('screen', rule['media'], rule['selectors'])


class TheZonesStackAndWidenByWidthTests(SimpleTestCase):

    def boxes(self, width):
        return value([('html', {}), SETUP], ('table', {'id': 'table-checkboxes', 'class': 'build-boxes-section'}), 'grid-template-columns', width)

    def test_the_checkbox_grid_is_one_column_on_a_phone_and_from_1440_to_1759(self):
        one = 'minmax(0,1fr)'
        for width in (360, 480, 1440, 1536, 1759):
            self.assertEqual(one, self.boxes(width), width)

    def test_the_checkbox_grid_is_two_columns_between_481_and_1439_and_from_1760(self):
        two = 'repeat(2,minmax(0,1fr))'
        for width in (481, 768, 900, 1280, 1439, 1760, 1920):
            self.assertEqual(two, self.boxes(width), width)

    def test_the_form_and_options_zones_sit_side_by_side_from_1440(self):
        side = SCOPE + '.setup-form-col > form'
        wide = [rule['media'] for rule in page_rules() if side in rule['selectors'] and 'grid-template-columns' in rule['declarations']]
        self.assertEqual(1, len(wide))
        self.assertIn('min-width:1440px', wide[0].replace(' ', ''))

    def test_the_register_is_two_columns_from_1440_to_1759_and_four_from_1760(self):
        register = SCOPE + '.register > tbody'
        two = declared(register, 'grid-template-columns', '(min-width:1440px) and (max-width:1759px)')
        four = declared(register, 'grid-template-columns', '(min-width:1760px)')
        self.assertEqual('repeat(2,minmax(0,1fr))', two)
        self.assertEqual('repeat(4,minmax(0,1fr))', four)

    def test_the_preview_sits_below_the_zones_from_901_to_1279_and_beside_them_from_1280(self):
        layout = [('html', {}), SETUP]
        for width in (901, 1100, 1279):
            self.assertEqual('block', value(layout, ('div', {'class': 'setup-layout'}), 'display', width), width)
            self.assertEqual('auto', value(layout + [('div', {'class': 'setup-layout'})], ('aside', {'class': 'setup-preview'}), 'width', width), width)
        for width in (1280, 1440, 1920):
            self.assertEqual('flex', value(layout, ('div', {'class': 'setup-layout'}), 'display', width), width)
            self.assertEqual('372px', value(layout + [('div', {'class': 'setup-layout'})], ('aside', {'class': 'setup-preview'}), 'width', width), width)

    def test_the_heading_sits_beside_its_sentence_from_1280(self):
        heading = 'html.fm-modern .setup-atelier.setup-new'
        grid = [rule['media'] for rule in page_rules() if heading in rule['selectors'] and rule['declarations'].get('display', [''])[0] == 'grid']
        self.assertEqual(1, len(grid))
        self.assertIn('min-width:1280px', grid[0].replace(' ', ''))

    def test_the_tips_stay_next_to_their_labels(self):
        found = declared(SCOPE + '#table-checkboxes td.build-boxes-column', 'grid-template-columns')
        self.assertEqual('repeat(2,minmax(min-content,max-content) auto)', found)
        self.assertEqual('start', declared(SCOPE + '#table-checkboxes td.build-boxes-column', 'justify-content'))

    def test_the_fields_keep_a_16_pixel_font_up_to_900(self):
        found = [rule for rule in page_rules() if SCOPE + 'input' in rule['selectors'] and 'font-size' in rule['declarations']]
        self.assertEqual(1, len(found))
        self.assertEqual('16px', found[0]['declarations']['font-size'][0])
        self.assertIn('max-width:900px', found[0]['media'].replace(' ', ''))
        self.assertIn(SCOPE + 'select', found[0]['selectors'])
