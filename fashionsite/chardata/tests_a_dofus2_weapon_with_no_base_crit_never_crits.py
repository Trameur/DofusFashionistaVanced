# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Dofus 2 a weapon with base critical 0 never crits and no weapon crits past 100%."""
import collections
from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from chardata.encyclopedia_view import _get_weapon_detail_lines
from chardata.item_exchange import _get_weapon_info, _get_weapon_rate
from chardata.spell_combo import crit_chance
from chardata.solution_result import evolve_result_item
from chardata.weapon_header import format_weapon_header
from fashionistapulp.dofus_constants import NEUTRAL, DamageDigest
from fashionistapulp.modelresult import ModelResultItem
from fashionistapulp.structure import get_structure, set_current_game_version
from fashionistapulp.weapon import Weapon

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
DOFUS2_ARCHONS_BOW = 14164
DOFUS2_ABATZ_SWORD = 7199


class _Pool(object):
    is_mageable = False


def _solution(crit_hits, **extra):
    stats = collections.defaultdict(int, {'ch': crit_hits, 'cridam': 100})
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
    weapon.crit_bonus = 0
    weapon.has_crits = True
    weapon.non_crit_hits = collections.defaultdict(list)
    weapon.crit_hits = collections.defaultdict(list)
    weapon.non_crit_hits[NEUTRAL] = [DamageDigest(40, 40, NEUTRAL, False, False)]
    weapon.crit_hits[NEUTRAL] = [DamageDigest(40, 40, NEUTRAL, False, False)]
    return weapon


class TheDofus2RatingTests(SimpleTestCase):

    def _rate_and_info(self, base_crit, crit_hits):
        solution = _solution(crit_hits)
        with mock.patch('chardata.item_exchange.get_structure') as structure, \
                mock.patch('chardata.item_exchange.get_solution',
                           return_value=solution):
            structure.return_value.game_version = 'dofus2'
            structure.return_value.get_weapon_by_name.return_value = \
                _weapon(base_crit)
            rate = _get_weapon_rate(_named('Any Weapon'), None, solution)
            info = _get_weapon_info(_named('Any Weapon'), None)
        return rate, info

    def test_base_zero_gets_no_crit_share_whatever_the_stat(self):
        for crit_hits in (0, 30, 60, 90):
            with self.subTest(ch=crit_hits):
                rate, info = self._rate_and_info(0, crit_hits)
                self.assertAlmostEqual(rate, 10.0)
                self.assertAlmostEqual(info['rating'], 10.0)
                self.assertNotIn('min_crit_dam', info)
                self.assertNotIn('max_crit_dam', info)

    def test_base_twenty_five_adds_the_stat(self):
        rate, info = self._rate_and_info(25, 30)
        self.assertAlmostEqual(rate, 0.45 * 10.0 + 0.55 * 35.0)
        self.assertEqual(info['min_crit_dam'], 140)
        self.assertEqual(info['max_crit_dam'], 140)

    def test_odds_stop_at_one_hundred_percent(self):
        for base_crit, crit_hits in ((25, 75), (25, 90), (30, 90), (50, 120)):
            with self.subTest(base=base_crit, ch=crit_hits):
                rate, _ = self._rate_and_info(base_crit, crit_hits)
                self.assertAlmostEqual(rate, 35.0)

    def test_a_total_under_zero_weighs_the_hit_by_the_engine_odds(self):
        for base_crit, crit_hits in ((5, -20), (25, -40)):
            with self.subTest(base=base_crit, ch=crit_hits):
                rate, _ = self._rate_and_info(base_crit, crit_hits)
                odds = crit_chance(base_crit, {'ch': crit_hits}, 'dofus2')
                self.assertAlmostEqual(rate, (1 - odds) * 10.0 + odds * 35.0)
                self.assertGreaterEqual(rate, 10.0)


