# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Touch a weapon with no base critical chance never crits."""
import collections
from unittest import mock

from django.test import SimpleTestCase

from chardata.item_exchange import _get_weapon_info, _get_weapon_rate
from fashionistapulp.dofus_constants import NEUTRAL, DamageDigest
from fashionistapulp.structure import get_structure, set_current_game_version
from fashionistapulp.weapon import Weapon


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


class _Mocked(SimpleTestCase):

    def _rate_and_info(self, version, base_crit, crit_hits):
        solution = _solution(crit_hits)
        with mock.patch('chardata.item_exchange.get_structure') as structure, \
                mock.patch('chardata.item_exchange.get_solution',
                           return_value=solution):
            structure.return_value.game_version = version
            structure.return_value.get_weapon_by_name.return_value = \
                _weapon(base_crit)
            rate = _get_weapon_rate(_named('Any Weapon'), None, solution)
            info = _get_weapon_info(_named('Any Weapon'), None)
        return rate, info


class TheTouchWeaponRatingFollowsTheCriticalRuleTests(_Mocked):

    def test_base_zero_gets_no_crit_share_whatever_the_stat(self):
        rate, info = self._rate_and_info('touch', 0, 60)
        self.assertAlmostEqual(rate, 10.0)
        self.assertAlmostEqual(info['rating'], 10.0)
        self.assertNotIn('min_crit_dam', info)
        self.assertNotIn('max_crit_dam', info)

    def test_base_twenty_five_adds_the_stat(self):
        rate, info = self._rate_and_info('touch', 25, 30)
        self.assertAlmostEqual(rate, 0.45 * 10.0 + 0.55 * 35.0)
        self.assertEqual(info['min_crit_dam'], 140)
        self.assertEqual(info['max_crit_dam'], 140)

    def test_odds_stop_at_one_hundred_percent(self):
        rate, _ = self._rate_and_info('touch', 50, 60)
        self.assertAlmostEqual(rate, 35.0)

    def test_odds_never_drop_under_one_percent(self):
        rate, _ = self._rate_and_info('touch', 5, -20)
        self.assertAlmostEqual(rate, 0.99 * 10.0 + 0.01 * 35.0)


class TheTouchRuleStaysOnTouchTests(_Mocked):

    MODERN = ((30, 90, 40.0), (5, -20, 6.25))
    LEGACY_CASES = {
        'dofus3': MODERN,
        'beta': MODERN,
    }

    def test_dofus3_and_beta_keep_the_legacy_rating(self):
        for version, cases in self.LEGACY_CASES.items():
            for base_crit, crit_hits, expected in cases:
                with self.subTest(version=version, base=base_crit, ch=crit_hits):
                    rate, info = self._rate_and_info(version, base_crit, crit_hits)
                    self.assertAlmostEqual(rate, expected)
                    self.assertEqual(info['min_crit_dam'], 140)


class TheTouchCatalogueTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('touch')
        self.structure = get_structure('touch')

    def tearDown(self):
        set_current_game_version('dofus3')

    def _weapons(self, base_crit):
        found = []
        for key, weapon in self.structure.weapons_by_key.items():
            if not str(key).isdigit() or not weapon.ap or not weapon.base_hit:
                continue
            if not weapon.has_crits:
                continue
            if (weapon.crit_chance or 0) != base_crit:
                continue
            item = self.structure.get_item_by_id(int(key))
            if item is None or self.structure.get_weapon_by_name(item.name) is not weapon:
                continue
            found.append(item)
        return found

    def _rate_and_info(self, item, crit_hits):
        solution = _solution(crit_hits)
        solution.stats_total.update({'str': 800, 'pow': 150, 'dam': 40})
        with mock.patch('chardata.item_exchange.get_solution',
                        return_value=solution):
            return (_get_weapon_rate(item, None, solution),
                    _get_weapon_info(item, None))

    def test_a_weapon_that_cannot_crit_ignores_critical_hits(self):
        weapons = self._weapons(0)
        self.assertTrue(weapons)
        for item in weapons:
            with self.subTest(weapon=item.name):
                without, _ = self._rate_and_info(item, 0)
                rate, info = self._rate_and_info(item, 60)
                self.assertAlmostEqual(rate, without)
                self.assertNotIn('min_crit_dam', info)

    def test_a_weapon_at_twenty_five_percent_keeps_its_crits(self):
        weapons = self._weapons(25)
        self.assertTrue(weapons)
        for item in weapons:
            with self.subTest(weapon=item.name):
                without, _ = self._rate_and_info(item, 0)
                rate, info = self._rate_and_info(item, 30)
                self.assertGreater(rate, without)
                self.assertIn('min_crit_dam', info)
