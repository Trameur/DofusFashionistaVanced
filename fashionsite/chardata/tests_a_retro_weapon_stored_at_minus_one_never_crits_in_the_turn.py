# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Retro a weapon stored at -1 never crits in the turn, as in the ranking."""
import collections
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata.item_exchange import _weapon_can_crit, _weapon_crit_odds
from chardata.spell_combo import WeaponCastable, best_turn, crit_chance
from fashionistapulp.dofus_constants import NEUTRAL, BaseDamage
from fashionistapulp.structure import get_structure, set_current_game_version

PROFILES = ({'ch': 0, 'agi': 0}, {'ch': 10, 'agi': 300},
            {'ch': 50, 'agi': 800}, {'ch': 300, 'agi': 5000},
            {'ch': -20, 'agi': 0})


class TheOddsTests(SimpleTestCase):

    def test_minus_one_gives_no_crit_whatever_the_stats(self):
        for stats in PROFILES:
            with self.subTest(**stats):
                self.assertEqual(0.0, crit_chance(-1, stats, 'retro'))

    def test_a_rate_that_can_crit_is_unchanged(self):
        self.assertAlmostEqual(1 / 50.0, crit_chance(50, {'ch': 0}, 'retro'))
        self.assertAlmostEqual(0.5, crit_chance(2, {'ch': 0}, 'retro'))
        self.assertAlmostEqual(0.5, crit_chance(4, {'ch': 0, 'agi': 1000},
                                                'retro'))


class TheTurnTests(SimpleTestCase):

    def _blade(self, base_crit):
        return SimpleNamespace(
            name='Test Blade', ap=4, crit_chance=base_crit, element_maged=None,
            non_crit_hits={NEUTRAL: [BaseDamage(20, 30, 'earth')]},
            crit_hits={NEUTRAL: [BaseDamage(40, 60, 'earth')]})

    def test_a_minus_one_weapon_lands_its_normal_hit(self):
        stats = {stat.key: 0 for stat in get_structure('retro').get_stats_list()}
        stats['str'] = 100
        normal, _o = best_turn(dict(stats, ch=0, agi=0),
                               [WeaponCastable(self._blade(0))], 4,
                               game_version='retro')
        self.assertGreater(normal, 0)
        for profile in PROFILES:
            with self.subTest(**profile):
                total, _o = best_turn(dict(stats, **profile),
                                      [WeaponCastable(self._blade(-1))], 4,
                                      game_version='retro')
                self.assertAlmostEqual(normal, total, places=6)
        one_in_two, _o = best_turn(dict(stats, ch=0, agi=0),
                                   [WeaponCastable(self._blade(2))], 4,
                                   game_version='retro')
        self.assertGreater(one_in_two, normal)


class TheCatalogueTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('retro')
        self.structure = get_structure('retro')

    def tearDown(self):
        set_current_game_version('dofus3')

    def _weapons(self):
        found = []
        for key, weapon in self.structure.weapons_by_key.items():
            if not str(key).isdigit() or weapon.crit_chance is None:
                continue
            item = self.structure.get_item_by_id(int(key))
            if item is None or self.structure.get_weapon_by_name(item.name) is not weapon:
                continue
            found.append((item, weapon))
        return found

    def test_the_turn_and_the_ranking_give_every_weapon_the_same_odds(self):
        found = self._weapons()
        minus_one = [item for item, weapon in found if weapon.crit_chance == -1]
        self.assertTrue(minus_one)
        self.assertGreater(len(found), len(minus_one))
        for profile in PROFILES:
            stats = collections.defaultdict(int, profile)
            for item, weapon in found:
                with self.subTest(weapon=item.name, **profile):
                    self.assertAlmostEqual(
                        crit_chance(weapon.crit_chance, stats, 'retro'),
                        _weapon_crit_odds(self.structure, weapon, stats))

    def test_every_minus_one_weapon_cannot_crit_anywhere(self):
        for item, weapon in self._weapons():
            if weapon.crit_chance != -1:
                continue
            with self.subTest(weapon=item.name):
                self.assertFalse(_weapon_can_crit(self.structure, weapon))
                self.assertEqual(
                    0.0, crit_chance(weapon.crit_chance,
                                     {'ch': 50, 'agi': 800}, 'retro'))
