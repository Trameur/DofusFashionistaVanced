# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The workshop and the inventory pages of the modern design: the workshop fills the shell instead of a 760 pixel column, its toolbar is a card that stacks on a phone, its item cards carry their state on a coloured edge and their icon in a loot frame, every control is a 44 pixel target, the shopping list is a card, the inventory is a two column layout that stacks on a phone with a card grid that grows with the width, the pages carry the opt-in class, the inline margins moved to classes, and every new rule is prefixed by the modern class so the classic design is untouched."""
import io
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, chain_of, parse, stylesheet, winning

MODERN = 'modern.css'
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
MODERN_LIVE = ['fm-modern', 'fm-light']
CLASSIC_LIVE = ['fm-light']
MARKER = '/* ---------- Tools: workshop and inventory ---------- */'

WORKSHOP = [(name, stylesheet(name)) for name in ('forms.css', 'workshop.css', MODERN)]
INVENTORY = [(name, stylesheet(name)) for name in ('forms.css', 'inventory.css', MODERN)]

WS_ROOT = ('div', {'class': 'workshop-wrapper tools-atelier'})
WS_CARD = ('li', {'class': 'ws-card brown-box', 'data-state': 'done'})
INV_ROOT = ('div', {'class': 'inv-page text tools-atelier'})
INV_BOX = ('div', {'class': 'inv-box brown-box'})


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


class TheWorkshopFillsTheShellAndItsToolbarIsACardTests(SimpleTestCase):

    def test_the_wrapper_is_not_held_to_760_pixels_in_modern_only(self):
        self.assertEqual('none', value(WORKSHOP, [], WS_ROOT, 'max-width', 1920))
        self.assertEqual('760px', value(WORKSHOP, [], WS_ROOT, 'max-width', 1920, CLASSIC_LIVE))

    def test_the_toolbar_is_a_card_that_stacks_stretched_on_a_phone(self):
        bar = ('div', {'class': 'ws-toolbar'})
        self.assertEqual('var(--fm-surface-2)', value(WORKSHOP, [WS_ROOT], bar, 'background', 1280))
        self.assertEqual('flex-end', value(WORKSHOP, [WS_ROOT], bar, 'align-items', 1280))
        self.assertEqual('stretch', value(WORKSHOP, [WS_ROOT], bar, 'align-items', 375))
        self.assertIsNone(value(WORKSHOP, [WS_ROOT], bar, 'background', 1280, CLASSIC_LIVE))

    def test_the_search_column_does_not_reserve_220_pixels_of_height_on_a_phone(self):
        search = ('div', {'class': 'ws-search'})
        self.assertEqual('0 0 auto', value(WORKSHOP, [WS_ROOT], search, 'flex', 375))
        self.assertEqual('1 1 220px', value(WORKSHOP, [WS_ROOT], search, 'flex', 1280))

    def test_the_pressed_chip_is_marked_by_more_than_its_colour(self):
        chip = ('button', {'class': 'ws-chip', 'aria-pressed': 'true'})
        self.assertEqual('var(--fm-accent-soft)', value(WORKSHOP, [WS_ROOT], chip, 'background', 1280))
        self.assertEqual('var(--fm-accent-text)', value(WORKSHOP, [WS_ROOT], chip, 'border-color', 1280))


