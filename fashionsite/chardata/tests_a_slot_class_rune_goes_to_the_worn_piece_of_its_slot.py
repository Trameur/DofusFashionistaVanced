# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A rune of a one-slot class goes to the worn piece of its slot, never to the first member the class lists."""

from fashionistapulp.model import Model
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.transcendence_terms import best_fitting, rune_fits

from chardata.dracorune_fixtures import (VERSION, BetaModelTestCase, SmallModel, piece, real_input)
from chardata.transcendence_fixtures import trans_input, with_transcendence

SLOT_OF_TYPE = {'Hat': 'hat', 'Cloak': 'cloak', 'Amulet': 'amulet', 'Belt': 'belt', 'Boots': 'boots'}


class _FullBetaSetup(BetaModelTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_current_game_version(VERSION)
        cls.addClassCleanup(set_current_game_version, 'dofus3')
        cls.model = Model()
        cls.model.setup(with_transcendence(real_input(), 4))
        cls.runes = {rune['id']: rune for group in cls.model.transcendence_runes.values()
                     for rune in group}

    def slot_class(self, type_name):
        """(class number, member ids) of the one-slot class of that type."""
        for number, members in sorted(self.model.transcendence_classes.items()):
            if self.model._type_of(members[0]) == type_name and self.model._single_slot_type(members[0]):
                return number, members
        self.fail('no slot class for %s' % type_name)

    def rune_ids(self, number):
        return sorted(rune_id for _name, (found, rune_id)
                      in self.model.transcendence_columns.items() if found == number)

    def line(self, item_id, rune):
        return self.model.transcendence_candidates[item_id].get(rune['stat_key'])

    def fitting_pair(self, number, members, skip_first=True, fits=True):
        """(member, rune id) of the class where the rune fits the member's own line or does not."""
        for item_id in members[1:] if skip_first else members:
            for rune_id in self.rune_ids(number):
                rune = self.runes[rune_id]
                if rune_fits(rune, self.line(item_id, rune)) == fits:
                    return item_id, rune_id
        self.fail('no pair')

    def hat_minimal(self, worn):
        return ModelResultMinimal({'hat': worn, 'cloak': None}, {}, None)


class ASlotClassRuneGoesToTheWornPieceOfItsSlotTests(_FullBetaSetup):

    def test_a_worn_hat_that_fits_takes_the_rune_and_an_unworn_hat_of_its_class_does_not(self):
        number, members = self.slot_class('Hat')
        worn, rune_id = self.fitting_pair(number, members)
        self.assertNotEqual(members[0], worn)
        self.assertGreater(len(members), 300)
        picks = self.model.transcendence_picks([(number, rune_id)], [worn])
        minimal = self.hat_minimal(worn)
        self.assertEqual([], minimal.place_transcendences(picks))
        self.assertEqual({'hat': (worn, rune_id)}, minimal.transcendences)
        self.assertNotIn(members[0], [item_id for item_id, _rune in minimal.transcendences.values()])

    def test_the_picks_of_a_slot_class_name_only_its_worn_piece(self):
        number, members = self.slot_class('Hat')
        worn, rune_id = self.fitting_pair(number, members)
        stat = self.runes[rune_id]['stat_key']
        self.assertEqual([([worn], rune_id, stat)],
                         self.model.transcendence_picks([(number, rune_id)], [worn]))
        other = next(item_id for item_id in members if item_id not in (worn, members[0]))
        self.assertEqual([([worn], rune_id, stat)],
                         self.model.transcendence_picks([(number, rune_id)], [worn, 'not a hat']))
        self.assertNotIn(other, self.model.transcendence_picks([(number, rune_id)], [worn])[0][0])

    def test_a_rune_the_worn_piece_does_not_fit_is_left_unplaced_and_logged(self):
        number, members = self.slot_class('Hat')
        worn, rune_id = self.fitting_pair(number, members, fits=False)
        picks = self.model.transcendence_picks([(number, rune_id)], [worn])
        self.assertEqual([([], rune_id, self.runes[rune_id]['stat_key'])], picks)
        minimal = self.hat_minimal(worn)
        with self.assertLogs('fashionistapulp.modelresult', 'ERROR'):
            left = minimal.place_transcendences(picks)
        self.assertEqual(picks, left)
        self.assertIsNone(minimal.transcendences)

    def test_a_worn_piece_takes_a_fitting_rune_its_own_kept_runes_left_out(self):
        number, members = self.slot_class('Hat')
        by_stat = self.model.transcendence_runes
        for item_id in members:
            lines = self.model.transcendence_candidates[item_id]
            for rune_id in self.rune_ids(number):
                rune = self.runes[rune_id]
                best = best_fitting(by_stat, lines, [rune['stat_key']])[rune['stat_key']]
                if rune_fits(rune, lines.get(rune['stat_key'])) and best['id'] != rune_id:
                    picks = self.model.transcendence_picks([(number, rune_id)], [item_id])
                    self.assertEqual([([item_id], rune_id, rune['stat_key'])], picks)
                    return
        self.fail('no member takes a rune below its best')

    def test_a_second_rune_on_one_slot_class_is_left_unplaced_and_logged(self):
        number, members = self.slot_class('Hat')
        worn, rune_id = self.fitting_pair(number, members)
        picks = [([worn], rune_id, 'vit'), ([worn], rune_id + 1, 'pow')]
        minimal = self.hat_minimal(worn)
        with self.assertLogs('fashionistapulp.modelresult', 'ERROR'):
            left = minimal.place_transcendences(picks)
        self.assertEqual([picks[1]], left)
        self.assertEqual({'hat': (worn, rune_id)}, minimal.transcendences)

    def test_a_slot_class_rune_on_a_stat_the_worn_pieces_dracorune_blocks_is_left_unplaced(self):
        minimal = self.hat_minimal(9)
        minimal.dracorunes = {'hat': (9, 'power')}
        with self.assertLogs('fashionistapulp.modelresult', 'ERROR'):
            left = minimal.place_transcendences([([9], 1, 'pow')])
        self.assertEqual(1, len(left))
        self.assertIsNone(minimal.transcendences)
        self.assertEqual([], minimal.place_transcendences([([9], 1, 'vit')]))
        self.assertEqual({'hat': (9, 1)}, minimal.transcendences)

    def test_every_ring_class_member_fits_every_column_of_its_class(self):
        checked = 0
        for number, members in sorted(self.model.transcendence_classes.items()):
            if self.model._single_slot_type(members[0]):
                continue
            for rune_id in self.rune_ids(number):
                rune = self.runes[rune_id]
                for item_id in members:
                    self.assertTrue(rune_fits(rune, self.line(item_id, rune)), (number, item_id, rune_id))
                    checked += 1
        self.assertGreater(checked, 1000)


class EachOneSlotTypePutsItsRuneOnItsOwnSlotTests(BetaModelTestCase):

    def test_each_one_slot_type_puts_its_rune_on_its_own_slot(self):
        pieces = [piece(type_name, {'vit': 10 * (number + 1)}) for number, type_name
                  in enumerate(SLOT_OF_TYPE)]
        model = SmallModel(pieces)
        result = self.solve(model, trans_input({'pow': 1, 'vit': 0.5}, 5))
        self.assertEqual(set(SLOT_OF_TYPE.values()), set(result.transcendences))
        for slot, (item_id, rune_id) in result.transcendences.items():
            self.assertEqual(result.item_per_slot[slot], item_id)
            self.assertEqual(slot, SLOT_OF_TYPE[model._type_of(item_id)])
