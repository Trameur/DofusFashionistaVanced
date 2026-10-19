# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Secondary stats grow at the rate the Dofus 3 client states."""

import json
import os

from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY
from fashionistapulp.fashionista_config import get_fashionista_path
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import get_structure, set_current_game_version

from chardata.tests_the_row_table_support import derived_rates, hp_floors

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


class TheSolverTests(SimpleTestCase):

    def _derived(self, version):
        return derived_rates(get_structure(version))

    def _hp_floor(self, version, level):
        return hp_floors(get_structure(version), {'HP': 0}, level)['HP']

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
