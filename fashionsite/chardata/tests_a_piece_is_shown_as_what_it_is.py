# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece is shown under its own type, not under its slot's."""

import pickle

from django.test import TestCase

from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.solution import get_solution


class ThePieceKeepsItsOwnTypeTests(TestCase):

    def _build_avec_une_piece_deplacee(self, type_source, slot_cible):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        piece = next(i for i in structure.types[200][type_source]
                     if not i.removed and i.ankama_id)
        autre = next(i for i in structure.types[200]['Hat']
                     if not i.removed and i.ankama_id)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(autre, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        mini = read_char_blob(char.minimal_solution, None, 'minimal_solution',
                              char)
        mini.item_per_slot[slot_cible] = piece.id
        char.minimal_solution = pickle.dumps(mini)
        char.save()
        return char, piece

    def test_a_cloak_in_a_ring_slot_is_still_announced_as_a_cloak(self):
        char, piece = self._build_avec_une_piece_deplacee('Cloak', 'ring1')
        solution = get_solution(char)
        annonces = {type_name: [i.name for i in items if i.item_added]
                    for type_name, items in (solution.items or {}).items()}
        self.assertIn(piece.name, annonces.get('Cloak', []))
        self.assertNotIn(piece.name, annonces.get('Ring', []))

    def test_a_shield_in_a_weapon_slot_too(self):
        char, piece = self._build_avec_une_piece_deplacee('Shield', 'weapon')
        solution = get_solution(char)
        annonces = {type_name: [i.name for i in items if i.item_added]
                    for type_name, items in (solution.items or {}).items()}
        self.assertIn(piece.name, annonces.get('Shield', []))
        self.assertNotIn(piece.name, annonces.get('Weapon', []))

    def test_nothing_moves_for_a_build_the_solver_made(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        solution = get_solution(char)
        for type_name, items in (solution.items or {}).items():
            for item in items:
                if item.item_added:
                    self.assertEqual(type_name, item.type,
                                     'une piece a change de rayon')

    def test_the_piece_is_moved_to_a_free_slot_of_its_own_type(self):
        char, piece = self._build_avec_une_piece_deplacee('Cloak', 'ring1')
        mini = read_char_blob(char.minimal_solution, None, 'minimal_solution',
                              char)
        from chardata.legacy_ids import repair_minimal_solution
        self.assertTrue(repair_minimal_solution(char, mini))
        self.assertEqual(piece.id, mini.item_per_slot.get('cloak'))
        self.assertIsNone(mini.item_per_slot.get('ring1'))

    def test_it_never_takes_the_place_of_another_piece(self):
        from chardata.legacy_ids import repair_minimal_solution
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        capes = [i for i in structure.types[200]['Cloak']
                 if not i.removed and i.ankama_id][:2]
        char, _piece = self._build_avec_une_piece_deplacee('Cloak', 'ring1')
        mini = read_char_blob(char.minimal_solution, None, 'minimal_solution',
                              char)
        mini.item_per_slot['cloak'] = capes[0].id
        mini.item_per_slot['ring1'] = capes[1].id
        char.minimal_solution = pickle.dumps(mini)
        char.save()
        mini = read_char_blob(char.minimal_solution, None, 'minimal_solution',
                              char)
        repair_minimal_solution(char, mini)
        self.assertEqual(capes[0].id, mini.item_per_slot['cloak'])
        self.assertEqual(capes[1].id, mini.item_per_slot['ring1'])
        # Both are still announced as cloaks
        solution = get_solution(char)
        capes_annoncees = [i.name for i in (solution.items or {}).get('Cloak', [])
                           if i.item_added]
        self.assertEqual(2, len(capes_annoncees), capes_annoncees)
