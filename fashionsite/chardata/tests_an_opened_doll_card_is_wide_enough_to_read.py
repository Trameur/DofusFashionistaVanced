# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An opened doll card spans both card columns in its own row, keeps the spot it was clicked on, and the closed cards keep their width beside the character."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import _declarations, read_css, top_level_split

LAPTOP = '@media (min-width:760px)'
BUSY = ('html.fm-modern .solution-item-section.fm-sol-doll:has(> .expand-container.fm-open)'
        ':has(> .expand-container:not(.fm-open))')
CLOSED_LEFT = ':has(> .expand-container:not(.fm-open))'
LEFT = ('hat', 'cloak', 'amulet', 'ring1', 'ring2')
RIGHT = ('weapon', 'shield', 'belt', 'boots', 'pet')
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')


def nested_rules(name):
    """Every style rule of a sheet with the chain of @media and @container preludes around it."""
    found = []

    def walk(source, context):
        position = 0
        while True:
            opening = source.find('{', position)
            if opening == -1:
                return
            prelude = ' '.join(source[position:opening].split())
            depth, index = 1, opening + 1
            while depth:
                depth += {'{': 1, '}': -1}.get(source[index], 0)
                index += 1
            body = source[opening + 1:index - 1]
            position = index
            if prelude.startswith(('@media', '@container', '@supports')):
                walk(body, context + (prelude,))
            elif not prelude.startswith('@'):
                found.append({'context': context, 'selectors': [' '.join(piece.split()) for piece in top_level_split(prelude)],
                              'declarations': {prop: value for prop, (value, _) in _declarations(body).items()}})

    walk(read_css(name), ())
    return found


PARTS = nested_rules('modern-solution-parts.css')


def value(selector, prop, context=(LAPTOP,)):
    found = [rule['declarations'][prop] for rule in PARTS
             if rule['context'] == context and selector in rule['selectors'] and prop in rule['declarations']]
    return found[-1] if found else None


def ids(slots):
    return ','.join('#item-container-' + slot for slot in slots)


RIGHT_OPEN = BUSY + ':has(> .expand-container.fm-open:is(%s)):not(:has(> .expand-container.fm-open:is(%s)))' % (ids(RIGHT), ids(LEFT))
LAYOUTS = {'a left card open': BUSY, 'only right cards open': RIGHT_OPEN}


def closed_doll():
    """The closed three column doll of the main sheet: its column tracks and the column each named area starts on."""
    rule = [rule for rule in nested_rules('modern.css')
            if rule['context'] == (LAPTOP,) and 'html.fm-modern .solution-item-section.fm-sol-doll' in rule['selectors']][-1]
    rows = re.findall(r'"([^"]*)"', rule['declarations']['grid-template-areas'])
    columns = {}
    for row in rows:
        for index, area in enumerate(row.split(), 1):
            columns.setdefault(area, index)
    return rule['declarations']['grid-template-columns'], columns


def tracks(template):
    return sorted(re.findall(r'minmax\([^)]*\)|\d+px', template))


def column_of(area):
    return int(area.split('/')[1].strip())


def span_of(column):
    start, end = (int(part) for part in column.split('/'))
    return range(start, end)


def doll_rules():
    return [(selector, rule) for rule in PARTS for selector in rule['selectors']
            if '.fm-sol-doll' in selector and '.fm-open' in selector and ':not(.fm-sol-doll)' not in selector]


