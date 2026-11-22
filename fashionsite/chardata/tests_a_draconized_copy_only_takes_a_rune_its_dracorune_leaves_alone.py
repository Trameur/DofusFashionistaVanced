# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A class of copies takes Dracorunes and runes exactly as a copy by copy placement allows."""

import itertools
import re
from unittest import mock

from fashionistapulp import dracorune_terms
from fashionistapulp.transcendence import load_runes
from fashionistapulp.transcendence_terms import dracorune_kind

from chardata.dracorune_fixtures import VERSION, BetaModelTestCase, SmallModel, element_move, piece
from chardata.transcendence_fixtures import can_place, trans_input

KINDS = (None, 'element', 'resistance', 'power')
TYPES = ('Hat', 'Cloak', 'Amulet', 'Belt')
HALL_ROW = re.compile(r'trans_t\d_\d+$')


def _every_variant(pool, _context):
    return {item_id: list(variants) for item_id, variants in pool.items()}, set()


class ADraconizedCopyOnlyTakesARuneItsDracoruneLeavesAloneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.stat_of = {rune['id']: rune['stat_key'] for rune in load_runes(VERSION)}
        self.weights = {self.target: 1, 'fireresper': 1, 'pow': 1, 'vit': 1}

    def model_of(self, weights, runes, dracorunes):
        pieces = [piece(type_name, {self.source: 50, 'neutres': 10}) for type_name in TYPES]
        with mock.patch.object(dracorune_terms, 'prune', side_effect=_every_variant):
            model = SmallModel(pieces)
            model.setup(trans_input(weights, runes, dracorunes))
        return model

    def worn(self, model, item_id):
        return model.problem.pulp_vars['x_%s' % str(item_id).replace('-', '_')]

    def test_the_rows_accept_exactly_the_placeable_assignments(self):
        model = self.model_of(self.weights, 8, 4)
        lp = model.problem.pulp_lp
        (members,) = model.transcendence_classes.values()
        self.assertEqual(['trans_t1_0', 'trans_t2_0', 'trans_t3_0', 'trans_t4_0'],
                         sorted(name for name in lp.constraints if HALL_ROW.match(name)))
        runes = {self.stat_of[rune_id]: model.problem.pulp_vars[name]
                 for name, (_number, rune_id) in model.transcendence_columns.items()}
        self.assertEqual({self.target, 'fireresper', 'pow', 'vit'}, set(runes))
        variants = {item_id: {} for item_id in members}
        for name, (item_id, key) in model.dracorune_columns.items():
            variants[item_id].setdefault(dracorune_kind(key), []).append(
                model.problem.pulp_vars[name])
        for item_id in members:
            self.assertEqual({'element', 'resistance', 'power'}, set(variants[item_id]))
        rows = [row for name, row in lp.constraints.items()
                if HALL_ROW.match(name) or name.startswith('draco_link_')]
        stats = sorted(runes)
        checked = 0
        for size in range(len(members) + 1):
            for copy_kinds in itertools.combinations_with_replacement(KINDS, size):
                for index, item_id in enumerate(members):
                    self.worn(model, item_id).varValue = int(index < size)
                    for kind, columns in variants[item_id].items():
                        for position, column in enumerate(columns):
                            column.varValue = int(index < size and position == 0
                                                  and kind == copy_kinds[index])
                for counts in itertools.product(range(3), repeat=len(stats)):
                    demand = dict(zip(stats, counts))
                    for stat, count in demand.items():
                        runes[stat].varValue = count
                    self.assertEqual(can_place(copy_kinds, demand),
                                     all(row.valid() for row in rows), (copy_kinds, demand))
                    checked += 1
        self.assertEqual(5670, checked)

    def test_the_solver_puts_no_blocked_rune_on_a_draconized_copy(self):
        weights = {self.target: 10, 'pow': 10, 'fireresper': 1}
        for runes, dracorunes in ((1, 1), (2, 2), (4, 4)):
            with self.subTest(runes=runes, dracorunes=dracorunes):
                model = self.model_of(weights, runes, dracorunes)
                model.run()
                self.assertEqual('Optimal', model.get_solved_status())
                (members,) = model.transcendence_classes.values()
                worn = sum(int(round(self.worn(model, item_id).varValue)) for item_id in members)
                kinds = [dracorune_kind(key) for item_id, key in model.chosen_dracorunes()
                         if item_id in members]
                demand = {}
                for _number, rune_id in model.chosen_transcendences():
                    stat = self.stat_of[rune_id]
                    demand[stat] = demand.get(stat, 0) + 1
                self.assertTrue(kinds)
                self.assertTrue(can_place(kinds + [None] * (worn - len(kinds)), demand),
                                (kinds, demand))

    def test_without_dracorunes_only_t1_is_written(self):
        model = self.model_of(self.weights, 8, None)
        self.assertEqual(['trans_t1_0'], sorted(name for name in model.problem.pulp_lp.constraints
                                                if HALL_ROW.match(name)))
