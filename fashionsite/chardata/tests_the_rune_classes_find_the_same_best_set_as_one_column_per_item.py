# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Grouping copies into rune classes never loses the best set of a build with one column per copy."""

from unittest import mock

import pulp

from fashionistapulp import model as model_module
from fashionistapulp.transcendence_terms import class_key

from chardata.dracorune_fixtures import BetaModelTestCase, SmallModel, element_move, piece
from chardata.transcendence_fixtures import exo_input


def _one_class_per_item(by_stat, lines, upper):
    key = class_key(by_stat, lines, upper)
    if any(rank for _stat, rank in key):
        return key + (('~item', id(lines)),)
    return key


class TheRuneClassesFindTheSameBestSetAsOneColumnPerItemTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        shared = {self.source: 50, 'neutres': 10}
        tall = {self.source: 60, 'vit': 150}
        self.pieces = [piece('Hat', shared), piece('Cloak', shared), piece('Amulet', tall),
                       piece('Belt', tall), piece('Boots', {})]

    def best(self, model_input, per_item):
        model = SmallModel(self.pieces)
        if per_item:
            with mock.patch.object(model_module, 'class_key', side_effect=_one_class_per_item):
                model.setup(model_input)
        else:
            model.setup(model_input)
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        return pulp.value(model.problem.pulp_lp.objective), len(model.transcendence_classes)

    def test_both_give_the_same_objective(self):
        cases = (({self.target: 3, 'pow': 2, 'fireresper': 1, 'vit': 1}, 3, 2, {}),
                 ({self.target: 1, 'pow': 3, 'fireresper': 2, 'vit': 1}, 4, 3, {}),
                 ({'pow': 1, 'fireresper': 1, 'vit': 1, 'ap': 5}, 3, 3, {'ap_exo': True}),
                 ({self.target: 2, 'earthres': 1, 'pow': 1, 'ap': 4, 'mp': 4}, 5, 4,
                  {'ap_exo': True, 'mp_exo': True}))
        for weights, runes, dracorunes, exos in cases:
            with self.subTest(weights=weights, runes=runes, dracorunes=dracorunes, exos=exos):
                grouped, classes = self.best(exo_input(weights, runes, dracorunes, **exos), False)
                alone, items = self.best(exo_input(weights, runes, dracorunes, **exos), True)
                self.assertLess(classes, items)
                self.assertAlmostEqual(grouped, alone, places=6)