class AnOpenedDollCardTests(SimpleTestCase):

    def test_an_open_doll_lays_two_card_columns_beside_the_character_without_named_areas(self):
        self.assertEqual('minmax(0,1fr) minmax(0,1fr) 190px', value(BUSY, 'grid-template-columns'))
        self.assertEqual('190px minmax(0,1fr) minmax(0,1fr)', value(RIGHT_OPEN, 'grid-template-columns'))
        self.assertEqual('repeat(6,auto)', value(BUSY, 'grid-template-rows'))
        self.assertEqual('none', value(BUSY, 'grid-template-areas'))
        self.assertEqual('row dense', value(BUSY, 'grid-auto-flow'))

    def test_the_open_layouts_keep_the_closed_doll_tracks_so_closed_cards_keep_their_width(self):
        closed, _ = closed_doll()
        for name, layout in LAYOUTS.items():
            with self.subTest(layout=name):
                self.assertEqual(tracks(closed), tracks(value(layout, 'grid-template-columns')))

    def test_the_open_layouts_start_where_the_three_column_doll_starts(self):
        doll = [rule for rule in nested_rules('modern.css')
                if 'html.fm-modern .solution-item-section.fm-sol-doll' in rule['selectors']
                and 'grid-template-areas' in rule['declarations'] and rule['declarations']['grid-template-areas'] != 'none']
        self.assertEqual([(LAPTOP,)], [rule['context'] for rule in doll])

    def test_every_piece_keeps_its_side_of_the_doll(self):
        self.assertEqual('auto / 1', value(BUSY + ' > :is(%s)' % ids(LEFT), 'grid-area'))
        self.assertEqual('auto / 2', value(BUSY + ' > :is(%s)' % ids(RIGHT), 'grid-area'))
        self.assertEqual('auto / 2', value(RIGHT_OPEN + ' > :is(%s)' % ids(LEFT), 'grid-area'))
        self.assertEqual('auto / 3', value(RIGHT_OPEN + ' > :is(%s)' % ids(RIGHT), 'grid-area'))

    def test_the_side_of_the_open_card_keeps_its_closed_column_so_the_header_stays_under_the_pointer(self):
        _, closed = closed_doll()
        for name, layout, side in (('a left card open', BUSY, LEFT), ('only right cards open', RIGHT_OPEN, RIGHT)):
            with self.subTest(layout=name):
                self.assertEqual(closed[side[0]], column_of(value(layout + ' > :is(%s)' % ids(side), 'grid-area')))

    def test_an_open_card_covers_both_card_columns_and_the_column_it_was_clicked_in(self):
        spans = {name: span_of(value(layout + ' > .expand-container.fm-open:is(%s)' % ids(LEFT + RIGHT), 'grid-column'))
                 for name, layout in LAYOUTS.items()}
        self.assertEqual(range(1, 3), spans['a left card open'])
        self.assertEqual(range(2, 4), spans['only right cards open'])
        for name, layout in LAYOUTS.items():
            for side in (LEFT, RIGHT):
                with self.subTest(layout=name, side=side[0]):
                    self.assertIn(column_of(value(layout + ' > :is(%s)' % ids(side), 'grid-area')), spans[name])

    def test_the_character_spans_every_row_beside_the_two_card_columns(self):
        self.assertEqual('1 / 3 / -1 / 4', value(BUSY + ' > .fm-sol-figure', 'grid-area'))
        self.assertEqual('1 / 1 / -1 / 2', value(RIGHT_OPEN + ' > .fm-sol-figure', 'grid-area'))

    def test_the_pieces_read_row_by_row_and_an_open_card_comes_before_its_row_partner(self):
        for row, (left, right) in enumerate(zip(LEFT, RIGHT), 1):
            with self.subTest(row=row):
                self.assertEqual(str(4 * row), value(BUSY + ' > #item-container-' + left, 'order'))
                self.assertEqual(str(4 * row + 2), value(BUSY + ' > #item-container-' + right, 'order'))
                self.assertEqual(str(4 * row - 1), value(BUSY + ' > .expand-container.fm-open:is(%s)' % ids((left, right)), 'order'))
                self.assertGreater(4 * row - 1, 4 * (row - 1) + 2)

    def test_the_right_hand_layout_steps_aside_once_a_left_card_is_open(self):
        self.assertTrue(RIGHT_OPEN.endswith(':not(:has(> .expand-container.fm-open:is(%s)))' % ids(LEFT)))
        self.assertIsNotNone(value(RIGHT_OPEN, 'grid-template-columns'))

    def test_every_open_doll_rule_waits_for_a_closed_card_so_show_all_keeps_the_closed_doll(self):
        checked = doll_rules()
        self.assertGreater(len(checked), 20)
        for selector, rule in checked:
            with self.subTest(selector=selector):
                self.assertEqual((LAPTOP,), rule['context'])
                self.assertIn(CLOSED_LEFT, selector)

    def test_no_rule_lifts_the_closed_cards_off_their_row_height_while_a_card_is_open(self):
        checked = doll_rules()
        self.assertTrue(checked)
        for selector, rule in checked:
            with self.subTest(selector=selector):
                self.assertNotIn('align-items', rule['declarations'])
                self.assertNotIn('align-self', rule['declarations'])

    def test_the_page_does_not_scroll_away_from_the_card_it_opens(self):
        self.assertEqual('none', value('html.fm-modern body', 'overflow-anchor'))

    def test_the_slots_the_stylesheet_places_are_the_slots_the_page_moves_into_the_doll(self):
        with open(os.path.join(TEMPLATES, 'solution.html'), encoding='utf-8') as page:
            moved = re.search(r"\[('hat'[^\]]*)\]\.forEach", page.read()).group(1)
        self.assertEqual(sorted(LEFT + RIGHT), sorted(slot.strip("' ") for slot in moved.split(',')))

    def test_only_shown_stat_lines_flow_in_columns_and_the_edit_rows_stay_one_column(self):
        lines = 'html.fm-modern .solution-item-section .expand-container.fm-open [id^="stat-lines-"]:has(> .solution-inline-stat-line)'
        self.assertEqual('14em', value(lines, 'column-width', ()))
        self.assertEqual('24px', value(lines, 'column-gap', ()))
        with open(os.path.join(TEMPLATES, 'solution.html'), encoding='utf-8') as page:
            script = page.read()
        edit = script[script.index('function showEditMode('):]
        edit = edit[:edit.index('\n        }\n')]
        self.assertIn('sol-stat-edit-row', edit)
        self.assertNotIn('solution-inline-stat-line', edit)
        with open(os.path.join(TEMPLATES, 'solution_item.html'), encoding='utf-8') as item:
            self.assertIn('<span class="solution-inline-stat-line', item.read())
