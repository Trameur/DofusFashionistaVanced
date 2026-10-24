from unittest import mock

from fashionistapulp import wakfu_model, wakfu_sublimations
from fashionistapulp.wakfu_stats import OUT_OF_COMBAT_CAPS
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    CRIT_ITEMS, EPIC_CHEST, RELIC_AMULET, RELIC_HELM)
from chardata.wakfu_invented_sublimation_model import (
    FERO_HELM, SublimationModelCase, state)

TEN_FEROCITY = {1: state(lines=[('A', 'ferocity', 0, 10, ())])}
ONE_PER_POSITION = {110: (1, 1, 'normal', ())}
THREE_AP = {9: state(lines=[('A', 'ap', 3, 0, ())], cap=1)}
ONE_AP_SUBLIMATION = {150: (9, 1, 'normal', ())}
WEIGHTS = {'ferocity': 1, 'hp': 0.001}
OUTBIDDERS = (FERO_HELM, RELIC_HELM, RELIC_AMULET, EPIC_CHEST)
SUBLIMATION_PREFIXES = ('sb_', 'sc_', 'sq_', 'sx_', 'sa_', 'sf_', 'sr_', 'sv_', 'ps_')


class TheMinimumsReadTheFightTotalTests(SublimationModelCase):
    def test_a_minimum_only_the_sublimations_reach_is_met_in_the_fight(self):
        self.invent(TEN_FEROCITY, ONE_PER_POSITION)
        build, worn = self.sublimate(WEIGHTS, minimums={'ferocity': 60})
        self.assertIsNotNone(worn)
        self.assertGreaterEqual(worn.totals['ferocity'], 60)
        self.assertLess(worn.sheet_totals['ferocity'], 60)
        self.assert_objective_is_read_back(build, worn)

    def test_the_same_minimum_is_infeasible_without_the_sublimations(self):
        self.invent(TEN_FEROCITY, ONE_PER_POSITION)
        _build, worn = self.sublimate(WEIGHTS, sublimations=None, minimums={'ferocity': 60})
        self.assertIsNone(worn)


class TheApCapReadsTheSheetTotalTests(SublimationModelCase):
    def test_a_fight_line_of_ap_may_pass_the_cap_the_sheet_total_obeys(self):
        self.invent(THREE_AP, ONE_AP_SUBLIMATION)
        build, worn = self.sublimate({'ap': 10, 'hp': 0.001})
        cap = OUT_OF_COMBAT_CAPS['AP']
        self.assertLessEqual(worn.sheet_totals['ap'], cap)
        self.assertEqual(worn.sheet_totals['ap'] + 3, worn.totals['ap'])
        self.assertGreater(worn.totals['ap'], cap)
        self.assert_objective_is_read_back(build, worn)


class AGateOfAPieceHoldsUnderBothReadingsTests(SublimationModelCase):
    def crit_pieces(self, worn):
        return [piece for piece in worn.values() if piece.id in CRIT_ITEMS]

    def test_a_fight_malus_tightens_the_gate_the_sheet_total_leaves_open(self):
        self.invent({1: state(lines=[('A', 'ferocity', 0, -4, ()), ('A', 'hp', 4000, 0, ())])},
                    ONE_PER_POSITION)
        _build, plain = self.sublimate({'hp': 1}, sublimations=None, forbidden=OUTBIDDERS)
        build, worn = self.sublimate({'hp': 1}, forbidden=OUTBIDDERS)
        self.assertTrue(worn.sublimations)
        self.assertGreaterEqual(len(self.crit_pieces(plain)), 2)
        self.assertLessEqual(len(self.crit_pieces(worn)), 1)
        self.assertEqual([], self.rules_broken(worn, forbidden=OUTBIDDERS))
        self.assert_objective_is_read_back(build, worn)


class ANoneSublimationArgumentKeepsTheModelOfTheLastStepTests(SublimationModelCase):
    def names(self, build):
        return sorted(build.problem.variable_names()), sorted(build.problem.row_names())

    def test_the_columns_and_rows_are_those_of_a_build_with_no_block(self):
        self.invent(TEN_FEROCITY, ONE_PER_POSITION)
        build, worn = self.sublimate(WEIGHTS, sublimations=None, passives=None)
        with mock.patch.object(wakfu_sublimations, 'load', return_value=None):
            plain, plain_worn = self.sublimate(WEIGHTS, sublimations=None, passives=None)
        self.assertEqual(self.names(plain), self.names(build))
        self.assertAlmostEqual(plain.problem.objective_value, build.problem.objective_value,
                               delta=1e-9)
        self.assertEqual(dict(plain_worn), dict(worn))

    def test_no_sublimation_column_exists_and_the_fight_total_is_the_sheet_total(self):
        self.invent(TEN_FEROCITY, ONE_PER_POSITION)
        build, worn = self.sublimate(WEIGHTS, sublimations=None, passives=None)
        for prefix in SUBLIMATION_PREFIXES:
            self.assertEqual([], self.columns(build, prefix))
        self.assertIsNone(worn.sublimations)
        self.assertIsNone(worn.passives)
        self.assertEqual(worn.sheet_totals, worn.totals)

    def test_the_sublimation_modes_are_validated(self):
        with self.assertRaises(ValueError):
            wakfu_model.WakfuBuild(self.structure, 100, WEIGHTS, sublimations='sometimes')


class TheObjectiveOfASetIsTheSolversObjectiveTests(SublimationModelCase):
    def test_a_set_with_runes_sublimations_specials_and_passives_reads_back(self):
        from chardata.tests_a_passive_slot_holds_the_best_open_passive_of_the_class import (
            PASSIVES)
        states = {1: state(lines=[('A', 'ferocity', 0, 10, ())], cap=3),
                  3: state(lines=[('B', 'ferocity', 30, 0, (0,))],
                           conditions=[('GetCharacMax', 'ap', '<=', 10)])}
        subs = {110: (1, 1, 'normal', (1, 2, 3)), 111: (1, 2, 'normal', ()),
                120: (3, 1, 'epic', ())}
        self.invent(states, subs, passives=PASSIVES)
        build, worn = self.sublimate({'ferocity': 1, 'melee_dmg': 1, 'hp': 0.001},
                                     runes='optimistic', passives='solve')
        self.assertTrue(worn.sublimations)
        self.assertTrue(worn.passives)
        self.assert_objective_is_read_back(build, worn)
        self.assertEqual([], self.rules_broken(worn))
