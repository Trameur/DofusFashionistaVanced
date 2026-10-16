# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The comparison pages of the modern design: the stat tables of a comparison scroll inside their own frame with the name column kept, the chooser keeps its measure, the basket panel fits a phone and opens from the keyboard, the DofusBook export is a card, and every new rule is prefixed by the modern class so the classic design is untouched."""
import io
import os

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import (STATIC, chain_of, parse, read_css, stylesheet, winning)

MODERN = stylesheet('modern.css')
COMPARE_SHEETS = [(name, stylesheet(name)) for name in ('forms.css', 'solution.css', 'compare.css', 'modern.css')]
CHOOSE_SHEETS = [(name, stylesheet(name)) for name in ('forms.css', 'choose_compare_sets.css', 'modern.css')]
LIVE = ['fm-modern', 'fm-light']
ROOT = 'html.fm-modern'
MARKER = '/* ---------- Comparison pages: compare sets, chooser, basket, DofusBook export ---------- */'
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
HTML = [('html', {})]
PAGE = [('html', {}), ('table', {'class': 'compare-page'}), ('tbody', {}), ('tr', {}), ('td', {})]
STAT_TABLE = ('table', {'class': 'solution-stat-table'})
HEADER = [('html', {}), ('div', {'class': 'header-controls'})]
CART = HEADER + [('div', {'class': 'compare-cart'})]
PANEL = ('div', {'class': 'compare-cart-panel'})


def template(name):
    with io.open(os.path.join(TEMPLATES, name + '.html'), encoding='utf-8') as handle:
        return handle.read()


def rules_after_the_marker():
    with io.open(os.path.join(STATIC, 'modern.css'), encoding='utf-8') as handle:
        source = handle.read()
    after = source[source.index(MARKER):]
    after = after[len(MARKER):]
    following = after.find('/* ---------- ')
    return parse(after if following < 0 else after[:following])


def value(sheets, ancestors, element, prop, width, classes=LIVE):
    found = winning(sheets, chain_of(ancestors, element[0], element[1], classes), prop, width)
    return None if found is None else found[0]


class TheStatTablesScrollInsideTheirFrameTests(SimpleTestCase):

    def stat(self, prop, width):
        return value(COMPARE_SHEETS, PAGE, STAT_TABLE, prop, width)

    def test_a_stat_table_is_a_horizontal_scroll_frame_up_to_900(self):
        for width in (375, 768, 900):
            self.assertEqual('block', self.stat('display', width), width)
            self.assertEqual('auto', self.stat('overflow-x', width), width)
            self.assertEqual('100%', self.stat('max-width', width), width)

    def test_a_stat_table_is_untouched_from_901(self):
        for width in (901, 1280, 1920):
            self.assertIsNone(self.stat('overflow-x', width), width)
            self.assertIsNone(self.stat('display', width), width)

    def test_the_rows_keep_the_full_frame_width(self):
        ancestors = PAGE + [STAT_TABLE]
        self.assertEqual('table', value(COMPARE_SHEETS, ancestors, ('tbody', {}), 'display', 375))
        self.assertEqual('100%', value(COMPARE_SHEETS, ancestors, ('tbody', {}), 'width', 375))

    def test_the_spell_name_column_stays_while_the_frame_scrolls(self):
        cell = ('td', {'class': 'compare-spell-name-cell'})
        ancestors = PAGE + [STAT_TABLE, ('tr', {'class': 'solution-stat-summary-line'})]
        self.assertEqual('sticky', value(COMPARE_SHEETS, ancestors, cell, 'position', 375))
        self.assertEqual('0', value(COMPARE_SHEETS, ancestors, cell, 'left', 375))
        self.assertEqual('var(--fm-surface-2)', value(COMPARE_SHEETS, ancestors, cell, 'background-color', 375))
        self.assertIsNone(value(COMPARE_SHEETS, ancestors, cell, 'position', 1280))

    def test_the_stat_name_column_stays_while_the_frame_scrolls(self):
        name = ('th', {'scope': 'row'})
        ancestors = PAGE + [STAT_TABLE, ('tr', {'class': 'solution-stat-summary-line'})]
        for width in (375, 768, 900):
            self.assertEqual('sticky', value(COMPARE_SHEETS, ancestors, name, 'position', width), width)
            self.assertEqual('0', value(COMPARE_SHEETS, ancestors, name, 'left', width), width)
            self.assertEqual('var(--fm-surface-2)', value(COMPARE_SHEETS, ancestors, name, 'background-color', width),
                             width)
        self.assertIsNone(value(COMPARE_SHEETS, ancestors, name, 'position', 901))

    def test_the_sticky_stat_name_keeps_the_zebra_tint_on_even_rows(self):
        even = [rule for rule in MODERN if rule['media'] == '(max-width:900px)'
                and any(s.endswith(':nth-child(even) > th[scope="row"]') for s in rule['selectors'])]
        self.assertTrue(even)
        self.assertIn('linear-gradient', even[0]['declarations']['background-image'][0])

    def test_a_tip_on_the_last_rows_opens_upward_inside_the_frame(self):
        last = [rule for rule in MODERN if rule['media'] == '(max-width:900px)'
                and any('tr:nth-last-child(-n+8) .spell-tip-panel' in s for s in rule['selectors'])]
        self.assertTrue(last)
        self.assertEqual('auto', last[0]['declarations']['top'][0])
        self.assertEqual('calc(100% + 7px)', last[0]['declarations']['bottom'][0])

    def test_a_focused_stat_tip_shows_a_ring(self):
        found = [rule for rule in rules_after_the_marker()
                 if any(s.endswith('.solution-stat-summary-value-cell > .spell-tip:focus-visible') for s in rule['selectors'])]
        self.assertTrue(found)
        self.assertEqual('2px solid var(--fm-accent-text)', found[0]['declarations']['outline'][0])

    def test_the_spell_name_column_gives_room_to_four_builds_on_a_phone(self):
        cell = ('td', {'class': 'compare-spell-name-cell'})
        ancestors = PAGE + [STAT_TABLE, ('tr', {'class': 'solution-stat-summary-line'})]
        for width in (375, 480):
            self.assertEqual('110px', value(COMPARE_SHEETS, ancestors, cell, 'min-width', width), width)
        self.assertEqual('140px', value(COMPARE_SHEETS, ancestors, cell, 'min-width', 481))

    def test_the_two_columns_layout_stacks_through_900(self):
        for width in (375, 768, 900):
            self.assertEqual('block', value(COMPARE_SHEETS, PAGE[:-1], ('td', {}), 'display', width), width)
        for width in (901, 1280):
            self.assertIsNone(value(COMPARE_SHEETS, PAGE[:-1], ('td', {}), 'display', width), width)

    def test_the_sharing_row_stacks_and_the_field_fills_the_width_up_to_900(self):
        part = ('div', {'class': 'compare-share-part'})
        link = ('input', {'id': 'link_sharing_url_text'})
        ancestors = HTML + [('div', {'class': 'compare-share'}), part]
        for width in (375, 768, 900):
            self.assertEqual('block', value(COMPARE_SHEETS, HTML, part, 'display', width), width)
            self.assertEqual('100%', value(COMPARE_SHEETS, ancestors, link, 'width', width), width)
        self.assertIsNone(value(COMPARE_SHEETS, HTML, part, 'display', 901))
        self.assertIsNone(value(COMPARE_SHEETS, ancestors, link, 'width', 901))