class TheDofus2CatalogueTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus2')
        self.structure = get_structure('dofus2')

    def tearDown(self):
        set_current_game_version('dofus3')

    def _weapons(self, base_crit):
        found = []
        for key, weapon in self.structure.weapons_by_key.items():
            if not str(key).isdigit() or not weapon.ap or not weapon.base_hit:
                continue
            if not weapon.has_crits or (weapon.crit_chance or 0) != base_crit:
                continue
            item = self.structure.get_item_by_id(int(key))
            if item is None or self.structure.get_weapon_by_name(item.name) is not weapon:
                continue
            found.append(item)
        return found

    def _rate_and_info(self, item, crit_hits):
        solution = _solution(crit_hits, str=800, pow=150, dam=40)
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

    def test_critical_hits_past_one_hundred_percent_add_nothing(self):
        weapons = self._weapons(25)
        self.assertTrue(weapons)
        for item in weapons:
            with self.subTest(weapon=item.name):
                at_cap, _ = self._rate_and_info(item, 75)
                past_cap, _ = self._rate_and_info(item, 90)
                self.assertAlmostEqual(past_cap, at_cap)


class TheDofus2HeaderTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus2')
        self.structure = get_structure('dofus2')

    def tearDown(self):
        set_current_game_version('dofus3')

    def _header(self, item_id, language):
        item = self.structure.get_item_by_id(item_id)
        self.assertIsNotNone(item, item_id)
        lines = _get_weapon_detail_lines(self.structure, [item], language)
        self.assertTrue(lines, item_id)
        return lines[0]

    def _picker_header(self, item_id, language):
        item = self.structure.get_item_by_id(item_id)
        self.assertIsNotNone(item, item_id)
        with translation.override(language):
            result_item = ModelResultItem(item)
            evolve_result_item(result_item)
        return result_item.damage_text.split('<br>')[0]

    def test_base_zero_prints_the_cost_alone(self):
        self.assertEqual('(Bow) AP: 4',
                         format_weapon_header('dofus2', 'Bow', 4, 0, 0))
        self.assertEqual('AP: 4', format_weapon_header('dofus2', None, 4, 0, 0))
        self.assertEqual('(Bow)',
                         format_weapon_header('dofus2', 'Bow', None, 0, 0))

    def test_archons_bow_shows_no_rate_in_any_language(self):
        weapon = self.structure.get_weapon_by_name(
            self.structure.get_item_by_id(DOFUS2_ARCHONS_BOW).name)
        self.assertEqual((4, 0, 0), (weapon.ap, weapon.crit_chance,
                                     weapon.crit_bonus))
        self.assertEqual('(Bow) AP: 4', self._header(DOFUS2_ARCHONS_BOW, 'en'))
        self.assertEqual('(Bow) AP: 4',
                         self._picker_header(DOFUS2_ARCHONS_BOW, 'en'))
        for language in LANGUAGES:
            with self.subTest(language=language):
                for header in (self._header(DOFUS2_ARCHONS_BOW, language),
                               self._picker_header(DOFUS2_ARCHONS_BOW,
                                                   language)):
                    self.assertIn('4', header)
                    self.assertNotIn('%', header)

    def test_abatz_sword_keeps_its_rate(self):
        self.assertEqual('(Sword) AP: 4 / CH: 25% (+10)',
                         self._header(DOFUS2_ABATZ_SWORD, 'en'))
        self.assertEqual('(Sword) AP: 4 / CH: 25% (+10)',
                         self._picker_header(DOFUS2_ABATZ_SWORD, 'en'))

    def test_every_weapon_shows_a_rate_exactly_when_its_base_is_set(self):
        zero = 0
        for name, weapon in self.structure.weapons_dict_by_name.items():
            if weapon.ap is None or weapon.crit_chance is None:
                continue
            header = format_weapon_header('dofus2', 'Sword', weapon.ap,
                                          weapon.crit_chance,
                                          weapon.crit_bonus)
            with self.subTest(weapon=name):
                if weapon.crit_chance == 0:
                    zero += 1
                    self.assertEqual('(Sword) AP: %d' % weapon.ap, header)
                else:
                    self.assertIn('%d%%' % weapon.crit_chance, header)
        self.assertTrue(zero)
