# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The monster list, the monster page, the resource page and the missing page of the modern design: the list is a card grid that grows with the width with a search card that never clips a button, the monster and resource pages are cards of sections, their icons sit in a loot frame, the spell tips show a focus ring, the missing page is a notice card, the pages carry the opt-in class, no template carries a style attribute, and every new rule is prefixed by the modern class so the classic design is untouched."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import (STATIC, chain_of, parse, stylesheet, winning)

MODERN = 'modern.css'
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
MODERN_LIVE = ['fm-modern', 'fm-light']
CLASSIC_LIVE = ['fm-light']
MARKER = '/* ---------- Encyclopedia: monster list, monster page, resource page, missing page ---------- */'
PAGES = ('encyclopedia_monsters', 'encyclopedia_monster', 'encyclopedia_resource', 'encyclopedia_missing')


def template(name):
    with io.open(os.path.join(TEMPLATES, name + '.html'), encoding='utf-8') as handle:
        return handle.read()


def style_block(name):
    block = re.search(r'<style>(.*?)</style>', template(name), re.S).group(1)
    return parse(re.sub(r'/\*.*?\*/', '', block, flags=re.S))


MONSTERS = [('encyclopedia_monsters.html style', style_block('encyclopedia_monsters')), (MODERN, stylesheet(MODERN))]
MONSTER = [('encyclopedia_monster.html style', style_block('encyclopedia_monster')), (MODERN, stylesheet(MODERN))]
RESOURCE = [(name, stylesheet(name)) for name in ('encyclopedia_detail.css', 'encyclopedia_resource.css', MODERN)]
MISSING = [(name, stylesheet(name)) for name in ('encyclopedia_missing.css', MODERN)]


def value(sheets, ancestors, element, prop, width, classes=MODERN_LIVE):
    found = winning(sheets, chain_of([('html', {})] + ancestors, element[0], element[1], classes), prop, width)
    return None if found is None else found[0]


def rules_after_the_marker():
    with io.open(os.path.join(STATIC, MODERN), encoding='utf-8') as handle:
        source = handle.read()
    return parse(re.sub(r'/\*.*?\*/', '', source[source.index(MARKER):], flags=re.S))


LIST_ROOT = ('div', {'class': 'encyclopedia-monsters encyclopedia-atelier text'})
SEARCH = ('div', {'class': 'encyclopedia-monsters-search-grid'})
GRID = ('div', {'class': 'encyclopedia-monsters-grid'})
LIST_CARD = ('div', {'class': 'encyclopedia-monster-card'})
PAGE_ROOT = ('div', {'class': 'encyclopedia-monster encyclopedia-atelier text'})
PAGE_CARD = ('div', {'class': 'encyclopedia-monster-card brown-box'})
SECTION = ('div', {'class': 'encyclopedia-section'})
RES_ROOT = ('div', {'class': 'encyclopedia-item encyclopedia-atelier text'})
RES_CARD = ('div', {'class': 'encyclopedia-item-card brown-box'})
MISSING_ROOT = ('div', {'class': 'encyclopedia-missing encyclopedia-atelier text'})
MISSING_CARD = ('div', {'class': 'encyclopedia-missing-card brown-box'})


class TheMonsterListIsACardGridThatGrowsWithTheWidthTests(SimpleTestCase):

    def test_modern_cards_are_as_many_as_the_width_allows(self):
        for width in (375, 768, 1280, 1920, 2560):
            self.assertEqual('repeat(auto-fill,minmax(min(100%,300px),1fr))',
                             value(MONSTERS, [LIST_ROOT], GRID, 'grid-template-columns', width).replace(' ', ''), width)

    def test_classic_keeps_its_240_pixel_columns(self):
        self.assertEqual('repeat(auto-fill, minmax(240px, 1fr))', value(MONSTERS, [LIST_ROOT], GRID, 'grid-template-columns', 1280, CLASSIC_LIVE))

    def test_the_search_row_wraps_instead_of_clipping_a_button_at_every_width(self):
        for width in (375, 768, 1280, 1920):
            self.assertEqual('repeat(auto-fit,minmax(min(100%,170px),1fr))',
                             value(MONSTERS, [LIST_ROOT], SEARCH, 'grid-template-columns', width).replace(' ', ''), width)

    def test_classic_keeps_its_five_column_search_row_and_its_phone_stack(self):
        self.assertIn('repeat(3, minmax(140px, 180px))', value(MONSTERS, [LIST_ROOT], SEARCH, 'grid-template-columns', 768, CLASSIC_LIVE))
        self.assertEqual('1fr', value(MONSTERS, [LIST_ROOT], SEARCH, 'grid-template-columns', 375, CLASSIC_LIVE))

    def test_a_card_is_an_atelier_card_in_modern_only(self):
        ancestors = [LIST_ROOT, GRID]
        self.assertEqual('flex', value(MONSTERS, ancestors, LIST_CARD, 'display', 1280))
        self.assertEqual('var(--fm-radius)', value(MONSTERS, ancestors, LIST_CARD, 'border-radius', 1280))
        self.assertEqual('6px', value(MONSTERS, [LIST_ROOT, GRID], LIST_CARD, 'border-radius', 1280, CLASSIC_LIVE))
        self.assertEqual('block', value(MONSTERS, [LIST_ROOT, GRID], LIST_CARD, 'display', 1280, CLASSIC_LIVE))


