# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The encyclopedia of the modern design: item and set lists are card grids that grow with the width, item and set pages are cards of sections with a bonus ladder, item icons sit in a loot frame, the most used page wraps its names, no template carries a style attribute, the shared rules apply only below the opt-in class of these pages, and every new rule is prefixed by the modern class so the classic design is untouched."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import (STATIC, chain_of, parse, stylesheet, winning)

MODERN = 'modern.css'
INDEX = [(name, stylesheet(name)) for name in ('forms.css', 'encyclopedia.css', MODERN)]
ITEM = [(name, stylesheet(name)) for name in ('encyclopedia_detail.css', 'encyclopedia_item.css', MODERN)]
SET_STYLE = parse(re.sub(r'/\*.*?\*/', '', re.search(r'<style>(.*?)</style>', io.open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'encyclopedia_set.html'), encoding='utf-8').read(), re.S).group(1), flags=re.S))
SET = [('encyclopedia_set.html style', SET_STYLE), (MODERN, stylesheet(MODERN))]
MOST_USED = [(name, stylesheet(name)) for name in ('encyclopedia_detail.css', 'most_used.css', MODERN)]
MODERN_LIVE = ['fm-modern', 'fm-light']
CLASSIC_LIVE = ['fm-light']
MARKER = '/* ---------- Encyclopedia: index, item and set pages, sets list, most used ---------- */'
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
PAGES = ('encyclopedia', 'encyclopedia_item', 'encyclopedia_sets', 'encyclopedia_set', 'encyclopedia_most_used')


def template(name):
    with io.open(os.path.join(TEMPLATES, name + '.html'), encoding='utf-8') as handle:
        return handle.read()


def value(sheets, ancestors, element, prop, width, classes=MODERN_LIVE):
    found = winning(sheets, chain_of([('html', {})] + ancestors, element[0], element[1], classes), prop, width)
    return None if found is None else found[0]


def rules_after_the_marker():
    with io.open(os.path.join(STATIC, MODERN), encoding='utf-8') as handle:
        source = handle.read()
    return parse(re.sub(r'/\*.*?\*/', '', source[source.index(MARKER):], flags=re.S))


GRID = ('div', {'class': 'encyclopedia-grid'})
CARD = ('div', {'class': 'encyclopedia-card brown-box'})
ROOT = ('div', {'class': 'encyclopedia-item encyclopedia-atelier text'})
PAGE_ROOT = ('div', {'class': 'encyclopedia-page encyclopedia-atelier text'})
OTHER_ROOT = ('div', {'class': 'encyclopedia-item text'})
ITEM_CARD = ('div', {'class': 'encyclopedia-item-card brown-box'})
SET_CARD = ('div', {'class': 'encyclopedia-item-card brown-box encyclopedia-set-card'})
SECTION = ('div', {'class': 'encyclopedia-section'})


