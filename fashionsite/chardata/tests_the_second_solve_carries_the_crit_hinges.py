# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The second solve prices crit and critical damage from the first set, and a stopped search carries that pricing."""
import copy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.crit_curve import CritReading, crit_hinges
from chardata.fashion_action import _bind_search, _new_search, continuation_input, solve_with_weapon_hits
from fashionistapulp.dofus_constants import STAT_KEY_TO_NAME, STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal
from fashionistapulp.structure import set_current_game_version

MINOTOT_SCEPTRE = 8275
CHAOTIC_SCYTHE = 26011
OWN = {'str': 900, 'int': 700, 'pow': 250, 'ch': 30, 'cridam': 40, 'ap': 12}
WEIGHTS = {'str': 120, 'int': 110, 'cha': 0, 'agi': 30, 'ch': 240, 'cridam': 100, 'hp': 25}
READING = CritReading(500.5, ((80, 300.25), (95, 200.25)), 350.75)
TERMS = {CHAOTIC_SCYTHE: 7.5}


def _input(**fields):
    given = dict(objective_values=dict(WEIGHTS), item_terms={}, forbidden_equips=set(), locked_equips={},
                 empty_slot_types=[], minimum_stats={})
    given.update(fields)
    return SimpleNamespace(**given)


def _char(game_version='dofus3', level=200):
    return SimpleNamespace(id=1, game_version=game_version, char_class='Iop', level=level)


def _minimal(weapon_id):
    base = {name: 0 for name, _key in STATS_NAMES}
    base.update({STAT_KEY_TO_NAME[key]: value for key, value in OWN.items()})
    given = {'options': {'ap_exo': False, 'mp_exo': False, 'range_exo': False},
             'base_stats_by_attr': base, 'char_level': 200, 'origin': 'generated'}
    return ModelResultMinimal({'weapon': weapon_id}, given, {})


def _run(char, model_input, first='first', second='second', terms=None, reading=None, fails=None):
    """(the solved triple, the inputs the solves were called with, the arguments the reading was asked with)."""
    calls = []

    def solve_once(solve_input, deadline=None, longest=None):
        calls.append((copy.copy(solve_input), deadline, longest))
        return 'Optimal', {}, first if len(calls) == 1 else second

    asked = []

    def read_it(*args):
        asked.append(args)
        if fails is not None:
            raise fails
        return reading

    with mock.patch('chardata.fashion_action.weapon_hit_terms', return_value=terms or {}), \
            mock.patch('chardata.fashion_action.crit_hinges', side_effect=read_it):
        solved = solve_with_weapon_hits(char, solve_once, model_input, 5, 6)
    return solved, calls, asked


