# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
from django.test import SimpleTestCase

from chardata.spells_view import _weapon_castable
from fashionistapulp.dofus_constants import (DAMAGE_TYPES, FIRE, NEUTRAL,
                                             calculate_damage)
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import get_structure, set_current_game_version

_HIDSAD_BOW = 1355
_TRUFFLE_SHOVEL = 6539
_KUKRI_KURA = 'Kukri Kura'
_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': set()}


def _rows(hits):
    return [(hit.min_dam, hit.max_dam, hit.element, bool(hit.heals))
            for hit in hits]


def _scaled(hits, stats):
    return calculate_damage(hits, stats, critical_hit=False, is_spell=False)


def _damage_and_heal(weapon, element, stats):
    hits = _scaled(weapon.non_crit_hits[element], stats)
    return (sum(hit.average() for hit in hits if not hit.heals),
            sum(hit.average() for hit in hits if hit.heals))


def _worth_by_element(weapon, stats):
    return {element: sum(_damage_and_heal(weapon, element, stats))
            for element in DAMAGE_TYPES}


class _WithAWornWeapon(SimpleTestCase):

    version = 'dofus3'

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(self.version)
        self.structure = get_structure(self.version)

    def _worn(self, item, **base):
        result = ModelResult({'options': dict(_OPTIONS),
                              'base_stats_by_attr': dict(_BASE, **base),
                              'char_level': 200})
        result.add_item_at_slot(item, 'weapon')
        result.calculate_stats()
        return result, result.items['Weapon'][0]

    def assertServesMost(self, weapon, stats):
        worths = _worth_by_element(weapon, stats)
        self.assertEqual(max(worths.values()), worths[weapon.element_maged])
        self.assertGreater(worths[weapon.element_maged], min(worths.values()))


class ABetaHealingBowTakesThePotionThatServesItTests(_WithAWornWeapon):

    version = 'beta'

    def setUp(self):
        super().setUp()
        self.bow = self.structure.get_item_by_ankama_id(_HIDSAD_BOW)

    def test_an_intelligence_character_shoots_fire_beside_the_neutral_heal(self):
        result, weapon = self._worn(self.bow, Intelligence=500)
        stats = result.get_stats_total()
        self.assertEqual(FIRE, weapon.element_maged)
        damage, heal = _damage_and_heal(weapon, FIRE, stats)
        neutral_damage, neutral_heal = _damage_and_heal(weapon, NEUTRAL, stats)
        self.assertGreater(damage, neutral_damage)
        self.assertEqual(heal, neutral_heal)
        self.assertServesMost(weapon, stats)

    def test_the_panel_swings_the_fire_roll_the_potion_gave(self):
        result, weapon = self._worn(self.bow, Intelligence=500)
        stats = result.get_stats_total()
        castable = _weapon_castable(result)
        self.assertEqual([(12, 42, FIRE, False), (12, 42, NEUTRAL, True)],
                         _rows(castable.hits))
        swung = _scaled(castable.hits, stats)
        self.assertEqual(
            [hit.average() for hit in _scaled(weapon.non_crit_hits[FIRE], stats)],
            [hit.average() for hit in swung])
        self.assertGreater(
            swung[0].average(),
            _scaled(weapon.non_crit_hits[NEUTRAL], stats)[0].average())

    def test_a_strength_character_takes_the_potion_that_adds_the_most_damage_and_heal(self):
        result, weapon = self._worn(self.bow, Strength=500)
        stats = result.get_stats_total()
        self.assertServesMost(weapon, stats)
        damage, heal = _damage_and_heal(weapon, weapon.element_maged, stats)
        self.assertEqual(damage, max(_damage_and_heal(weapon, element, stats)[0]
                                     for element in DAMAGE_TYPES))
        self.assertEqual(heal, max(_damage_and_heal(weapon, element, stats)[1]
                                   for element in DAMAGE_TYPES))


class ALiveHealingShovelTakesThePotionThatServesItTests(_WithAWornWeapon):

    def setUp(self):
        super().setUp()
        self.shovel = self.structure.get_item_by_ankama_id(_TRUFFLE_SHOVEL)

    def test_a_healer_hits_fire_beside_the_fire_heal(self):
        result, weapon = self._worn(self.shovel, Intelligence=500)
        stats = result.get_stats_total()
        self.assertEqual(FIRE, weapon.element_maged)
        damage, heal = _damage_and_heal(weapon, FIRE, stats)
        neutral_damage, neutral_heal = _damage_and_heal(weapon, NEUTRAL, stats)
        self.assertGreater(damage, neutral_damage)
        self.assertEqual(heal, neutral_heal)
        self.assertServesMost(weapon, stats)

    def test_a_fighter_keeps_the_neutral_roll_that_hits_hardest(self):
        result, weapon = self._worn(self.shovel, Strength=500)
        stats = result.get_stats_total()
        self.assertEqual(NEUTRAL, weapon.element_maged)
        damage, heal = _damage_and_heal(weapon, NEUTRAL, stats)
        self.assertEqual(damage, max(_damage_and_heal(weapon, element, stats)[0]
                                     for element in DAMAGE_TYPES))
        self.assertServesMost(weapon, stats)


class ADamageWeaponKeepsItsHardestElementTests(_WithAWornWeapon):

    def test_the_kukri_kura_hits_in_the_element_the_character_scales(self):
        kukri = self.structure.get_item_by_name(_KUKRI_KURA)
        for base, expected in (({'Intelligence': 500}, FIRE),
                               ({'Strength': 500}, NEUTRAL)):
            with self.subTest(**base):
                result, weapon = self._worn(kukri, **base)
                stats = result.get_stats_total()
                self.assertEqual(expected, weapon.element_maged)
                damage, heal = _damage_and_heal(weapon, expected, stats)
                self.assertEqual(0, heal)
                self.assertEqual(damage, max(
                    _damage_and_heal(weapon, element, stats)[0]
                    for element in DAMAGE_TYPES))
