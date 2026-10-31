from django.test import SimpleTestCase

from fashionistapulp import wakfu_sublimations
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, SublimationModelCase, block, state, use_block)

try:
    from fashionistapulp import wakfu_special_items as live
except ImportError:
    live = None

SUBLIMATION = wakfu_sublimations.SUBLIMATION
LATE = wakfu_sublimations.LATE
EMPTY_THE_MASTERY = state(conversions=[('critical_bonus', 'critical_bonus', 0, 1, -1, ()),
                                       ('critical_bonus', 'dmg_in_percent', 0, 1, 1, ())])
QUIET = state(lines=[('B', 'ferocity', 0, 5, (0, 1))], cap=6,
              conditions=[(LATE, 'critical_bonus', '<=', 0), (LATE, 'melee_dmg', '<=', 0)])
LOUD = state(shares=[('A', 'melee_dmg', 0, 5, ())], cap=6)


def passive(lines=(), conditions=(), shares=()):
    return {'name': 'Passive', 'breed': ALPHA, 'unlock': 1, 'family': 'B', 'lines': list(lines),
            'shares': list(shares), 'conditions': list(conditions), 'conversions': [],
            'uncounted': []}


class AFirstTurnConditionIsReadAfterTheStartOfTheFightTests(SimpleTestCase):
    def lines(self, *states, totals=None):
        use_block(self, block(
            states={at: found for at, found in enumerate(states, 1)},
            sublimations={at * 10: (at, 3, 'normal', ()) for at in range(1, len(states) + 1)}))
        choices = [(SUBLIMATION, at * 10) for at in range(1, len(states) + 1)]
        return wakfu_sublimations.fight_lines(choices, totals or {}, 230, ALPHA)[0]

    def test_it_does_not_hold_while_the_sheet_still_has_the_mastery(self):
        self.assertEqual({}, self.lines(QUIET, totals={'critical_bonus': 100}))

    def test_it_holds_once_a_conversion_of_the_start_has_emptied_the_mastery(self):
        lines = self.lines(EMPTY_THE_MASTERY, QUIET, totals={'critical_bonus': 100})
        self.assertEqual(15, lines['ferocity'])
        self.assertEqual(-100, lines['critical_bonus'])

    def test_the_order_the_states_are_chosen_in_changes_nothing(self):
        self.assertEqual(self.lines(EMPTY_THE_MASTERY, QUIET, totals={'critical_bonus': 100}),
                         self.lines(QUIET, EMPTY_THE_MASTERY, totals={'critical_bonus': 100}))

    def test_a_share_the_start_adds_to_a_mastery_closes_it_again(self):
        lines = self.lines(EMPTY_THE_MASTERY, LOUD, QUIET, totals={'critical_bonus': 100})
        self.assertNotIn('ferocity', lines)

    def test_a_report_says_whether_the_state_gave_its_lines(self):
        use_block(self, block(states={1: QUIET}, sublimations={10: (1, 3, 'normal', ())}))
        _lines, reports = wakfu_sublimations.fight_lines([(SUBLIMATION, 10)], {}, 230, ALPHA)
        self.assertEqual({'ferocity': 15}, reports[1].lines)
        self.assertTrue(reports[1].condition)


class TheSolvedModelReadsTheTotalsOfTheFirstTurnTests(SublimationModelCase):
    def solve(self, weights):
        self.invent(passives={
            1: passive(lines=[('A', 'critical_bonus', 50, 0, ())]),
            2: passive(lines=[('B', 'ferocity', 30, 0, (0,))],
                       conditions=[(LATE, 'critical_bonus', '<=', 0)])})
        return self.sublimate(weights, sublimations=None, passives='solve')

    def test_the_solver_leaves_out_the_mastery_that_would_close_the_condition(self):
        build, worn = self.solve({'critical_bonus': 0.1, 'ferocity': 1})
        self.assertEqual([2], worn.passives)
        self.assertEqual(30, worn.totals['ferocity'] - worn.sheet_totals['ferocity'])
        self.assertEqual([], self.rules_broken(worn))
        self.assert_objective_is_read_back(build, worn)

    def test_it_takes_the_mastery_when_the_mastery_is_worth_more(self):
        build, worn = self.solve({'critical_bonus': 1, 'ferocity': 1})
        self.assertEqual([1], worn.passives)
        self.assertEqual(0, worn.totals['ferocity'] - worn.sheet_totals['ferocity'])
        self.assert_objective_is_read_back(build, worn)


class TheLiveBlockReadsTheSecondaryMasteriesOnTheFirstTurnTests(SimpleTestCase):
    def setUp(self):
        if live is None:
            self.skipTest('no wakfu_special_items.py; run '
                          'itemscraper/generate_wakfu_special_items.py')

    def ambition(self):
        return next((ident, found) for ident, found in live.STATES.items()
                    if found['name'] == 'Ambition')

    def test_ambition_is_a_counted_line_behind_late_conditions_only(self):
        _ident, found = self.ambition()
        self.assertEqual([('B', 'ferocity', 0, 5, tuple(range(len(found['conditions']))))],
                         [tuple(line) for line in found['lines']])
        self.assertEqual({LATE}, {condition[0] for condition in found['conditions']})
        self.assertEqual({('<=', 0)}, {tuple(condition[2:]) for condition in found['conditions']})

    def test_ambition_gives_five_percent_a_level_only_when_every_secondary_mastery_is_empty(self):
        ident, _found = self.ambition()
        item = next(one for one, row in live.SUBLIMATIONS.items() if row[0] == ident)
        level = live.SUBLIMATIONS[item][1]
        empty = wakfu_sublimations.fight_lines([(SUBLIMATION, item)], {}, 230, 1)[0]
        self.assertEqual({'ferocity': 5 * level}, empty)
        closed = wakfu_sublimations.fight_lines(
            [(SUBLIMATION, item)], {'melee_dmg': 1}, 230, 1)[0]
        self.assertEqual({}, closed)
