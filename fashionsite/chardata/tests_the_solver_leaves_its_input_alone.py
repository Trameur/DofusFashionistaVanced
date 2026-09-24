# -*- coding: utf-8 -*-
"""Setting up a solve does not rewrite the request it was handed."""
import inspect
import re

from django.test import SimpleTestCase

from fashionistapulp import model as model_module
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure


def _un_groupe_scinde(structure):
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
        _nom, membres = _un_groupe_scinde(self.structure)
        modele = Model()
        modele.setup(self._entree(interdits))
        return {m.id: modele.restrictions.forbidden_items_constraints[m.id].constant
                for m in membres}

    def test_forbidding_one_row_still_forbids_its_siblings(self):
        base = self._plafonds([])
        libres = [i for i, c in base.items() if c != 0]
        deja = [i for i, c in base.items() if c == 0]
        self.assertTrue(libres, 'all the rows are already forbidden at '
                                'zero: this test would prove nothing')
        self.assertTrue(deja, 'no row to forbid to trigger the '
                              'expansion')
        apres = self._plafonds([deja[0]])
        for identifiant in libres:
            self.assertEqual(apres[identifiant], 0,
                             'the sibling row %s stayed allowed while '
                             '%s was forbidden' % (identifiant, deja[0]))

    def test_an_item_nobody_forbade_keeps_its_ceiling(self):
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