class TheMonsterPageIsACardOfSectionsTests(SimpleTestCase):

    def test_the_card_flows_its_sections_in_columns_in_modern_only(self):
        self.assertEqual('380px', value(MONSTER, [PAGE_ROOT], PAGE_CARD, 'column-width', 1280))
        self.assertIsNone(value(MONSTER, [PAGE_ROOT], PAGE_CARD, 'column-width', 1280, CLASSIC_LIVE))

    def test_a_section_is_a_tile_that_is_never_cut_between_columns(self):
        ancestors = [PAGE_ROOT, PAGE_CARD]
        self.assertEqual('avoid', value(MONSTER, ancestors, SECTION, 'break-inside', 1280))
        self.assertEqual('var(--fm-surface)', value(MONSTER, ancestors, SECTION, 'background', 1280))
        self.assertIsNone(value(MONSTER, [PAGE_ROOT, PAGE_CARD], SECTION, 'break-inside', 1280, CLASSIC_LIVE))

    def test_the_stats_table_and_the_head_span_every_column(self):
        stats = ('div', {'class': 'encyclopedia-section', 'id': 'monster-stats'})
        self.assertEqual('all', value(MONSTER, [PAGE_ROOT, PAGE_CARD], stats, 'column-span', 1280))
        head = ('div', {'class': 'monster-drop-summary'})
        self.assertEqual('all', value(MONSTER, [PAGE_ROOT, PAGE_CARD], head, 'column-span', 1280))

    def test_the_drop_lists_are_divided_rows_without_bullets(self):
        li = ('li', {})
        lst = ('ul', {'class': 'encyclopedia-list'})
        ancestors = [PAGE_ROOT, PAGE_CARD, SECTION, lst]
        self.assertEqual('none', value(MONSTER, ancestors[:3], lst, 'list-style', 375))
        self.assertEqual('1px solid var(--fm-border)', value(MONSTER, ancestors, li, 'border-top', 375))

    def test_the_summary_links_are_44_pixel_targets(self):
        link = ('a', {'class': 'monster-drop-summary-link'})
        self.assertEqual('44px', value(MONSTER, [PAGE_ROOT, PAGE_CARD], link, 'min-height', 375))

    def test_the_spell_tips_show_a_focus_ring_in_modern(self):
        selector = 'html.fm-modern .encyclopedia-atelier .monster-spells-list .spell-tip:focus-visible'
        rules = [rule for rule in rules_after_the_marker() if selector in rule['selectors']]
        self.assertEqual(1, len(rules))
        self.assertEqual('2px solid var(--fm-accent-text)', rules[0]['declarations']['outline'][0])


class TheWeaknessCueKeepsItsGreenTests(SimpleTestCase):

    LINK = ('a', {'class': 'encyclopedia-monsters-meta encyclopedia-monsters-weakness'})
    CELL = ('td', {'class': 'monster-weak'})
    TABLE = [PAGE_ROOT, PAGE_CARD, SECTION, ('table', {'class': 'monster-grades'}), ('tr', {})]

    def test_the_weakness_link_of_a_list_card_is_green_in_both_modern_themes(self):
        ancestors = [LIST_ROOT, GRID, LIST_CARD]
        self.assertEqual('#0a6b0a', value(MONSTERS, ancestors, self.LINK, 'color', 1280, MODERN_LIVE))
        self.assertEqual('#74e074', value(MONSTERS, ancestors, self.LINK, 'color', 1280, ['fm-modern', 'fm-dark']))

    def test_the_weak_cell_of_the_grades_table_is_green_in_both_modern_themes(self):
        self.assertEqual('#0a6b0a', value(MONSTER, self.TABLE, self.CELL, 'color', 1280))
        self.assertEqual('#74e074', value(MONSTER, self.TABLE, self.CELL, 'color', 1280, ['fm-modern', 'fm-dark']))

    def test_classic_keeps_its_own_green(self):
        self.assertEqual('#0a7d0a', value(MONSTER, self.TABLE, self.CELL, 'color', 1280, CLASSIC_LIVE))
        self.assertEqual('#0a7d0a', value(MONSTERS, [LIST_ROOT, GRID, LIST_CARD], self.LINK, 'color', 1280, CLASSIC_LIVE))


