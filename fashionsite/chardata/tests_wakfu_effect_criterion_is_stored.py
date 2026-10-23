import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import build_wakfu_db as builder  # noqa: E402
import get_wakfu_client  # noqa: E402

GROUP_EFFECT = 164893
GROUP_EFFECT_TEXT = 'GetCharac("HP", "target") < 80000'
CLIENT_DIR = Path(SCRAPER) / 'wakfu_client'


def newest_tables():
    found = sorted(CLIENT_DIR.glob('*/tables.json'),
                   key=lambda path: get_wakfu_client.version_key(path.parent.name))
    if not found:
        return None
    with open(found[-1], encoding='utf-8') as handle:
        return json.load(handle)


def an_effect(ident, **fields):
    row = {'id': ident, 'action_id': 330, 'container_id': 7, 'container_type': 'ITEM_EQUIP',
           'root_container_type': 'ITEM_EQUIP', 'normal_or_critical': 'NORMAL',
           'area_shape': 1, 'area_size': [], 'params': [1.0, 0.0]}
    row.update(fields)
    return row


class TheStoredEffectCriterionIsTheClientsTests(SimpleTestCase):
    def setUp(self):
        self.tables = newest_tables()
        if self.tables is None or not builder.WAKFU_DB.exists():
            self.skipTest('no decoded Wakfu client or database; run get_wakfu_client.py')
        self.db = sqlite3.connect('file:%s?mode=ro' % builder.WAKFU_DB, uri=True)
        self.addCleanup(self.db.close)
        columns = [row[1] for row in self.db.execute('PRAGMA table_info(effects)')]
        if 'criterion' not in columns:
            self.skipTest('the database predates the effect criterion; run build_wakfu_db.py')

    def test_every_stored_criterion_is_the_stripped_text_of_the_same_client_effect(self):
        client = {effect['id']: effect['criterion'] for effect in self.tables['effects']}
        stored = self.db.execute('SELECT id, criterion FROM effects').fetchall()
        self.assertGreater(len(stored), 100000)
        wrong = [(ident, text) for ident, text in stored
                 if client[ident] != text or text != text.strip() or text is None]
        self.assertEqual([], wrong[:5])

    def test_an_ability_and_a_set_effect_carry_a_criterion(self):
        for root in ('ABILITY', 'SET'):
            count = self.db.execute(
                "SELECT COUNT(*) FROM effects WHERE root_container_type = ?"
                " AND criterion != ''", (root,)).fetchone()[0]
            self.assertGreater(count, 0, root)

    def test_the_hit_point_threshold_effect_holds_its_text(self):
        row = self.db.execute(
            'SELECT root_container_type, criterion FROM effects WHERE id = ?',
            (GROUP_EFFECT,)).fetchone()
        self.assertEqual(('ABILITY', GROUP_EFFECT_TEXT), row)


class TheBuilderNeedsTheDecodedCriterionTests(SimpleTestCase):
    def test_a_tables_payload_without_a_criterion_is_refused(self):
        tables = {'item_ids': [7], 'effects': [an_effect(100)], 'groups': [], 'states': [],
                  'sets': [], 'abilities': [], 'ability_categories': []}
        with self.assertRaisesMessage(ValueError, 'decode the client again'):
            builder.write_client_tables(mock.Mock(), tables, {})

    def test_a_failed_build_keeps_the_previous_database(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            db = directory / 'items_wakfu.db'
            dump = directory / 'transformed_wakfu.json'
            item = {'id': 10, 'name': {'en': 'Helmet', 'fr': 'Casque'}, 'level': 50,
                    'type_id': 134, 'type_name': {'en': 'Helmet', 'fr': 'Casque'},
                    'positions': ['HEAD'], 'disables': [], 'rarity': 3, 'set_id': None,
                    'gfx_id': 1010, 'two_handed': False, 'exclusive': None,
                    'lines': [{'stat': 'HP', 'value': 100}]}
            dump.write_text(json.dumps({'version': '1.0', 'equipment': [item]}),
                            encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                builder.build(dump, db, str(directory / 'raw'))
            before = db.read_bytes()
            tables = {'item_ids': [10], 'effects': [an_effect(100)], 'groups': [],
                      'states': [], 'sets': [], 'abilities': [], 'ability_categories': []}
            with mock.patch.object(builder, 'find_client_tables',
                                   side_effect=lambda d, v, name='tables.json':
                                   tables if name == 'tables.json' else None):
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(ValueError):
                        builder.build(dump, db, str(directory / 'raw'),
                                      str(directory / 'client'))
            self.assertEqual(before, db.read_bytes())


class AnOldDecodedFolderIsDecodedAgainTests(SimpleTestCase):
    def test_a_decoded_json_without_tables_format_is_not_current(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'decoded.json').write_text(
                json.dumps({'files': {'a.jar': {'sha1': 'x'}}}), encoding='utf-8')
            (folder / 'tables.json').write_text('{}', encoding='utf-8')
            families = {family: {} for family in get_wakfu_client.wakfu_client.ALL_TEXT_FAMILIES}
            (folder / 'texts.json').write_text(json.dumps({'texts': families}),
                                               encoding='utf-8')
            self.assertFalse(get_wakfu_client.is_current(folder, {'a.jar': 'x'}))
            (folder / 'decoded.json').write_text(
                json.dumps({'files': {'a.jar': {'sha1': 'x'}},
                            'tables_format': get_wakfu_client.TABLES_FORMAT}),
                encoding='utf-8')
            self.assertTrue(get_wakfu_client.is_current(folder, {'a.jar': 'x'}))