class TheSecondSolvePricesCritFromTheFirstSetTests(SimpleTestCase):

    def test_the_second_solve_carries_the_hinges_and_the_prices(self):
        model_input = _input()
        solved, calls, _asked = _run(_char(), model_input, reading=READING)
        self.assertEqual('second', solved[2])
        weighed = calls[1][0]
        self.assertEqual(READING.hinges, weighed.crit_hinges)
        self.assertEqual(dict(WEIGHTS, ch=READING.ch, cridam=READING.cridam), weighed.objective_values)
        self.assertEqual((5, 6), calls[1][1:])

    def test_the_stored_weights_and_the_first_solve_are_left_alone(self):
        model_input = _input()
        _solved, calls, _asked = _run(_char(), model_input, reading=READING)
        self.assertEqual(WEIGHTS, model_input.objective_values)
        self.assertFalse(hasattr(model_input, 'crit_hinges'))
        self.assertEqual(WEIGHTS, calls[0][0].objective_values)
        self.assertFalse(hasattr(calls[0][0], 'crit_hinges'))

    def test_the_reading_is_asked_on_the_first_set_and_the_terms(self):
        char, model_input = _char(), _input()
        _solved, _calls, asked = _run(char, model_input, terms=TERMS, reading=READING)
        self.assertEqual([(char, 'first', model_input, TERMS)], asked)

    def test_the_terms_and_the_reading_go_together(self):
        _solved, calls, _asked = _run(_char(), _input(), terms=TERMS, reading=READING)
        self.assertEqual(TERMS, calls[1][0].item_terms)
        self.assertEqual(READING.hinges, calls[1][0].crit_hinges)

    def test_a_locked_weapon_solves_again_with_the_hinges_and_no_terms(self):
        model_input = _input(locked_equips={'weapon': MINOTOT_SCEPTRE})
        _solved, calls, _asked = _run(_char(), model_input, terms={}, reading=READING)
        self.assertEqual(2, len(calls))
        self.assertEqual({}, calls[1][0].item_terms)
        self.assertEqual(READING.hinges, calls[1][0].crit_hinges)

    def test_the_terms_alone_leave_the_crit_as_it_is(self):
        _solved, calls, _asked = _run(_char(), _input(), terms=TERMS)
        self.assertEqual(TERMS, calls[1][0].item_terms)
        self.assertEqual(WEIGHTS, calls[1][0].objective_values)
        self.assertFalse(hasattr(calls[1][0], 'crit_hinges'))

    def test_a_price_without_a_slope_changes_the_critical_damage_weight_only(self):
        _solved, calls, _asked = _run(_char(), _input(), reading=CritReading(None, (), 3.5))
        self.assertEqual(2, len(calls))
        self.assertEqual(dict(WEIGHTS, cridam=3.5), calls[1][0].objective_values)
        self.assertFalse(hasattr(calls[1][0], 'crit_hinges'))

    def test_a_slope_without_a_price_changes_the_crit_weight_only(self):
        _solved, calls, _asked = _run(_char(), _input(), reading=CritReading(500.5, ((80, 500.5),), None))
        self.assertEqual(dict(WEIGHTS, ch=500.5), calls[1][0].objective_values)
        self.assertEqual(((80, 500.5),), calls[1][0].crit_hinges)

    def test_without_terms_or_a_reading_there_is_one_solve(self):
        solved, calls, _asked = _run(_char(), _input())
        self.assertEqual('first', solved[2])
        self.assertEqual(1, len(calls))

    def test_a_failed_second_solve_keeps_the_first_set(self):
        solved, calls, _asked = _run(_char(), _input(), second=None, reading=READING)
        self.assertEqual('first', solved[2])
        self.assertEqual(2, len(calls))

    def test_a_reading_that_raises_leaves_the_first_solve_as_it_is(self):
        with self.assertLogs('chardata.fashion_action', 'ERROR'):
            solved, calls, asked = _run(_char(), _input(), fails=ValueError('bad hull'))
        self.assertEqual(1, len(asked))
        self.assertEqual('first', solved[2])
        self.assertEqual(1, len(calls))

    def test_a_reading_that_raises_still_solves_again_with_the_terms(self):
        with self.assertLogs('chardata.fashion_action', 'ERROR'):
            solved, calls, _asked = _run(_char(), _input(), terms=TERMS, fails=ValueError('bad hull'))
        self.assertEqual('second', solved[2])
        self.assertEqual(TERMS, calls[1][0].item_terms)
        self.assertEqual(WEIGHTS, calls[1][0].objective_values)
        self.assertFalse(hasattr(calls[1][0], 'crit_hinges'))


class TheReadingComesFromTheCurveTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')

    def run_solves(self, char, model_input):
        first = _minimal(MINOTOT_SCEPTRE)
        with mock.patch('chardata.crit_curve.get_char_aspects', return_value={'str'}), \
                mock.patch('chardata.crit_curve.get_standard_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.crit_curve.get_stats_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.solution.get_solution_from_minimal',
                           side_effect=lambda char, minimal, refresh_base_stats=True:
                           model_result_from_minimal(minimal)):
            expected = crit_hinges(char, first, model_input, {})
            calls = []

            def solve_once(solve_input, deadline=None, longest=None):
                calls.append(copy.copy(solve_input))
                return 'Optimal', {}, first if len(calls) == 1 else 'second'

            with mock.patch('chardata.fashion_action.weapon_hit_terms', return_value={}):
                solved = solve_with_weapon_hits(char, solve_once, model_input, 5, 6)
        return solved, calls, expected

    def test_dofus_three_at_level_two_hundred_reads_the_curve_of_the_first_set(self):
        solved, calls, expected = self.run_solves(_char(), _input())
        self.assertIsNotNone(expected)
        self.assertEqual('second', solved[2])
        self.assertEqual(expected.hinges, calls[1].crit_hinges)
        self.assertEqual(expected.ch, calls[1].objective_values['ch'])
        self.assertEqual(expected.cridam, calls[1].objective_values['cridam'])
        self.assertEqual(WEIGHTS['str'], calls[1].objective_values['str'])

    def test_the_other_versions_and_levels_solve_once(self):
        for game_version, level in (('dofus2', 200), ('beta', 200), ('touch', 200), ('retro', 200),
                                    ('dofus3', 199)):
            with self.subTest(game_version=game_version, level=level):
                _solved, calls, expected = self.run_solves(_char(game_version, level), _input())
                self.assertIsNone(expected)
                self.assertEqual(1, len(calls))

    def test_a_curve_that_breaks_while_it_is_read_solves_once(self):
        first, calls = _minimal(MINOTOT_SCEPTRE), []

        def solve_once(solve_input, deadline=None, longest=None):
            calls.append(copy.copy(solve_input))
            return 'Optimal', {}, first

        with mock.patch('chardata.crit_curve.get_char_aspects', return_value={'str'}), \
                mock.patch('chardata.crit_curve.get_standard_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.crit_curve.get_stats_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.solution.get_solution_from_minimal',
                           side_effect=lambda char, minimal, refresh_base_stats=True:
                           model_result_from_minimal(minimal)), \
                mock.patch('chardata.crit_curve.concave_hull', side_effect=ValueError('no hull')), \
                mock.patch('chardata.fashion_action.weapon_hit_terms', return_value={}), \
                self.assertLogs('chardata.fashion_action', 'ERROR'):
            solved = solve_with_weapon_hits(_char(), solve_once, _input(), 5, 6)
        self.assertIs(first, solved[2])
        self.assertEqual(1, len(calls))

    def test_a_char_the_curve_cannot_read_solves_once(self):
        with mock.patch('chardata.fashion_action.weapon_hit_terms', return_value={}):
            calls = []

            def solve_once(solve_input, deadline=None, longest=None):
                calls.append(solve_input)
                return 'Optimal', {}, 'first'

            solve_with_weapon_hits(object(), solve_once, _input(), 5, 6)
        self.assertEqual(1, len(calls))


