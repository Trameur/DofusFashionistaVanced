# -*- coding: utf-8 -*-
"""Setting up a solve must not rewrite the request it was handed.

`modify_forbidden_items_constraints` expanded a forbidden item to its sibling
rows -- an item split into "(#1)" and "(#2)" is one item -- and wrote them into
the caller's own set, because `new_forbid_list = forbidden_equips` aliased it.

That is invisible in the gear returned, and expensive everywhere else.
fashion_action asks the cache for a key BEFORE setup and stores under a key
computed AFTER it, so the two differed; and the counter born under the mutated
key starts at zero, which put() refuses to store. A character who forbade
Gelano cached nothing at all, and repaid the whole nine-second solve on every
view. Found by an audit of 105 solves, and it survived a refuter.

The second test guards the other half of the same audit: model.py compared a
game version to the literal 'retro' in one place while reading the registry's
rings_can_double in another, a migration left half done by a4e18dff7.
"""
import inspect
import re

from django.test import SimpleTestCase

from fashionistapulp import model as model_module
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure


def _un_groupe_scinde(structure):
    """(nom, membres) d'un objet livre en plusieurs lignes, ou None."""
    for nom, membres in structure.get_available_or_items().items():
        if len(membres) >= 2:
            return nom, membres
    return None, None


class TheSolverLeavesItsInputAlone(SimpleTestCase):

    def setUp(self):
        self.structure = get_structure('dofus3')

    def _entree(self, interdits):
        return ModelInput(
            200,
            {'AP': 7, 'MP': 3, 'Range': 0, 'Summon': 1, 'Vitality': 200,
             'Wisdom': 100, 'Strength': 100, 'Intelligence': 100,
             'Chance': 100, 'Agility': 100, 'Prospecting': 100},
            {}, {}, set(interdits),
            {'vit': 20, 'wis': 40, 'str': 0, 'int': 0, 'cha': 0, 'agi': 6,
             'pow': 0, 'ap': 800, 'mp': 600, 'range': 300, 'summon': 20},
            {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
             'dofus': True, 'trophies': True, 'dragoturkey': True,
             'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
             'dofuses': {}, 'dofusnotforchar': set()},
            'Iop', 0)

    def test_a_split_item_exists_to_be_forbidden(self):
        """Without one, every assertion below passes on an empty case."""
        nom, membres = _un_groupe_scinde(self.structure)
        self.assertIsNotNone(nom, 'no split item in dofus3: the tests below '
                                  'would prove nothing')
        self.assertGreaterEqual(len(membres), 2)

    def test_forbidding_one_row_does_not_rewrite_the_request(self):
        _nom, membres = _un_groupe_scinde(self.structure)
        une_ligne = membres[0].id
        entree = self._entree([une_ligne])
        avant_set = set(entree.forbidden_equips)
        avant_cle = entree.cache_key()

        Model().setup(entree)

        self.assertEqual(set(entree.forbidden_equips), avant_set,
                         'setup() added the sibling rows to the caller\'s set')
        self.assertEqual(entree.cache_key(), avant_cle,
                         'the cache key moved between the read and the write')

    def _plafonds(self, interdits):
        """Le plafond de chaque ligne du groupe scinde. 0 = interdit."""
        _nom, membres = _un_groupe_scinde(self.structure)
        modele = Model()
        modele.setup(self._entree(interdits))
        return {m.id: modele.restrictions.forbidden_items_constraints[m.id].constant
                for m in membres}

    def test_forbidding_one_row_still_forbids_its_siblings(self):
        """La copie ne doit pas couter la regle : une ligne interdite interdit
        tout l'objet, sinon on aurait echange un defaut de cache contre un
        build que le joueur a refuse.

        Il faut viser la bonne ligne. A vide, Gelano (#1) est DEJA interdit --
        c'est la variante a identifiant decale -- donc l'interdire ne prouve
        rien. On interdit celle qui l'est deja et on regarde bouger l'autre.
        Une premiere version de ce test lisait la presence d'une cle dans un
        dictionnaire pre-rempli pour tous les objets : elle ne pouvait pas
        echouer, et seule une falsification l'a montre.
        """
        base = self._plafonds([])
        libres = [i for i, c in base.items() if c != 0]
        deja = [i for i, c in base.items() if c == 0]
        self.assertTrue(libres, 'toutes les lignes sont deja interdites a '
                                'vide : ce test ne prouverait rien')
        self.assertTrue(deja, 'aucune ligne a interdire pour declencher '
                              'l expansion')
        apres = self._plafonds([deja[0]])
        for identifiant in libres:
            self.assertEqual(apres[identifiant], 0,
                             'la ligne soeur %s est restee autorisee alors '
                             'que %s etait interdit' % (identifiant, deja[0]))

    def test_an_item_nobody_forbade_keeps_its_ceiling(self):
        """The other half: if every ceiling were 0, the test above would pass
        on a model that forbids the whole catalogue."""
        scindes = {m.id for _n, ms in
                   self.structure.get_available_or_items().items() for m in ms}
        libre = next(i for i in self.structure.get_available_items_list()
                     if i.id not in scindes)
        modele = Model()
        modele.setup(self._entree([]))
        contrainte = modele.restrictions.forbidden_items_constraints[libre.id]
        self.assertNotEqual(contrainte.constant, 0,
                            'item %s is forbidden without being asked' % libre.id)

    def test_an_ordinary_forbidden_item_is_left_alone_too(self):
        scindes = {m.id for _n, ms in
                   self.structure.get_available_or_items().items() for m in ms}
        ordinaire = next(i for i in self.structure.get_available_items_list()
                         if i.id not in scindes)
        entree = self._entree([ordinaire.id])
        avant = set(entree.forbidden_equips)
        Model().setup(entree)
        self.assertEqual(set(entree.forbidden_equips), avant)


class TheVersionRuleComesFromTheRegistry(SimpleTestCase):

    def test_model_asks_the_registry_and_not_a_literal_key(self):
        """One ceiling read rings_can_double, its twin read `!= 'retro'`.

        Both decide whether a setless ring may be worn twice. dofus_constants
        keeps its own literal comparisons on purpose -- those are game rules
        with no registry entry -- so this looks only at model.py.
        """
        source = inspect.getsource(model_module)
        en_dur = re.findall(r"game_version\s*[!=]=\s*'[a-z0-9]+'", source)
        self.assertEqual(en_dur, [],
                         'model.py compares a version to a literal key: %r'
                         % en_dur)

    def test_both_ceilings_derive_from_the_same_rule(self):
        for methode in (Model.create_item_number_variables,
                        Model.create_or_item_count_constraints):
            source = inspect.getsource(methode)
            self.assertIn('rings_can_double', source,
                          '%s stopped reading the registry' % methode.__name__)
