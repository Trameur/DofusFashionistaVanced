# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A hand-written legendary weight follows the item's effect from Dofus 3.7."""
from django.test import SimpleTestCase

from chardata.data_versions import current_data_version, patch_key, patch_of
from fashionistapulp.model import Model
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta')


class _Objective(object):

    def __init__(self):
        self.calls = []

    def add_to_of(self, *args):
        self.calls.append(args)


def item_weight(version, name, objective_values, level=200):
    set_current_game_version(version)
    model = Model.__new__(Model)
    model.structure = get_structure(version)
    model.problem = _Objective()
    model.add_weird_item_weights_to_objective_funcion(
        dict({'str': 1}, **objective_values), level)
    item_id = model.structure.get_item_by_name(name).id
    return sum(value for category, key, value in model.problem.calls
               if category == 'p' and key == item_id)


def versions_on_3_7():
    return [version for version in VERSIONS
            if patch_key(patch_of(current_data_version(version))) >= (3, 7)]


def effect_text(version, name):
    item = get_structure(version).get_item_by_name(name)
    return ' '.join(item.localized_extras['en'])


class ALegendaryWeightFollowsIts37EffectTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_buhorado_feather_weighs_more_with_more_crit_without_a_ten_stack_cap(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                low = item_weight(version, 'Buhorado Feather',
                                  {'pshdam': 200, 'ch': 240})
                high = item_weight(version, 'Buhorado Feather',
                                   {'pshdam': 200, 'ch': 2800})
                self.assertGreater(low, 0)
                self.assertAlmostEqual(2800 / 240, high / low)

    def test_crocobur_weighs_more_hp_for_a_melee_bearer(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                ranged = item_weight(version, 'Crocobur 3',
                                     {'hp': 30, 'permedam': 100, 'perrandam': 900})
                melee = item_weight(version, 'Crocobur 3',
                                    {'hp': 30, 'permedam': 900, 'perrandam': 100})
                self.assertGreater(ranged, 0)
                self.assertGreater(melee, ranged)

    def test_dodges_audacity_weighs_every_stat_its_effect_names(self):
        for version in VERSIONS:
            for stat in ('mp', 'ch', 'dodge', 'pshdam'):
                with self.subTest(version=version, stat=stat):
                    self.assertGreater(
                        item_weight(version, "Dodge's Audacity", {stat: 100}), 0)
            with self.subTest(version=version, stat='lock'):
                self.assertEqual(
                    0, item_weight(version, "Dodge's Audacity", {'lock': 100}))

    def test_bram_crown_passive_weighs_final_damage_not_weapon_damage(self):
        crown = "Bram Worldbeard's Crown"
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(0, item_weight(version, crown, {'perweadam': 100}))
                self.assertGreater(item_weight(version, crown, {'permedam': 100}), 0)
                self.assertGreater(item_weight(version, crown, {'perrandam': 100}), 0)

    def test_the_effects_these_weights_follow_are_the_3_7_ones(self):
        versions = versions_on_3_7()
        self.assertIn('beta', versions)
        for version in versions:
            with self.subTest(version=version):
                buhorado = effect_text(version, 'Buhorado Feather')
                self.assertIn('they gain 10 Pushback Damage for 3 turns', buhorado)
                self.assertNotIn('stackable', buhorado)
                self.assertIn('on enemies hit for 2 turns',
                              effect_text(version, 'Crocobur 3'))
                self.assertIn('gains 1 MP and 10% Critical',
                              effect_text(version, "Dodge's Audacity"))
                crown = "Bram Worldbeard's Crown"
                self.assertIn('they gain 2% final damage for 2 turns',
                              effect_text(version, crown))
                structure = get_structure(version)
                self.assertIn(structure.get_stat_by_key('ch').id,
                              dict(structure.get_item_by_name(crown).stats))
