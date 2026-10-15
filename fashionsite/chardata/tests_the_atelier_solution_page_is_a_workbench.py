# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solution page of the modern design: columns at each width, loot frames, shiny, title ribbon, lifted caps."""
import re

from django.test import SimpleTestCase

from chardata.tests_the_atelier_modern_rules_stay_under_the_modern_prefix import FROZEN_UNPREFIXED
from chardata.tests_the_setup_stylesheet_support import media_applies, read_css, rule_order, stylesheet

MODERN = stylesheet('modern.css')
ROOT = 'html.fm-modern'
ROW = ROOT + ' .solution-table > tbody > tr'
TABLE = ROOT + ' .solution-table'
FRAME = TABLE + ' .solution-item-icon-container'
SUMMARY = ROOT + ' .solution-item-summary'
SHINY = FRAME + '.shiny-slot'
REDUCED = '(prefers-reduced-motion:reduce)'


def at(selector, prop, width):
    """The value modern.css gives a property for exactly this selector at a viewport width: the last rule in file order."""
    found = None
    for rule in MODERN:
        if selector in rule['selectors'] and prop in rule['declarations'] and media_applies(rule['media'], width):
            found = rule['declarations'][prop][0]
    return found


def tracks(value):
    depth, count, inside = 0, 0, False
    for char in value:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        if char.isspace() and depth == 0:
            inside = False
        elif not inside:
            inside = True
            count += 1
    return count


def media_rules(selector, prop, media):
    return [rule for rule in MODERN if rule['media'] == media and selector in rule['selectors'] and prop in rule['declarations']]


class TheSolutionTableHasColumnsFromTheWidthTests(SimpleTestCase):

    def test_the_table_row_is_stacked_below_1280(self):
        for width in (375, 768, 1100, 1279):
            with self.subTest(width=width):
                self.assertEqual('block', at(ROW, 'display', width))

    def test_the_row_has_an_items_track_and_a_stats_track_from_1280_up_to_1759(self):
        for width in (1280, 1440, 1536, 1759):
            with self.subTest(width=width):
                self.assertEqual('grid', at(ROW, 'display', width))
                self.assertEqual(2, tracks(at(ROW, 'grid-template-columns', width)))

    def test_the_row_has_a_fifth_track_for_the_explanation_from_1760(self):
        for width in (1760, 1920, 2560):
            with self.subTest(width=width):
                self.assertEqual(5, tracks(at(ROW, 'grid-template-columns', width)))

    def test_the_stats_are_a_scroll_box_no_taller_than_the_window_that_sticks_from_1280(self):
        stats = ROOT + ' .solution-stat-summary'
        self.assertIsNone(at(stats, 'position', 1279))
        for width in (1280, 1536, 1920):
            with self.subTest(width=width):
                self.assertEqual('sticky', at(stats, 'position', width))
                self.assertEqual('start', at(stats, 'align-self', width))
                self.assertEqual('auto', at(stats, 'overflow-y', width))
                cap = at(stats, 'max-height', width)
                self.assertRegex(cap, r'^calc\(100vh - \d+px\)$')
                self.assertIsNotNone(at(stats, 'top', width))

    def test_the_cards_of_every_section_flow_in_one_grid_from_1280_up_to_1759(self):
        section = SUMMARY + ' > .solution-item-section'
        self.assertEqual('grid', at(SUMMARY, 'display', 1280))
        self.assertEqual('grid', at(SUMMARY, 'display', 1759))
        self.assertNotEqual('grid', at(SUMMARY, 'display', 1279))
        for width in (1280, 1759):
            with self.subTest(width=width):
                self.assertEqual('contents', at(section, 'display', width))
        for width in (375, 1279, 1760, 2560):
            with self.subTest(width=width):
                self.assertIsNone(at(section, 'display', width))

    def test_the_item_cards_fill_a_grid_at_every_width(self):
        section = ROOT + ' .solution-item-section'
        for width in (375, 1280, 1920):
            with self.subTest(width=width):
                self.assertEqual('grid', at(section, 'display', width))
        self.assertEqual('contents', at(ROOT + ' .solution-item-section-column', 'display', 375))


