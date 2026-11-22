# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The weight per point of every forgemagie stat is the one the game files give."""

from pathlib import Path

from django.test import SimpleTestCase

from chardata.forgemagie_data import get_fm_stat
from chardata.tests import itemscraper_module
from chardata.tests_the_transcendence_rune_files_match_the_client_dumps import _dump, _table
from fashionistapulp import transcendence
from fashionistapulp.transcendence_terms import TRANSCENDENCE_VERSIONS

SMITHMAGIC_RUNE_TYPE_ID = 78


def _rune_densities(folder):
    store = itemscraper_module('store_transcendence_runes')
    effect_id_of = itemscraper_module('get_spells').effect_id_of
    effects = store._load_datacenter_table(Path(folder) / 'effects.json')
    english = store._translations(folder).get('en', {})
    items, _flag = store._modern_items(folder)
    found = {}
    for record, lines, _weapon in items.values():
        if record.get('typeId') != SMITHMAGIC_RUNE_TYPE_ID:
            continue
        for line in lines:
            action = effect_id_of(line)
            key = store.stat_key(action, effects, english)
            if key is not None:
                found.setdefault(key, set()).add(store._density(action, effects))
    return found


class TheForgemagieWeightsMatchTheGameTests(SimpleTestCase):

    def test_every_transcendence_rune_weighs_what_the_table_says(self):
        for version in TRANSCENDENCE_VERSIONS:
            for rune in transcendence.load_runes(version):
                with self.subTest(version=version, rune=rune['id']):
                    stat = get_fm_stat(version, rune['stat_key'])
                    self.assertIsNotNone(stat)
                    self.assertEqual(float(rune['density']), float(stat['density']))

    def test_the_dofus2_melee_and_ranged_resistance_runes_weigh_fifteen(self):
        for key in ('respermee', 'resperran'):
            self.assertEqual(get_fm_stat('dofus2', key)['density'], 15)
            self.assertEqual(get_fm_stat('dofus3', key)['density'], 10)

    def test_every_smithmagic_rune_of_the_dumps_weighs_what_the_table_says(self):
        folders = {version: _dump(version, _table(version)['source_tag'])
                   for version in TRANSCENDENCE_VERSIONS}
        if not any(folders.values()):
            self.skipTest('no raw dump on this machine, weights untested')
        for version, folder in folders.items():
            if folder is None:
                continue
            densities = _rune_densities(folder)
            self.assertGreater(len(densities), 40, version)
            for key, found in sorted(densities.items()):
                with self.subTest(version=version, stat=key):
                    self.assertEqual(len(found), 1, found)
                    stat = get_fm_stat(version, key)
                    self.assertIsNotNone(stat)
                    self.assertEqual(float(next(iter(found))), float(stat['density']))
