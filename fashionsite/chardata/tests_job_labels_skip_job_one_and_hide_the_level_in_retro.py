# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Card job labels: never job 1 ("Base"), no level number in Retro."""

import re
import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopItem
from chardata.workshop_sources import get_item_craft_jobs
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

BASE_JOB_ANKAMA_ID = 1


def _an_item_with_a_non_base_job(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            'SELECT item FROM item_craft_jobs WHERE job_ankama_id != ? LIMIT 1',
            (BASE_JOB_ANKAMA_ID,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _base_job_name(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            "SELECT name FROM job_names WHERE job_ankama_id = ? AND language = 'en'",
            (BASE_JOB_ANKAMA_ID,)).fetchone()
    finally:
        conn.close()
    return row[0] if row else None


class NoCardEverShowsTheBaseJobTests(TestCase):

    def test_job_one_is_never_returned(self):
        for game_version in ('dofus3', 'beta', 'dofus2', 'retro', 'touch'):
            with self.subTest(game_version=game_version):
                conn = sqlite3.connect(get_items_db_path(game_version))
                try:
                    item_ids = [row[0] for row in conn.execute(
                        'SELECT DISTINCT item FROM item_craft_jobs')]
                finally:
                    conn.close()
                self.assertTrue(item_ids, 'no craft job at all in %s' % game_version)
                info = get_item_craft_jobs(item_ids, game_version, 'en')
                base_name = _base_job_name(game_version)
                names = {row['job_name'] for row in info['items'].values()}
                if base_name:
                    self.assertNotIn(base_name, names)


class RetroCardsNeverShowANumericLevelTests(TestCase):

    def test_retro_levels_are_hidden(self):
        item_id = _an_item_with_a_non_base_job('retro')
        self.assertIsNotNone(item_id, 'no non-base craft job in retro')
        info = get_item_craft_jobs([item_id], 'retro', 'en')
        self.assertIn(item_id, info['items'])
        self.assertIsNone(info['items'][item_id]['level'])

    def test_dofus3_keeps_its_level(self):
        item_id = _an_item_with_a_non_base_job('dofus3')
        self.assertIsNotNone(item_id, 'no non-base craft job in dofus3')
        info = get_item_craft_jobs([item_id], 'dofus3', 'en')
        self.assertIn(item_id, info['items'])
        self.assertIsNotNone(info['items'][item_id]['level'])


class TheWorkshopCardShowsAJobLabelTests(TestCase):

    def test_a_card_with_a_recipe_shows_its_job_but_never_job_one(self):
        structure = get_structure('dofus3')
        item_id = _an_item_with_a_non_base_job('dofus3')
        self.assertIsNotNone(item_id)
        item = structure.get_item_by_id(item_id)
        self.assertIsNotNone(item, 'the sampled item is not in the live structure')

        user = User.objects.create_user('jobcard', 'jobcard@test.local', 'pw-4242xy')
        WorkshopItem.objects.create(
            user=user, item_id=item.id, game_version='dofus3', quantity=1)
        self.client.force_login(user)
        page = self.client.get('/workshop/', follow=True)
        self.assertEqual(200, page.status_code)
        body = page.content.decode('utf-8')

        match = re.search(r'ws-craft-job">([^<]*)<', body)
        self.assertIsNotNone(match, 'the page ships no job label')
        base_name = _base_job_name('dofus3')
        if base_name:
            self.assertNotIn(base_name, match.group(1))