class TheSlotsWearTheLootFrameTests(SimpleTestCase):

    def test_the_icon_container_has_the_double_gold_frame(self):
        border = at(FRAME, 'border', 1440)
        self.assertGreaterEqual(int(border.split('px')[0]), 2)
        self.assertEqual('var(--fm-frame-gold)', border.split()[-1])
        card = at(ROOT + ' .solution-item-expand-header', 'border', 1440)
        self.assertNotEqual(card.split()[-1], border.split()[-1])
        shadow = at(FRAME, 'box-shadow', 1440)
        self.assertEqual(2, shadow.count('inset'))
        self.assertIn('var(--fm-frame-gold)', shadow)

    def test_the_frame_stays_on_the_solution_table(self):
        for rule in MODERN:
            if ROOT + ' .solution-item-icon-container' in rule['selectors']:
                self.assertNotIn('border', rule['declarations'])

    def test_the_popup_slot_wears_the_same_frame(self):
        shared = [rule for rule in MODERN if FRAME in rule['selectors'] and ROOT + ' .item-exchange-icon-container' in rule['selectors']
                  and 'border' in rule['declarations']]
        self.assertTrue(shared)

    def test_the_frame_has_a_fallback_for_forced_colours(self):
        rules = media_rules(FRAME, 'border-color', '(forced-colors:active)')
        self.assertEqual('CanvasText', rules[0]['declarations']['border-color'][0])


class ShinyDiffersFromTheFrameTests(SimpleTestCase):

    def test_the_shiny_border_is_not_the_frame_border(self):
        self.assertNotEqual('var(--fm-frame-gold)', at(SHINY, 'border-color', 1440))
        self.assertEqual('var(--fm-tape)', at(SHINY, 'border-color', 1440))
        self.assertNotEqual(at(FRAME, 'box-shadow', 1440), at(SHINY, 'box-shadow', 1440))

    def test_a_diamond_marks_it_without_any_animation(self):
        marker = SHINY + '::before'
        self.assertEqual('""', at(marker, 'content', 1440))
        self.assertEqual('rotate(45deg)', at(marker, 'transform', 1440))
        self.assertIsNone(at(marker, 'animation', 1440))
        self.assertIsNone(at(marker, 'opacity', 1440))

    def test_reduced_motion_stops_the_glint_and_leaves_the_marker_alone(self):
        glint = media_rules(SHINY + '::after', 'animation', REDUCED)
        self.assertEqual('none', glint[0]['declarations']['animation'][0])
        for rule in MODERN:
            if rule['media'] == REDUCED:
                for selector in rule['selectors']:
                    self.assertNotIn('::before', selector)
                    self.assertFalse(selector.endswith('.shiny-slot'), selector)

    def test_the_glint_is_one_keyframe_animation(self):
        self.assertTrue(at(SHINY + '::after', 'animation', 1440).startswith('fm-shiny-glint '))
        self.assertIn('@keyframes fm-shiny-glint', read_css('modern.css'))


class TheTitleRibbonFollowsTheTitleTests(SimpleTestCase):

    CENTRED = ROOT + ' h1[align="center"]::after'
    LEFT = ROOT + ' .maincontent h1::after'

    def test_a_centred_title_gets_a_centred_ribbon(self):
        self.assertEqual('50%', at(self.CENTRED, 'left', 1440))
        self.assertEqual('translateX(-50%)', at(self.CENTRED, 'transform', 1440))

    def test_a_title_inside_the_content_column_keeps_a_left_ribbon(self):
        self.assertEqual('0', at(self.LEFT, 'left', 1440))
        self.assertEqual('none', at(self.LEFT, 'transform', 1440))
        self.assertEqual('left', at(ROOT + ' .maincontent h1', 'text-align', 1440))

    def test_the_left_ribbon_rule_comes_after_the_centred_one(self):
        self.assertGreater(rule_order(MODERN, self.LEFT)[0], rule_order(MODERN, self.CENTRED)[0])

    def test_the_ribbon_is_anchored_to_the_title_box(self):
        self.assertEqual('absolute', at(ROOT + ' h1::after', 'position', 1440))
        self.assertEqual('relative', at(ROOT + ' h1', 'position', 1440))