class TheChooserKeepsItsMeasureTests(SimpleTestCase):

    def test_every_block_is_held_to_960_and_centred(self):
        for cls in ('compare-picker', 'compare-manual-title', 'compare-manual-help', 'compare-link-div-outer',
                    'compare-link-button-div', 'compare-link-error-div'):
            for width in (375, 1920, 2560):
                block = ('div', {'class': cls})
                self.assertEqual('960px', value(CHOOSE_SHEETS, HTML, block, 'max-width', width), (cls, width))
                self.assertEqual('auto', value(CHOOSE_SHEETS, HTML, block, 'margin-left', width), (cls, width))

    def test_a_link_field_fills_its_row_on_a_phone_and_keeps_its_width_above(self):
        field = ('input', {'class': 'compare-link-input'})
        self.assertEqual('100%', value(CHOOSE_SHEETS, HTML, field, 'width', 375))
        self.assertEqual('100%', value(CHOOSE_SHEETS, HTML, field, 'width', 700))
        self.assertEqual('600px', value(CHOOSE_SHEETS, HTML, field, 'width', 701))

    def test_a_section_and_a_build_choice_are_cards(self):
        section = ('section', {'class': 'compare-picker-section'})
        self.assertEqual('var(--fm-surface-2)', value(CHOOSE_SHEETS, HTML, section, 'background', 1280))
        self.assertEqual('var(--fm-radius)', value(CHOOSE_SHEETS, HTML, section, 'border-radius', 1280))
        card = ('label', {'class': 'compare-build-choice-card'})
        self.assertEqual('44px', value(CHOOSE_SHEETS, HTML, card, 'min-height', 375))
        self.assertEqual('left', value(CHOOSE_SHEETS, HTML, card, 'text-align', 375))

    def test_a_chosen_build_keeps_the_accent_in_both_themes(self):
        card = ('label', {'class': 'compare-build-choice-card selected'})
        for classes in (['fm-modern', 'fm-light'], ['fm-modern', 'fm-dark', 'dark-theme-active']):
            found = winning(CHOOSE_SHEETS, chain_of(HTML, card[0], card[1], classes), 'border-color', 1280)
            self.assertEqual(('var(--fm-accent-strong)', 'modern.css'), found[:2], classes)

    def test_a_long_list_scrolls_inside_its_section_from_601(self):
        listing = ('div', {'class': 'compare-picker-list'})
        self.assertIsNone(value(CHOOSE_SHEETS, HTML, listing, 'overflow-y', 600))
        self.assertEqual('auto', value(CHOOSE_SHEETS, HTML, listing, 'overflow-y', 601))


