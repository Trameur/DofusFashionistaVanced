# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Ankama reuses translated names: each piece still gets its own forbid entry."""

import json

from django.test import SimpleTestCase

from chardata.exclusions_view import _one_door_per_piece
from fashionistapulp.structure import get_structure, set_current_game_version

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# Extra entries from same-name pieces, per version and language
_PORTES_GAGNEES = {
    'dofus3': {'en': 0, 'fr': 5, 'es': 13, 'pt': 7, 'de': 10},
    'beta': {'en': 0, 'fr': 5, 'es': 13, 'pt': 7, 'de': 10},
    'dofus2': {'en': 0, 'fr': 5, 'es': 45, 'pt': 37, 'de': 42},
    'touch': {'en': 29, 'fr': 25, 'es': 31, 'pt': 31, 'de': 36},
    'retro': {'en': 63, 'fr': 61, 'es': 65, 'pt': 66, 'de': 66},
}


def _portes(version, langue):
    set_current_game_version(version)
    structure = get_structure(version)
    return structure, _one_door_per_piece(structure, langue, lambda i: i)


def _derriere(portes, etiquette):
    valeur = portes[etiquette]
    return valeur if isinstance(valeur, list) else [valeur]


class EveryPieceIsReachableTests(SimpleTestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_each_version_and_language_gained_the_doors_it_gained(self):
        for version, attendu in _PORTES_GAGNEES.items():
            for langue, gagnees in attendu.items():
                with self.subTest(version=version, langue=langue):
                    structure, portes = _portes(version, langue)
                    avant = structure.get_all_unique_items_names_with_ids(
                        langue)
                    self.assertEqual(gagnees, len(portes) - len(avant))

    def test_no_piece_is_left_without_a_door(self):
        """An entry holds one of its rows, or a branch of the same OR item."""
        for version in _PORTES_GAGNEES:
            for langue in LANGUES:
                with self.subTest(version=version, langue=langue):
                    structure, portes = _portes(version, langue)
                    familles = structure.get_available_or_items()
                    derriere = set()
                    for etiquette in portes:
                        derriere.update(_derriere(portes, etiquette))
                    manquants = []
                    for nom, ids in structure.\
                            get_all_unique_items_ids_by_name(langue).items():
                        for item_id in ids:
                            item = structure.get_item_by_id(item_id)
                            joignable = set(
                                structure.get_rows_of_the_same_item(item_id)
                                or (item_id,))
                            if item is not None:
                                joignable.update(
                                    membre.id for membre
                                    in familles.get(item.or_name, ()))
                            if not derriere & joignable:
                                manquants.append((nom, item_id))
                    self.assertEqual([], manquants[:5])

    def test_an_or_item_keeps_the_single_door_it_had(self):
        """Gelano is one ring in two rows."""
        for langue in LANGUES:
            with self.subTest(langue=langue):
                structure, portes = _portes('dofus3', langue)
                gelano = structure.get_item_by_name('Gelano (#1)')
                nom = structure.get_item_name_in_language(gelano, langue)
                self.assertIn(nom, portes)
                self.assertEqual([], [etiquette for etiquette in portes
                                      if etiquette.startswith('%s (' % nom)])

    def test_two_labels_are_never_the_same_string(self):
        for version in _PORTES_GAGNEES:
            for langue in LANGUES:
                with self.subTest(version=version, langue=langue):
                    structure, portes = _portes(version, langue)
                    self.assertEqual(len(portes), len(set(portes)))


class TheLabelSaysWhatSeparatesThemTests(SimpleTestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_the_level_tells_two_spanish_swords_apart(self):
        _structure, portes = _portes('dofus2', 'es')
        cocobur = sorted(nom for nom in portes if nom.startswith('Cocobur'))
        self.assertEqual(['Cocobur (Arma | Niv. 100)',
                          'Cocobur (Arma | Niv. 200)'], cocobur)
        self.assertNotIn('Cocobur', portes)

    def test_the_set_tells_the_four_retro_rings_apart(self):
        _structure, portes = _portes('retro', 'fr')
        bronze = sorted(nom for nom in portes
                        if nom.startswith('Anneau en bronze'))
        self.assertEqual(4, len(bronze))
        for nom in bronze:
            self.assertIn('Panoplie', nom)
        self.assertEqual(4, len({nom.split('|')[-1] for nom in bronze}))

    def test_ankamas_own_name_tells_two_trophies_apart(self):
        """Same type and level, no set: the English name separates them."""
        _structure, portes = _portes('dofus2', 'es')
        majeurs = sorted(nom for nom in portes
                         if nom.startswith('Acróbata mayor'))
        self.assertEqual(['Acróbata mayor (Dofus | Niv. 150 | Major Acrobat)',
                          'Acróbata mayor (Dofus | Niv. 150 | Major Stunter)'],
                         majeurs)

    def test_a_name_nobody_shares_stays_the_bare_name(self):
        _structure, portes = _portes('dofus2', 'es')
        self.assertIn('Dofus Ocre', portes)
        self.assertEqual(1, len([nom for nom in portes
                                 if nom.startswith('Dofus Ocre')]))


class AnkamaNumbersItsRepeatsTests(SimpleTestCase):
    """Ecaflip Paw 2 is the same ring as Ecaflip Paw unless its values differ."""

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_a_numbered_repeat_is_the_same_piece(self):
        structure = get_structure('dofus3')
        patte = structure.get_item_by_name('Ecaflip Paw')
        deuxieme = structure.get_item_by_name('Ecaflip Paw 2')
        self.assertIsNotNone(deuxieme)
        self.assertIn(deuxieme.id,
                      structure.get_rows_of_the_same_item(patte.id))

    def test_a_numbered_name_with_its_own_values_keeps_its_own_piece(self):
        structure = get_structure('dofus3')
        for nom_de_base, numerote in (('Cocoa Dofus', 'Cocoa Dofus 2'),
                                      ('Nomoon', 'Nomoon 2')):
            with self.subTest(piece=numerote):
                base = structure.get_item_by_name(nom_de_base)
                autre = structure.get_item_by_name(numerote)
                self.assertIsNotNone(autre, numerote)
                self.assertNotIn(
                    autre.id, structure.get_rows_of_the_same_item(base.id))

    def test_touch_and_retro_number_nothing(self):
        for version in ('touch', 'retro'):
            with self.subTest(version=version):
                structure = get_structure(version)
                numerotes = [item.name
                             for item in structure.get_available_items_list()
                             if item.name and item.name.rsplit(' ', 1)[-1]
                             .isdigit()]
                self.assertEqual([], numerotes)


class TheSetPathStillWorksTests(SimpleTestCase):
    """A set forbids by bare piece names, qualified labels need the fallback map."""

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_the_fallback_map_covers_exactly_the_names_that_lost_their_key(
            self):
        for version in ('dofus2', 'retro'):
            for langue in ('es', 'fr'):
                with self.subTest(version=version, langue=langue):
                    structure, portes = _portes(version, langue)
                    nus = structure.get_all_unique_items_ids_by_name(langue)
                    repli = {nom for nom in nus if nom not in portes}
                    self.assertTrue(repli)
                    for nom in repli:
                        self.assertNotIn(nom, portes)

    def test_the_page_receives_both_maps(self):
        import io
        import os
        gabarit = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'templates', 'chardata', 'exclusions.html')
        with io.open(gabarit, encoding='utf-8') as fichier:
            source = fichier.read()
        self.assertIn('ids_by_plain_name_json', source)
        self.assertIn('idsByPlainName[item] || allItemsNames[item]', source)


class TheDoorsStayCheapTests(SimpleTestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_a_door_that_closes_one_piece_is_a_bare_number(self):
        _structure, portes = _portes('retro', 'fr')
        listes = [nom for nom, valeur in portes.items()
                  if isinstance(valeur, list)]
        self.assertEqual([], listes)

    def test_pieces_nothing_separates_share_one_door(self):
        """Touch has four identical Albuera capes, one entry closes all four."""
        for langue in LANGUES:
            with self.subTest(langue=langue):
                _structure, portes = _portes('touch', langue)
                partagees = {nom: valeur for nom, valeur in portes.items()
                             if isinstance(valeur, list)}
                self.assertEqual(1, len(partagees), sorted(partagees))
                self.assertEqual([4], [len(valeur)
                                       for valeur in partagees.values()])

    def test_the_payload_grows_by_less_than_a_tenth(self):
        for version in ('dofus2', 'retro'):
            with self.subTest(version=version):
                structure, portes = _portes(version, 'fr')
                avant = json.dumps(
                    structure.get_all_unique_items_names_with_ids('fr'))
                repli = {nom: ids for nom, ids
                         in structure.get_all_unique_items_ids_by_name(
                             'fr').items() if nom not in portes}
                apres = json.dumps(portes) + json.dumps(repli)
                self.assertLess(len(apres), len(avant) * 1.10)
