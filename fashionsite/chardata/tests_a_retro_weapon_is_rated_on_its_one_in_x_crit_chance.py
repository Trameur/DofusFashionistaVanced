# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Retro the weapon swap ranking weighs a crit by the 1/X the client computes."""
import collections
from unittest import mock

from django.test import SimpleTestCase

from chardata.item_exchange import _get_weapon_info, _get_weapon_rate
from chardata.spell_combo import crit_chance
from fashionistapulp.dofus_constants import NEUTRAL, DamageDigest
from fashionistapulp.structure import get_structure, set_current_game_version
from fashionistapulp.weapon import Weapon

RETRO_KAISER = 233
RETRO_DUBYA_BOW = 7187


class _Pool(object):
    is_mageable = False


def _solution(crit_hits, agility, **extra):
    stats = collections.defaultdict(int, {'ch': crit_hits, 'agi': agility})
    stats.update(extra)

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
    weapon.crit_bonus = 5
    weapon.has_crits = True
    weapon.non_crit_hits = collections.defaultdict(list)
    weapon.crit_hits = collections.defaultdict(list)
    weapon.non_crit_hits[NEUTRAL] = [DamageDigest(40, 40, NEUTRAL, False, False)]
    weapon.crit_hits[NEUTRAL] = [DamageDigest(60, 60, NEUTRAL, False, False)]
    return weapon


class _Mocked(SimpleTestCase):

    def _rate_and_info(self, version, base_crit, crit_hits, agility):
        solution = _solution(crit_hits, agility)
        with mock.patch('chardata.item_exchange.get_structure') as structure, \
                mock.patch('chardata.item_exchange.get_solution',
                           return_value=solution):
            structure.return_value.game_version = version
            structure.return_value.get_weapon_for_item.return_value = \
                _weapon(base_crit)
            rate = _get_weapon_rate(_named('Any Weapon'), None, solution)
            info = _get_weapon_info(_named('Any Weapon'), None)
        return rate, info


class TheRetroRatingWeighsTheCritByOneInXTests(_Mocked):

    def test_hand_worked_cases(self):
        cases = (
            (50, 0, 0, 50),
            (50, 10, 300, 20),
            (30, 30, 0, 2),
            (200, 10, 300, 98),
            (2, 0, 0, 2),
        )
        for base, crit_hits, agility, x in cases:
            with self.subTest(base=base, ch=crit_hits, agi=agility):
                rate, info = self._rate_and_info('retro', base, crit_hits,
                                                 agility)
                self.assertAlmostEqual(rate, 10.0 + 5.0 / x)
                self.assertAlmostEqual(info['rating'], 10.0 + 5.0 / x)
                self.assertEqual(info['min_crit_dam'], 60)
                self.assertEqual(info['max_crit_dam'], 60)

    def test_the_stored_x_is_never_read_as_a_percentage(self):
        rate, _ = self._rate_and_info('retro', 50, 10, 0)
        self.assertAlmostEqual(rate, 10.0 + 5.0 / 40)
        self.assertNotAlmostEqual(rate, 0.4 * 10.0 + 0.6 * 15.0)

    def test_the_rating_uses_the_damage_engine_odds(self):
        for base in (2, 30, 50, 200):
            for crit_hits in (-10, 0, 10, 30, 60):
                for agility in (0, 100, 1000):
                    with self.subTest(base=base, ch=crit_hits, agi=agility):
                        odds = crit_chance(base, {'ch': crit_hits,
                                                  'agi': agility}, 'retro')
                        rate, _ = self._rate_and_info('retro', base,
                                                      crit_hits, agility)
                        self.assertAlmostEqual(rate, 10.0 + 5.0 * odds)

    def test_a_weapon_stored_at_minus_one_never_crits(self):
        rate, info = self._rate_and_info('retro', -1, 50, 800)
        self.assertAlmostEqual(rate, 10.0)
        self.assertNotIn('min_crit_dam', info)
        self.assertNotIn('max_crit_dam', info)


class TheRetroCatalogueTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('retro')
        self.structure = get_structure('retro')

    def tearDown(self):
        set_current_game_version('dofus3')

    def _item_and_weapon(self, item_id):
        item = self.structure.get_item_by_id(item_id)
        self.assertIsNotNone(item, item_id)
        weapon = self.structure.get_weapon_by_name(item.name)
        self.assertIsNotNone(weapon, item_id)
        return item, weapon

    def _rate_and_info(self, item, crit_hits, agility):
        solution = _solution(crit_hits, agility, str=300, dam=20)
        with mock.patch('chardata.item_exchange.get_solution',
                        return_value=solution):
            return (_get_weapon_rate(item, None, solution),
                    _get_weapon_info(item, None))

    def _weighted(self, info, ap, x):
        normal = (info['min_noncrit_dam'] + info['max_noncrit_dam']) / 2.0
        crit = (info['min_crit_dam'] + info['max_crit_dam']) / 2.0
        return (normal * (x - 1) + crit) / x / ap

    def test_kaiser_at_one_in_two_hundred(self):
        item, weapon = self._item_and_weapon(RETRO_KAISER)
        self.assertEqual((4, 200, 20), (weapon.ap, weapon.crit_chance,
                                        weapon.crit_bonus))
        for crit_hits, agility, x in ((0, 0, 200), (10, 300, 98)):
            with self.subTest(ch=crit_hits, agi=agility):
                rate, info = self._rate_and_info(item, crit_hits, agility)
                self.assertAlmostEqual(rate, self._weighted(info, 4, x))

    def test_a_one_in_two_weapon_crits_every_other_hit(self):
        item, weapon = self._item_and_weapon(RETRO_DUBYA_BOW)
        self.assertEqual(2, weapon.crit_chance)
        rate, info = self._rate_and_info(item, 0, 0)
        self.assertAlmostEqual(rate, self._weighted(info, weapon.ap, 2))

    def test_every_weapon_that_cannot_crit_shows_no_crit_range(self):
        found = []
        for key, weapon in self.structure.weapons_by_key.items():
            if not str(key).isdigit() or weapon.crit_chance != -1:
                continue
            item = self.structure.get_item_by_id(int(key))
            if item is None or self.structure.get_weapon_by_name(item.name) is not weapon:
                continue
            found.append(item)
        self.assertTrue(found)
        for item in found:
            with self.subTest(weapon=item.name):
                _rate, info = self._rate_and_info(item, 50, 800)
                self.assertNotIn('min_crit_dam', info)
