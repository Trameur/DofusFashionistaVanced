# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A conditional drop whose code get_resource_sources cannot parse still shows a label."""

import re
import sqlite3

from django.test import SimpleTestCase

from chardata.workshop_sources import get_resource_sources
from fashionistapulp.fashionista_config import get_items_db_path

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch')
_PLAYER_LEVEL_ONLY = re.compile(r'PL[<>]\d+(&PL[<>]\d+)*')


def _a_resource_with_an_unparsed_condition_in_its_top_three(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        resource_ids = [row[0] for row in conn.execute(
            "SELECT DISTINCT resource_ankama_id FROM resource_drops "
            "WHERE conditions IS NOT NULL AND conditions != ''")]
        for resource_id in resource_ids:
            rows = conn.execute(
                "SELECT conditions FROM resource_drops "
                "WHERE resource_ankama_id = ? ORDER BY rate DESC LIMIT 3",
                (resource_id,)).fetchall()
            for (conditions,) in rows:
                if conditions and not _PLAYER_LEVEL_ONLY.fullmatch(conditions):
                    return resource_id
    finally:
        conn.close()
    return None


class UnparsedConditionalDropsStillShowALabelTests(SimpleTestCase):

    def test_a_non_player_level_condition_still_produces_a_visible_label(self):
        checked = 0
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                resource_id = _a_resource_with_an_unparsed_condition_in_its_top_three(
                    game_version)
                if resource_id is None:
                    continue
                sources = get_resource_sources(
                    [(resource_id, 'resources')], game_version, 'en')
                monsters = sources['%d:resources' % resource_id]['monsters']
                conditioned = [m for m in monsters if m['has_conditions']]
                self.assertTrue(
                    conditioned,
                    '%s: resource %s lost its conditioned monster'
                    % (game_version, resource_id))
                for monster in conditioned:
                    self.assertTrue(
                        monster['conditions_text'],
                        '%s: a conditional drop must show a label' % game_version)
                checked += 1
        self.assertGreater(
            checked, 0, 'no version had an unparsed conditional drop to test')
