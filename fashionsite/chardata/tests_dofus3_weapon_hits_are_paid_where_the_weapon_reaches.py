# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 3 weapon hits are paid by the share of the build's attacks the weapon's range lets it take part in."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.spell_combo import castable_spells
from chardata.weapon_terms import (melee_share, ranged_band, reach_share, terms_on_stats,
                                   weapon_hit_terms, weapon_reach)
from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY

FLINTY_DAGGERS = 14132
CHAOTIC_SCYTHE = 26011
EROTEGG_BOW = 32235


def _structure():
    from fashionistapulp.structure import get_structure
    return get_structure('dofus3')


def _class_weights(race, aspects=('agi',)):
    from chardata.smart_build import _set_weights
    char = SimpleNamespace(char_class=race, level=200, game_version='dofus3')
    return _set_weights(char, set(aspects), apply=False)


def _band(race):
    return ranged_band(castable_spells(race, 200, 'dofus3'), 'dofus3', race, 200)


STATS = dict({key: 0 for key in STAT_NAME_TO_KEY.values()},
             str=900, cha=900, int=900, agi=900, pow=250, ch=30, cridam=40, ap=12)


def _reach_passed_on_the_first_set(race):
    char = SimpleNamespace(game_version='dofus3', char_class=race, level=200)
    model_input = SimpleNamespace(objective_values=_class_weights(race), empty_slot_types=[],
                                  locked_equips={}, forbidden_equips=set())
    solution = SimpleNamespace(items={'Weapon': []}, get_stats_total=lambda: dict(STATS))
    with mock.patch('chardata.weapon_terms.terms_on_stats', return_value={}) as terms, \
            mock.patch('chardata.solution.get_solution_from_minimal', return_value=solution):
        weapon_hit_terms(char, object(), model_input)
    return terms.call_args[1]['reach']


