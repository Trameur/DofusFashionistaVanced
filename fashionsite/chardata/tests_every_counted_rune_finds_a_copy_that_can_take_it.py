# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every transcendence rune the solver counts lands on a worn copy that fits it and whose Dracorune leaves its stat alone."""

import itertools
from types import SimpleNamespace
from unittest import mock

from fashionistapulp import modelresult
from fashionistapulp.model import Model
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.transcendence_terms import (ELEMENT_BLOCKED, RESISTANCE_BLOCKED, dracorune_kind,
                                                 rows_hold, rune_allowed_on, rune_fits)

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, element_move, piece)
from chardata.transcendence_fixtures import can_place, trans_input

KINDS = (None, 'element', 'resistance', 'power')
GROUP_STATS = ('vit', sorted(ELEMENT_BLOCKED)[0], 'pow', sorted(RESISTANCE_BLOCKED)[0])
COPY_SLOTS = ('ring1', 'ring2', 'hat', 'cloak')
ITEM_ID = 7


def demands(copies):
    """Every {stat: count} using one stat per group with at most that many runes in all."""
    for counts in itertools.product(range(copies + 1), repeat=len(GROUP_STATS)):
        if sum(counts) <= copies:
            yield {stat: count for stat, count in zip(GROUP_STATS, counts) if count}


def minimal_of(slots, items, kinds=None):
    """A minimal result wearing items[i] on slots[i], each slot's Dracorune kind being kinds[i] when set."""
    minimal = ModelResultMinimal(dict(zip(slots, items)), {}, None)
    held = {slot: (item, kind) for slot, item, kind in zip(slots, items, kinds or ()) if kind}
    minimal.dracorunes = held or None
    return minimal


class EveryCountedRuneFindsACopyThatCanTakeItTests(BetaModelTestCase):

    def test_the_four_rows_hold_exactly_when_every_rune_finds_a_copy(self):
        checked = 0
        for copies in range(1, 5):
            slots = COPY_SLOTS[:copies]
            ids = list(range(100, 100 + copies))
            for kinds in itertools.product(KINDS, repeat=copies):
                kind_counts = {kind: kinds.count(kind) for kind in KINDS if kind}
                for demand in demands(copies):
                    picks = [(ids, 1000 + index, stat) for index, stat in enumerate(
                        stat for stat, count in sorted(demand.items()) for _ in range(count))]
                    minimal = minimal_of(slots, ids, kinds)
                    with mock.patch.object(modelresult.logger, 'error'):
                        left = minimal.place_transcendences(picks)
                    self.assertEqual(rows_hold(copies, kind_counts, demand), not left, (kinds, demand))
                    self.assertEqual(can_place(kinds, demand), not left, (kinds, demand))
                    checked += 1
        self.assertEqual(20420, checked)

    def test_each_placed_rune_sits_on_a_worn_copy_of_its_class_that_fits_it_and_whose_dracorune_leaves_the_stat_alone(self):
        minimal = minimal_of(('ring1', 'ring2', 'hat', 'cloak'), [5, 5, 9, 11],
                             ('element', None, 'power', None))
        picks = [([5, 8], 1, 'vit'), ([5, 8], 2, sorted(ELEMENT_BLOCKED)[0]),
                 ([9], 3, 'vit'), ([11, 12], 4, 'pow')]
        self.assertEqual([], minimal.place_transcendences(picks))
        by_rune = {rune_id: (ids, stat) for ids, rune_id, stat in picks}
        self.assertEqual(4, len(minimal.transcendences))
        for slot, (item_id, rune_id) in minimal.transcendences.items():
            ids, stat = by_rune[rune_id]
            self.assertEqual(minimal.item_per_slot[slot], item_id)
            self.assertIn(item_id, ids)
            held = minimal.dracorunes.get(slot)
            self.assertTrue(rune_allowed_on(dracorune_kind(held[1]) if held else None, stat))
        self.assertNotIn(8, [item_id for item_id, _rune in minimal.transcendences.values()])
        self.assertEqual((9, 3), minimal.transcendences['hat'])
        self.assertEqual((5, 2), minimal.transcendences['ring2'])

    def test_two_copies_of_one_ring_take_two_runes(self):
        minimal = minimal_of(('ring1', 'ring2'), [ITEM_ID, ITEM_ID])
        self.assertEqual([], minimal.place_transcendences([([ITEM_ID], 2, 'pow'), ([ITEM_ID], 1, 'vit')]))
        self.assertEqual({'ring1': (ITEM_ID, 1), 'ring2': (ITEM_ID, 2)}, minimal.transcendences)

    def test_a_third_rune_on_a_pair_of_copies_is_left_unplaced_and_logged(self):
        minimal = minimal_of(('ring1', 'ring2'), [ITEM_ID, ITEM_ID])
        picks = [([ITEM_ID], rune, 'vit') for rune in (1, 2, 3)]
        with self.assertLogs('fashionistapulp.modelresult', 'ERROR'):
            left = minimal.place_transcendences(picks)
        self.assertEqual([picks[2]], left)
        self.assertEqual(2, len(minimal.transcendences))

    def test_an_element_rune_skips_the_ring_copy_an_element_dracorune_holds(self):
        stat = sorted(ELEMENT_BLOCKED)[0]
        minimal = minimal_of(('ring1', 'ring2'), [ITEM_ID, ITEM_ID], ('element', None))
        self.assertEqual([], minimal.place_transcendences([([ITEM_ID], 5, stat)]))
        self.assertEqual({'ring2': (ITEM_ID, 5)}, minimal.transcendences)

    def test_a_pick_the_first_slot_suits_is_moved_along_an_augmenting_path(self):
        minimal = minimal_of(('ring1', 'ring2'), [ITEM_ID, 8])
        picks = [([ITEM_ID, 8], 1, 'vit'), ([ITEM_ID], 2, 'vit')]
        self.assertEqual([], minimal.place_transcendences(picks))
        self.assertEqual({'ring1': (ITEM_ID, 2), 'ring2': (8, 1)}, minimal.transcendences)

    def test_no_pick_leaves_no_runes(self):
        minimal = minimal_of(('hat',), [ITEM_ID])
        self.assertEqual([], minimal.place_transcendences([]))
        self.assertIsNone(minimal.transcendences)


