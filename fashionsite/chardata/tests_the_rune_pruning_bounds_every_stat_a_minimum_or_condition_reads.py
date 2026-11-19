# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The rune pruning bounds every stat a minimum, a condition or a set cap of the build reads."""

from copy import deepcopy

from fashionistapulp.model import (EFFECTIVE_HP_MINIMUM, _effective_hp_terms,
                                   _minimum_dependencies)

from chardata.dracorune_fixtures import (VERSION, BetaModelTestCase, SmallModel, build_input,
                                         piece, stat_id, structure)


def ids(names):
    return {structure().get_stat_by_name(name).id for name in names}


class TheRunePruningBoundsTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.hat = piece('Hat', {'str': 10})
        self.cloak = piece('Cloak', {'int': 10})
        self.model = SmallModel([self.hat, self.cloak])

    def context(self, weights=None, minimums=None, forbidden=()):
        model_input = build_input(weights or {}, 1, minimums, forbidden=forbidden)
        self.model.setup(model_input)
        wearable = [item for item in self.model.items_list if self.model._could_be_worn(item)]
        return self.model.dracorune_context(model_input, wearable)

    def test_a_minimum_bounds_its_stat_and_every_stat_it_counts(self):
        dependencies = _minimum_dependencies(VERSION)
        for name in ('Initiative', 'Dodge', 'Lock', 'Pods', 'Prospecting', 'HP', 'Vitality'):
            with self.subTest(minimum=name):
                expected = ids([name] + dependencies.get(name, [[]])[0])
                self.assertEqual(expected, self.context(minimums={name: 10}).lower)

    def test_an_initiative_minimum_bounds_the_four_characteristics(self):
        lower = self.context(minimums={'Initiative': 1000}).lower
        self.assertLessEqual({stat_id(key) for key in ('str', 'int', 'cha', 'agi')}, lower)

    def test_an_advanced_minimum_bounds_each_of_its_stats(self):
        for entry in structure().get_adv_mins():
            with self.subTest(minimum=entry['name']):
                context = self.context(minimums={'adv_mins': {entry['name']: 10}})
                self.assertEqual(ids(entry['stats']), context.lower)

    def test_an_effective_hp_minimum_bounds_hp_vitality_and_the_percent_resists(self):
        context = self.context(minimums={EFFECTIVE_HP_MINIMUM: 4000})
        self.assertEqual(ids(name for _coefficient, name in _effective_hp_terms(4000)),
                         context.lower)

    def test_conditions_of_a_wearable_piece_bound_their_stats(self):
        self.hat.min_stats_to_equip = [(stat_id('agi'), 20)]
        self.hat.max_stats_to_equip = [(stat_id('cha'), 20)]
        self.cloak.or_conditions = [[(stat_id('int'), False, 5)], [(stat_id('str'), True, 5)]]
        context = self.context()
        self.assertEqual({stat_id('agi'), stat_id('int')}, context.lower)
        self.assertEqual({stat_id('cha'), stat_id('str')}, context.upper)

    def test_the_conditions_of_a_forbidden_piece_bound_nothing(self):
        self.hat.min_stats_to_equip = [(stat_id('agi'), 20)]
        self.assertEqual(frozenset(), self.context(forbidden=[self.hat.id]).lower)

    def test_a_set_cap_bounds_its_stat_from_above(self):
        item_set = deepcopy(structure().get_sets_list()[0])
        item_set.items = [self.hat.id]
        item_set.bonus = []
        item_set.max_caps = [(1, stat_id('mp'), 3)]
        self.hat.set = item_set.id
        self.model = SmallModel([self.hat, self.cloak], [item_set])
        self.assertEqual({stat_id('mp')}, self.context().upper)

    def test_the_capped_stats_are_those_of_the_stat_maximum(self):
        capped = self.context().capped
        self.assertEqual(ids(self.model.stat_maximum), capped)

    def test_weights_are_read_by_stat_id(self):
        context = self.context(weights={'str': 2, 'agi': -1, 'meleeness': 5, 'vit': 0})
        self.assertEqual({stat_id('str'): 2, stat_id('agi'): -1}, context.weights)

    def test_a_spell_modifier_or_a_crit_hinge_bounds_the_stat_it_reads(self):
        model_input = build_input({'str': 1}, 1)
        model_input.crit_hinges = ((10, 1),)
        model_input.modifier_values = {self.hat.id: {11: 5}}
        self.model.setup(model_input)
        context = self.model.dracorune_context(model_input, self.model.items_list)
        self.assertEqual({stat_id('ch'), stat_id('ap')}, context.lower & context.upper)
