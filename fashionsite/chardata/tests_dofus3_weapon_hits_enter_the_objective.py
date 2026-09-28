# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 3 weapons are paid for the turn their hits add, read on the first set of a two-solve run."""
import copy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.spell_combo import castable_spells
from chardata.weapon_terms import (TurnReader, candidate_weapons, terms_on_stats,
                                   weapon_hit_terms, weapon_swing)
from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY

CHAOTIC_SCYTHE = 26011
MINOTOT_SCEPTRE = 8275
DREGGON_DAGGERS = 8414
BASIC_BROOM = 27645


def _stats(**values):
    stats = {key: 0 for key in STAT_NAME_TO_KEY.values()}
    stats.update(values)
    return stats


def _structure():
    from fashionistapulp.structure import get_structure
    return get_structure('dofus3')


def _swing(item_id, stats):
    return weapon_swing(_structure().get_item_by_id(item_id), stats)


class _DofusThree(SimpleTestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')


class TheGainComesFromBestTurnTests(_DofusThree):

    STATS = _stats(str=900, cha=900, int=900, agi=900, pow=250, ch=30, cridam=40, ap=12)

    def test_without_spell_buffs_the_playable_plan_is_best_turn_itself(self):
        spells = castable_spells('Xelor', 200, 'dofus3')
        self.assertFalse(any(spell.buffs for spell in spells))
        reader = TurnReader(self.STATS, spells, 12, 'dofus3', 200)
        for item_id in (CHAOTIC_SCYTHE, MINOTOT_SCEPTRE, DREGGON_DAGGERS):
            with self.subTest(item_id=item_id):
                weapon = _swing(item_id, self.STATS)
                self.assertAlmostEqual(reader.gain(weapon), reader.lower_gain(weapon), places=6)

    def test_with_spell_buffs_the_playable_plan_never_beats_best_turn(self):
        spells = castable_spells('Iop', 200, 'dofus3')
        self.assertTrue(any(spell.buffs for spell in spells))
        reader = TurnReader(self.STATS, spells, 12, 'dofus3', 200)
        lower = []
        for item_id in (CHAOTIC_SCYTHE, MINOTOT_SCEPTRE, DREGGON_DAGGERS):
            with self.subTest(item_id=item_id):
                weapon = _swing(item_id, self.STATS)
                lower.append(reader.lower_gain(weapon))
                self.assertLessEqual(lower[-1], reader.gain(weapon) + 1e-6)
        self.assertGreater(max(lower), 0)

    def test_the_gain_is_the_turn_with_the_weapon_less_the_turn_without(self):
        spells = castable_spells('Iop', 200, 'dofus3')
        reader = TurnReader(self.STATS, spells, 12, 'dofus3', 200)
        weapon = _swing(CHAOTIC_SCYTHE, self.STATS)
        self.assertAlmostEqual(reader.full(weapon) - reader.full(), reader.gain(weapon), places=6)

    def test_the_swings_stop_at_the_uses_per_turn_and_the_ap(self):
        weapon = _swing(CHAOTIC_SCYTHE, self.STATS)
        self.assertEqual(1, weapon.limit)
        self.assertEqual(1, TurnReader(self.STATS, [], 12, 'dofus3', 200).swing_counts(weapon))
        self.assertEqual(0, TurnReader(self.STATS, [], weapon.cost - 1, 'dofus3', 200)
                         .swing_counts(weapon))

    def test_a_weapon_without_uses_per_turn_is_left_out(self):
        self.assertIsNone(_swing(BASIC_BROOM, self.STATS).limit)
        char = SimpleNamespace(game_version='dofus3', char_class='Iop', level=200)
        with mock.patch('chardata.weapon_terms.terms_on_stats', return_value={}) as terms, \
                mock.patch('chardata.solution.get_solution_from_minimal',
                           return_value=_Solution(self.STATS)):
            weapon_hit_terms(char, object(), _input(_weights()))
        self.assertNotIn(BASIC_BROOM, terms.call_args[0][3])
        self.assertIn(CHAOTIC_SCYTHE, terms.call_args[0][3])

    def test_the_candidates_follow_the_level_and_the_exclusions(self):
        structure = _structure()
        low = {item.id for item in candidate_weapons(structure, 151, set())}
        self.assertIn(MINOTOT_SCEPTRE, low)
        self.assertNotIn(CHAOTIC_SCYTHE, low)
        self.assertNotIn(MINOTOT_SCEPTRE, {item.id for item in candidate_weapons(
            structure, 200, {MINOTOT_SCEPTRE})})


class _Solution(object):

    def __init__(self, stats):
        self.items = {'Weapon': []}
        self._stats = stats

    def get_stats_total(self):
        return dict(self._stats)


class _Weapon(object):

    def __init__(self, item_id, lower, exact):
        self.weapon = SimpleNamespace(id=item_id)
        self.lower = lower
        self.exact = exact


class _Reader(object):
    """A turn of 1000 plus 2 per point of each characteristic."""

    def __init__(self):
        self.searched = []

    def full(self, weapon=None, deltas=None):
        return 1000.0 + 2 * sum((deltas or {}).values()) + (weapon.exact if weapon else 0)

    def lower_gain(self, weapon):
        return weapon.lower

    def gain(self, weapon):
        self.searched.append(weapon.weapon.id)
        return weapon.exact


def _weights(**values):
    weights = {'str': 120, 'int': 0, 'cha': 0, 'agi': 30, 'hp': 25}
    weights.update(values)
    return weights


def _input(weights, **fields):
    values = dict(objective_values=weights, empty_slot_types=[], locked_equips={},
                  forbidden_equips=set())
    values.update(fields)
    return SimpleNamespace(**values)


class TheTermIsTheGainInPlayedPointsTests(SimpleTestCase):

    def test_a_term_is_the_gain_over_the_turn_per_point_at_the_played_weight(self):
        weapons = {1: _Weapon(1, 300.0, 300.0), 2: _Weapon(2, 100.0, 100.0)}
        terms = terms_on_stats(_Reader(), _weights(), None, weapons, searched=2)
        self.assertEqual({1: 300.0 / 2 * 120, 2: 100.0 / 2 * 120}, terms)

    def test_the_shortlist_and_the_worn_weapon_get_best_turn_s_gain(self):
        reader = _Reader()
        weapons = {1: _Weapon(1, 300.0, 450.0), 2: _Weapon(2, 200.0, 260.0),
                   3: _Weapon(3, 100.0, 180.0), 4: _Weapon(4, 50.0, 90.0)}
        terms = terms_on_stats(reader, _weights(), weapons[4], weapons, searched=1)
        self.assertEqual({1, 4}, set(reader.searched))
        self.assertEqual({1: 450.0 * 60, 2: 200.0 * 60, 3: 100.0 * 60, 4: 90.0 * 60}, terms)

    def test_the_shortlist_counts_the_stat_lines(self):
        reader = _Reader()
        weapons = {1: _Weapon(1, 300.0, 300.0), 2: _Weapon(2, 250.0, 250.0)}
        terms_on_stats(reader, _weights(), None, weapons, {2: 10000}, searched=1)
        self.assertEqual([2], reader.searched)

    def test_no_played_characteristic_no_term(self):
        weapons = {1: _Weapon(1, 300.0, 300.0)}
        self.assertEqual({}, terms_on_stats(_Reader(), {'hp': 25, 'wis': 40}, None, weapons))

    def test_a_weapon_that_adds_nothing_gets_no_term(self):
        weapons = {1: _Weapon(1, 0.0, 0.0)}
        self.assertEqual({}, terms_on_stats(_Reader(), _weights(), None, weapons))


class OnlyDofus3PaysWeaponHitsTests(SimpleTestCase):

    def test_other_versions_get_no_term(self):
        for version in ('beta', 'dofus2', 'touch', 'retro'):
            with self.subTest(version=version):
                char = SimpleNamespace(game_version=version, char_class='Iop', level=200)
                self.assertEqual({}, weapon_hit_terms(char, object(), _input(_weights())))

    def test_no_set_a_locked_or_an_empty_weapon_slot_gets_no_term(self):
        char = SimpleNamespace(game_version='dofus3', char_class='Iop', level=200)
        self.assertEqual({}, weapon_hit_terms(char, None, _input(_weights())))
        self.assertEqual({}, weapon_hit_terms(
            char, object(), _input(_weights(), locked_equips={'weapon': CHAOTIC_SCYTHE})))
        self.assertEqual({}, weapon_hit_terms(
            char, object(), _input(_weights(), empty_slot_types=['weapon'])))


class _Recorder(object):

    def __init__(self):
        self.terms = {}

    def init_objective_function(self):
        self.terms = {}

    def add_to_of(self, category, item_id, weight):
        self.terms[(category, item_id)] = self.terms.get((category, item_id), 0) + weight

    def finish_objective_function(self):
        pass


class ItemTermsEnterTheObjectiveTests(_DofusThree):

    def _objective(self, item_terms):
        from fashionistapulp.model import Model
        model = Model.__new__(Model)
        model.structure = _structure()
        model.problem = _Recorder()
        model.write_objective_function(_weights(), 200, item_terms)
        return model.problem.terms

    def test_an_item_term_adds_to_the_item_s_presence(self):
        without = self._objective(None)
        with_terms = self._objective({CHAOTIC_SCYTHE: 7.5})
        self.assertEqual(without.get(('p', CHAOTIC_SCYTHE), 0) + 7.5,
                         with_terms[('p', CHAOTIC_SCYTHE)])
        del with_terms[('p', CHAOTIC_SCYTHE)]
        without.pop(('p', CHAOTIC_SCYTHE), None)
        self.assertEqual(without, with_terms)

    def test_a_rewritten_objective_keeps_the_item_terms(self):
        from fashionistapulp.model import Model
        model = Model.__new__(Model)
        model.structure = _structure()
        model.problem = _Recorder()
        model.input = {'objective_values': _weights(vit=25), 'char_level': 200}
        model.item_terms = {CHAOTIC_SCYTHE: 7.5}
        model.problem.run = mock.Mock()
        model.run(0, change_of=True)
        self.assertEqual(self._objective({CHAOTIC_SCYTHE: 7.5})[('p', CHAOTIC_SCYTHE)],
                         model.problem.terms[('p', CHAOTIC_SCYTHE)])


class ModelInputKeysTests(_DofusThree):

    def _input(self, **kwargs):
        from fashionistapulp.model import ModelInput
        return ModelInput(200, {}, {'AP': 11}, {}, set(), _weights(), {}, 'Iop', 0, [], {},
                          **kwargs)

    def test_no_item_term_keeps_the_keys_of_before(self):
        self.assertEqual(self._input().cache_key(), self._input(item_terms={}).cache_key())
        self.assertEqual(hash(self._input()), hash(self._input(item_terms={})))

    def test_item_terms_change_the_keys(self):
        plain, weighed = self._input(), self._input(item_terms={CHAOTIC_SCYTHE: 7.5})
        self.assertNotEqual(plain.cache_key(), weighed.cache_key())
        self.assertNotEqual(hash(plain), hash(weighed))
        self.assertNotEqual(weighed.cache_key(),
                            self._input(item_terms={CHAOTIC_SCYTHE: 8.5}).cache_key())


class TheSecondSolveUsesTheTermsTests(SimpleTestCase):

    def _run(self, terms, second_result='second'):
        from chardata.fashion_action import solve_with_weapon_hits
        calls = []

        def solve_once(model_input, deadline=None, longest=None):
            calls.append((copy.copy(model_input), deadline, longest))
            if len(calls) == 1:
                return 'Optimal', {}, 'first'
            return 'Optimal', {}, second_result
        model_input = SimpleNamespace(item_terms={})
        with mock.patch('chardata.fashion_action.weapon_hit_terms', return_value=terms):
            solved = solve_with_weapon_hits(object(), solve_once, model_input, 5, 6)
        return solved, calls, model_input

    def test_without_terms_one_solve(self):
        solved, calls, _model_input = self._run({})
        self.assertEqual('first', solved[2])
        self.assertEqual(1, len(calls))

    def test_with_terms_the_second_solve_is_kept(self):
        solved, calls, model_input = self._run({CHAOTIC_SCYTHE: 7.5})
        self.assertEqual('second', solved[2])
        self.assertEqual({CHAOTIC_SCYTHE: 7.5}, calls[1][0].item_terms)
        self.assertEqual((5, 6), calls[1][1:])
        self.assertEqual({}, model_input.item_terms)

    def test_a_failed_second_solve_keeps_the_first_set(self):
        solved, _calls, _model_input = self._run({CHAOTIC_SCYTHE: 7.5}, second_result=None)
        self.assertEqual('first', solved[2])


class AStoppedSearchCarriesItsItemTermsTests(SimpleTestCase):

    def test_the_search_keeps_the_terms_its_input_had(self):
        from chardata.fashion_action import _new_search
        state = {'objective': 10.0, 'bound': 12.0, 'values': {'x_1': 1}}
        weighed = SimpleNamespace(minimum_stats={}, objective_values={},
                                  item_terms={CHAOTIC_SCYTHE: 7.5})
        plain = SimpleNamespace(minimum_stats={}, objective_values={}, item_terms={})
        self.assertEqual({CHAOTIC_SCYTHE: 7.5}, _new_search(state, weighed, 90)['item_terms'])
        self.assertIsNone(_new_search(state, plain, 90)['item_terms'])
