# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The community pages of the modern design: shared builds is a grid of one to five card columns by width, the build list becomes one card per row on narrow screens without hiding a cell, and the feed and the profile list their builds as cards, while every rule is prefixed by the modern class and the markup the rules rely on is still there."""
import os

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import chain_of, media_applies, stylesheet, winning

MODERN = stylesheet('modern.css')
SHEETS = [(name, stylesheet(name)) for name in ('sharedbuilds.css', 'responsive.css', 'modern.css')]
GRID_CHAIN = chain_of([('html', {})], 'div', {'class': 'builds-grid'}, ['fm-modern', 'fm-light'])
CARD_CHAIN = chain_of([('html', {})], 'div', {'class': 'build-card'}, ['fm-modern', 'fm-light'])
ROOT = 'html.fm-modern'
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
WIDTHS = [375, 699, 700, 768, 1279, 1280, 1440, 1599, 1600, 1920, 2299, 2300, 2560]
GRID = ROOT + ' .builds-grid'
LOAD_ROW = ROOT + ' .load-project-table > tbody > tr'
LOAD_CELL = ROOT + ' .load-project-line > td'
FEED = ROOT + ' .feed-wrap'
PROFILE = ROOT + ' .profile-wrap'
CARD_ROWS = [ROOT + ' .feed-row', ROOT + ' .profile-build-row']
FILTERS = [('html', {}), ('div', {'class': 'filters-section'}), ('form', {}), ('div', {'class': 'filter-row'})]


def at(selector, prop, width):
    found = None
    for rule in MODERN:
        if selector in rule['selectors'] and prop in rule['declarations'] and media_applies(rule['media'], width):
            found = rule['declarations'][prop][0]
    return found


def template(name):
    with open(os.path.join(TEMPLATES, name + '.html'), encoding='utf-8') as handle:
        return handle.read()


def grid_value(width):
    return winning(SHEETS, GRID_CHAIN, 'grid-template-columns', width)[0]


def columns(width):
    value = grid_value(width)
    return 1 if value in ('1fr', 'minmax(0,1fr)') else int(value.split('repeat(')[1].split(',')[0])


class TheSharedBuildsGridTests(SimpleTestCase):

    def test_the_card_columns_by_width(self):
        expected = {375: 1, 699: 1, 700: 2, 768: 2, 1279: 2, 1280: 3, 1440: 3, 1599: 3, 1600: 4, 1920: 4,
                    2299: 4, 2300: 5, 2560: 5}
        for width in WIDTHS:
            self.assertEqual(expected[width], columns(width), width)

    def test_a_card_can_shrink_below_its_content(self):
        for width in WIDTHS:
            self.assertTrue(grid_value(width) == '1fr' or 'minmax(0' in grid_value(width), width)
        self.assertEqual('0', winning(SHEETS, CARD_CHAIN, 'min-width', 375)[0])

    def test_the_cards_still_come_from_one_loop_without_a_wrapper(self):
        page = template('shared_builds')
        self.assertEqual(1, page.count('class="builds-grid"'))
        self.assertEqual(1, page.count('class="build-card"'))


class TheSharedBuildsFiltersTests(SimpleTestCase):

    def test_each_filter_takes_the_whole_row_on_a_phone_and_shares_it_from_601(self):
        chain = chain_of(FILTERS, 'div', {'class': 'filter-group'}, ['fm-modern', 'fm-light'])
        self.assertEqual('1 1 100%', winning(SHEETS, chain, 'flex', 375)[0])
        self.assertEqual('1 1 100%', winning(SHEETS, chain, 'flex', 600)[0])
        self.assertEqual('1', winning(SHEETS, chain, 'flex', 601)[0])

    def test_the_build_type_groups_stack_on_a_phone(self):
        chain = chain_of(FILTERS + [('div', {'class': 'filter-group'})], 'table', {'class': 'build-boxes-section'},
                         ['fm-modern', 'fm-light'])
        self.assertEqual('flex', winning(SHEETS, chain, 'display', 375)[0])
        self.assertEqual('column', winning(SHEETS, chain, 'flex-direction', 375)[0])
        self.assertIsNone(winning(SHEETS, chain, 'display', 768))
        for column in range(4):
            self.assertIn('id="filter-checkboxes-column-%d"' % column, template('shared_builds'))

    def test_the_light_theme_does_not_paint_the_table_behind_the_rounded_groups(self):
        chain = chain_of(FILTERS + [('div', {'class': 'filter-group'})], 'table', {'class': 'build-boxes-section'},
                         ['fm-modern', 'fm-light'])
        sheets = [('forms_lighttheme.css', stylesheet('forms_lighttheme.css'))] + SHEETS
        self.assertEqual('transparent', winning(sheets, chain, 'background-color', 1920)[0])


