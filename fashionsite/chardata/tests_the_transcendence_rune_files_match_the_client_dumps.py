# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The shipped transcendence rune files match their client dumps and keep the Beta-only runes out of live."""

import json
import os
from pathlib import Path

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module
from fashionistapulp import transcendence

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_ROOT = os.path.join(REPO_ROOT, 'itemscraper', 'raw')
LOOP_BETA_ROOT = os.path.join(os.path.expanduser('~'), 'Documents', 'fashionista-loop',
                              'meta', 'dofus3_3.8')
NEW_BETA_RUNES = {29679: ('ap', 111), 29680: ('mp', 128), 29681: ('range', 117),
                  29682: ('summon', 182)}


def _table(version):
    path = os.path.join(transcendence.DEFAULT_FOLDER, '%s.json' % version)
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def _dump(version, tag):
    candidates = [os.path.join(RAW_ROOT, tag)]
    if version == 'beta':
        candidates.append(os.path.join(LOOP_BETA_ROOT, 'raw_%s' % tag))
    for folder in candidates:
        if os.path.isfile(os.path.join(folder, 'items.json')):
            return folder
    return None


def _extract(folder):
    return itemscraper_module('store_transcendence_runes').read_runes(folder)


def _count_rune_items(folder):
    items, _flag = itemscraper_module('store_weapon_conversions')._modern_items(folder)
    return sum(1 for record, _lines, _weapon in items.values() if record.get('typeId') == 211)


class TranscendenceRuneFilesMatchTheirDumpsTests(SimpleTestCase):

    def _check_matches(self, version):
        table = _table(version)
        folder = _dump(version, table['source_tag'])
        if folder is None:
            self.skipTest('no raw dump for %s (%s) on this machine, file untested'
                          % (version, table['source_tag']))
        self.assertEqual(table['count'], _count_rune_items(folder))
        self.assertEqual(len(table['runes']), table['count'])
        self.assertEqual(table['runes'], _extract(folder))
        self._check_density(table, folder)

    def _check_density(self, table, folder):
        module = itemscraper_module('store_transcendence_runes')
        effects = itemscraper_module('get_spells')._load_datacenter_table(Path(folder) / 'effects.json')
        for rune in table['runes']:
            rate = effects[rune['action']]['effectPowerRate']
            self.assertEqual(rune['density'], module.normalize_rate(float(rate)), rune['id'])

    def test_the_beta_file_matches_its_dump(self):
        self._check_matches('beta')

    def test_the_dofus3_file_matches_the_live_dump_count(self):
        self._check_matches('dofus3')

    def test_the_dofus2_file_matches_the_dofus2_dump_count(self):
        self._check_matches('dofus2')


class TranscendenceRuneFilesContentTests(SimpleTestCase):

    def test_the_beta_file_counts_the_four_new_runes_with_their_action_bonus_weight_and_level(self):
        runes = {rune['id']: rune for rune in transcendence.load_runes('beta')}
        self.assertEqual(len(runes), 85)
        for item_id, (stat_key, action) in NEW_BETA_RUNES.items():
            rune = runes[item_id]
            self.assertEqual((rune['stat_key'], rune['action']), (stat_key, action))
            self.assertEqual((rune['bonus'], rune['weight'], rune['level']), (1, 80, 208))
            self.assertTrue(rune['beta_only'])
            self.assertEqual(sorted(rune['notice']), ['de', 'en', 'es', 'fr', 'pt'])
            self.assertEqual(sorted(rune['names']), ['de', 'en', 'es', 'fr', 'pt'])

    def test_the_beta_file_carries_the_density_of_the_four_new_runes(self):
        runes = {rune['id']: rune for rune in transcendence.load_runes('beta')}
        densities = {item_id: runes[item_id]['density'] for item_id in NEW_BETA_RUNES}
        self.assertEqual(densities, {29679: 100, 29680: 90, 29681: 51, 29682: 30})

    def test_only_the_four_new_runes_are_beta_only(self):
        flagged = {rune['id'] for rune in transcendence.load_runes('beta') if rune['beta_only']}
        self.assertEqual(flagged, set(NEW_BETA_RUNES))

    def test_no_beta_only_rune_is_in_the_dofus3_or_dofus2_file(self):
        for version in ('dofus3', 'dofus2'):
            runes = transcendence.load_runes(version)
            self.assertEqual(len(runes), 81, version)
            self.assertFalse([rune['id'] for rune in runes if rune['beta_only']], version)
            self.assertFalse(set(NEW_BETA_RUNES) & {rune['id'] for rune in runes}, version)

    def test_a_version_without_a_file_has_no_rune(self):
        self.assertEqual(transcendence.load_runes('retro'), [])