class TheWorkshopCardsCarryTheirStateAndTheirIconTests(SimpleTestCase):

    def test_the_state_edge_wins_over_the_generic_panel_border_in_modern(self):
        for state, token in (('done', '--ws-done-line'), ('part', '--ws-part-line'), ('none', '--ws-none-line')):
            card = ('li', {'class': 'ws-card brown-box', 'data-state': state})
            self.assertEqual('var(%s)' % token, value(WORKSHOP, [WS_ROOT], card, 'border-left-color', 1280))

    def test_the_cards_keep_their_height_instead_of_stretching_to_the_tallest_of_the_row(self):
        self.assertEqual('start', value(WORKSHOP, [WS_ROOT], ('ul', {'class': 'ws-list'}), 'align-items', 1920))

    def test_the_search_results_follow_the_width_of_the_search_field(self):
        box = ('div', {'class': 'ws-search-results brown-box'})
        wrapper = ('div', {'class': 'ws-search-wrapper'})
        self.assertEqual('auto', value(WORKSHOP, [WS_ROOT, wrapper], box, 'width', 1920))
        self.assertEqual('none', value(WORKSHOP, [WS_ROOT, wrapper], box, 'max-width', 1920))
        self.assertEqual('620px', value(WORKSHOP, [WS_ROOT, wrapper], box, 'width', 1920, CLASSIC_LIVE))

    def test_the_card_decoration_that_beats_the_print_sheet_is_screen_only(self):
        loud = [rule for rule in rules_after_the_marker()
                if any(selector.startswith('html.fm-modern .tools-atelier .ws-card') for selector in rule['selectors'])
                and any(important and (prop.startswith('border') or prop.startswith('background'))
                        for prop, (_, important) in rule['declarations'].items())]
        self.assertGreaterEqual(len(loud), 4)
        for rule in loud:
            self.assertEqual('screen', rule['media'], rule['selectors'])

    def test_the_edge_is_four_pixels_wide(self):
        self.assertEqual('4px solid var(--fm-border-strong)', value(WORKSHOP, [WS_ROOT], ('li', {'class': 'ws-card brown-box'}), 'border-left', 1280))

    def test_the_card_has_no_stitched_outline_that_would_cross_its_foot(self):
        self.assertEqual('none', value(WORKSHOP, [WS_ROOT], WS_CARD, 'outline', 1280))

    def test_the_item_icon_sits_in_a_loot_frame_in_modern_only(self):
        icon = ('img', {'class': 'ws-head-img'})
        self.assertEqual('2px solid var(--fm-frame-gold)', value(WORKSHOP, [WS_ROOT, WS_CARD, ('div', {'class': 'ws-head'})], icon, 'border', 1280))
        self.assertIsNone(value(WORKSHOP, [WS_ROOT, WS_CARD, ('div', {'class': 'ws-head'})], icon, 'border', 1280, CLASSIC_LIVE))

    def test_the_state_foot_keeps_the_shared_status_tokens(self):
        foot = ('div', {'class': 'ws-foot'})
        self.assertEqual('var(--ws-done-bg)', value(WORKSHOP, [WS_ROOT, WS_CARD], foot, 'background', 1280))
        self.assertEqual('var(--ws-done-bg)', value(WORKSHOP, [WS_ROOT, WS_CARD], foot, 'background', 1280, CLASSIC_LIVE))

    def test_the_shopping_list_is_a_card_whose_rows_are_at_least_460_pixels(self):
        section = ('section', {'class': 'ws-shopping'})
        lst = ('ul', {'class': 'ws-shopping-list'})
        self.assertEqual('var(--fm-surface-2)', value(WORKSHOP, [WS_ROOT], section, 'background', 1280))
        self.assertEqual('repeat(auto-fill,minmax(min(100%,460px),1fr))',
                         value(WORKSHOP, [WS_ROOT, section], lst, 'grid-template-columns', 1920).replace(' ', ''))
        self.assertIsNone(value(WORKSHOP, [WS_ROOT, section], lst, 'grid-template-columns', 1920, CLASSIC_LIVE))


class EveryControlOfTheseToolPagesIsA44PixelTargetTests(SimpleTestCase):

    def test_the_workshop_controls(self):
        for tag, classes in (('button', 'ws-chip'), ('button', 'ws-mini-btn'), ('button', 'ws-step'), ('button', 'ws-remove'),
                             ('button', 'ws-source-toggle'), ('button', 'ws-subrecipe-toggle'), ('button', 'ws-undo-inline'),
                             ('input', 'ws-num pretty-input ws-qty-input')):
            element = (tag, {'class': classes})
            for width in (375, 1920):
                self.assertEqual('44px', value(WORKSHOP, [WS_ROOT, WS_CARD], element, 'min-height', width), classes)

    def test_the_workshop_controls_keep_their_36_pixels_in_classic(self):
        self.assertEqual('36px', value(WORKSHOP, [WS_ROOT], ('button', {'class': 'ws-chip'}), 'min-height', 1280, CLASSIC_LIVE))

    def test_the_inventory_controls(self):
        wrapper = ('div', {'class': 'inv-search-wrapper'})
        for ancestors, element in (([INV_ROOT, INV_BOX], ('a', {'class': 'inv-folder-link'})),
                                   ([INV_ROOT, INV_BOX], ('button', {'class': 'button-thin inv-remove'})),
                                   ([INV_ROOT, INV_BOX, wrapper], ('input', {'class': 'pretty-input', 'type': 'text', 'id': 'inv-search'}))):
            self.assertEqual('44px', value(INVENTORY, ancestors, element, 'min-height', 375), element)


