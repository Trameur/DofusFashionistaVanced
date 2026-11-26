# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest import TestCase, mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'itemscraper'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import build_wakfu_db as builder  # noqa: E402
import update_all  # noqa: E402


class AWakfuItemIsNamedFromTheTitlesItHasTests(TestCase):
    """An item keeps the titles Ankama gives it, and no title means no item."""

    def setUp(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.db = self.directory / 'items_wakfu.db'

    def item(self, ident, names):
        return {'id': ident, 'name': names, 'level': 50, 'type_id': 103,
                'type_name': {'en': 'Ring', 'fr': 'Anneau'}, 'positions': ['LEFT_HAND', 'RIGHT_HAND'],
                'disables': [], 'rarity': 3, 'set_id': None, 'gfx_id': 1000 + ident, 'two_handed': False,
                'exclusive': None, 'lines': [{'stat': 'HP', 'value': 100}]}

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

    def structure(self):
        from fashionistapulp import structure as structure_module
        with mock.patch.object(structure_module, 'get_items_db_path', return_value=str(self.db)):
            return structure_module.Structure('wakfu')

    def test_an_item_titled_in_french_only_takes_its_french_title_as_its_name(self):
        output = self.build(self.item(10, {'fr': 'Bague fleurie'}),
                            self.item(11, {'en': 'Ring', 'fr': 'Anneau', 'de': 'Ring'}))
        self.assertEqual([(10, 'Bague fleurie'), (11, 'Ring')], self.rows('SELECT id, name FROM items ORDER BY id'))
        self.assertEqual([('fr', 'Bague fleurie')], self.rows('SELECT language, name FROM item_names WHERE item = 10'))
        self.assertIn('missing translation, named in fr', output)

    def test_an_item_titled_in_no_language_is_left_out(self):
        output = self.build(self.item(10, {}), self.item(11, {'en': 'Ring', 'fr': 'Anneau'}))
        self.assertEqual([(11,)], self.rows('SELECT id FROM items'))
        self.assertEqual([], self.rows('SELECT item FROM item_names WHERE item = 10'))
        self.assertEqual([], self.rows('SELECT item FROM item_picture WHERE item = 10'))
        self.assertIn('title not found in any language, not shown', output)

    def test_the_site_loads_a_build_holding_an_item_titled_in_one_language(self):
        self.build(self.item(10, {'fr': 'Bague fleurie'}), self.item(11, {}),
                   self.item(12, {'en': 'Ring', 'fr': 'Anneau', 'es': 'Anillo', 'pt': 'Anel', 'de': 'Ring'}))
        structure = self.structure()
        self.assertIsNone(structure.get_item_by_id(11))
        french_only = structure.get_item_by_id(10)
        self.assertEqual('Bague fleurie', french_only.name)
        self.assertEqual('Bague fleurie', french_only.localized_names['fr'])
        self.assertEqual('[!] Bague fleurie', french_only.localized_names['es'])
        self.assertEqual('Anillo', structure.get_item_by_id(12).localized_names['es'])

    def test_the_recap_keeps_both_counts(self):
        output = self.build(self.item(10, {'fr': 'Bague fleurie'}), self.item(11, {}),
                            self.item(12, {'en': 'Ring', 'fr': 'Anneau'}))
        notices = update_all.log_notices(output.splitlines())
        self.assertTrue(any('missing translation, named in fr' in line for line in notices), notices)
        self.assertTrue(any('title not found in any language, not shown' in line for line in notices), notices)