class TheSolutionCapsAreLiftedTests(SimpleTestCase):

    def test_the_banner_and_the_build_check_are_uncapped_from_1280_only(self):
        for selector in (ROOT + ' .char-banner', ROOT + ' .build-check', ROOT + ' .comments-section'):
            with self.subTest(selector=selector):
                self.assertIsNone(at(selector, 'max-width', 1279))
                self.assertEqual('none', at(selector, 'max-width', 1280))

    def test_the_explanation_panel_is_uncapped_from_1280(self):
        self.assertEqual('none', at(TABLE + ' .solver-why', 'max-width', 1280))
        self.assertIsNone(at(TABLE + ' .solver-why', 'max-width', 1279))
        self.assertIsNone(at(ROOT + ' .solver-why', 'max-width', 1920))

    def test_the_hint_paragraph_keeps_the_reading_measure(self):
        self.assertEqual('var(--fm-measure)', at(ROOT + ' .maincontent p.text', 'max-width', 1920))

    def test_the_ingredient_note_beats_its_inline_width(self):
        rule = [r for r in MODERN if ROOT + ' #solution_ingredients' in r['selectors'] and 'max-width' in r['declarations']][0]
        self.assertTrue(rule['declarations']['max-width'][1])


class TheLoadingTapeTests(SimpleTestCase):

    def test_the_tape_is_wide_tall_and_ticked(self):
        bar = ROOT + ' .loading-progress'
        self.assertTrue(at(bar, 'max-width', 1440).endswith(',100%)'))
        self.assertGreaterEqual(int(re.search(r'\d+', at(bar, 'max-width', 1440)).group()), 400)
        self.assertGreaterEqual(int(at(bar, 'height', 1440)[:-2]), 16)
        self.assertIn('repeating-linear-gradient', at(bar, 'background', 1440))

    def test_the_fill_is_the_tape(self):
        shared = [r for r in MODERN if ROOT + ' .loading-progress > span' in r['selectors'] and 'background' in r['declarations']]
        self.assertIn('var(--fm-tape)', shared[0]['declarations']['background'][0])

    def test_the_blanket_covers_the_window_and_never_widens_the_page(self):
        blanket = ROOT + ' #blanket'
        self.assertEqual('fixed', at(blanket, 'position', 1440))
        self.assertEqual('0', at(blanket, 'inset', 1440))
        self.assertEqual('auto', at(blanket, 'width', 2560))
        self.assertEqual('auto', at(blanket, 'height', 2560))

    def test_the_wider_popup_is_limited_to_the_solution_page(self):
        self.assertEqual('560px', at(ROOT + ':has(.solution-table) #popUpDiv', 'width', 1280))
        self.assertIsNone(at(ROOT + ':has(.solution-table) #popUpDiv', 'width', 1279))
        self.assertIsNone(at(ROOT + ' #popUpDiv', 'width', 1440))


class TheSolutionRulesStayUnderThePrefixTests(SimpleTestCase):

    def test_every_rule_about_the_solution_page_starts_with_the_modern_prefix(self):
        pattern = re.compile(r'solution-|loading-progress|#popUpDiv|#blanket|item-exchange|char-banner|build-check|proj_info')
        for rule in MODERN:
            for selector in rule['selectors']:
                if pattern.search(selector) and selector not in FROZEN_UNPREFIXED:
                    with self.subTest(selector=selector):
                        self.assertTrue(selector.startswith(ROOT), selector)
