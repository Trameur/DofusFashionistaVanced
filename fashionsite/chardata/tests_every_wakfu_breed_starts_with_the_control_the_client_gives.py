import json
import os
import sqlite3
import sys
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'itemscraper'))

import build_wakfu_db  # noqa: E402

CLIENT_DIR = ROOT / 'itemscraper' / 'wakfu_client'


def written(breeds, defaults):
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE breeds (id INTEGER, name TEXT)')
    conn.execute('CREATE TABLE breed_base_values (breed INTEGER, stat INTEGER, value INTEGER)')
    stat_ids = {'CONTROL': 1, 'HP': 2, 'WISDOM': 3}
    counts = {'breeds': 0, 'breed base values': 0}
    build_wakfu_db.write_breeds(conn, {'breeds': breeds}, stat_ids, counts, defaults)
    return {(breed, {1: 'control', 2: 'hp', 3: 'wisdom'}[stat]): value for breed, stat, value
            in conn.execute('SELECT breed, stat, value FROM breed_base_values')}


class TheBreedWriterStartsEachStatAtTheClientDefaultTests(SimpleTestCase):
    def test_a_stat_the_breed_record_lacks_starts_at_its_client_default(self):
        found = written([{'id': 1, 'name': 'A', 'base': {'HP': 50}}],
                        {'LEADERSHIP': 1, 'HP': 7, 'WISDOM': 0})
        self.assertEqual({(1, 'control'): 1, (1, 'hp'): 50}, found)

    def test_the_breed_record_wins_over_the_client_default(self):
        found = written([{'id': 1, 'name': 'A', 'base': {'WISDOM': 4}}], {'WISDOM': 9})
        self.assertEqual({(1, 'wisdom'): 4}, found)

    def test_no_default_adds_nothing(self):
        found = written([{'id': 1, 'name': 'A', 'base': {'HP': 50}}], None)
        self.assertEqual({(1, 'hp'): 50}, found)


class EveryWakfuBreedStartsWithTheControlTheClientGivesTests(SimpleTestCase):
    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.bases = get_structure('wakfu').get_breed_base_values()
        if not self.bases:
            self.skipTest('the Wakfu database holds no breed table')
        dump_path = ROOT / 'itemscraper' / 'transformed_wakfu.json'
        if not dump_path.exists():
            self.skipTest('no Wakfu dump; run update_data_wakfu.py')
        with open(dump_path, encoding='utf-8') as handle:
            version = json.load(handle)['version']
        code = build_wakfu_db.find_client_tables(CLIENT_DIR, version, 'client_code.json')
        if code is None:
            self.skipTest('no client_code.json; run itemscraper/get_wakfu_client.py')
        self.defaults = code.get('characteristic_defaults')
        if not self.defaults:
            self.skipTest('client_code.json holds no characteristic defaults')

    def test_the_client_starts_control_at_one(self):
        self.assertEqual(1, self.defaults['LEADERSHIP'])

    def test_every_breed_holds_the_client_default_control(self):
        self.assertGreaterEqual(len(self.bases), 18)
        self.assertEqual({self.defaults['LEADERSHIP']},
                         {table.get('control') for table in self.bases.values()})
