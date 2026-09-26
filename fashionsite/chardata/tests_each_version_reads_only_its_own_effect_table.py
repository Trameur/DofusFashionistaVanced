# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Only a version with its own effect table reads one; beta keeps its hand formulas."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from fashionistapulp.item_effects import (effect_term, load_effect_table,
                                          played_characteristics, versions_with_effect_table)

ALL_VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')


def weights(version, aspects=('str',), race='Iop'):
    from chardata.smart_build import _set_weights
    char = SimpleNamespace(char_class=race, level=200, game_version=version)
    return _set_weights(char, set(aspects), apply=False)


class Recorder(object):

    def __init__(self):
        self.terms = {}

    def add_to_of(self, category, item_id, weight):
        self.terms[(category, item_id)] = self.terms.get((category, item_id), 0) + weight


class EachVersionReadsOnlyItsOwnEffectTableTests(SimpleTestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        self.addCleanup(set_current_game_version, 'dofus3')

    def _model(self, version, objective_values):
        from fashionistapulp.model import Model
        from fashionistapulp.structure import get_structure, set_current_game_version
        set_current_game_version(version)
        model = Model.__new__(Model)
        model.structure = get_structure(version)
        model.problem = Recorder()
        model.add_weird_item_weights_to_objective_funcion(objective_values, 200)
        return model

    def test_a_version_without_its_file_gets_no_table(self):
        self.assertIn('dofus3', versions_with_effect_table())
        for version in ALL_VERSIONS:
            if version not in versions_with_effect_table():
                with self.subTest(version=version):
                    self.assertIsNone(load_effect_table(version))

    def test_dofus2_touch_and_retro_get_no_effect_terms(self):
        for version in ('dofus2', 'touch', 'retro'):
            with self.subTest(version=version):
                model = self._model(version, weights(version))
                self.assertEqual({}, model.problem.terms)

    def test_beta_keeps_its_hand_formulas(self):
        w = weights('beta')
        model = self._model('beta', w)

        def term(name):
            return model.problem.terms[('p', model.structure.get_item_by_name(name).id)]
        self.assertEqual(w['ch'] * 5, term('Turquoise Dofus'))
        self.assertEqual(w['ch'] * 20, term('Surpryz'))
        self.assertEqual(w['ap'] * 0.5, term('Prysipitate-O-Mat'))
        self.assertEqual(w['ap'] * 2.5 + w['mp'] * 2.5, term('Abyssal Dofus'))
        self.assertEqual((w.get('respermee', 0) + w.get('resperran', 0)) * 80 * 0.18,
                         term('Prymune'))

    def test_dofus3_puts_one_term_on_each_valued_entry_of_its_table(self):
        for aspects in (('str',), ('int', 'cha'), ('str', 'int', 'agi'), ('str', 'int', 'cha', 'agi')):
            with self.subTest(aspects=aspects):
                w = weights('dofus3', aspects)
                model = self._model('dofus3', w)
                expected = {}
                for key, entry in load_effect_table('dofus3')['items'].items():
                    term = effect_term(entry, w, 200)
                    if term:
                        expected[('p', model.structure.get_item_by_ankama_id(int(key)).id)] = term
                self.assertTrue(expected)
                self.assertEqual(expected, model.problem.terms)


class EffectTermTests(SimpleTestCase):

    ENTRY = {'equivalents': {'final': 2, 'hp': 100, 'played_char': 10, 'ap': 0.5},
             'equivalents_by_elements': {'2': {'final': 3, 'sets': 4}}}
    WEIGHTS = {'str': 100, 'int': 90, 'agi': 20, 'permedam': 30, 'perrandam': 50,
               'hp': 20, 'ap': 1000}

    def test_the_played_characteristics_are_those_near_the_heaviest(self):
        self.assertEqual(['str', 'int'], played_characteristics(self.WEIGHTS))
        self.assertEqual(['str'], played_characteristics(dict(self.WEIGHTS, int=60)))
        self.assertEqual([], played_characteristics({'vit': 20}))

    def test_the_element_count_picks_its_own_equivalents(self):
        self.assertEqual(3 * 80, effect_term(self.ENTRY, self.WEIGHTS, 200))

    def test_without_a_group_the_overall_equivalents_are_paid(self):
        w = dict(self.WEIGHTS, int=60)
        self.assertEqual(2 * 80 + 100 * 20 * 100 / 200.0 + 10 * 100 + 0.5 * 1000,
                         effect_term(self.ENTRY, w, 100))

    def test_entries_without_equivalents_or_bound_to_a_class_are_not_paid(self):
        self.assertEqual(0, effect_term({'status': 'not_valued', 'equivalents': {}},
                                        self.WEIGHTS, 200))
        self.assertEqual(0, effect_term({'status': 'not_measured', 'equivalents': None},
                                        self.WEIGHTS, 200))
        self.assertEqual(0, effect_term({'rule': 'class_item_spell_modifiers',
                                         'equivalents': {'played_char': 5}},
                                        self.WEIGHTS, 200))
