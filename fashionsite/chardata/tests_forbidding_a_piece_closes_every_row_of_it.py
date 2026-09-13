# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Interdire une piece la retire vraiment, sous tous ses numeros.

Trouve en exercant l'inventaire: une recherche <<Gelano>> rendait deux lignes
identiques. En remontant le fil, le catalogue lui-meme repete des entrees.
**Le fichier d'objets d'Ankama** porte onze lignes <<Ecaflip Paw>> en Retro et
deux <<Boracelet>> en Touch: meme nom, meme niveau, memes valeurs, memes
conditions, seul le numero change. Les `ankama_id` sont ceux d'Ankama, pas des
numeros que nous fabriquons.

Le solveur etendait deja une interdiction aux branches d'un objet <<OU>>. Ces
lignes-la n'en sont pas, donc la piece revenait sous le numero suivant.

Mesure du 13 septembre 2026, sur les cinq versions:

| version | pieces repetees | lignes en trop |
|---------|-----------------|----------------|
| dofus3  | 0               | 0              |
| beta    | 0               | 0              |
| dofus2  | 0               | 0              |
| touch   | 2               | 11             |
| retro   | 19              | 28             |

**Le nom fait partie de l'identite, et il le faut.** Sans lui, la meme regle
reunit 41 groupes en Dofus 3 dont <<Black Bow Wow>> avec <<White Bow Meow>> et
les huit armes d'initie entre elles: des pieces differentes qui ne portent
simplement aucune caracteristique. Mesure faite avant d'ecrire la regle.

Preuve au niveau du lecteur, avant le correctif: en ne laissant que les deux
lignes <<Snow Bow Meow (+40 Prospecting)>> parmi les familiers Retro, le
solveur rend la premiere; on l'interdit, il rend la seconde. Apres: il n'en
rend aucune.
"""

from django.test import SimpleTestCase

from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure, set_current_game_version

#: Ce que chaque version repetait le jour ou la regle a ete ecrite.
#: (pieces repetees, lignes en trop)
_REPETITIONS = {'dofus3': (0, 0), 'beta': (0, 0), 'dofus2': (0, 0),
                'touch': (2, 11), 'retro': (19, 28)}

#: La piece Retro la plus repetee, et de combien de lignes.
_PATTE = 8941
_LIGNES_DE_LA_PATTE = 11

#: Les deux lignes du familier qui sert de preuve.
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
    """Le plancher: sans repetition a fermer, tout le reste passe a vide."""

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
    """La regle sans le nom reunissait des pieces differentes: elle merite
    d'etre gardee au large de ce piege."""

    #: Des pieces sans aucune caracteristique, que la regle sans le nom
    #: fusionnait, et que le lecteur distingue tres bien.
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
        # The version is a thread local and the runner does not run setUpClass
        # in the thread that runs the test: without this, the model holds the
        # Retro catalogue while `get_result_minimal` reads the Dofus 3 one and
        # silently drops every Retro-only piece from the answer.
        set_current_game_version('retro')

    def tearDown(self):
        set_current_game_version('dofus3')

    def _entree(self, interdits, minimums=None):
        return ModelInput(100, dict(_BASE), dict(minimums or {'AP': 6,
                                                              'MP': 3}),
                          {}, set(interdits), dict(_POIDS), dict(_OPTIONS),
                          'Ecaflip', 0)

    def test_forbidding_one_row_takes_every_row_out_of_the_pool(self):
        """Onze lignes quittent l'offre, pas une."""
        self.model.setup(self._entree([]))
        avant = self.model.get_candidate_pool()['Weapon']
        self.model.setup(self._entree([_PATTE]))
        apres = self.model.get_candidate_pool()['Weapon']
        self.assertEqual(_LIGNES_DE_LA_PATTE, avant - apres)

    def test_setting_up_does_not_rewrite_the_request(self):
        """L'expansion travaille sur une copie: la meme demande doit donner
        la meme cle de cache au deuxieme appel."""
        entree = self._entree([_PATTE])
        demande = set(entree.forbidden_equips)
        cle = entree.cache_key()
        self.model.setup(entree)
        self.assertEqual(demande, set(entree.forbidden_equips))
        self.assertEqual(cle, entree.cache_key())

    def test_the_reader_who_forbids_the_pet_does_not_get_it_back(self):
        """La preuve au niveau du lecteur, de bout en bout.

        On ne laisse que les deux lignes du meme familier, on demande de la
        prospection, on interdit celui qu'on recoit. Avant le correctif, le
        solveur rendait l'autre.
        """
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
    """L'autre moitie de la meme regle: interdire ferme tout, posseder garde
    tout. Sans quoi le lecteur qui possede la piece se la verrait retirer par
    la restriction d'inventaire, qui parle par les memes exclusions."""

    def test_the_inventory_keeps_the_rows_it_would_otherwise_exclude(self):
        from chardata.inventory_solver import _with_or_siblings
        structure = get_structure('retro')
        items = list(structure.get_concatenated_items_lists())
        gardes = _with_or_siblings(items, {_PATTE})
        self.assertEqual(set(structure.get_rows_of_the_same_item(_PATTE)),
                         {row for row in gardes
                          if structure.get_item_by_id(row).name
                          == 'Ecaflip Paw'})
