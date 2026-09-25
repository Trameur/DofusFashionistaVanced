# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""get_resource_sources flags crafted by id alone, for every ingredient subtype."""

import random
import sqlite3

from django.test import SimpleTestCase

from chardata.item_sources import get_source_ankama_ids
from chardata.workshop_sources import get_resource_sources
from fashionistapulp.fashionista_config import get_items_db_path

VERSIONS = ('dofus3', 'beta', 'dofus2', 'retro', 'touch')
SEED = 20260925
SAMPLE_PER_VERSION = 8


def _ingredient_keys(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        return conn.execute(
            "SELECT DISTINCT ingredient_ankama_id, ingredient_subtype "
            "FROM item_recipe_ingredient_names").fetchall()
    finally:
        conn.close()


class TheCraftedFlagMatchesTheCraftableIdSetTests(SimpleTestCase):

    def test_crafted_is_true_only_for_ids_with_their_own_recipe(self):
        chance = random.Random(SEED)
        checked_true = 0
        checked_false = 0
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                keys = _ingredient_keys(game_version)
                if not keys:
                    continue
                craftable_ids = get_source_ankama_ids(game_version)['craftable']
                sample = chance.sample(
                    keys, min(SAMPLE_PER_VERSION, len(keys)))
                for ankama_id, subtype in sample:
                    sources = get_resource_sources(
                        [(ankama_id, subtype)], game_version, 'en')
                    entry = sources['%d:%s' % (ankama_id, subtype)]
                    expected = ankama_id in craftable_ids
                    self.assertEqual(
                        expected, entry['crafted'],
                        '%s: %s:%s expected crafted=%s'
                        % (game_version, ankama_id, subtype, expected))
                    if expected:
                        checked_true += 1
                    else:
                        checked_false += 1
        self.assertGreater(checked_true, 0, 'no craftable ingredient sampled')
        self.assertGreater(checked_false, 0, 'no non-craftable ingredient sampled')
