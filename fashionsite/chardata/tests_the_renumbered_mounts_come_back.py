# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A mount the source renumbered comes back to the build that wears it, matched by name and type."""

import pickle

from django.test import SimpleTestCase, TestCase

from chardata.legacy_ids import renumbered_item_id, repaired_slots
from chardata.legacy_missing import name_of_missing
from chardata.models import Char


class TheMountIsFoundAgainTests(SimpleTestCase):

    def test_the_almond_dragoturkey_has_a_new_number(self):
        neuf = renumbered_item_id('dofus3', 1)
        self.assertIsNone(neuf, "l'Amande SAUVAGE n'a pas d'equivalent")
        self.assertEqual('Wild Almond Dragoturkey',
                         name_of_missing('dofus3', 1, 'en'))

    def test_a_tamed_mount_is_found(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        neuf = renumbered_item_id('dofus3', 10)
        self.assertIsNotNone(neuf)
        set_current_game_version('dofus3')
        item = get_structure('dofus3').get_item_by_id(neuf)
        self.assertEqual('Ginger Dragoturkey', item.name)
        self.assertGreaterEqual(item.ankama_id, 33000)

    def test_the_mount_offset_form_finds_the_same_beast(self):
        self.assertEqual(renumbered_item_id('dofus3', 10),
                         renumbered_item_id('dofus3', 1000010))

    def test_the_two_tables_never_overlap(self):
        import io
        import json
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        retrouves = json.load(io.open(
            os.path.join(here, 'legacy_renumbered_items.json'),
            encoding='utf-8'))['dofus3']
        restants = json.load(io.open(
            os.path.join(here, 'legacy_missing_items.json'),
            encoding='utf-8'))['dofus3']
        self.assertEqual(set(), set(retrouves) & set(restants))
        self.assertGreaterEqual(len(retrouves), 200)
        self.assertLessEqual(len(restants), 60)

    def test_another_version_is_never_touched(self):
        for version in ('retro', 'touch', 'dofus2', 'beta', ''):
            with self.subTest(version=version):
                self.assertIsNone(renumbered_item_id(version, 10))


class OnlyABuildThatNeedsItIsTouchedTests(TestCase):

    def _structure(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        return get_structure('dofus3')

    def test_the_pet_slot_gets_its_mount_back(self):
        structure = self._structure()
        repare = repaired_slots(structure, 'dofus3', {'pet': 10})
        self.assertIsNotNone(repare)
        item = structure.get_item_by_id(repare['pet'])
        self.assertEqual('Ginger Dragoturkey', item.name)

    def test_a_mount_is_never_put_in_a_slot_that_refuses_it(self):
        self.assertIsNone(repaired_slots(self._structure(), 'dofus3',
                                         {'weapon': 10}))

    def test_a_wild_mount_is_left_alone(self):
        self.assertIsNone(repaired_slots(self._structure(), 'dofus3',
                                         {'pet': 1}))

    def test_a_build_wearing_one_stops_being_refused(self):
        from chardata.char_blobs import read_char_blob
        from chardata.gallery_visibility import refusal_reason
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        mini = read_char_blob(char.minimal_solution, None, 'minimal_solution',
                              char)
        mini.item_per_slot['pet'] = 10
        char.minimal_solution = pickle.dumps(mini)
        char.link_shared = True
        char.save()
        self.assertIsNone(refusal_reason(char))

    def test_a_wild_one_is_still_refused_and_named(self):
        from chardata.char_blobs import read_char_blob
        from chardata.gallery_visibility import refusal_reason, sentence_for
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        mini = read_char_blob(char.minimal_solution, None, 'minimal_solution',
                              char)
        mini.item_per_slot['pet'] = 1
        char.minimal_solution = pickle.dumps(mini)
        char.link_shared = True
        char.save()
        self.assertEqual('missing_items', refusal_reason(char))
        self.assertIn('Wild Almond Dragoturkey', sentence_for(char))
