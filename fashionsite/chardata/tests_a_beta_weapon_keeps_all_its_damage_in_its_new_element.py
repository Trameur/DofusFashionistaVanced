# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A weapon element potion keeps 100% of the neutral damage from Dofus 3.7, 85% before."""
import sqlite3
from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import FIRE, NEUTRAL
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.game_versions import dofus_versions, get_game_version
from fashionistapulp.modelresult import ModelResultItem
from fashionistapulp.structure import get_structure, set_current_game_version

_KUKRI = 'Kukri Kura'
_HIDSAD_BOW = 1355
_GOLDEN_SCARABUGLY_WAND = 8118


def _rows(hits):
    return [(hit.min_dam, hit.max_dam, hit.element, bool(hit.heals))
            for hit in hits]


def _weapon(version, ankama_id):
    structure = get_structure(version)
    return structure.get_weapon_for_item(
        structure.get_item_by_ankama_id(ankama_id))


class ABetaWeaponKeepsAllItsDamageInItsNewElementTests(SimpleTestCase):

    def test_the_kukri_kura_hits_fire_for_its_whole_neutral_roll(self):
        weapon = get_structure('beta').get_weapon_by_name(_KUKRI)
        self.assertEqual([(10, 21, NEUTRAL, False)] * 2, _rows(weapon.base_hit))
        self.assertEqual([(10, 21, FIRE, False)] * 2,
                         _rows(weapon.non_crit_hits[FIRE]))
        self.assertEqual([(17, 28, FIRE, False)] * 2,
                         _rows(weapon.crit_hits[FIRE]))

    def test_dofus3_still_keeps_85_percent_of_the_roll(self):
        weapon = get_structure('dofus3').get_weapon_by_name(_KUKRI)
        self.assertEqual([(10, 21, NEUTRAL, False)] * 2, _rows(weapon.base_hit))
        self.assertEqual([(8, 17, FIRE, False)] * 2,
                         _rows(weapon.non_crit_hits[FIRE]))
        self.assertEqual([(15, 24, FIRE, False)] * 2,
                         _rows(weapon.crit_hits[FIRE]))

    def test_a_neutral_heal_stays_neutral_on_the_beta(self):
        weapon = _weapon('beta', _HIDSAD_BOW)
        self.assertEqual([(12, 42, NEUTRAL, False), (12, 42, NEUTRAL, True)],
                         _rows(weapon.base_hit))
        self.assertEqual([(12, 42, FIRE, False), (12, 42, NEUTRAL, True)],
                         _rows(weapon.non_crit_hits[FIRE]))

    def test_a_weapon_whose_only_neutral_line_heals_takes_no_potion(self):
        weapon = _weapon('beta', _GOLDEN_SCARABUGLY_WAND)
        self.assertEqual([(11, 30, NEUTRAL, True)], _rows(weapon.base_hit))
        self.assertFalse(weapon.is_mageable)
        self.assertEqual(_rows(weapon.base_hit),
                         _rows(weapon.non_crit_hits[FIRE]))

    def test_no_version_that_still_converts_heals_has_a_neutral_heal_line(self):
        for key in dofus_versions():
            if not get_game_version(key).element_potion_heals:
                continue
            connection = sqlite3.connect(
                'file:%s?mode=ro' % get_items_db_path(key), uri=True)
            try:
                found = connection.execute(
                    'SELECT COUNT(*) FROM weapon_hits'
                    ' WHERE element = ? AND heals = 1', (NEUTRAL,)).fetchone()[0]
            finally:
                connection.close()
            with self.subTest(version=key):
                self.assertEqual(0, found)


class TheTurnSwingsTheWeaponAsItsVersionConvertsItTests(SimpleTestCase):

    def _swing(self, version):
        from chardata.spells_view import _weapon_castable
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(version)
        structure = get_structure(version)
        result_item = ModelResultItem(structure.get_item_by_name(_KUKRI))
        stats = {stat.key: 0 for stat in structure.get_stats_list()}
        stats['int'] = 500
        result_item.mage_weapon_smartly(stats)
        castable = _weapon_castable(
            SimpleNamespace(items={'Weapon': [result_item]}))
        return (result_item.element_maged, _rows(castable.hits),
                _rows(castable.crit_alternatives[0]))

    def test_the_beta_swings_the_whole_roll_in_fire(self):
        self.assertEqual((FIRE, [(10, 21, FIRE, False)] * 2,
                          [(17, 28, FIRE, False)] * 2),
                         self._swing('beta'))

    def test_dofus3_swings_85_percent_of_it(self):
        self.assertEqual((FIRE, [(8, 17, FIRE, False)] * 2,
                          [(15, 24, FIRE, False)] * 2),
                         self._swing('dofus3'))


class TheElementPotionFollowsTheDataPatchTests(SimpleTestCase):

    def test_the_potion_keeps_the_whole_roll_and_spares_heals_from_patch_3_7(self):
        for key in ('dofus3', 'beta'):
            label = settings.SITE_VERSIONS[key]
            patch = tuple(int(part) for part in label.split('.')[:2])
            version = get_game_version(key)
            expected = (1.0, False) if patch >= (3, 7) else (0.85, True)
            with self.subTest(version=key, label=label):
                self.assertEqual(
                    expected,
                    (version.weapon_element_rate, version.element_potion_heals),
                    '%s data is %s: update weapon_element_rate and'
                    ' element_potion_heals in game_versions.py' % (key, label))