class TheResourceTitleFlexStaysOnTheTitlesThatHoldAnIconTests(SimpleTestCase):

    def test_the_flex_rule_is_guarded_by_the_icon_and_the_modern_prefix(self):
        flex = [rule for rule in rules_after_the_marker() if any('.encyclopedia-item-name' in selector for selector in rule['selectors'])
                and 'flex' in [value[0] for key, value in rule['declarations'].items() if key == 'display']]
        self.assertEqual(1, len(flex))
        for selector in flex[0]['selectors']:
            self.assertTrue(selector.startswith('html.fm-modern .encyclopedia-item.encyclopedia-atelier '), selector)
            self.assertIn(':has(> .resource-icon)', selector)

    def test_the_item_page_title_has_no_modern_display_rule_without_the_icon(self):
        name = ('h1', {'class': 'encyclopedia-item-name'})
        item = ('div', {'class': 'encyclopedia-item encyclopedia-atelier text'})
        self.assertNotEqual('flex', value(RESOURCE, [item], name, 'display', 1280))


class TheIconsOfTheseCardsSitInTheLootFrameTests(SimpleTestCase):

    FRAME = '2px solid var(--fm-frame-gold)'

    def test_every_icon_of_the_pages_is_framed_in_modern(self):
        cases = ((RESOURCE, [RES_ROOT, RES_CARD], ('img', {'class': 'resource-icon'})),
                 (MONSTER, [PAGE_ROOT, PAGE_CARD], ('img', {'class': 'monster-portrait'})),
                 (MONSTER, [PAGE_ROOT, PAGE_CARD, SECTION], ('img', {'class': 'drop-icon'})),
                 (MONSTERS, [LIST_ROOT, GRID, LIST_CARD], ('img', {'class': 'encyclopedia-monsters-thumb'})))
        for sheets, ancestors, img in cases:
            self.assertEqual(self.FRAME, value(sheets, ancestors, img, 'border', 1280), img[1])
            self.assertIsNone(value(sheets, ancestors, img, 'border', 1280, CLASSIC_LIVE), img[1])

    def test_a_resource_page_is_the_item_page_card_with_the_opt_in_class(self):
        self.assertEqual('380px', value(RESOURCE, [RES_ROOT], RES_CARD, 'column-width', 1280))
        self.assertEqual('0', value(RESOURCE, [], RES_ROOT, 'padding', 1280))
        self.assertEqual('12px', value(RESOURCE, [], ('div', {'class': 'encyclopedia-item text'}), 'padding', 1280))
        craft = ('img', {'class': 'craft-icon'})
        self.assertEqual(self.FRAME, value(RESOURCE, [RES_ROOT, RES_CARD, SECTION, ('ul', {'class': 'encyclopedia-list'}), ('li', {'class': 'craft-item'})], craft, 'border', 1280))


class TheMissingPageIsANoticeCardTests(SimpleTestCase):

    def test_the_card_holds_the_measure_and_carries_a_gold_edge_in_modern(self):
        self.assertEqual('var(--fm-measure)', value(MISSING, [MISSING_ROOT], MISSING_CARD, 'max-width', 1280))
        self.assertIn('inset 5px 0 0 var(--fm-accent)', value(MISSING, [MISSING_ROOT], MISSING_CARD, 'box-shadow', 375))
        self.assertIsNone(value(MISSING, [MISSING_ROOT], MISSING_CARD, 'max-width', 1280, CLASSIC_LIVE))

    def test_the_buttons_are_44_pixel_targets(self):
        button = ('a', {'class': 'button-generic'})
        self.assertEqual('44px', value(MISSING, [MISSING_ROOT, MISSING_CARD], button, 'min-height', 375))


class TheTemplatesCarryTheOptInClassAndNoStyleAttributeTests(SimpleTestCase):

    def test_each_root_carries_the_opt_in_class(self):
        for name in PAGES:
            root = re.search(r'<div class="(encyclopedia-(?:monsters|monster|item|missing)[^"]*)">', template(name))
            self.assertIn('encyclopedia-atelier', root.group(1), name)

    def test_no_template_has_a_style_attribute(self):
        for name in PAGES:
            self.assertIsNone(re.search(r'<[^>]+\sstyle="', template(name)), name)


class EveryNewRuleIsPrefixedByTheModernClassTests(SimpleTestCase):

    def test_every_selector_after_the_marker_starts_with_the_modern_prefix(self):
        rules = rules_after_the_marker()
        self.assertGreater(len(rules), 50)
        for rule in rules:
            for selector in rule['selectors']:
                self.assertTrue(selector.startswith('html.fm-modern'), selector)
