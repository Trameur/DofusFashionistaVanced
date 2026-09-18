# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece whose recorded rolls differ from the encyclopedia wears a mark.

Thibaud, 2026-09-18: "ca serait bien de mettre un petit marqueur de FM sur les
items FM/exo comme sur dofus book". Two marks, from the rolls the player
recorded (manual overrides or an inventory): SM (FM in French) when a line
differs from the encyclopedia value, Exo when the piece carries a line it
does not have, or an AP, MP or Range point above its own.
"""
from django.test import SimpleTestCase

from chardata.solution_result import evolve_result_item
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': set()}


class AForgedPieceWearsItsMarkTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.structure = get_structure('dofus3')
        self.vitality = self.structure.get_stat_by_key('vit').id
        self.mp = self.structure.get_stat_by_key('mp').id
        self.hat = next(
            item for item in self.structure.types[200]['Hat']
            if not item.removed and self.vitality in dict(item.stats)
            and self.mp not in dict(item.stats))

    def _worn(self, overrides=None, options=_OPTIONS):
        result = ModelResult({'options': dict(options),
                              'base_stats_by_attr': dict(_BASE),
                              'char_level': 200})
        result.add_item_at_slot(self.hat, 'hat', overrides)
        item = result.item_list[0]
        evolve_result_item(item, result)
        return item

    def test_a_piece_as_the_encyclopedia_gives_it_has_no_mark(self):
        item = self._worn()
        self.assertFalse(item.has_forge)
        self.assertFalse(item.has_exo)

    def test_a_line_off_the_encyclopedia_carries_the_sm_mark(self):
        vitality = dict(self.hat.stats)[self.vitality]
        item = self._worn({self.hat.id: {self.vitality: vitality - 7}})
        self.assertTrue(item.has_forge)
        self.assertFalse(item.has_exo)

    def test_a_roll_equal_to_the_encyclopedia_carries_no_mark(self):
        vitality = dict(self.hat.stats)[self.vitality]
        item = self._worn({self.hat.id: {self.vitality: vitality}})
        self.assertFalse(item.has_forge)

    def test_an_added_mp_carries_the_exo_mark(self):
        item = self._worn({self.hat.id: {self.mp: 1}})
        self.assertTrue(item.has_exo)
        self.assertFalse(item.has_forge)

    def test_another_pieces_rolls_leave_this_one_unmarked(self):
        item = self._worn({self.hat.id + 1: {self.mp: 1}})
        self.assertFalse(item.has_exo)
        self.assertFalse(item.has_forge)
