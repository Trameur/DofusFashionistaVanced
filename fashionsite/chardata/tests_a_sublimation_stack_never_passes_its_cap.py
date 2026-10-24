from django.test import SimpleTestCase

from chardata.wakfu_invented_sublimations import (
    RED, Piece, Structure, block, socket_row, state, use_block)
from fashionistapulp import wakfu_legality, wakfu_sublimations

try:
    from fashionistapulp import wakfu_special_items as live
except ImportError:
    live = None

# The states the design pins by name, with the cap the game gives them
CONFLICTS = {6007: 1, 6090: 3, 6022: 2, 8132: 4}

SUBLIMATIONS = {100: (1, 1, 'normal', ()), 101: (1, 1, 'normal', ()),
                102: (1, 1, 'normal', ()), 103: (2, 1, 'normal', ())}
STATES = {1: state(lines=[('A', 'dmg_in_percent', 0, 5, ())], cap=2),
          2: state(lines=[('A', 'dmg_in_percent', -3, 0, ())], cap=2)}
CHOICES = [(wakfu_sublimations.SUBLIMATION, ident) for ident in (100, 101, 102)]


class TheCountedLevelIsHeldUnderTheCapTests(SimpleTestCase):
    def test_the_levels_are_added_up_and_held_under_the_cap(self):
        counted = wakfu_sublimations.counted_level
        self.assertEqual(3, counted([1, 2], 5))
        self.assertEqual(4, counted([3, 3], 4))
        self.assertEqual(0, counted([], 2))
        self.assertEqual(1, counted([1], 2))

    def test_a_state_with_no_cap_counts_every_level(self):
        self.assertEqual(7, wakfu_sublimations.counted_level([3, 4], None))


class AnInventedStateOfCapTwoIsCountedAtTwoTests(SimpleTestCase):
    def setUp(self):
        use_block(self, block(states=STATES, sublimations=SUBLIMATIONS))

    def test_three_positions_of_one_state_count_two_levels(self):
        lines, reports = wakfu_sublimations.fight_lines(CHOICES, {}, 100, 1)
        self.assertEqual({'dmg_in_percent': 10}, lines)
        self.assertEqual((3, 2, 2), (reports[1].summed, reports[1].cap, reports[1].counted))

    def test_two_positions_stay_under_the_cap(self):
        lines, reports = wakfu_sublimations.fight_lines(CHOICES[:2], {}, 100, 1)
        self.assertEqual({'dmg_in_percent': 10}, lines)
        self.assertEqual(2, reports[1].counted)

    def test_one_position_counts_one_level(self):
        lines, _reports = wakfu_sublimations.fight_lines(CHOICES[:1], {}, 100, 1)
        self.assertEqual({'dmg_in_percent': 5}, lines)

    def test_a_negative_line_is_counted_at_the_lower_of_the_sum_and_the_cap(self):
        for chosen, counted in ((1, 1), (2, 2), (3, 2)):
            with self.subTest(chosen=chosen):
                lines, reports = wakfu_sublimations.fight_lines(
                    [(wakfu_sublimations.SUBLIMATION, 103)] * chosen, {}, 100, 1)
                self.assertEqual(counted, reports[2].counted)
                self.assertEqual({'dmg_in_percent': -3}, lines)

    def test_the_value_scales_with_the_counted_level_not_with_the_sum(self):
        lines, _reports = wakfu_sublimations.fight_lines(CHOICES, {}, 100, 1)
        self.assertEqual(2 * 5, lines['dmg_in_percent'])


class TheCheckerReadsTheReportedStackTests(SimpleTestCase):
    def setUp(self):
        use_block(self, block(states=STATES, sublimations=SUBLIMATIONS))
        self.pieces = [Piece(10 + at, 1 + at) for at in range(3)]
        self.structure = Structure(self.pieces)
        self.worn = {'HEAD': self.pieces[0], 'NECK': self.pieces[1], 'CHEST': self.pieces[2]}
        self.chosen = {'HEAD': 100, 'NECK': 101, 'CHEST': 102}
        self.runes = {place: socket_row(RED) for place in self.worn}

    def rules(self, states):
        found = wakfu_legality.violations(
            self.structure, 100, self.worn, class_id=1, sublimations=self.chosen,
            runes=self.runes, states=states)
        return [rule for rule, _text in found]

    def test_a_reported_level_three_on_a_cap_of_two_is_flagged(self):
        report = wakfu_sublimations.StateReport(3, 2, 3, 'A', True, {'dmg_in_percent': 15})
        self.assertEqual([wakfu_legality.STACK], self.rules({1: report}))

    def test_the_level_the_checker_computes_is_legal(self):
        report = wakfu_sublimations.StateReport(3, 2, 2, 'A', True, {'dmg_in_percent': 10})
        self.assertEqual([], self.rules({1: report}))

    def test_a_reported_level_under_the_cap_the_sources_reach_is_flagged(self):
        report = wakfu_sublimations.StateReport(3, 2, 1, 'A', True, {'dmg_in_percent': 5})
        self.assertEqual([wakfu_legality.STACK], self.rules({1: report}))

    def test_a_state_reported_with_no_source_is_flagged_with_the_one_left_unreported(self):
        report = wakfu_sublimations.StateReport(1, 2, 1, 'A', True, {'dmg_in_percent': 5})
        self.assertEqual([wakfu_legality.STACK, wakfu_legality.STACK], self.rules({2: report}))

    def test_a_set_with_no_reported_state_has_nothing_to_compare(self):
        self.assertEqual([], self.rules(None))


class TheLiveStackCapsAreTheLowestOfTheOnesReadTests(SimpleTestCase):
    def setUp(self):
        if live is None:
            self.skipTest('no wakfu_special_items.py; run '
                          'itemscraper/generate_wakfu_special_items.py')

    def normal_states(self):
        return {row[0] for row in live.SUBLIMATIONS.values() if row[2] == 'normal'}

    def test_every_normal_state_caps_at_the_lowest_cap_the_game_gives(self):
        for state_id in sorted(self.normal_states()):
            entry = live.STATES[state_id]
            with self.subTest(state=state_id):
                self.assertTrue(entry['caps'], entry['name'])
                self.assertEqual(min(entry['caps'].values()), entry['cap'])

    def test_the_four_states_whose_sources_disagree_take_the_lowest(self):
        for state_id, cap in CONFLICTS.items():
            with self.subTest(state=state_id):
                self.assertEqual(cap, live.STATES[state_id]['cap'])

    def test_the_sources_disagree_only_on_the_two_states_that_name_two_caps(self):
        disagreeing = {state_id for state_id in self.normal_states()
                       if len(set(live.STATES[state_id]['caps'].values())) > 1}
        self.assertEqual({6090, 8132}, disagreeing)

    def test_the_live_counted_level_never_passes_the_cap_of_any_normal_state(self):
        for state_id in self.normal_states():
            cap = live.STATES[state_id]['cap']
            for summed in range(1, cap + 4):
                self.assertLessEqual(
                    wakfu_sublimations.counted_level([summed], cap), cap, (state_id, summed))
