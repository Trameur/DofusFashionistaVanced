# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Solving with the pruned dracorune variants reaches the best value all of them reach."""

import random
from unittest import mock

from fashionistapulp import dracorune_terms, dracorunes

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input, piece,
                                         stat_id, structure)

SEEDS = range(12)
TYPES = ('Hat', 'Cloak', 'Amulet', 'Belt')


def _keys():
    elements = [key for pair in dracorunes.ELEMENT_PAIRS for key in pair] + ['pow', 'dam']
    resistances = [element + suffix for element in dracorunes.RESISTANCE_ELEMENTS
                   for suffix in ('res', 'resper')]
    return [key for key in elements + resistances if structure().get_stat_by_key(key)]


def _value(rng, key):
    return rng.randint(3, 15) if key.endswith('resper') else rng.randint(10, 60)


def random_case(seed):
    rng = random.Random(seed)
    keys = _keys()
    characteristics = [key for key, _damage in dracorunes.ELEMENT_PAIRS]
    pieces = [piece(type_name, {key: _value(rng, key) for key in rng.sample(keys, 3)})
              for type_name in TYPES]
    low, high = rng.sample(pieces, 2)
    low.min_stats_to_equip = [(stat_id(rng.choice(characteristics)), rng.randint(0, 50))]
    high.max_stats_to_equip = [(stat_id(rng.choice(characteristics)), rng.randint(0, 40))]
    weights = {key: rng.randint(-2, 5) for key in rng.sample(keys, 5)}
    minimum = structure().get_stat_by_key(rng.choice(characteristics)).name
    return pieces, weights, {minimum: rng.randint(0, 40)}


def _every_variant(candidates, context, *args, **kwargs):
    return dict(candidates), False


class PruningNeverLosesTheBestSetTests(BetaModelTestCase):

    def best(self, model, model_input):
        model.setup(model_input)
        kept = len(model.dracorune_columns)
        model.run()
        status = model.get_solved_status()
        return status, model.problem.objective_value if status == 'Optimal' else None, kept

    def test_random_small_builds_reach_the_same_best_value(self):
        pruned_away = 0
        for seed in SEEDS:
            pieces, weights, minimums = random_case(seed)
            model = SmallModel(pieces)
            for allowed in (1, 2):
                with self.subTest(seed=seed, allowed=allowed):
                    model_input = build_input(weights, allowed, minimums)
                    status, value, kept = self.best(model, model_input)
                    with mock.patch.object(dracorune_terms, 'prune', _every_variant):
                        every_status, every_value, every = self.best(model, model_input)
                    self.assertEqual(every_status, status)
                    if value is not None:
                        self.assertAlmostEqual(every_value, value, places=6)
                    pruned_away += every - kept
        self.assertGreater(pruned_away, 0)
