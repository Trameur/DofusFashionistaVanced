# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Dofus 3 and the beta a weapon with base critical 0 never crits."""
import collections
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from chardata.encyclopedia_view import _get_weapon_detail_lines
from chardata.item_exchange import (_get_weapon_info, _get_weapon_rate,
                                    _weapon_can_crit)
from chardata.solution_result import evolve_result_item
from chardata.spell_combo import WeaponCastable, best_turn, crit_chance
from chardata.weapon_header import format_weapon_header
from fashionistapulp.dofus_constants import NEUTRAL, BaseDamage, DamageDigest
from fashionistapulp.modelresult import ModelResultItem
from fashionistapulp.structure import get_structure, set_current_game_version
from fashionistapulp.weapon import Weapon

VERSIONS = ('dofus3', 'beta')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
ARCHONS_BOW = 14164
ABATZ_SWORD = 7199


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


class TheRankingTests(SimpleTestCase):

    def _rate_and_info(self, version, base_crit, crit_hits):
        solution = _solution(crit_hits)
        with mock.patch('chardata.item_exchange.get_structure') as structure, \
                mock.patch('chardata.item_exchange.get_solution',
                           return_value=solution):
            structure.return_value.game_version = version
            structure.return_value.get_weapon_for_item.return_value = \
                _weapon(base_crit)
            rate = _get_weapon_rate(_named('Any Weapon'), None, solution)
            info = _get_weapon_info(_named('Any Weapon'), None)
        return rate, info

    def test_base_zero_gets_no_crit_share_whatever_the_stat(self):
        for version in VERSIONS:
            for crit_hits in (0, 30, 60, 90):
                with self.subTest(version=version, ch=crit_hits):
                    rate, info = self._rate_and_info(version, 0, crit_hits)
                    self.assertAlmostEqual(10.0, rate)
                    self.assertAlmostEqual(10.0, info['rating'])
                    self.assertNotIn('min_crit_dam', info)
                    self.assertNotIn('max_crit_dam', info)

    def test_base_twenty_five_keeps_its_crits(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                rate, info = self._rate_and_info(version, 25, 30)
                self.assertAlmostEqual(0.45 * 10.0 + 0.55 * 35.0, rate)
                self.assertEqual(140, info['min_crit_dam'])


class TheTurnTests(SimpleTestCase):

    def _blade(self, base_crit):
        return SimpleNamespace(
            name='Test Blade', ap=4, uses_per_turn=1, crit_chance=base_crit,
            element_maged=None,
            non_crit_hits={NEUTRAL: [BaseDamage(20, 30, 'earth')]},
            crit_hits={NEUTRAL: [BaseDamage(40, 60, 'earth')]})

    def test_a_base_zero_weapon_lands_its_normal_hit_at_any_crit(self):
        for version in VERSIONS:
            stats = {stat.key: 0
                     for stat in get_structure(version).get_stats_list()}
            stats['str'] = 100
            with self.subTest(version=version):
                never, _o = best_turn(dict(stats, ch=0),
                                      [WeaponCastable(self._blade(0))], 4,
                                      game_version=version)
                crit_stat, _o = best_turn(dict(stats, ch=100),
                                          [WeaponCastable(self._blade(0))], 4,
                                          game_version=version)
                with_base, _o = best_turn(dict(stats, ch=100),
                                          [WeaponCastable(self._blade(30))], 4,
                                          game_version=version)
                self.assertAlmostEqual(never, crit_stat, places=6)
                self.assertGreater(with_base, crit_stat)


class TheCatalogueTests(SimpleTestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def _weapons(self, version):
        set_current_game_version(version)
        structure = get_structure(version)
        found = []
        for key, weapon in structure.weapons_by_key.items():
            if not str(key).isdigit():
                continue
            item = structure.get_item_by_id(int(key))
            if item is None or structure.get_weapon_by_name(item.name) is not weapon:
                continue
            found.append((item, weapon))
        return structure, found

    def _rate_and_info(self, item, crit_hits):
        solution = _solution(crit_hits, str=800, pow=150, dam=40)
        with mock.patch('chardata.item_exchange.get_solution',
                        return_value=solution):
            return (_get_weapon_rate(item, None, solution),
                    _get_weapon_info(item, None))

    def test_every_base_zero_weapon_ignores_critical_hits(self):
        for version in VERSIONS:
            _structure, found = self._weapons(version)
            zero = [(item, weapon) for item, weapon in found
                    if weapon.has_crits and weapon.crit_chance == 0
                    and weapon.ap]
            self.assertTrue(zero, version)
            for item, weapon in zero:
                with self.subTest(version=version, weapon=item.name):
                    without, _ = self._rate_and_info(item, 0)
                    rate, info = self._rate_and_info(item, 60)
                    self.assertAlmostEqual(without, rate)
                    self.assertNotIn('min_crit_dam', info)

    def test_the_ranking_can_crit_exactly_when_the_turn_does(self):
        for version in VERSIONS:
            structure, found = self._weapons(version)
            self.assertTrue(found, version)
            for item, weapon in found:
                if weapon.crit_chance is None:
                    continue
                with self.subTest(version=version, weapon=item.name):
                    self.assertEqual(
                        crit_chance(weapon.crit_chance, {'ch': 50}, version) > 0,
                        _weapon_can_crit(structure, weapon))

    def test_every_header_shows_a_rate_exactly_when_the_base_is_set(self):
        for version in VERSIONS:
            _structure, found = self._weapons(version)
            zero = 0
            for item, weapon in found:
                if weapon.ap is None or weapon.crit_chance is None:
                    continue
                header = format_weapon_header(version, 'Sword', weapon.ap,
                                              weapon.crit_chance,
                                              weapon.crit_bonus)
                with self.subTest(version=version, weapon=item.name):
                    if weapon.crit_chance == 0:
                        zero += 1
                        self.assertEqual('(Sword) AP: %d' % weapon.ap, header)
                    else:
                        self.assertIn('%d%%' % weapon.crit_chance, header)
            self.assertTrue(zero, version)


class TheHeaderTests(SimpleTestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def _headers(self, version, item_id, language):
        set_current_game_version(version)
        structure = get_structure(version)
        item = structure.get_item_by_id(item_id)
        self.assertIsNotNone(item, item_id)
        lines = _get_weapon_detail_lines(structure, [item], language)
        self.assertTrue(lines, item_id)
        with translation.override(language):
            result_item = ModelResultItem(item)
            evolve_result_item(result_item)
        return lines[0], result_item.damage_text.split('<br>')[0]

    def test_base_zero_prints_the_cost_alone(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual('(Bow) AP: 4',
                                 format_weapon_header(version, 'Bow', 4, 0, 0))
                self.assertEqual('AP: 4',
                                 format_weapon_header(version, None, 4, 0, 0))
                self.assertEqual('(Bow)',
                                 format_weapon_header(version, 'Bow', None, 0, 0))

    def test_archons_bow_shows_no_rate_in_any_language(self):
        for version in VERSIONS:
            set_current_game_version(version)
            structure = get_structure(version)
            weapon = structure.get_weapon_by_name(
                structure.get_item_by_id(ARCHONS_BOW).name)
            self.assertEqual((4, 0, 0), (weapon.ap, weapon.crit_chance,
                                         weapon.crit_bonus))
            self.assertEqual(('(Bow) AP: 4', '(Bow) AP: 4'),
                             self._headers(version, ARCHONS_BOW, 'en'))
            for language in LANGUAGES:
                with self.subTest(version=version, language=language):
                    for header in self._headers(version, ARCHONS_BOW, language):
                        self.assertIn('4', header)
                        self.assertNotIn('%', header)

    def test_abatz_sword_keeps_its_rate(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(('(Sword) AP: 4 / CH: 25% (+10)',) * 2,
                                 self._headers(version, ABATZ_SWORD, 'en'))
