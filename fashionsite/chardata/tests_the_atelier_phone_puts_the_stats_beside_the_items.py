# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a phone the Atelier build page sets the items and the stats side by side, and the narrow columns keep every line readable and every action pressable."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, matching, parse, read_css, stylesheet

PARTS = stylesheet('modern-solution-parts.css')
ROW = 'html.fm-modern .solution-table > tbody > tr'
SIDE = '(min-width:360px) and (max-width:759px)'
PHONE = '(max-width:759px)'
TILE = '@container fm-items (max-width:259px)'
STAT_BOX = '@container (max-width:329px)'
ONE = '@container fm-items (max-width:229px)'
TWO = '@container fm-items (min-width:230px) and (max-width:349px)'
ICONS = 'html.fm-modern .fm-sol-doll .solution-item-expand-header .solution-item-icons'
HEADER = 'html.fm-modern .solution-table .solution-item-section.fm-sol-doll .expand-container > .solution-item-expand-header'
SECTION = 'html.fm-modern .solution-item-section:not(.fm-sol-doll)'
STAT_BODY = 'html.fm-modern .solution-stat-summary .solution-stat-table > tbody'
STAT_NAME = ('html.fm-modern .solution-stat-table .solution-stat-summary-line:not(.fm-stat-group) '
             '.solution-stat-summary-name')


def block(text, header):
    """The text between the braces of the last block that opens with this header."""
    opening = text.index('{', text.rindex(header))
    depth, index = 1, opening + 1
    while depth:
        depth += {'{': 1, '}': -1}.get(text[index], 0)
        index += 1
    return text[opening + 1:index - 1]


SOURCE = read_css('modern-solution-parts.css')
PHONE_TEXT = block(SOURCE, '@media (max-width:759px)')
SIDE_TEXT = block(SOURCE, '@media (min-width:360px) and (max-width:759px)')
TILE_RULES = parse(block(SIDE_TEXT, TILE), 'tile')
STAT_RULES = parse(block(PHONE_TEXT, STAT_BOX), 'stat')
ONE_RULES = parse(block(PHONE_TEXT, ONE), 'one')
TWO_RULES = parse(block(PHONE_TEXT, TWO), 'two')


class TheSideBySideColumnsTests(SimpleTestCase):

    def test_the_stuff_and_the_stats_sit_in_two_columns_from_360_up(self):
        self.assertEqual('minmax(0,1fr) clamp(156px,44%,280px)', declared(PARTS, ROW, 'grid-template-columns', SIDE)[0])
        self.assertTrue(declared(PARTS, ROW, 'grid-template-areas', SIDE)[0].startswith('"stuff stats"'))

    def test_a_screen_under_360_keeps_the_stacked_layout(self):
        self.assertIsNone(declared(PARTS, ROW, 'grid-template-columns', PHONE))
        self.assertIsNone(declared(PARTS, ROW, 'grid-template-areas', PHONE))

    def test_the_desktop_rules_do_not_name_the_side_by_side_areas(self):
        for rule in PARTS:
            if rule['media'] != SIDE:
                self.assertNotIn('stuff stats', rule['declarations'].get('grid-template-areas', ('', False))[0])

    def test_show_all_and_hide_all_fill_the_column_width(self):
        selector = 'html.fm-modern .solution-item-summary > :is(#expand_button,#collapse_button)'
        self.assertEqual('100%', declared(PARTS, selector, 'width', SIDE)[0])
        self.assertEqual('flex', declared(PARTS, selector, 'display', SIDE)[0])

    def test_the_turn_the_reasons_and_the_criteria_stay_under_both_columns(self):
        areas = declared(PARTS, ROW, 'grid-template-areas', SIDE)[0]
        for name in ('turn', 'why', 'crit'):
            self.assertIn('"%s %s"' % (name, name), areas)


class TheNarrowStatColumnTests(SimpleTestCase):

    def test_a_narrow_stats_container_sets_the_table_in_one_column(self):
        self.assertEqual('minmax(0,1fr)', declared(STAT_RULES, STAT_BODY, 'grid-template-columns', 'stat')[0])

    def test_a_stat_name_never_breaks_inside_a_word(self):
        self.assertEqual('normal', declared(STAT_RULES, STAT_NAME, 'overflow-wrap', 'stat')[0])

    def test_the_stat_container_query_lives_in_the_phone_media_only(self):
        self.assertEqual(1, SOURCE.count(STAT_BOX))


class TheNarrowItemColumnTests(SimpleTestCase):

    def test_the_dofus_get_one_column_under_230(self):
        self.assertEqual('minmax(0,1fr)', declared(ONE_RULES, SECTION, 'grid-template-columns', 'one')[0])

    def test_the_dofus_get_two_columns_from_230_to_349(self):
        self.assertEqual('repeat(2,minmax(0,1fr))', declared(TWO_RULES, SECTION, 'grid-template-columns', 'two')[0])

    def test_the_doll_actions_sit_two_by_two_in_a_narrow_tile(self):
        self.assertEqual('repeat(2,minmax(0,44px))', declared(TILE_RULES, ICONS, 'grid-template-columns', 'tile')[0])

    def test_the_dofus_actions_sit_two_by_two_beside_the_stats(self):
        selector = SECTION + ' .solution-item-expand-header .solution-item-icons'
        self.assertEqual('repeat(2,minmax(0,44px))', declared(PARTS, selector, 'grid-template-columns', SIDE)[0])

    def test_a_narrow_tile_stacks_the_icon_the_name_and_the_level(self):
        self.assertEqual('column', declared(TILE_RULES, HEADER, 'flex-direction', 'tile')[0])
        self.assertEqual(1, len(matching(TILE_RULES, HEADER, 'tile')))

    def test_the_link_tap_area_grows_down_away_from_the_card_above(self):
        link = 'html.fm-modern .solution-item-expand-header .item-external-link'
        self.assertEqual('4px 14.5px 25px', declared(PARTS, link, 'padding', SIDE)[0])
        self.assertEqual('-4px -14.5px -25px', declared(PARTS, link, 'margin', SIDE)[0])
        self.assertIsNone(declared(PARTS, HEADER, 'padding-bottom', SIDE))
