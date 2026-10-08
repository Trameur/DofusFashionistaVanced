# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Dofus 2 a crit total under zero gives no crit at all, where Touch keeps one percent."""
import collections
import copy
from unittest import mock

from django.test import SimpleTestCase

from chardata.item_exchange import _get_weapon_rate
from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import best_turn, castable_spells, crit_chance
from fashionistapulp.dofus_constants import NEUTRAL, DamageDigest
from fashionistapulp.structure import get_structure, set_current_game_version
from fashionistapulp.weapon import Weapon


class TheDofus2OddsTests(SimpleTestCase):

    def test_a_total_at_or_under_zero_never_crits(self):
        for base, crit_hits in ((5, -90), (25, -25), (25, -40), (1, -1),
                                (15, -1000)):
            with self.subTest(base=base, ch=crit_hits):
                self.assertEqual(0.0,
                                 crit_chance(base, {'ch': crit_hits}, 'dofus2'))

    def test_a_total_of_one_is_one_percent(self):
        self.assertAlmostEqual(0.01, crit_chance(25, {'ch': -24}, 'dofus2'))
        self.assertAlmostEqual(0.01, crit_chance(1, {'ch': 0}, 'dofus2'))

    def test_the_rest_of_the_range_is_unchanged(self):
        self.assertAlmostEqual(0.15, crit_chance(15, {'ch': 0}, 'dofus2'))
        self.assertAlmostEqual(0.35, crit_chance(15, {'ch': 20}, 'dofus2'))
        self.assertAlmostEqual(1.0, crit_chance(30, {'ch': 90}, 'dofus2'))
        self.assertEqual(0.0, crit_chance(0, {'ch': 50}, 'dofus2'))

    def test_touch_keeps_its_one_percent_floor(self):
        self.assertAlmostEqual(0.01, crit_chance(5, {'ch': -90}, 'touch'))
        self.assertAlmostEqual(0.01, crit_chance(25, {'ch': -25}, 'touch'))


class _Pool(object):
    is_mageable = False


def _solution(crit_hits):
    stats = collections.defaultdict(int, {'ch': crit_hits, 'cridam': 100})

    class Solution(object):
        stats_total = stats

        def switch_item(self, item, slot, overrides=None):
            return _Pool()
    return Solution()


def _named(name):
    class Named(object):
        pass
    Named.name = name
    return Named()


def _weapon(base_crit):
    weapon = Weapon()
    weapon.ap = 4
    weapon.crit_chance = base_crit
    weapon.crit_bonus = 0
    weapon.has_crits = True
    weapon.non_crit_hits = collections.defaultdict(list)
    weapon.crit_hits = collections.defaultdict(list)
    weapon.non_crit_hits[NEUTRAL] = [DamageDigest(40, 40, NEUTRAL, False, False)]
    weapon.crit_hits[NEUTRAL] = [DamageDigest(40, 40, NEUTRAL, False, False)]
    return weapon


class TheDofus2RankingTests(SimpleTestCase):

    def _rate(self, base_crit, crit_hits):
        solution = _solution(crit_hits)
        with mock.patch('chardata.item_exchange.get_structure') as structure, \
                mock.patch('chardata.item_exchange.get_solution',
                           return_value=solution):
            structure.return_value.game_version = 'dofus2'
            structure.return_value.get_weapon_for_item.return_value = \
                _weapon(base_crit)
            return _get_weapon_rate(_named('Any Weapon'), None, solution)

    def test_a_total_under_zero_rates_the_normal_hit_alone(self):
        for base_crit, crit_hits in ((25, -25), (25, -40), (5, -90)):
            with self.subTest(base=base_crit, ch=crit_hits):
                self.assertAlmostEqual(10.0, self._rate(base_crit, crit_hits))

    def test_a_total_of_one_weighs_the_crit_at_one_percent(self):
        self.assertAlmostEqual(0.99 * 10.0 + 0.01 * 35.0, self._rate(25, -24))


class TheDofus2TurnTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus2')

    def tearDown(self):
        set_current_game_version('dofus3')

    def _stats(self, crit_hits):
        stats = {stat.key: 0
                 for stat in get_structure('dofus2').get_stats_list()}
        stats.update({'str': 800, 'int': 800, 'cha': 800, 'agi': 800,
                      'pow': 150, 'dam': 40, 'cridam': 60, 'ch': crit_hits})
        return stats

    @staticmethod
    def _without_crits(spells):
        out = []
        for spell in spells:
            plain = copy.copy(spell)
            plain.crit_alternatives = []
            out.append(plain)
        return out

    def test_a_turn_under_zero_crit_lands_only_normal_hits(self):
        classes = sorted(get_damage_spells_for_version('dofus2'))
        self.assertTrue(classes)
        crits_count_at_zero = 0
        for char_class in classes:
            for level in (1, 100, 200):
                spells = castable_spells(char_class, level, 'dofus2')
                if not spells:
                    continue
                plain = self._without_crits(spells)
                with self.subTest(char_class=char_class, level=level):
                    below, _o = best_turn(self._stats(-200), spells, 11,
                                          game_version='dofus2')
                    alone, _o = best_turn(self._stats(-200), plain, 11,
                                          game_version='dofus2')
                    self.assertAlmostEqual(alone, below, places=6)
                at_zero, _o = best_turn(self._stats(0), spells, 11,
                                        game_version='dofus2')
                plain_at_zero, _o = best_turn(self._stats(0), plain, 11,
                                              game_version='dofus2')
                crits_count_at_zero += at_zero > plain_at_zero + 1e-6
        self.assertGreater(crits_count_at_zero, 0,
                           'no turn gains from its crits at 0 either, so the '
                           'comparison under zero proves nothing')