class TheItemListIsACardGridThatGrowsWithTheWidthTests(SimpleTestCase):

    def columns(self, width, classes=MODERN_LIVE):
        return value(INDEX, [], GRID, 'grid-template-columns', width, classes)

    def test_modern_columns_are_as_many_as_the_width_allows_from_a_phone_to_2560(self):
        for width in (375, 768, 1280, 1920, 2560):
            self.assertEqual('repeat(auto-fill,minmax(min(100%,320px),1fr))', self.columns(width).replace(' ', ''), width)

    def test_classic_keeps_its_fixed_three_two_one_columns(self):
        self.assertEqual('repeat(3, minmax(0, 1fr))', self.columns(1280, CLASSIC_LIVE))
        self.assertEqual('repeat(2, minmax(0, 1fr))', self.columns(768, CLASSIC_LIVE))
        self.assertEqual('minmax(0, 1fr)', self.columns(375, CLASSIC_LIVE))

    def test_a_card_is_lifted_and_loses_the_dashed_seam(self):
        self.assertEqual('0', value(INDEX, [GRID], CARD, 'outline', 1280))
        self.assertEqual('14px', value(INDEX, [GRID], CARD, 'padding', 375))

    def test_the_item_icon_of_a_card_sits_in_the_loot_frame_in_modern_only(self):
        rules = [rule for rule in rules_after_the_marker()
                 if 'html.fm-modern .encyclopedia-card > div:first-child img' in rule['selectors']
                 and 'border' in rule['declarations']]
        self.assertEqual(1, len(rules))
        self.assertEqual('2px solid var(--fm-frame-gold)', rules[0]['declarations']['border'][0])
        self.assertEqual('var(--fm-surface-3)', rules[0]['declarations']['background-color'][0])
        for sheet in ('encyclopedia.css', 'encyclopedia_detail.css'):
            self.assertFalse([rule for rule in stylesheet(sheet) if 'border' in rule['declarations']
                              and any('img' in selector for selector in rule['selectors'])], sheet)

    def test_the_pagination_targets_are_44_pixels_in_modern_and_24_in_classic(self):
        link = ('a', {'class': 'encyclopedia-page-link'})
        pagination = [PAGE_ROOT, ('div', {'class': 'encyclopedia-pagination'})]
        self.assertEqual('44px', value(INDEX, pagination, link, 'min-height', 375))
        self.assertEqual('24px', value(INDEX, pagination, link, 'min-height', 375, CLASSIC_LIVE))

    def test_the_current_page_is_the_gold_gradient_and_the_others_are_not_bold(self):
        pagination = [PAGE_ROOT, ('div', {'class': 'encyclopedia-pagination'})]
        current = ('span', {'class': 'encyclopedia-page-link encyclopedia-page-link-current'})
        link = ('a', {'class': 'encyclopedia-page-link'})
        self.assertTrue(value(INDEX, pagination, current, 'background', 1280).startswith('linear-gradient'))
        self.assertEqual('#2a2010', value(INDEX, pagination, current, 'color', 1280))
        self.assertEqual('700', value(INDEX, pagination, current, 'font-weight', 1280))
        self.assertEqual('var(--fm-surface)', value(INDEX, pagination, link, 'background', 1280))
        self.assertEqual('400', value(INDEX, pagination, link, 'font-weight', 1280))


class TheItemAndSetPagesAreCardsOfSectionsTests(SimpleTestCase):

    def test_a_page_of_lot_9b_keeps_the_card_without_columns_and_the_sections_without_tiles(self):
        self.assertIsNone(value(ITEM, [OTHER_ROOT], ITEM_CARD, 'column-width', 1920))
        self.assertNotEqual('var(--fm-surface)', value(ITEM, [OTHER_ROOT, ITEM_CARD], SECTION, 'background', 1920))
        self.assertIsNone(value(ITEM, [OTHER_ROOT, ITEM_CARD], SECTION, 'break-inside', 1920))
        link = ('a', {'class': 'encyclopedia-page-link'})
        pagination = [('div', {'class': 'encyclopedia-monsters text'}), ('div', {'class': 'encyclopedia-pagination'})]
        self.assertEqual('24px', value(INDEX, pagination, link, 'min-height', 375))

    def test_the_card_flows_its_sections_in_columns_from_380_pixels(self):
        self.assertEqual('block', value(ITEM, [ROOT], ITEM_CARD, 'display', 1920))
        self.assertEqual('380px', value(ITEM, [ROOT], ITEM_CARD, 'column-width', 1920))
        self.assertIsNone(value(ITEM, [ROOT], ITEM_CARD, 'column-width', 1920, CLASSIC_LIVE))

    def test_a_section_is_a_tile_that_is_never_cut_between_two_columns(self):
        self.assertEqual('avoid', value(ITEM, [ROOT, ITEM_CARD], SECTION, 'break-inside', 1920))
        self.assertEqual('var(--fm-surface)', value(ITEM, [ROOT, ITEM_CARD], SECTION, 'background', 1920)
                         or value(ITEM, [ROOT, ITEM_CARD], SECTION, 'background-color', 1920))

    def test_the_section_title_is_the_title_font_at_one_weight(self):
        wanted = 'html.fm-modern .encyclopedia-atelier .encyclopedia-item-card .encyclopedia-section > b:first-child'
        found = [rule['declarations'] for rule in rules_after_the_marker() if wanted in rule['selectors']]
        self.assertEqual(1, len(found))
        self.assertEqual('400', found[0]['font-weight'][0])
        self.assertEqual('var(--fm-font-display)', found[0]['font-family'][0])

    def test_the_head_and_the_calls_to_action_span_every_column(self):
        head = ('div', {'class': 'encyclopedia-item-head'})
        self.assertEqual('all', value(ITEM, [ROOT, ITEM_CARD], head, 'column-span', 1920))

    def test_a_set_page_spans_its_sections_and_lays_the_bonus_ladder_in_a_grid(self):
        self.assertEqual('all', value(SET, [ROOT, SET_CARD], SECTION, 'column-span', 1920))
        self.assertIsNone(value(ITEM, [ROOT, ITEM_CARD], SECTION, 'column-span', 1920))
        selectors = [selector for rule in rules_after_the_marker() for selector in rule['selectors']]
        self.assertIn('html.fm-modern .encyclopedia-set-card .encyclopedia-section:has(> .encyclopedia-set-bonus-group)', selectors)

    def test_the_piece_count_of_a_bonus_group_is_a_tape_badge(self):
        declarations = [rule['declarations'] for rule in rules_after_the_marker() if any(
            '.encyclopedia-set-bonus-group > .encyclopedia-item-meta:first-child' in selector for selector in rule['selectors'])]
        self.assertEqual('var(--fm-tape)', declarations[0]['background'][0])
        self.assertEqual(('var(--fm-tape-text)', True), declarations[0]['color'])
        competing = [rule['declarations']['color'] for rule in stylesheet(MODERN)
                     if 'html.fm-modern .encyclopedia-item-meta' in rule['selectors'] and 'color' in rule['declarations']]
        self.assertEqual([('var(--fm-text)', True)], competing)

    def test_the_icons_of_an_item_page_and_a_set_page_sit_in_the_loot_frame(self):
        selectors = [selector for rule in rules_after_the_marker() if 'box-shadow' in rule['declarations']
                     and 'border' in rule['declarations'] for selector in rule['selectors']]
        for wanted in ('html.fm-modern .encyclopedia-atelier .encyclopedia-item-head img', 'html.fm-modern .encyclopedia-set-item img',
                       'html.fm-modern .most-used-icon', 'html.fm-modern .encyclopedia-atelier .encyclopedia-list .craft-icon'):
            self.assertIn(wanted, selectors)


