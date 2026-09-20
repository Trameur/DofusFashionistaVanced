# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The pieces the id migration left in the old numbering come back."""

import pickle

from django.test import SimpleTestCase, TestCase

from chardata.legacy_ids import (ankama_id_of_legacy, repair_minimal_solution,
                                 repaired_slots)
from chardata.models import Char


class TheTableIsTheOneFromThatDayTests(SimpleTestCase):

    # (old number, item name in the old catalogue, its ankama id)
    TEMOINS = (
        (2396, "Archon's Bow", 14164),
        (2515, "Nidas's Ring", 15187),
        (3357, "Director Grunob's Hat", 26336),
        (1623, "Grute's Amulet", 10623),
        (1624, "Grute's Belt", 10624),
    )

    def test_the_seven_ids_the_builds_carry_are_in_it(self):
        for ancien, _nom, ankama in self.TEMOINS:
            with self.subTest(ancien=ancien):
                self.assertEqual(ankama, ankama_id_of_legacy('dofus3', ancien))

    def test_it_covers_the_whole_catalogue_of_that_day(self):
        from chardata.legacy_ids import _tables
        self.assertGreaterEqual(len(_tables()['dofus3']), 3782)

    def test_another_version_is_never_translated(self):
        for version in ('retro', 'touch', 'dofus2', 'beta', ''):
            with self.subTest(version=version):
                self.assertIsNone(ankama_id_of_legacy(version, 2396))


class OnlyWhatIsBrokenIsTouchedTests(TestCase):

    def _structure(self):
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        return get_structure('dofus3')

    def test_a_piece_that_fits_is_never_moved(self):
        structure = self._structure()
        chapeau = next(i for i in structure.types[200]['Hat']
                       if not i.removed and i.ankama_id)
        self.assertIsNone(repaired_slots(structure, 'dofus3',
                                         {'hat': chapeau.id}))

    def test_the_bow_comes_back_to_the_weapon_slot(self):
        structure = self._structure()
        repare = repaired_slots(structure, 'dofus3', {'weapon': 2396})
        self.assertIsNotNone(repare)
        item = structure.get_item_by_id(repare['weapon'])
        self.assertEqual('Weapon', structure.get_type_name_by_id(item.type))
        self.assertIn('Archon', item.name)

    def test_the_two_grute_pieces_come_back(self):
        structure = self._structure()
        repare = repaired_slots(structure, 'dofus3',
                                {'amulet': 1623, 'belt': 1624})
        self.assertIsNotNone(repare)
        for slot, attendu in (('amulet', 'Amulet'), ('belt', 'Belt')):
            item = structure.get_item_by_id(repare[slot])
            self.assertEqual(attendu,
                             structure.get_type_name_by_id(item.type))

    def test_a_translation_that_would_not_help_is_refused(self):
        structure = self._structure()
        # The old 1623 is an amulet: in the boots slot, translating it would change nothing
        self.assertIsNone(repaired_slots(structure, 'dofus3', {'boots': 1623}))

    def test_an_unknown_id_is_left_where_it_is(self):
        structure = self._structure()
        self.assertIsNone(repaired_slots(structure, 'dofus3',
                                         {'hat': 999999999}))


class TheBuildReadsBackWholeTests(TestCase):

    def _char(self, item_per_slot):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')

        class _Mini(object):
            def __init__(self, par_slot):
                self.item_per_slot = dict(par_slot)
                self.input = {'base_stats_by_attr': {'AP': 7},
                              'char_level': 200, 'options': {}}

        char = Char.objects.create(
            name='Essai', char_name='', char_class='Cra', char_build='',
            level=200, link_shared=True, minimum_stats=pickle.dumps({}),
            minimum_crits=pickle.dumps({}), stats_weight=pickle.dumps({}),
            options=pickle.dumps({}), inclusions=pickle.dumps({}),
            exclusions=pickle.dumps({}), game_version='dofus3')
        return char, _Mini(item_per_slot)

    def test_the_repair_lands_on_the_stored_object(self):
        char, mini = self._char({'weapon': 2396, 'amulet': 1623})
        self.assertTrue(repair_minimal_solution(char, mini))
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        for slot, attendu in (('weapon', 'Weapon'), ('amulet', 'Amulet')):
            item = structure.get_item_by_id(mini.item_per_slot[slot])
            self.assertEqual(attendu,
                             structure.get_type_name_by_id(item.type))

    def test_a_build_that_needs_nothing_is_reported_untouched(self):
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        chapeau = next(i for i in structure.types[200]['Hat']
                       if not i.removed and i.ankama_id)
        char, mini = self._char({'hat': chapeau.id})
        self.assertFalse(repair_minimal_solution(char, mini))
        self.assertEqual({'hat': chapeau.id}, mini.item_per_slot)

    def test_the_gallery_stops_refusing_a_build_the_repair_fixes(self):
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
        from chardata.char_blobs import read_char_blob
        mini = read_char_blob(char.minimal_solution, None, 'minimal_solution',
                              char)
        mini.item_per_slot['weapon'] = 2396
        char.minimal_solution = pickle.dumps(mini)
        char.link_shared = True
        char.save()
        self.assertIsNone(refusal_reason(char),
                          'la galerie refuse encore un build reparable')
