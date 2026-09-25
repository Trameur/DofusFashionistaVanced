# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The workshop job summary is a direct SQL MAX(level) over the list's items."""

import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopItem
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

BASE_JOB_ANKAMA_ID = 1


def _two_items_sharing_a_job(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        shared = conn.execute(
            'SELECT job_ankama_id FROM item_craft_jobs WHERE job_ankama_id != ? '
            'GROUP BY job_ankama_id HAVING COUNT(DISTINCT item) > 1 LIMIT 1',
            (BASE_JOB_ANKAMA_ID,)).fetchone()
        if shared is None:
            return None, []
        job_ankama_id = shared[0]
        item_ids = [row[0] for row in conn.execute(
            'SELECT item FROM item_craft_jobs WHERE job_ankama_id = ? '
            'ORDER BY item LIMIT 3', (job_ankama_id,))]
    finally:
        conn.close()
    return job_ankama_id, item_ids


def _expected_max_level(game_version, job_ankama_id, item_ids):
    placeholders = ','.join('?' * len(item_ids))
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            'SELECT MAX(level) FROM item_craft_jobs '
            'WHERE job_ankama_id = ? AND item IN (%s)' % placeholders,
            [job_ankama_id] + item_ids).fetchone()
    finally:
        conn.close()
    return row[0]


def _job_name(game_version, job_ankama_id):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            "SELECT name FROM job_names WHERE job_ankama_id = ? AND language = 'en'",
            (job_ankama_id,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


class TheJobSummaryMatchesADirectSqlMaxTests(TestCase):

    def test_the_shown_level_equals_a_direct_sql_max(self):
        job_ankama_id, item_ids = _two_items_sharing_a_job('dofus3')
        self.assertIsNotNone(job_ankama_id, 'no job shared by two dofus3 items')
        expected_level = _expected_max_level('dofus3', job_ankama_id, item_ids)
        job_name = _job_name('dofus3', job_ankama_id)
        self.assertIsNotNone(job_name)

        structure = get_structure('dofus3')
        user = User.objects.create_user('jobsum', 'jobsum@test.local', 'pw-4242xy')
        for item_id in item_ids:
            item = structure.get_item_by_id(item_id)
            if item is None:
                continue
            WorkshopItem.objects.create(
                user=user, item_id=item.id, game_version='dofus3', quantity=1)
        self.client.force_login(user)

        page = self.client.get('/workshop/', follow=True)
        self.assertEqual(200, page.status_code)
        body = page.content.decode('utf-8')

        self.assertIn(job_name, body)
        self.assertIn(str(expected_level), body)