class TheMostUsedPageWrapsItsNamesTests(SimpleTestCase):

    def test_a_name_wraps_in_modern_and_stays_on_one_line_in_classic(self):
        slot = ('div', {'class': 'most-used-slots'})
        name = ('span', {'class': 'most-used-name'})
        item = ('li', {'class': 'most-used-item'})
        for width in (375, 1920):
            self.assertEqual('normal', value(MOST_USED, [slot, item], name, 'white-space', width), width)
            self.assertEqual('nowrap', value(MOST_USED, [slot, item], name, 'white-space', width, CLASSIC_LIVE), width)

    def test_the_slots_are_a_grid_that_grows_with_the_width(self):
        slots = ('div', {'class': 'most-used-slots'})
        self.assertEqual('grid', value(MOST_USED, [], slots, 'display', 2560))
        self.assertIsNone(value(MOST_USED, [], slots, 'display', 2560, CLASSIC_LIVE))


class NoInlineStyleIsLeftAndClassicKeepsTheValuesTests(SimpleTestCase):

    def test_no_template_of_the_lot_carries_a_style_attribute(self):
        for name in PAGES:
            self.assertIsNone(re.search(r'<[^>]+\sstyle="', template(name)), name)

    def test_the_hub_links_row_and_the_hidden_forms_have_their_classic_rule(self):
        hub = ('p', {'class': 'encyclopedia-hub-links'})
        self.assertEqual('6px 0 10px', value(INDEX, [], hub, 'margin', 1280, CLASSIC_LIVE))
        csrf = ('form', {'class': 'encyclopedia-csrf-form'})
        self.assertEqual('none', value(ITEM, [], csrf, 'display', 1280, CLASSIC_LIVE))
        self.assertIn('.encyclopedia-csrf-form { display: none; }', template('encyclopedia_set'))


class EveryNewRuleIsPrefixedByTheModernClassTests(SimpleTestCase):

    def test_every_selector_after_the_marker_starts_with_the_modern_prefix(self):
        rules = rules_after_the_marker()
        self.assertGreater(len(rules), 60)
        for rule in rules:
            for selector in rule['selectors']:
                self.assertTrue(selector.startswith('html.fm-modern'), selector)
