import math

from fashionistapulp import wakfu_sublimations
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import BREEDS
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, LEVEL, SublimationModelCase, state)

AP_AT_MOST_TEN = ('GetCharacMax', 'ap', '<=', 10)
GAIN = state(lines=[('B', 'ferocity', 30, 0, (0,))], conditions=[AP_AT_MOST_TEN])
PENALTY = state(lines=[('A', 'ferocity', 50, 0, ()), ('B', 'ferocity', -30, 0, (0,))],
                conditions=[AP_AT_MOST_TEN])
CONVERT_UP = state(conversions=[('hp', 'ferocity', 0.01, 0, 1, ())])
CONVERT_DOWN = state(lines=[('A', 'ferocity', 100, 0, ())],
                     conversions=[('hp', 'ferocity', 0.01, 0, -1, ())], cap=1)

WEIGHTS = {'ferocity': 1, 'ap': 1, 'hp': 0.001}
BASE_HP = BREEDS[0]['base']['HP']


def holds(worn, entry):
    return wakfu_sublimations.condition_holds(
        entry['conditions'], worn.sheet_totals, LEVEL, ALPHA)[0]


class AnEpicGainBehindAnApGateTests(SublimationModelCase):
    def solve_with(self, ap_weight):
        self.invent({3: GAIN}, {120: (3, 1, 'epic', ())})
        return self.sublimate(dict(WEIGHTS, ap=ap_weight))

    def test_the_gain_counts_when_the_ap_total_stays_under_the_gate(self):
        build, worn = self.solve_with(1)
        self.assertEqual({120}, {row[0] for row in worn.specials.values()})
        self.assertTrue(holds(worn, GAIN))
        self.assertEqual(30, worn.totals['ferocity'] - worn.sheet_totals['ferocity'])
        self.assert_objective_is_read_back(build, worn)
        self.assertEqual([], self.rules_broken(worn))

    def test_the_epic_stays_off_when_the_ap_items_are_worth_more(self):
        build, worn = self.solve_with(100)
        self.assertFalse(worn.specials)
        self.assertGreater(worn.sheet_totals['ap'], 10)
        self.assert_objective_is_read_back(build, worn)


class AnEpicPenaltyBehindAnApGateTests(SublimationModelCase):
    def test_the_solver_cannot_switch_the_penalty_off_while_the_gate_holds(self):
        self.invent({4: PENALTY}, {121: (4, 1, 'epic', ())})
        build, worn = self.sublimate(WEIGHTS)
        self.assertEqual({121}, {row[0] for row in worn.specials.values()})
        self.assertGreater(worn.sheet_totals['ap'], 10)
        self.assertFalse(holds(worn, PENALTY))
        self.assertEqual(50, worn.totals['ferocity'] - worn.sheet_totals['ferocity'])
        self.assert_objective_is_read_back(build, worn)

    def test_a_set_that_keeps_the_gate_open_pays_the_penalty(self):
        self.invent({4: PENALTY}, {121: (4, 1, 'epic', ())})
        build, worn = self.sublimate(dict(WEIGHTS, ap=-10))
        self.assertTrue(holds(worn, PENALTY))
        self.assertEqual(20, worn.totals['ferocity'] - worn.sheet_totals['ferocity'])
        self.assert_objective_is_read_back(build, worn)


class AConversionIsFlooredLikeTheClientTests(SublimationModelCase):
    def moved(self, entry):
        self.invent({5: entry}, {130: (5, 1, 'normal', ())})
        build, worn = self.sublimate(WEIGHTS)
        gain = worn.totals['ferocity'] - worn.sheet_totals['ferocity']
        return build, worn, gain

    def test_the_converted_amount_is_the_floor_of_the_share_of_the_sheet_total(self):
        build, worn, gain = self.moved(CONVERT_UP)
        self.assertTrue(worn.sublimations)
        self.assertEqual(math.floor((worn.sheet_totals['hp'] + BASE_HP) * 0.01), gain)
        self.assertGreater(gain, 0)
        self.assertEqual([], self.rules_broken(worn))
        self.assert_objective_is_read_back(build, worn)

    def test_a_conversion_that_costs_the_target_takes_the_whole_floored_amount(self):
        self.invent({5: CONVERT_DOWN}, {130: (5, 1, 'normal', ())})
        build, worn = self.sublimate(dict(WEIGHTS, hp=0.1))
        net = worn.totals['ferocity'] - worn.sheet_totals['ferocity']
        self.assertTrue(worn.sublimations)
        self.assertEqual(100 - math.floor((worn.sheet_totals['hp'] + BASE_HP) * 0.01), net)
        self.assertEqual([], self.rules_broken(worn))
        self.assert_objective_is_read_back(build, worn)
