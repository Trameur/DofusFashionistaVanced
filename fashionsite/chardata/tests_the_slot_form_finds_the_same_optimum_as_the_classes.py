# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Giving each one-slot type one column per rune never changes the best set the classes find."""

from copy import deepcopy
from unittest import mock

import pulp

from fashionistapulp import dracorune_terms
from fashionistapulp.model import Model

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, bare, element_move, piece,
                                         runes, structure)
from chardata.transcendence_fixtures import exo_input, trans_input


class TheSlotFormFindsTheSameOptimumAsTheClassesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        low = {self.source: 50, 'neutres': 10, 'pow': 0}
        mid = {self.source: 60, 'vit': 150, 'pow': 15}
        high = {self.source: 40, 'pow': 25, 'fireresper': 4}
        self.pieces = [piece('Hat', low), piece('Hat', mid, 1), piece('Cloak', high),
                       piece('Cloak', low, 1), piece('Amulet', mid), piece('Belt', high),
                       piece('Boots', {}), piece('Ring', low), piece('Ring', high, 1)]

    def best(self, model_input, slots):
        model = SmallModel(self.pieces)
        if slots:
            model.setup(model_input)
        else:
            with mock.patch.object(Model, '_single_slot_type', return_value=False):
                model.setup(model_input)
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        self.assertTrue(model.transcendence_columns)
        return pulp.value(model.problem.pulp_lp.objective)

    def test_both_forms_give_the_same_objective(self):
        cases = (({self.target: 3, 'pow': 2, 'fireresper': 1, 'vit': 1}, 3, 2, {}),
                 ({self.target: 1, 'pow': 3, 'fireresper': 2, 'vit': 1}, 4, 3, {}),
                 ({'pow': 2, 'vit': 1}, 7, 0, {}),
                 ({'pow': 1, 'fireresper': 1, 'vit': 1, 'ap': 5}, 3, 3, {'ap_exo': True}),
                 ({self.target: 2, 'earthres': 1, 'pow': 1, 'ap': 4, 'mp': 4}, 5, 4,
                  {'ap_exo': True, 'mp_exo': True}))
        for weights, runes, dracorunes, exos in cases:
            with self.subTest(weights=weights, runes=runes, dracorunes=dracorunes, exos=exos):
                in_slots = self.best(exo_input(weights, runes, dracorunes or None, **exos), True)
                in_classes = self.best(exo_input(weights, runes, dracorunes or None, **exos), False)
                self.assertAlmostEqual(in_classes, in_slots, places=6)


def set_rings(lines):
    """Copies of the first set rings a rune can go on, one per entry of lines, with these lines."""
    found = structure()
    rules = runes()
    rings = [item for item in sorted(found.get_available_items_list(), key=lambda one: one.id)
             if found.get_type_name_by_id(item.type) == 'Ring' and item.set is not None
             and dracorune_terms.is_eligible(item, found, rules)]
    return [bare(deepcopy(ring), line) for ring, line in zip(rings, lines)]


class TheSlotFormKeepsSetRingsInTheirClassesTests(BetaModelTestCase):

    def solve_with(self, rings, slots):
        model = SmallModel(rings)
        weights = {'vit': 1, 'pow': 5}
        model_input = trans_input(weights, 8, None, {'Power': 1})
        if slots:
            model.setup(model_input)
        else:
            with mock.patch.object(Model, '_single_slot_type', return_value=False):
                model.setup(model_input)
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        return model, pulp.value(model.problem.pulp_lp.objective)

    def test_two_set_rings_with_one_fitting_both_runes_take_one_rune_each(self):
        rings = set_rings([{'vit': 10}, {'pow': 25, 'vit': 400}])
        self.assertEqual(2, len(rings))
        model, in_slots = self.solve_with(rings, True)
        _model, in_classes = self.solve_with(rings, False)
        self.assertTrue(model.transcendence_columns)
        self.assertAlmostEqual(in_classes, in_slots, places=6)
        per_class = {}
        for number, _rune_id in model.chosen_transcendences():
            per_class[number] = per_class.get(number, 0) + 1
        self.assertEqual({1}, set(per_class.values()))
