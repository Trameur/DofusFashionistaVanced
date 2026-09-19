# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Ankama repeats some pieces under several ids: forbidding one closes them all."""

from django.test import SimpleTestCase

from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure, set_current_game_version

# (repeated pieces, extra rows)
_REPETITIONS = {'dofus3': (2, 11), 'beta': (2, 11), 'dofus2': (2, 11),
                'touch': (2, 11), 'retro': (19, 28)}

# Most repeated Retro piece
_PATTE = 8941
_LIGNES_DE_LA_PATTE = 11

# Two rows of the same Retro pet
_FAMILIER = (10000065, 10000066)

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_POIDS = {'vit': 1, 'wis': 1, 'str': 1, 'int': 1, 'cha': 1, 'agi': 1,
          'pow': 1, 'ap': 100, 'mp': 100, 'range': 10, 'summon': 1}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': set()}


def _groupes(structure):
    groupes = set()
    for item in structure.get_available_items_list():
        rows = structure.get_rows_of_the_same_item(item.id)
        if rows:
            groupes.add(rows)
    return groupes


class TheCatalogueRepeatsSomeRowsTests(SimpleTestCase):

    def test_each_version_repeats_what_it_repeated(self):
        for version, (pieces, en_trop) in _REPETITIONS.items():
            with self.subTest(version=version):
                groupes = _groupes(get_structure(version))
                self.assertEqual(pieces, len(groupes))
                self.assertEqual(en_trop,
                                 sum(len(groupe) - 1 for groupe in groupes))

    def test_the_most_repeated_piece_is_the_one_measured(self):
        structure = get_structure('retro')
        self.assertEqual(_LIGNES_DE_LA_PATTE,
                         len(structure.get_rows_of_the_same_item(_PATTE)))
        self.assertEqual(
            {'Ecaflip Paw'},
            {structure.get_item_by_id(row).name
             for row in structure.get_rows_of_the_same_item(_PATTE)})

    def test_a_piece_the_catalogue_gives_once_answers_nothing(self):
        structure = get_structure('dofus3')
        seul = structure.get_item_by_name('Cawwot Dofus')
        self.assertIsNotNone(seul)
        self.assertEqual((), structure.get_rows_of_the_same_item(seul.id))


class TwoPiecesWithoutStatsAreStillTwoPiecesTests(SimpleTestCase):
    """Pieces without stats are told apart by their name."""

    _DISTINCTES = (('Black Bow Wow', 'White Bow Meow'),
                   ("Initiate's Axe", "Initiate's Bow"),
                   ('Flute', 'Paintbrush'))

    def test_pieces_that_merely_carry_no_stats_stay_apart(self):
        structure = get_structure('dofus3')
        for premier, second in self._DISTINCTES:
            with self.subTest(pieces=(premier, second)):
                un = structure.get_item_by_name(premier)
                autre = structure.get_item_by_name(second)
                self.assertIsNotNone(un, premier)
                self.assertIsNotNone(autre, second)
                self.assertNotIn(autre.id,
                                 structure.get_rows_of_the_same_item(un.id))


class ForbiddingOneRowClosesThemAllTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_current_game_version('retro')
        cls.structure = get_structure('retro')
        cls.model = Model()

    @classmethod
    def tearDownClass(cls):
        set_current_game_version('dofus3')
        super().tearDownClass()

    def setUp(self):
        # Version is a thread local, setUpClass runs in another thread
        set_current_game_version('retro')

    def tearDown(self):
        set_current_game_version('dofus3')

    def _entree(self, interdits, minimums=None):
        return ModelInput(100, dict(_BASE), dict(minimums or {'AP': 6,
                                                              'MP': 3}),
                          {}, set(interdits), dict(_POIDS), dict(_OPTIONS),
                          'Ecaflip', 0)

    def test_forbidding_one_row_takes_every_row_out_of_the_pool(self):
        self.model.setup(self._entree([]))
        avant = self.model.get_candidate_pool()['Weapon']
        self.model.setup(self._entree([_PATTE]))
        apres = self.model.get_candidate_pool()['Weapon']
        self.assertEqual(_LIGNES_DE_LA_PATTE, avant - apres)

    def test_setting_up_does_not_rewrite_the_request(self):
        entree = self._entree([_PATTE])
        demande = set(entree.forbidden_equips)
        cle = entree.cache_key()
        self.model.setup(entree)
        self.assertEqual(demande, set(entree.forbidden_equips))
        self.assertEqual(cle, entree.cache_key())

    def test_the_reader_who_forbids_the_pet_does_not_get_it_back(self):
        type_familier = self.structure.get_type_id_by_name('Pet')
        autres = [item.id for item in self.structure.get_available_items_list()
                  if item.type == type_familier and item.id not in _FAMILIER]
        minimums = {'AP': 6, 'MP': 3, 'Prospecting': 140}

        self.model.setup(self._entree(autres, minimums))
        self.model.run(1)
        rendu = self.model.get_result_minimal().item_per_slot.values()
        recu = [identifiant for identifiant in rendu
                if identifiant in _FAMILIER]
        self.assertEqual(1, len(recu),
                         'the pair was not on offer, the test below would '
                         'prove nothing')

        self.model.setup(self._entree(autres + recu, minimums))
        self.model.run(1)
        apres = self.model.get_result_minimal().item_per_slot.values()
        self.assertEqual(
            [], [identifiant for identifiant in apres
                 if identifiant in _FAMILIER],
            'the piece the reader forbade came back under the other number')


class AFolderThatHoldsOneRowKeepsThemAllTests(SimpleTestCase):
    """Owning one row keeps them all, the inventory restriction uses exclusions."""

    def test_the_inventory_keeps_the_rows_it_would_otherwise_exclude(self):
        from chardata.inventory_solver import _with_or_siblings
        structure = get_structure('retro')
        items = list(structure.get_concatenated_items_lists())
        gardes = _with_or_siblings(items, {_PATTE})
        self.assertEqual(set(structure.get_rows_of_the_same_item(_PATTE)),
                         {row for row in gardes
                          if structure.get_item_by_id(row).name
                          == 'Ecaflip Paw'})
