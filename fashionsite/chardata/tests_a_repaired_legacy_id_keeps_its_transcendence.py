# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A stored set whose item ids are repaired keeps each transcendence rune on the repaired piece."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata.legacy_ids import repair_minimal_solution
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version
from fashionistapulp.transcendence import load_runes


class ARepairedLegacyIdKeepsItsTranscendenceTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        self.rune = next(rune for rune in load_runes('dofus3') if rune['stat_key'] == 'vit')
        self.char = SimpleNamespace(game_version='dofus3')

    def stored(self, transcendences):
        minimal = ModelResultMinimal({'amulet': 1623, 'belt': 1624}, {}, None)
        minimal.transcendences = transcendences
        return minimal

    def test_the_saved_item_id_follows_the_repair(self):
        minimal = self.stored({'amulet': (1623, self.rune['id']), 'belt': (1624, self.rune['id'])})
        self.assertTrue(repair_minimal_solution(self.char, minimal))
        structure = get_structure('dofus3')
        self.assertNotEqual(1623, minimal.item_per_slot['amulet'])
        self.assertEqual('Amulet', structure.get_type_name_by_id(
            structure.get_item_by_id(minimal.item_per_slot['amulet']).type))
        self.assertEqual({'amulet': (minimal.item_per_slot['amulet'], self.rune['id']),
                          'belt': (minimal.item_per_slot['belt'], self.rune['id'])},
                         minimal.transcendences)

    def test_a_set_without_runes_stays_without(self):
        minimal = self.stored(None)
        self.assertTrue(repair_minimal_solution(self.char, minimal))
        self.assertIsNone(minimal.transcendences)

    def test_an_unreadable_entry_is_left_for_the_reload_to_refuse(self):
        minimal = self.stored({'amulet': 'junk'})
        repair_minimal_solution(self.char, minimal)
        self.assertEqual({'amulet': 'junk'}, minimal.transcendences)

    def test_a_rune_follows_its_piece_moved_to_a_slot_of_its_type(self):
        structure = get_structure('dofus3')
        ring = next(item for item in sorted(structure.get_available_items_list(), key=lambda one: one.id)
                    if structure.get_type_name_by_id(item.type) == 'Ring' and not item.removed)
        minimal = ModelResultMinimal({'belt': ring.id}, {}, None)
        minimal.transcendences = {'belt': (ring.id, self.rune['id'])}
        self.assertTrue(repair_minimal_solution(self.char, minimal))
        self.assertEqual({'ring1': (ring.id, self.rune['id'])}, minimal.transcendences)
        self.assertEqual(ring.id, minimal.item_per_slot['ring1'])