class TheMinimalResultKeepsTheTranscendenceRunesTests(BetaModelTestCase):

    def stub(self, **extra):
        item = SimpleNamespace(slot='hat', id=ITEM_ID)
        return SimpleNamespace(item_list=[item], input={}, get_stats=lambda: {}, **extra)

    def test_from_model_result_keeps_the_placed_transcendence_runes(self):
        minimal = ModelResultMinimal.from_model_result(self.stub(transcendences={'hat': (ITEM_ID, 3)}))
        self.assertEqual({'hat': (ITEM_ID, 3)}, minimal.transcendences)

    def test_from_model_result_gives_none_when_the_result_has_no_transcendence_attribute(self):
        self.assertIsNone(ModelResultMinimal.from_model_result(self.stub()).transcendences)


class EveryRuneTheSolverCountsIsPlacedTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.weights = {self.target: 3, 'pow': 1, 'vit': 0.5}

    def pieces(self):
        self.first_hat = piece('Hat', {'vit': 10}, 0)
        self.worn_hat = piece('Hat', {'vit': 100}, 1)
        self.cloak = piece('Cloak', {'vit': 50})
        self.ring = piece('Ring', {self.source: 50, 'vit': 5})
        return [self.first_hat, self.worn_hat, self.cloak, self.ring]

    def solved(self):
        model = SmallModel(self.pieces())
        result = self.solve(model, trans_input(self.weights, 4, 1))
        return model, result

    def rune_stat(self, model, rune_id):
        return next(rune['stat_key'] for group in model.transcendence_runes.values()
                    for rune in group if rune['id'] == rune_id)

    def unplaced(self, model, result):
        worn = [item_id for item_id in result.item_per_slot.values() if item_id]
        chosen = model.useful_rune_choices(model.chosen_dracorunes(), model.chosen_transcendences())
        picks = model.transcendence_picks(chosen[1], worn)
        fresh = ModelResultMinimal(dict(result.item_per_slot), {}, None)
        fresh.dracorunes = result.dracorunes
        return picks, fresh.place_transcendences(picks), fresh

    def test_every_rune_the_solver_counts_is_placed(self):
        model, result = self.solved()
        self.assertEqual(self.worn_hat.id, result.item_per_slot['hat'])
        self.assertEqual(self.ring.id, result.item_per_slot['ring1'])
        self.assertEqual(self.ring.id, result.item_per_slot['ring2'])
        picks, left, _fresh = self.unplaced(model, result)
        self.assertTrue(picks)
        self.assertEqual([], left)
        self.assertEqual(len(picks), len(result.transcendences))
        for slot, (item_id, _rune) in result.transcendences.items():
            self.assertEqual(result.item_per_slot[slot], item_id)
            self.assertNotEqual(self.first_hat.id, item_id)
        hat_runes = [rune for slot, (_item, rune) in result.transcendences.items() if slot == 'hat']
        self.assertEqual(1, len(hat_runes))
        self.assertEqual(['element:%s>%s' % (self.source, self.target)],
                         [key for _item, key in result.dracorunes.values()])
        self.assertEqual(1, len(result.dracorunes))
        ring_stats = {slot: self.rune_stat(model, result.transcendences[slot][1])
                      for slot in ('ring1', 'ring2')}
        blocked_rings = [slot for slot, stat in ring_stats.items() if stat in ELEMENT_BLOCKED]
        self.assertEqual(1, len(blocked_rings))
        self.assertNotIn(blocked_rings[0], result.dracorunes)

    def test_the_placement_holds_in_both_forms(self):
        for slot_form in (True, False):
            with self.subTest(slot_form=slot_form):
                model = SmallModel(self.pieces())
                if slot_form:
                    result = self.solve(model, trans_input(self.weights, 4, 1))
                else:
                    with mock.patch.object(Model, '_single_slot_type', return_value=False):
                        result = self.solve(model, trans_input(self.weights, 4, 1))
                picks, left, _fresh = self.unplaced(model, result)
                self.assertTrue(picks)
                self.assertEqual([], left)
                self.assertEqual(len(picks), len(result.transcendences))
                for slot, (item_id, rune_id) in result.transcendences.items():
                    self.assertEqual(result.item_per_slot[slot], item_id)
                    named = [stat for ids, rune, stat in picks if rune == rune_id and item_id in ids]
                    self.assertTrue(named)
                    rune = next(rune for group in model.transcendence_runes.values()
                                for rune in group if rune['id'] == rune_id)
                    line = model.transcendence_candidates[item_id].get(named[0])
                    self.assertTrue(rune_fits(rune, line))
                ring_stats = {slot: self.rune_stat(model, result.transcendences[slot][1])
                              for slot in ('ring1', 'ring2')}
                blocked_rings = [slot for slot, stat in ring_stats.items() if stat in ELEMENT_BLOCKED]
                self.assertEqual(1, len(blocked_rings))
                self.assertNotIn(blocked_rings[0], result.dracorunes)
