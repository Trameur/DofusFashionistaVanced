# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""get_resource_sources lists a resource's monsters best rate first."""

import random
import sqlite3

from django.test import SimpleTestCase

from chardata.workshop_sources import get_resource_sources
from fashionistapulp.fashionista_config import get_items_db_path

VERSIONS = ('dofus3', 'beta', 'dofus2', 'retro', 'touch')
SEED = 20260925
SAMPLE_PER_VERSION = 6


def _resources_with_drops(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        return [row[0] for row in conn.execute(
            'SELECT DISTINCT resource_ankama_id FROM resource_drops')]
    finally:
        conn.close()


def _best_rate(game_version, ankama_id):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            'SELECT MAX(rate) FROM resource_drops WHERE resource_ankama_id = ?',
            (ankama_id,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _resource_count(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        with_drop = conn.execute(
            'SELECT COUNT(DISTINCT resource_ankama_id) FROM resource_drops').fetchone()[0]
        total = conn.execute(
            "SELECT COUNT(DISTINCT ingredient_ankama_id) FROM item_recipe_ingredient_names "
            "WHERE ingredient_subtype = 'resources'").fetchone()[0]
    finally:
        conn.close()
    return with_drop, total


class TheFirstMonsterHasTheBestDropRateTests(SimpleTestCase):

    def test_a_seeded_sample_lists_the_highest_rate_first(self):
        chance = random.Random(SEED)
        checked = 0
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                candidates = _resources_with_drops(game_version)
                self.assertTrue(candidates,
                                'no resource with a drop in %s' % game_version)
                sample = chance.sample(
                    candidates, min(SAMPLE_PER_VERSION, len(candidates)))
                for ankama_id in sample:
                    expected_best = _best_rate(game_version, ankama_id)
                    sources = get_resource_sources(
                        [(ankama_id, 'resources')], game_version, 'en')
                    monsters = sources['%d:resources' % ankama_id]['monsters']
                    self.assertTrue(
                        monsters,
                        'seed %d: %s has no listed monster' % (SEED, ankama_id))
                    self.assertEqual(
                        expected_best, monsters[0]['rate'],
                        'seed %d: %s did not list the best rate first'
                        % (SEED, ankama_id))
                    self.assertLessEqual(len(monsters), 3)
                    checked += 1
        self.assertGreaterEqual(checked, len(VERSIONS) * 2, 'seed %d' % SEED)

    def test_the_share_of_resources_with_a_monster_is_printed(self):
        for game_version in VERSIONS:
            with_drop, total = _resource_count(game_version)
            share = (100.0 * with_drop / total) if total else 0.0
            print('%s: %d/%d resources have at least one monster (%.1f%%)'
                  % (game_version, with_drop, total, share))
            self.assertGreater(total, 0, 'no resource ingredient in %s' % game_version)
