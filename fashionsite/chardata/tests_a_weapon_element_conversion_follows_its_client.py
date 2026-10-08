# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each version's weapon element conversions are what its client states,
and the forge helpers convert a weapon as the site does."""
import os
import re

from django.conf import settings
from django.test import SimpleTestCase

from chardata.tests import itemscraper_module
from fashionistapulp import weapon_forge
from fashionistapulp.dofus_constants import (AIR, EARTH, FIRE, NEUTRAL, WATER,
                                             DamageDigest)
from fashionistapulp.game_versions import get_game_version
from fashionistapulp.structure import get_structure

_VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PIPELINES = (('update_data.py', 'dofus3'), ('update_data_beta.py', 'beta'),
              ('update_data_dofus2.py', 'dofus2'), ('update_data_touch.py', 'touch'),
              ('update_data_retro.py', 'retro'))
_ELEMENTS = (EARTH, FIRE, WATER, AIR)
_POTION_TYPE = 26
_ENGRAVING_TYPE = 258
_SHARD_TYPE = 335
_NAMING_CLIENTS = ('dofus3', 'beta', 'dofus2')
_WEAPON_CURSE = 19637
_BLORD_SCYTHE = 8992
_KUKRI_KURA = 8932
_KOUARTZ_WAND = 6519


def _extracted(version):
    store = itemscraper_module('store_weapon_conversions')
    stored = weapon_forge.load(version)
    tag = stored.get('data_version')
    if not os.path.exists(store.source_path(version, tag)):
        return None
    return store.extract(version, tag, stored['languages'])


def _rates(version):
    return {(kind, tier): weapon_forge.rate(version, kind, tier)
            for kind in weapon_forge.kinds(version)
            for tier in weapon_forge.tiers(version, kind)}


def _ladder(kinds, rates):
    return {(kind, tier): rate for kind in kinds
            for tier, rate in zip(weapon_forge.TIERS, rates)}


def _types(version, kind):
    return {row['type_id'] for row in weapon_forge.load(version)['conversions']
            if row['kind'] == kind}


def _rows(hits):
    if hits is None:
        return None
    return [(hit.min_dam, hit.max_dam, hit.element, bool(hit.steals), bool(hit.heals))
            for hit in hits]


def _crit_rows(weapon, element):
    return None if weapon.crit_hits is None else _rows(weapon.crit_hits[element])


def _as_structure_converts(version, element, ankama_id):
    if not weapon_forge.can_forge(version, ankama_id):
        return {}
    game = get_game_version(version)
    choice = {'damage': (element, game.weapon_element_rate)}
    if game.element_potion_heals:
        choice['heal'] = (element, game.weapon_element_rate)
    return choice


def _weapons(structure):
    yield from structure.weapons_by_key.items()
    yield from structure.dt_weapons_by_key.items()


class EachStoredTableIsItsClientsTests(SimpleTestCase):

    def test_each_stored_table_is_what_its_client_files_give(self):
        for version in _VERSIONS:
            with self.subTest(version=version):
                extracted = _extracted(version)
                if extracted is None:
                    self.skipTest('no %s client files on this machine' % version)
                table, notes = extracted
                self.assertEqual([], notes)
                self.assertEqual(weapon_forge.load(version), table)

    def test_dofus3_and_the_beta_keep_all_or_a_tenth_of_each_neutral_line(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertEqual({(kind, tier): rate
                                  for kind in weapon_forge.KINDS
                                  for tier, rate in (('strong', 1.0), ('weak', 0.1))},
                                 _rates(version))
                self.assertEqual({_POTION_TYPE}, _types(version, 'damage'))
                self.assertEqual({_ENGRAVING_TYPE}, _types(version, 'steal'))
                self.assertEqual({_SHARD_TYPE}, _types(version, 'heal'))
                self.assertEqual([60, 120, 180, 200],
                                 sorted(gem['max_weapon_level']
                                        for gem in weapon_forge.load(version)['gems']))

    def test_dofus2_potions_and_engravings_keep_85_68_or_50_percent(self):
        self.assertEqual(_ladder(('damage', 'steal'), (0.85, 0.68, 0.5)), _rates('dofus2'))
        self.assertEqual({_POTION_TYPE}, _types('dofus2', 'damage'))
        self.assertEqual({_ENGRAVING_TYPE}, _types('dofus2', 'steal'))
        self.assertEqual([], weapon_forge.load('dofus2')['gems'])

    def test_touch_converts_neutral_damage_with_potions_only(self):
        self.assertEqual(_ladder(('damage',), (0.85, 0.68, 0.5)), _rates('touch'))
        self.assertEqual({_POTION_TYPE}, _types('touch', 'damage'))
        self.assertEqual([], weapon_forge.load('touch')['gems'])

    def test_retro_names_its_potions_and_publishes_no_rate(self):
        table = weapon_forge.load('retro')
        self.assertFalse(table['rate_published'])
        self.assertEqual(_ladder(('damage',), (None, None, None)), _rates('retro'))
        self.assertTrue(table['languages'])
        for row in table['conversions']:
            with self.subTest(ankama_id=row['ankama_id']):
                self.assertEqual(set(table['languages']), set(row['names']))
                self.assertTrue(all(row['names'].values()))

    def test_retro_potions_carry_the_element_and_level_touch_gives_them(self):
        def by_id(version):
            return {row['ankama_id']: (row['element'], row['level'], row['tier'])
                    for row in weapon_forge.load(version)['conversions']}
        self.assertEqual(by_id('touch'), by_id('retro'))

    def test_the_codes_touch_borrows_are_what_every_naming_client_states(self):
        store = itemscraper_module('store_weapon_conversions')
        for version in _NAMING_CLIENTS:
            folder = store._modern_dir(version, weapon_forge.load(version)['data_version'])
            if not os.path.exists(os.path.join(folder, 'effects.json')):
                continue
            codes = store.client_codes(folder)
            for code, named in store.TOUCH_CODES.items():
                with self.subTest(version=version, code=code):
                    self.assertEqual(named, codes.get(code))

    def test_a_change_of_any_stored_field_is_a_warning(self):
        store = itemscraper_module('store_weapon_conversions')
        previous = weapon_forge.load('retro')
        table = weapon_forge.load('retro')
        table['rate_note'] = 'published'
        table['unforgeable'] = table['unforgeable'][1:]
        lines = store.changes(previous, table)
        self.assertIn('rate_note changed: %s -> published' % previous['rate_note'], lines)
        self.assertIn('unforgeable removed: %s' % previous['unforgeable'][:1], lines)
        self.assertEqual([], store.changes(previous, dict(previous, data_version='9.9')))


class WhichWeaponTakesAConversionTests(SimpleTestCase):

    def test_the_weapon_curse_takes_none_on_dofus3(self):
        self.assertFalse(weapon_forge.can_forge('dofus3', _WEAPON_CURSE))

    def test_the_blord_scythe_takes_one_on_dofus3_and_the_beta(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertTrue(weapon_forge.can_forge(version, _BLORD_SCYTHE))

    def test_a_retro_weapon_takes_a_potion_exactly_when_it_takes_an_exo(self):
        structure = get_structure('retro')
        weapons = [item for item in structure.get_concatenated_items_lists()
                   if structure.get_type_name_by_id(item.type) == 'Weapon'
                   and item.ankama_id is not None]
        self.assertTrue([item for item in weapons if not item.forgeable])
        self.assertEqual([], [item.ankama_id for item in weapons
                              if weapon_forge.can_forge('retro', item.ankama_id)
                              != item.forgeable])

    def test_a_version_without_a_table_converts_nothing(self):
        self.assertEqual((), weapon_forge.kinds('wakfu'))
        self.assertFalse(weapon_forge.can_forge('wakfu', _KUKRI_KURA))

    def test_a_german_name_touch_does_not_serve_falls_back_to_english(self):
        self.assertNotIn('de', weapon_forge.load('touch')['languages'])
        row = weapon_forge.load('touch')['conversions'][0]
        self.assertEqual(row['names']['en'],
                         weapon_forge.name('touch', row['ankama_id'], 'de'))


class TheHelpersConvertAsTheSiteDoesTests(SimpleTestCase):

    def test_convert_and_compose_leave_their_input_alone(self):
        hits = [DamageDigest(10, 21, NEUTRAL), DamageDigest(12, 42, NEUTRAL, heals=True),
                DamageDigest(4, 8, EARTH)]
        before = _rows(hits)
        converted = weapon_forge.convert(hits[0], FIRE, 0.85)
        composed, critical = weapon_forge.compose(
            hits, 7, {'damage': (FIRE, 0.85), 'heal': (FIRE, 0.85)})
        self.assertEqual(before, _rows(hits))
        self.assertEqual([(8, 17, FIRE, False, False)], _rows([converted]))
        self.assertEqual([(8, 17, FIRE, False, False), (10, 35, FIRE, False, True),
                          (4, 8, EARTH, False, False)], _rows(composed))
        self.assertEqual([(15, 24, FIRE, False, False), (17, 42, FIRE, False, True),
                          (11, 15, EARTH, False, False)], _rows(critical))
        made = [converted] + composed + critical
        self.assertEqual(len(made), len({id(hit) for hit in made} - {id(hit) for hit in hits}))

    def test_compose_gives_the_rows_structure_gives_for_sample_weapons(self):
        for version in _VERSIONS:
            structure = get_structure(version)
            for ankama_id in (_KUKRI_KURA, _KOUARTZ_WAND, _BLORD_SCYTHE):
                weapon = structure.get_weapon_for_item(
                    structure.get_item_by_ankama_id(ankama_id))
                for element in _ELEMENTS:
                    with self.subTest(version=version, ankama_id=ankama_id, element=element):
                        hits, critical = weapon_forge.compose(
                            weapon.base_hit, weapon.crit_bonus if weapon.has_crits else None,
                            _as_structure_converts(version, element, ankama_id))
                        self.assertEqual(_rows(weapon.non_crit_hits[element]), _rows(hits))
                        self.assertEqual(_crit_rows(weapon, element), _rows(critical))

    def test_compose_gives_every_weapon_the_rows_structure_gives(self):
        for version in _VERSIONS:
            structure = get_structure(version)
            differing, converted = [], 0
            for key, weapon in _weapons(structure):
                crit_bonus = weapon.crit_bonus if weapon.has_crits else None
                converted += bool(weapon.is_mageable)
                ankama_id = key if isinstance(key, int) else None
                for element in _ELEMENTS:
                    hits, critical = weapon_forge.compose(
                        weapon.base_hit, crit_bonus,
                        _as_structure_converts(version, element, ankama_id))
                    if (_rows(hits) != _rows(weapon.non_crit_hits[element])
                            or _rows(critical) != _crit_rows(weapon, element)):
                        differing.append((key, element))
            with self.subTest(version=version):
                self.assertGreater(converted, 0)
                self.assertEqual([], differing)


class TheTablesFollowTheDataUpdateTests(SimpleTestCase):

    def test_each_versioned_table_was_stored_from_the_site_data(self):
        for version in ('dofus3', 'beta', 'dofus2'):
            with self.subTest(version=version):
                self.assertEqual(settings.SITE_VERSIONS[version],
                                 weapon_forge.load(version)['data_version'],
                                 'run itemscraper/store_weapon_conversions.py'
                                 ' --game-version %s' % version)

    def test_a_3_7_or_later_conversion_keeps_the_whole_roll_of_every_kind(self):
        for version, label in settings.SITE_VERSIONS.items():
            patch = tuple(int(part) for part in label.split('.')[:2])
            if patch[0] != 3 or patch < (3, 7):
                continue
            with self.subTest(version=version, label=label):
                self.assertTrue(weapon_forge.kinds(version))
                for kind in weapon_forge.kinds(version):
                    self.assertEqual(1.0, weapon_forge.rate(version, kind, 'strong'))

    def test_every_pipeline_stores_its_own_version_table(self):
        for name, version in _PIPELINES:
            with open(os.path.join(_REPO, name), encoding='utf-8') as handle:
                found = re.search(r'step\("items/weapon-conversions", \[(.*?)\]',
                                  handle.read(), re.S)
            with self.subTest(pipeline=name):
                self.assertIsNotNone(found)
                self.assertRegex(found.group(1), r'"--game-version",\s*"%s"' % version)
                if version == 'retro':
                    self.assertRegex(found.group(1), r'"--lang",\s*args\.lang')

    def test_every_version_backs_up_its_table_before_an_update(self):
        audit = itemscraper_module('update_audit')
        for version in _VERSIONS:
            with self.subTest(version=version):
                names = {audit.relative_name(path) for path in audit.version_files(version)}
                self.assertIn('fashionistapulp/fashionistapulp/weapon_conversions/%s.json'
                              % version, names)
