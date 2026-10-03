# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 3 keeps one exo point per stat for the whole build, with none of the Retro per-piece rows."""

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.options import set_options
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import ModelResult, model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_WEIGHTS = {'vit': 1, 'str': 3, 'pow': 2, 'ap': 1000, 'mp': 800, 'range': 100}
_OPTIONS = {'ap_exo': True, 'mp_exo': True, 'range_exo': True, 'dofus': True,
            'trophies': True, 'dragoturkey': True, 'seemyool': True,
            'rhineetle': True, 'prysmaradite': True, 'dofuses': {},
            'dofusnotforchar': set()}
_EXO_KEYS = ('ap', 'mp', 'range')


def _never(*args, **kwargs):
    raise AssertionError('a Retro per-piece exo path ran on Dofus 3')


class OneExoPerStatTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.structure = get_structure('dofus3')

    def test_each_exo_variable_stays_between_zero_and_one(self):
        model = Model()
        for key in _EXO_KEYS:
            variable = model.problem.pulp_vars['exo_%d' % self.structure.get_stat_by_key(key).id]
            self.assertEqual((0, 1), (variable.lowBound, variable.upBound))
        self.assertIsNone(model.restrictions.exo_capacity)
        self.assertEqual({}, model.restrictions.exo_owned_floor)

    def test_an_option_set_to_yes_allows_one_point_and_a_count_none(self):
        model = Model()
        for option, bound in ((True, 1), (False, 0), ('gelano', 0), (3, 0)):
            with self.subTest(option=option):
                model.modify_exo_constraints({'ap_exo': option})
                self.assertEqual(-bound, model.restrictions.exo_constraints['ap'].constant)

    def test_a_solve_with_the_three_options_adds_one_point_each(self):
        with mock.patch.object(Model, '_create_exo_per_item_constraints', _never), \
                mock.patch.object(ModelResult, 'place_assumed_exos', _never):
            model = Model()
            model.setup(ModelInput(200, dict(_BASE), {}, {}, set(), dict(_WEIGHTS),
                                   dict(_OPTIONS), 'Iop', 995))
            model.run(1)
            values = model.problem.get_result()
            minimal = model.get_result_minimal()
            result = model_result_from_minimal(minimal)
            gear = result.get_stats_gear()
        self.assertIsNone(minimal.exo_assumed)
        self.assertIsNone(result.exo_points)
        worn = [item for item in result.item_list if item.item_added]
        self.assertFalse([item.name for item in worn if item.assumed_exo])
        for key in _EXO_KEYS:
            with self.subTest(stat=key):
                self.assertEqual(1, round(values['exo_%d' % self.structure.get_stat_by_key(key).id]))
                pieces = sum(item.stats.get(key, 0) for item in worn)
                sets = sum(item_set.get_bonus().get(key, 0) for item_set in result.sets)
                self.assertEqual(pieces + sets + 1, gear[key])

    def test_saving_a_count_on_dofus3_is_refused(self):
        char = SimpleNamespace(game_version='dofus3', options=None)
        for option in ('ap_exo', 'mp_exo', 'range_exo'):
            with self.subTest(option=option), self.assertRaises(AssertionError):
                set_options(char, {option: 2})