class _DofusThree(SimpleTestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')


class _Weapon(object):

    def __init__(self, item_id, gain):
        self.weapon = SimpleNamespace(id=item_id)
        self.lower = gain
        self.exact = gain


class _Reader(object):
    """A turn of 1000 plus 2 per point of each characteristic."""

    def full(self, weapon=None, deltas=None):
        return 1000.0 + 2 * sum((deltas or {}).values()) + (weapon.exact if weapon else 0)

    def lower_gain(self, weapon):
        return weapon.lower

    def gain(self, weapon):
        return weapon.exact


def _equal_gains(*item_ids):
    return {item_id: _Weapon(item_id, 300.0) for item_id in item_ids}


class AMeleeOnlyBuildKeepsTodaysCreditTests(_DofusThree):

    def test_a_melee_weapon_of_a_build_attacking_only_in_melee_is_paid_in_full(self):
        weights = {'agi': 120, 'permedam': 300, 'perrandam': 0}
        reach = weapon_reach(_structure(), [FLINTY_DAGGERS, CHAOTIC_SCYTHE], weights,
                             _band('Iop'))
        self.assertEqual({FLINTY_DAGGERS: 1.0, CHAOTIC_SCYTHE: 1.0}, reach)
        weapons = _equal_gains(FLINTY_DAGGERS, CHAOTIC_SCYTHE)
        self.assertEqual(terms_on_stats(_Reader(), weights, None, weapons),
                         terms_on_stats(_Reader(), weights, None, weapons, reach=reach))


class ACraDaggerIsPaidLessThanItsBowTests(_DofusThree):

    def test_at_equal_raw_gain_the_cra_dagger_gets_less_than_its_bow(self):
        weights = _class_weights('Cra')
        reach = weapon_reach(_structure(), [FLINTY_DAGGERS, EROTEGG_BOW], weights, _band('Cra'))
        weapons = _equal_gains(FLINTY_DAGGERS, EROTEGG_BOW)
        terms = terms_on_stats(_Reader(), weights, None, weapons, reach=reach)
        today = terms_on_stats(_Reader(), weights, None, weapons)
        self.assertEqual(today[FLINTY_DAGGERS], today[EROTEGG_BOW])
        self.assertLess(terms[FLINTY_DAGGERS], terms[EROTEGG_BOW])
        self.assertLess(terms[FLINTY_DAGGERS], today[FLINTY_DAGGERS])

    def test_the_first_set_read_passes_each_weapon_reach(self):
        reach = _reach_passed_on_the_first_set('Cra')
        self.assertLess(reach[FLINTY_DAGGERS], reach[EROTEGG_BOW])
        self.assertTrue(all(0.0 <= share <= 1.0 for share in reach.values()))

    def test_the_melee_share_is_the_one_smart_build_gives_the_final_damage(self):
        self.assertAlmostEqual(0.1, melee_share(_class_weights('Cra')))
        self.assertAlmostEqual(0.7, melee_share(_class_weights('Sacrier')))


class AMissingRangeChangesNothingTests(_DofusThree):

    def test_weapons_without_a_range_get_no_reach(self):
        structure = _structure()
        no_range = SimpleNamespace(get_item_by_id=structure.get_item_by_id,
                                   get_weapon_for_item=lambda item: SimpleNamespace(range=None))
        self.assertEqual({}, weapon_reach(no_range, [FLINTY_DAGGERS, EROTEGG_BOW],
                                          _class_weights('Cra'), _band('Cra')))

    def test_no_reach_gives_today_s_terms(self):
        weights = _class_weights('Cra')
        weapons = _equal_gains(FLINTY_DAGGERS, EROTEGG_BOW)
        self.assertEqual(terms_on_stats(_Reader(), weights, None, weapons),
                         terms_on_stats(_Reader(), weights, None, weapons, reach={}))

    def test_the_first_set_read_passes_no_reach_when_no_weapon_has_a_range(self):
        weapons = list(_structure().weapons_by_key.values())
        held = [(weapon, weapon.range) for weapon in weapons]
        self.addCleanup(lambda: [setattr(weapon, 'range', kept) for weapon, kept in held])
        for weapon in weapons:
            weapon.range = None
        self.assertEqual({}, _reach_passed_on_the_first_set('Cra'))

    def test_weights_without_a_melee_or_ranged_share_change_nothing(self):
        self.assertIsNone(melee_share({'agi': 120}))
        self.assertIsNone(melee_share({'agi': 120, 'permedam': 0, 'perrandam': 0}))
        self.assertEqual({}, weapon_reach(_structure(), [FLINTY_DAGGERS], {'agi': 120},
                                          _band('Cra')))


class TheReachShareTests(SimpleTestCase):

    def test_a_weapon_reaching_distance_one_takes_the_melee_share(self):
        self.assertAlmostEqual(0.3, reach_share((1, 1), 0.3, (3, 8)))
        self.assertAlmostEqual(0.3, reach_share((1, 2), 0.3, (3, 8)))

    def test_a_weapon_reaching_beyond_two_takes_the_part_of_the_band_it_covers(self):
        self.assertAlmostEqual(0.7 * 5 / 6, reach_share((3, 7), 0.3, (3, 8)))
        self.assertAlmostEqual(0.7 * 3 / 6, reach_share((4, 6), 0.3, (3, 8)))
        self.assertAlmostEqual(0.7, reach_share((2, 10), 0.3, (3, 8)))

    def test_a_weapon_reaching_both_takes_both_shares(self):
        self.assertAlmostEqual(0.3 + 0.7 * 3 / 6, reach_share((1, 5), 0.3, (3, 8)))

    def test_a_weapon_reaching_neither_takes_nothing(self):
        self.assertEqual(0.0, reach_share((2, 2), 0.3, (3, 8)))

    def test_without_a_band_a_weapon_reaching_beyond_two_takes_the_whole_ranged_share(self):
        self.assertAlmostEqual(0.7, reach_share((3, 7), 0.3, None))
        self.assertAlmostEqual(0.3, reach_share((1, 2), 0.3, None))


class TheBandComesFromTheClassSpellsTests(_DofusThree):

    def test_the_band_runs_from_three_to_the_median_reach_of_the_class_attack_spells(self):
        from chardata.spell_buffs import _decide_spell_level
        from chardata.spell_reference import reference_by_spell_id
        reference = reference_by_spell_id('dofus3', 'Cra')
        reaches = []
        for spell in castable_spells('Cra', 200, 'dofus3'):
            entry = reference.get(spell.spell_id)
            if spell.hits and entry:
                farthest = entry['range'][_decide_spell_level(entry['levels'], 200)][1]
                if farthest >= 3:
                    reaches.append(farthest)
        near, far = _band('Cra')
        self.assertEqual(3, near)
        self.assertIn(far, reaches)
        self.assertGreaterEqual(2 * sum(1 for reach in reaches if reach <= far), len(reaches))
        self.assertGreaterEqual(2 * sum(1 for reach in reaches if reach >= far), len(reaches))

    def test_a_class_the_reference_does_not_know_has_no_band(self):
        self.assertIsNone(ranged_band(castable_spells('Cra', 200, 'dofus3'), 'dofus3',
                                      'Nobody', 200))


class OtherVersionsAreUnchangedTests(SimpleTestCase):

    def test_other_versions_get_no_weapon_term(self):
        for version in ('beta', 'dofus2', 'touch', 'retro'):
            with self.subTest(version=version):
                char = SimpleNamespace(game_version=version, char_class='Cra', level=200)
                model_input = SimpleNamespace(objective_values=_class_weights('Cra'),
                                              empty_slot_types=[], locked_equips={},
                                              forbidden_equips=set())
                self.assertEqual({}, weapon_hit_terms(char, object(), model_input))
