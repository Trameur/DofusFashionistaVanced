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


class ARemovedWakfuItemKeepsItsIdTests(TestCase):
    def setUp(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.db = self.directory / 'items_wakfu.db'

    def item(self, ident, name, type_id=134):
        return {'id': ident, 'name': {'en': name, 'fr': name + ' fr'}, 'level': 50, 'type_id': type_id,
                'type_name': {'en': 'Helmet', 'fr': 'Casque'}, 'positions': ['HEAD'], 'disables': [],
                'rarity': 3, 'set_id': None, 'gfx_id': 1000 + ident, 'two_handed': False, 'exclusive': None,
                'lines': [{'stat': 'HP', 'value': 100}, {'stat': 'MP', 'value': 1}]}

    def build(self, *items):
        dump = self.directory / 'transformed_wakfu.json'
        dump.write_text(json.dumps({'version': '1.0', 'equipment': list(items)}), encoding='utf-8')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            builder.main(['--dump', str(dump), '--db', str(self.db), '--out', str(self.directory / 'raw')])
        return output.getvalue()

    def rows(self, query):
        connection = sqlite3.connect(self.db)
        try:
            return connection.execute(query).fetchall()
        finally:
            connection.close()

    def test_an_item_the_new_build_lost_stays_under_its_id_flagged_removed(self):
        self.build(self.item(10, 'Old Helmet'), self.item(11, 'Kept Helmet'))
        output = self.build(self.item(11, 'Kept Helmet'), self.item(12, 'New Helmet'))
        self.assertIn('kept 1 items this build no longer has, flagged removed', output)
        self.assertEqual([(10, 1), (11, 0), (12, 0)], self.rows('SELECT id, removed FROM items ORDER BY id'))
        self.assertEqual([(10, 'equipment')], self.rows('SELECT ankama_id, ankama_type FROM items WHERE id = 10'))
        self.assertEqual({('en', 'Old Helmet'), ('fr', 'Old Helmet fr')},
                         set(self.rows('SELECT language, name FROM item_names WHERE item = 10')))
        self.assertEqual([(2,)], self.rows('SELECT COUNT(*) FROM stats_of_item WHERE item = 10'))
        self.assertEqual([(1010,)], self.rows('SELECT gfx FROM item_picture WHERE item = 10'))
        self.assertEqual([(3,)], self.rows('SELECT rarity FROM item_rarity WHERE item = 10'))

    def test_a_removed_item_stays_kept_through_later_builds_and_comes_back_live(self):
        self.build(self.item(10, 'Old Helmet'), self.item(11, 'Kept Helmet'))
        self.build(self.item(11, 'Kept Helmet'))
        self.assertIn('kept 1 items', self.build(self.item(11, 'Kept Helmet')))
        self.assertEqual([(10, 1), (11, 0)], self.rows('SELECT id, removed FROM items ORDER BY id'))
        self.assertIn('kept 0 items', self.build(self.item(10, 'Old Helmet'), self.item(11, 'Kept Helmet')))
        self.assertEqual([(10, 0), (11, 0)], self.rows('SELECT id, removed FROM items ORDER BY id'))
        self.assertEqual([(2,)], self.rows('SELECT COUNT(*) FROM item_names WHERE item = 10'))

    def test_a_removed_item_keeps_a_type_the_new_build_no_longer_has(self):
        self.build(self.item(10, 'Old Cape', type_id=132), self.item(11, 'Kept Helmet'))
        self.build(self.item(11, 'Kept Helmet'))
        self.assertEqual([(132,), (134,)], self.rows('SELECT id FROM item_types ORDER BY id'))
        self.assertEqual([(132, 'HEAD')], self.rows('SELECT item_type, position FROM item_type_position'
                                                    ' WHERE item_type = 132'))

    def test_the_site_hides_the_removed_item_but_still_resolves_its_id(self):
        self.build(self.item(10, 'Old Helmet'), self.item(11, 'Kept Helmet'))
        self.build(self.item(11, 'Kept Helmet'))
        from fashionistapulp import structure as structure_module
        with mock.patch.object(structure_module, 'get_items_db_path', return_value=str(self.db)):
            structure = structure_module.Structure('wakfu')
        self.assertTrue(structure.get_item_by_id(10).removed)
        available = [item.id for item in structure.get_available_items_list()]
        self.assertNotIn(10, available)
        self.assertIn(11, available)