class TheBasketFitsAPhoneTests(SimpleTestCase):

    def panel(self, prop, width):
        return value(COMPARE_SHEETS, CART, PANEL, prop, width)

    def test_the_panel_spans_the_header_row_below_the_toggle_up_to_600(self):
        for width in (375, 600):
            self.assertEqual('0', self.panel('left', width), width)
            self.assertEqual('0', self.panel('right', width), width)
            self.assertEqual('auto', self.panel('top', width), width)
            self.assertEqual('auto', self.panel('width', width), width)
            self.assertEqual('static', value(COMPARE_SHEETS, HEADER, ('div', {'class': 'compare-cart'}),
                                             'position', width), width)

    def test_the_panel_hangs_from_the_toggle_above_600(self):
        self.assertEqual('relative', value(COMPARE_SHEETS, HEADER, ('div', {'class': 'compare-cart'}), 'position', 601))
        self.assertEqual('250px', self.panel('width', 601))
        self.assertIsNone(self.panel('left', 601))

    def test_the_basket_controls_are_touch_targets_on_a_phone(self):
        ancestors = CART + [PANEL]
        self.assertEqual('36px', value(COMPARE_SHEETS, ancestors, ('button', {'class': 'cc-x'}), 'min-height', 375))
        self.assertEqual('44px', value(COMPARE_SHEETS, ancestors, ('button', {'class': 'cc-go button-generic'}),
                                       'min-height', 375))

    def test_the_panel_opens_when_the_keyboard_reaches_the_basket(self):
        found = [rule for rule in MODERN if rule['media'] == '(hover:hover)'
                 and any(':focus-within .compare-cart-panel' in s for s in rule['selectors'])]
        self.assertTrue(found)
        self.assertEqual('block', found[0]['declarations']['display'][0])
        self.assertTrue(all(s.startswith(ROOT) for s in found[0]['selectors']))


class TheExportPageIsACardTests(SimpleTestCase):

    def wrap(self, prop, width):
        return value(COMPARE_SHEETS, HTML, ('div', {'class': 'export-wrap'}), prop, width)

    def test_the_wrapper_is_an_atelier_card(self):
        self.assertEqual('var(--fm-surface-2)', self.wrap('background', 1280))
        self.assertEqual('var(--fm-radius)', self.wrap('border-radius', 1280))
        self.assertEqual('640px', self.wrap('max-width', 1280))

    def test_the_card_padding_tightens_on_a_phone(self):
        self.assertEqual('var(--fm-space-4)', self.wrap('padding', 375))
        self.assertEqual('var(--fm-space-5)', self.wrap('padding', 601))

    def test_the_open_action_is_a_full_width_touch_target_on_a_phone(self):
        ancestors = HTML + [('div', {'class': 'export-go'})]
        action = ('a', {'class': 'button-generic'})
        self.assertEqual('44px', value(COMPARE_SHEETS, ancestors, action, 'min-height', 375))
        self.assertEqual('100%', value(COMPARE_SHEETS, ancestors, action, 'width', 375))
        self.assertIsNone(value(COMPARE_SHEETS, ancestors, action, 'width', 1280))

    def test_the_page_still_carries_the_classes_the_rules_address(self):
        page = template('dofusbook_export')
        for token in ('export-wrap', 'export-go', 'export-piece', 'export-note', 'button-generic'):
            self.assertIn(token, page, token)


class TheClassicDesignIsUntouchedTests(SimpleTestCase):

    def test_every_rule_of_the_section_is_prefixed_by_the_modern_class(self):
        rules = rules_after_the_marker()
        self.assertTrue(rules)
        for rule in rules:
            for selector in rule['selectors']:
                self.assertTrue(selector.startswith(ROOT), selector)

    def test_the_new_classes_have_no_classic_rule(self):
        for name in ('forms.css', 'compare.css', 'solution.css', 'choose_compare_sets.css', 'responsive.css'):
            source = read_css(name)
            self.assertNotIn('compare-share', source, name)
            self.assertNotIn('compare-manual-help', source, name)

    def test_the_templates_only_gained_classes(self):
        self.assertEqual(1, template('compare_sets').count('class="compare-share"'))
        self.assertEqual(2, template('compare_sets').count('compare-share-part'))
        self.assertIn('class="text compare-manual-help"', template('choose_compare_sets'))