class TheBuildListTests(SimpleTestCase):

    def test_each_row_is_a_wrapping_card_below_1024_and_a_table_row_from_1024(self):
        for width in WIDTHS:
            self.assertEqual('flex' if width < 1024 else None, at(LOAD_ROW, 'display', width), width)

    def test_the_table_does_not_scroll_sideways_on_a_phone(self):
        self.assertEqual('block', at(ROOT + ' .load-project-table', 'display', 375))
        self.assertIsNone(at(ROOT + ' .load-project-table', 'overflow-x', 375))

    def test_no_data_cell_is_hidden(self):
        for rule in MODERN:
            if any(selector.startswith(LOAD_CELL) and not selector.endswith(':empty') for selector in rule['selectors']):
                self.assertNotEqual('none', rule['declarations'].get('display', ('',))[0], rule['selectors'])

    def test_only_the_column_titles_after_the_first_are_hidden(self):
        self.assertEqual('none', at(ROOT + ' .load-project-table > tbody > tr > th:not(:first-child)', 'display', 375))
        self.assertIsNone(at(ROOT + ' .load-project-table > tbody > tr > th:not(:first-child)', 'display', 1280))

    def test_the_compare_button_is_a_touch_target_on_a_phone(self):
        self.assertEqual('44px', at(LOAD_CELL + ':last-child > button', 'min-height', 375))

    def test_no_rule_depends_on_the_column_count_of_a_signed_in_row(self):
        for rule in MODERN:
            for selector in rule['selectors']:
                if selector.startswith(LOAD_CELL):
                    self.assertNotIn('nth-child(8)', selector)
                    self.assertNotIn('nth-child(9)', selector)

    def test_the_list_keeps_the_cells_the_rules_address(self):
        page = template('load_projects')
        for token in ['load-project-table', 'load-project-line', 'load-project-cell', 'visibility-toggle',
                      'data-compare-add', 'class="all-proj"', 'class="no-proj"']:
            self.assertIn(token, page, token)


class TheFeedAndProfileCardTests(SimpleTestCase):

    def test_the_lists_are_grids_of_cards(self):
        for selector in (FEED, PROFILE):
            self.assertEqual('grid', at(selector, 'display', 375))
            self.assertIn('auto-fill', at(selector, 'grid-template-columns', 1920))

    def test_a_row_is_a_card(self):
        for selector in CARD_ROWS:
            self.assertEqual('var(--fm-surface-2)', at(selector, 'background', 1280))
            self.assertEqual('var(--fm-radius)', at(selector, 'border-radius', 1280))
            self.assertEqual('column', at(selector, 'flex-direction', 1280))

    def test_the_first_row_keeps_its_border(self):
        for selector in CARD_ROWS:
            self.assertEqual('1px solid var(--fm-border)', at(selector + ':first-child', 'border', 1280))

    def test_the_text_is_not_dimmed_by_opacity(self):
        for selector in (ROOT + ' .feed-meta', ROOT + ' .profile-build-meta', ROOT + ' .feed-author',
                         ROOT + ' .profile-meta', ROOT + ' .feed-empty', ROOT + ' .profile-empty'):
            self.assertEqual('1', at(selector, 'opacity', 1280), selector)

    def test_the_rows_stay_direct_children_of_their_wrapper(self):
        feed = template('feed')
        self.assertIn('<div class="feed-wrap">', feed)
        self.assertIn('<a class="feed-row"', feed)
        self.assertNotIn('feed-list', feed)
        profile = template('user_profile')
        self.assertIn('<div class="profile-wrap">', profile)
        self.assertIn('<a class="profile-build-row"', profile)
        self.assertNotIn('profile-list', profile)


class TheCommunitySectionIsModernOnlyTests(SimpleTestCase):

    def test_every_rule_after_the_section_heading_carries_the_modern_prefix(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'chardata', 'modern.css'),
                  encoding='utf-8') as handle:
            source = handle.read()
        start = source.index('Community pages: shared builds')
        section = source[source.index('*/', start) + 2:]
        names = [name for rule in stylesheet_of(section) for name in rule['selectors']]
        self.assertTrue(names)
        for name in names:
            self.assertTrue(name.startswith(ROOT), name)


def stylesheet_of(source):
    import re
    from chardata.tests_the_setup_stylesheet_support import parse
    return parse(re.sub(r'/\*.*?\*/', '', source, flags=re.S))
