# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Secondary stats grow at the rate the Dofus 3 client states."""

import json
import os
from types import SimpleNamespace

from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY
from fashionistapulp.fashionista_config import get_fashionista_path
from fashionistapulp.model import Model
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta')

# {secondary stat: ({characteristic: gain per point}, client text id)}
RATES = {
    'Prospecting': ({'Chance': 0.1}, '1113697'),
    'Dodge': ({'Agility': 0.1}, '1113698'),
    'Lock': ({'Agility': 0.1}, '1113698'),
    'AP Loss Resist': ({'Wisdom': 0.1}, '1113699'),
    'MP Loss Resist': ({'Wisdom': 0.1}, '1113699'),
    'AP Reduction': ({'Wisdom': 0.1}, '1113699'),
    'MP Reduction': ({'Wisdom': 0.1}, '1113699'),
    'Pods': ({'Strength': 5}, '1113707'),
    'Initiative': ({'Strength': 1, 'Intelligence': 1, 'Chance': 1,
                    'Agility': 1}, '1147405'),
    'HP': ({'Vitality': 1}, '1119659'),
}

HP_PER_LEVEL = 5

STATED = {
    '1113697': '10 Chance points increase your Prospecting by 1 point',
    '1113698': '10 Agility points increase your Dodge and Lock by 1 point',
    '1113699': ('10 Wisdom points increase your Parry and Reduction by 1 '
                'point'),
    '1113707': '1 Strength point increases your Pods by 5 points',
    '1147405': ('Each Strength, Intelligence, Chance or Agility point gives 1 '
                'Initiative point'),
    '1119659': 'One characteristic point equals one Health Point',
    '756779': 'They get 5 health points',
}

CHARACTERISTICS = ('Strength', 'Intelligence', 'Chance', 'Agility', 'Wisdom',
                   'Vitality')

TRAINED = 100


class _Problem:
    def restriction_lt_eq(self, rhs, matrix):
        return list(matrix)


class _Restriction:
    rhs = None

    def changeRHS(self, rhs):
        self.rhs = rhs


class TheSolverTests(SimpleTestCase):

    def _derived(self, version):
        structure = get_structure(version)
        model = SimpleNamespace(
            stats_list=structure.get_stats_list(), problem=_Problem(),
            structure=structure,
            restrictions=SimpleNamespace(minimum_stat_constraints={}))
        Model.create_minimum_stat_constraints(model)
        name_by_id = {stat.id: stat.name for stat in model.stats_list}
        derived = {}
        for name, matrix in model.restrictions.minimum_stat_constraints.items():
            sources = {name_by_id[stat_id]: -coefficient
                       for coefficient, _kind, stat_id in matrix
                       if name_by_id[stat_id] != name}
            if sources:
                derived[name] = sources
        return derived

    def _hp_floor(self, version, level):
        structure = get_structure(version)
        restrictions = {stat.name: _Restriction()
                        for stat in structure.get_stats_list()}
        model = SimpleNamespace(
            stats_list=structure.get_stats_list(),
            restrictions=SimpleNamespace(minimum_stat_constraints=restrictions),
            modify_advanced_minimum_stat_constraints=lambda minimums: None)
        Model.modify_minimum_stat_constraints(model, {'HP': 0}, level)
        return restrictions['HP'].rhs

    def test_the_solver_derives_each_secondary_stat_at_the_client_rate(self):
        expected = {name: rate for name, (rate, _text) in RATES.items()}
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(expected, self._derived(version))

    def test_the_solver_counts_five_hit_points_per_level(self):
        for version in VERSIONS:
            for level in (2, 100, 200):
                with self.subTest(version=version, level=level):
                    self.assertEqual(HP_PER_LEVEL,
                                     self._hp_floor(version, level)
                                     - self._hp_floor(version, level - 1))


class TheStatSheetTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    @staticmethod
    def _totals(base, level=200):
        return ModelResult({
            'base_stats_by_attr': dict(base),
            'options': {'ap_exo': False, 'mp_exo': False, 'range_exo': False},
            'char_level': level,
        }).get_stats_total()

    def test_each_characteristic_moves_the_sheet_only_at_the_client_rates(self):
        name_by_key = {key: name for name, key in STAT_NAME_TO_KEY.items()}
        for version in VERSIONS:
            set_current_game_version(version)
            bare = self._totals({})
            for trained in CHARACTERISTICS:
                grown = self._totals({trained: TRAINED})
                with self.subTest(version=version, trained=trained):
                    self.assertEqual(set(bare), set(grown))
                for key in bare:
                    name = name_by_key.get(key)
                    if name == trained:
                        expected = TRAINED
                    else:
                        expected = TRAINED * RATES.get(name, ({},))[0].get(
                            trained, 0)
                    with self.subTest(version=version, trained=trained,
                                      stat=name or key):
                        self.assertAlmostEqual(expected,
                                               grown[key] - bare[key])

    def test_the_sheet_counts_five_hit_points_per_level(self):
        for version in VERSIONS:
            set_current_game_version(version)
            for level in (2, 100, 200):
                with self.subTest(version=version, level=level):
                    self.assertEqual(
                        HP_PER_LEVEL,
                        self._totals({}, level)['hp']
                        - self._totals({}, level - 1)['hp'])


class TheShippedClientTests(SimpleTestCase):

    def test_every_rate_names_a_stated_sentence(self):
        self.assertLessEqual({text for _rate, text in RATES.values()},
                             set(STATED))

    def test_the_client_still_states_these_rates(self):
        import fashionista_version as ours
        builds = {'dofus3': ours.FASHIONISTA_VERSION,
                  'beta': ours.FASHIONISTA_BETA_VERSION}
        read = 0
        for version, build in builds.items():
            path = os.path.join(get_fashionista_path(), 'itemscraper', 'raw',
                                build, 'en.json')
            if not os.path.exists(path):
                continue
            with open(path, encoding='utf-8') as fh:
                texts = json.load(fh)['entries']
            read += 1
            for text_id, fragment in STATED.items():
                with self.subTest(version=version, text=text_id):
                    self.assertIn(fragment, texts.get(text_id, ''))
        if not read:
            self.skipTest('no client text on this machine')
