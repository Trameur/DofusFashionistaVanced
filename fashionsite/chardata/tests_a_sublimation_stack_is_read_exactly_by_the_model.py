from fashionistapulp import wakfu_sublimations
from chardata.wakfu_invented_sublimation_model import SublimationModelCase, state

STATES = {1: state(lines=[('A', 'ferocity', 0, 10, ())], cap=3)}
SUBLIMATIONS = {110: (1, 2, 'normal', ()), 111: (1, 1, 'normal', ())}
WEIGHTS = {'ferocity': 1, 'hp': 0.001}


class AStateStackIsHeldUnderItsCapTests(SublimationModelCase):
    def setUp(self):
        self.invent(STATES, SUBLIMATIONS)
        self.build, self.worn = self.sublimate(WEIGHTS)
        self.summed = sum(level for _ident, _state, level, _pattern
                          in self.worn.sublimations.values())

    def test_the_levels_placed_reach_the_cap(self):
        self.assertGreaterEqual(self.summed, 3)

    def test_the_fight_counts_the_cap_and_not_the_sum(self):
        gain = self.worn.totals['ferocity'] - self.worn.sheet_totals['ferocity']
        self.assertEqual(10 * wakfu_sublimations.counted_level([self.summed], 3), gain)
        self.assertEqual(30, gain)

    def test_the_cap_row_and_the_exact_stack_rows_exist(self):
        rows = self.build.problem.row_names()
        for name in ('stack_1_one', 'stack_1_below'):
            self.assertIn(name, rows)

    def test_no_level_is_placed_that_the_cap_would_waste(self):
        self.assertLessEqual(self.summed, 4)

    def test_the_objective_is_read_back_from_the_set(self):
        self.assert_objective_is_read_back(self.build, self.worn)

    def test_the_checker_reads_the_same_counted_level(self):
        self.assertEqual([], self.rules_broken(self.worn, states=self.worn.states))
        self.assertEqual(3, self.worn.states[1].counted)
        self.assertEqual(self.summed, self.worn.states[1].summed)
