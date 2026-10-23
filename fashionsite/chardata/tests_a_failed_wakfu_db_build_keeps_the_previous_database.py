import contextlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest import TestCase, mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'itemscraper'))
import build_wakfu_db as builder


class AFailedWakfuDbBuildKeepsThePreviousDatabaseTests(TestCase):
    def setUp(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.db = self.directory / 'items_wakfu.db'
        item = {'id': 10, 'name': {'en': 'Helmet', 'fr': 'Casque'}, 'level': 50, 'type_id': 134,
                'type_name': {'en': 'Helmet', 'fr': 'Casque'}, 'positions': ['HEAD'], 'disables': [],
                'rarity': 3, 'set_id': None, 'gfx_id': 1010, 'two_handed': False, 'exclusive': None,
                'lines': [{'stat': 'HP', 'value': 100}]}
        self.dump = self.directory / 'transformed_wakfu.json'
        self.dump.write_text(json.dumps({'version': '1.0', 'equipment': [item]}), encoding='utf-8')
        self.out = self.directory / 'raw'

    def build(self):
        return builder.build(self.dump, self.db, str(self.out))

    def test_a_schema_error_leaves_the_old_database_and_no_temporary_file(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.build()
        before = self.db.read_bytes()
        with mock.patch.object(builder, 'create_tables', side_effect=sqlite3.OperationalError('boom')):
            with self.assertRaises(sqlite3.OperationalError):
                self.build()
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(['items_wakfu.db'], sorted(p.name for p in self.directory.glob('items_wakfu*')))

    def test_a_decoded_client_with_no_decoded_json_says_the_picture_table_stays_empty(self):
        client = self.directory / 'client' / 'v1'
        client.mkdir(parents=True)
        (client / 'tables.json').write_text('{}', encoding='utf-8')
        with mock.patch.object(builder, 'find_client_tables',
                               side_effect=lambda d, v, name='tables.json':
                               {} if name == 'tables.json' else None), \
                mock.patch.object(builder, 'write_client_tables'):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                builder.build(self.dump, self.db, str(self.out), str(self.directory / 'client'))
        self.assertIn('client pictures not found', output.getvalue())