class TheInventoryStacksOnAPhoneAndItsCardsGrowWithTheWidthTests(SimpleTestCase):

    LAYOUT = ('div', {'class': 'inv-layout'})
    GRID = ('div', {'class': 'inv-grid'})

    def test_the_two_columns_become_one_below_801_pixels(self):
        self.assertEqual('minmax(220px,280px) minmax(0,1fr)', value(INVENTORY, [INV_ROOT], self.LAYOUT, 'grid-template-columns', 1280).replace(', ', ','))
        self.assertEqual('minmax(0,1fr)', value(INVENTORY, [INV_ROOT], self.LAYOUT, 'grid-template-columns', 375))
        self.assertEqual('minmax(0,1fr)', value(INVENTORY, [INV_ROOT], self.LAYOUT, 'grid-template-columns', 800))

    def test_the_folder_column_and_its_gap_leave_room_for_two_cards_at_1280(self):
        self.assertEqual('var(--fm-space-3)', value(INVENTORY, [INV_ROOT], self.LAYOUT, 'gap', 1280))

    def test_the_cards_are_as_many_as_the_width_allows(self):
        for width in (375, 1280, 2560):
            self.assertEqual('repeat(auto-fill,minmax(min(100%,280px),1fr))',
                             value(INVENTORY, [INV_ROOT, INV_BOX], self.GRID, 'grid-template-columns', width).replace(' ', ''))
        self.assertEqual('repeat(auto-fill, minmax(240px, 1fr))', value(INVENTORY, [INV_ROOT, INV_BOX], self.GRID, 'grid-template-columns', 1280, CLASSIC_LIVE))

    def test_the_item_icon_sits_in_a_loot_frame(self):
        card = ('div', {'class': 'inv-card brown-box'})
        icon = ('img', {'class': 'inv-card-img'})
        self.assertEqual('2px solid var(--fm-frame-gold)', value(INVENTORY, [INV_ROOT, INV_BOX, self.GRID, card], icon, 'border', 1280))

    def test_the_roll_colours_read_on_both_modern_themes(self):
        line = ('div', {'class': 'inv-stat-line inv-stat-over'})
        for classes, light, dark in ((line, '#1a5a85', '#6cb8ec'),
                                     (('div', {'class': 'inv-stat-line inv-stat-under'}), '#8a4e00', '#f0b45c')):
            self.assertEqual(light, value(INVENTORY, [INV_ROOT], classes, 'color', 1280))
            self.assertEqual(dark, value(INVENTORY, [INV_ROOT], classes, 'color', 1280, ['fm-modern', 'fm-dark']))


class TheToolPagesCarryTheOptInClassAndNoStaticInlineMarginTests(SimpleTestCase):

    def test_the_roots_carry_the_opt_in_class(self):
        self.assertIn('class="workshop-wrapper tools-atelier"', template('workshop'))
        self.assertIn('class="inv-page text tools-atelier"', template('inventory'))

    def test_the_inventory_inline_styles_left_are_the_ones_a_script_toggles(self):
        for tag in re.findall(r'<[^>]*style="[^"]*"[^>]*>', template('inventory')):
            self.assertRegex(tag, r'style="display:none;?"', tag)

    def test_the_moved_margins_keep_their_classic_values(self):
        sheet = stylesheet('inventory.css')
        for selector, margin in (('.inv-folder-delete', '8px'), ('.inv-entry-buttons', '8px'),
                                 ('.inv-ocr-controls.inv-ocr-controls-spaced', '8px'),
                                 ('.inv-section-title.inv-section-title-spaced', '8px'),
                                 ('.inv-page .small-explain.inv-empty', '12px')):
            rules = [rule for rule in sheet if selector in rule['selectors']]
            self.assertEqual(1, len(rules), selector)
            self.assertEqual(margin, rules[0]['declarations']['margin-top'][0])

    def test_every_selector_after_the_marker_starts_with_the_modern_prefix(self):
        rules = rules_after_the_marker()
        self.assertGreater(len(rules), 60)
        for rule in rules:
            for selector in rule['selectors']:
                self.assertTrue(selector.startswith('html.fm-modern'), selector)