class AStoppedSearchCarriesTheHingesTests(SimpleTestCase):

    STATE = {'objective': 10.0, 'bound': 12.0, 'values': {'x_1': 1}}
    PLAN = ('turn', 10)

    def weighed(self):
        return _input(objective_values=dict(WEIGHTS, ch=READING.ch, cridam=READING.cridam), item_terms=TERMS,
                      crit_hinges=READING.hinges, cache_key=lambda: 'key')

    def plain(self):
        return _input(crit_hinges=(), cache_key=lambda: 'key')

    def test_the_search_keeps_the_hinges_its_input_had(self):
        self.assertEqual(READING.hinges, _new_search(self.STATE, self.weighed(), 90)['crit_hinges'])
        self.assertIsNone(_new_search(self.STATE, self.plain(), 90)['crit_hinges'])
        self.assertIsNone(_new_search(self.STATE, _input(), 90)['crit_hinges'])

    def test_the_hinges_are_bound_to_the_input_they_differ_from(self):
        result = SimpleNamespace(search=_new_search(self.STATE, self.weighed(), 90))
        _bind_search(result, self.plain(), self.PLAN)
        self.assertEqual(READING.hinges, result.search['crit_hinges'])
        self.assertEqual(dict(WEIGHTS, ch=READING.ch, cridam=READING.cridam), result.search['objective_values'])
        same = SimpleNamespace(search=_new_search(self.STATE, self.weighed(), 90))
        _bind_search(same, self.weighed(), self.PLAN)
        self.assertIsNone(same.search['crit_hinges'])

    def continued(self, solve_input):
        result = SimpleNamespace(search=_new_search(self.STATE, solve_input, 90))
        _bind_search(result, self.plain(), self.PLAN)
        minimal = SimpleNamespace(proven=False, data_version='3.7', search=result.search)
        char = _char()
        with mock.patch('chardata.fashion_action.current_data_version', return_value='3.7'), \
                mock.patch('chardata.fashion_action.get_stats_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.fashion_action._model_input', return_value=self.plain()), \
                mock.patch('chardata.fashion_action.guard_plan', return_value=self.PLAN):
            return continuation_input(None, char, minimal)

    def test_a_continued_search_gets_the_hinges_and_the_prices_back(self):
        solve_input = self.continued(self.weighed())
        self.assertEqual(READING.hinges, solve_input.crit_hinges)
        self.assertEqual(dict(WEIGHTS, ch=READING.ch, cridam=READING.cridam), solve_input.objective_values)
        self.assertEqual(TERMS, solve_input.item_terms)

    def test_a_search_of_the_first_solve_gets_no_hinges(self):
        solve_input = self.continued(self.plain())
        self.assertEqual((), solve_input.crit_hinges)
        self.assertEqual(WEIGHTS, solve_input.objective_values)
