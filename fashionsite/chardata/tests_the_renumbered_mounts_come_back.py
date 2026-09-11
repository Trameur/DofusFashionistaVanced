# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une monture que la source a renumerotee revient au build qui la porte.

La section 44 disait que 264 objets avaient quitte notre catalogue. C'etait
faux pour la plus grande part, et la verification l'a montre le lendemain:
notre fournisseur de donnees a RENUMEROTE les montures. La Dragodinde Amande
portait l'ankama 1 dans le catalogue du 4 novembre 2025; elle porte
aujourd'hui un numero au-dela de 33000, et notre catalogue l'a toujours.
Le fichier de montures livre en porte 308, dont 68 dragodindes.

Mesure du 11 septembre 2026: sur les 264, **222 se retrouvent** par leur nom
anglais exact et leur type, sans une seule ambiguite. Les **42** qui restent
sont les versions SAUVAGES, que la source ne liste plus.

Un appariement par nom est plus faible qu'un appariement par numero. Il ne
sert donc qu'a REPARER: si l'objet retrouve ne convient pas a l'emplacement,
rien n'est fait, exactement comme pour la traduction de la section 43.
"""

import pickle

from django.test import SimpleTestCase, TestCase

from chardata.legacy_ids import renumbered_item_id, repaired_slots
from chardata.legacy_missing import name_of_missing
from chardata.models import Char


class TheMountIsFoundAgainTests(SimpleTestCase):

    def test_the_almond_dragoturkey_has_a_new_number(self):
        """L'ankama 1 du catalogue de novembre 2025."""
        neuf = renumbered_item_id('dofus3', 1)
        self.assertIsNone(neuf, "l'Amande SAUVAGE n'a pas d'equivalent")
        self.assertEqual('Wild Almond Dragoturkey',
                         name_of_missing('dofus3', 1, 'en'))

    def test_a_tamed_mount_is_found(self):
        """La Dragodinde Rousse, ankama 10 en novembre 2025."""
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        neuf = renumbered_item_id('dofus3', 10)
        self.assertIsNotNone(neuf)
        set_current_game_version('dofus3')
        item = get_structure('dofus3').get_item_by_id(neuf)
        self.assertEqual('Ginger Dragoturkey', item.name)
        self.assertGreaterEqual(item.ankama_id, 33000)

    def test_the_mount_offset_form_finds_the_same_beast(self):
        """Selon le jour ou le build a ete enregistre, la meme bete est
        stockee en ankama nu ou decalee de l'espace des montures."""
        self.assertEqual(renumbered_item_id('dofus3', 10),
                         renumbered_item_id('dofus3', 1000010))

    def test_the_two_tables_never_overlap(self):
        """Un objet retrouve n'a rien a faire dans la table de ceux qu'on ne
        peut que nommer: il serait annonce manquant alors qu'il est rendu."""
        import io
        import json
        retrouves = json.load(io.open(
            'fashionsite/chardata/legacy_renumbered_items.json',
            encoding='utf-8'))['dofus3']
        restants = json.load(io.open(
            'fashionsite/chardata/legacy_missing_items.json',
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
        """Le meme nombre dans un emplacement d'arme n'y met rien: un
        appariement par nom ne sert qu'a reparer."""
        self.assertIsNone(repaired_slots(self._structure(), 'dofus3',
                                         {'weapon': 10}))

    def test_a_wild_mount_is_left_alone(self):
        """Les 42 sans equivalent restent introuvables, et c'est la section
        44 qui les nomme."""
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
        """Le cas contraire: ce qui n'est pas retrouve doit rester annonce."""
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
