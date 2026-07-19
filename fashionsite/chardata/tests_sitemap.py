# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Sitemap quality thresholds.

The sitemap must only submit encyclopedia pages that carry real content:
thousands of one-line monster and resource pages pushed for indexing read
as "low value content" to crawlers and ad reviews (AdSense refusal of
2026-07-10). Thin pages stay served and internally linked, they are just
not submitted.

Separate module from tests.py so it can evolve without touching the shared
test file (the worktree is shared with a second session).
"""

import sqlite3

from django.test import TestCase

from fashionistapulp.fashionista_config import get_items_db_path


def _monster_by_drop_count(version, minimum=None, maximum=None):
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        rows = conn.execute(
            """
            SELECT m, SUM(n) AS total FROM (
                SELECT monster_ankama_id AS m, COUNT(*) AS n
                FROM resource_drops GROUP BY 1
                UNION ALL
                SELECT monster_ankama_id, COUNT(*) FROM item_drops GROUP BY 1
            ) GROUP BY m ORDER BY m
            """).fetchall()
    finally:
        conn.close()
    for monster_id, total in rows:
        if minimum is not None and total < minimum:
            continue
        if maximum is not None and total > maximum:
            continue
        return monster_id
    return None


class SitemapQualityThresholdTests(TestCase):
    def _sitemap(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode('utf-8')

    def test_single_drop_monsters_are_not_submitted(self):
        thin = _monster_by_drop_count('retro', maximum=1)
        rich = _monster_by_drop_count('retro', minimum=2)
        self.assertIsNotNone(thin)
        self.assertIsNotNone(rich)
        xml = self._sitemap()
        self.assertNotIn('/retro/encyclopedia/monster/%d-' % thin, xml)
        self.assertIn('/retro/encyclopedia/monster/%d-' % rich, xml)

    def test_thin_resources_are_not_submitted(self):
        # A resource with a single recipe usage and no drops is a one-line
        # page; one with several usages or a drop section carries content.
        conn = sqlite3.connect(get_items_db_path('retro'))
        try:
            row = conn.execute(
                """
                WITH usage_counts AS (
                    SELECT ingredient_ankama_id AS ankama_id,
                           ingredient_subtype AS subtype, COUNT(*) AS uses
                    FROM item_recipes GROUP BY 1, 2
                )
                SELECT u.ankama_id FROM usage_counts u
                WHERE u.subtype = 'resources' AND u.uses = 1
                  AND NOT EXISTS (SELECT 1 FROM resource_drops d
                                  WHERE d.resource_ankama_id = u.ankama_id)
                ORDER BY u.ankama_id LIMIT 1
                """).fetchone()
            rich_row = conn.execute(
                """
                SELECT ingredient_ankama_id FROM item_recipes
                WHERE ingredient_subtype = 'resources'
                GROUP BY ingredient_ankama_id HAVING COUNT(*) >= 2
                ORDER BY ingredient_ankama_id LIMIT 1
                """).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(rich_row)
        xml = self._sitemap()
        if row is not None:
            self.assertNotIn(
                '/retro/encyclopedia/resource/resources/%d-' % row[0], xml)
        self.assertIn(
            '/retro/encyclopedia/resource/resources/%d-' % rich_row[0], xml)
