# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An items-only rebuild gets back, from the copy taken before it, the tables it did not write."""
import importlib.util
import os
import sqlite3
import tempfile

from django.test import SimpleTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def keep_db_tables():
    spec = importlib.util.spec_from_file_location(
        'keep_db_tables', os.path.join(ROOT, 'itemscraper', 'keep_db_tables.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class APartialItemRebuildKeepsTheTablesItDoesNotWriteTests(SimpleTestCase):

    def database(self, path, script):
        conn = sqlite3.connect(path)
        conn.executescript(script)
        conn.commit()
        conn.close()

    def test_only_the_missing_tables_come_back_with_their_rows_and_indexes(self):
        module = keep_db_tables()
        with tempfile.TemporaryDirectory() as work:
            before = os.path.join(work, 'before.db')
            after = os.path.join(work, 'after.db')
            self.database(before, 'CREATE TABLE items (id INTEGER, name TEXT);'
                                  "INSERT INTO items VALUES (1, 'old');"
                                  'CREATE TABLE item_drops (item INTEGER, monster INTEGER);'
                                  'INSERT INTO item_drops VALUES (1, 7), (1, 8);'
                                  'CREATE INDEX item_drops_item ON item_drops (item);')
            self.database(after, 'CREATE TABLE items (id INTEGER, name TEXT);'
                                 "INSERT INTO items VALUES (1, 'new'), (2, 'added');")
            self.assertEqual(['item_drops'], module.keep_missing_tables(before, after))
            conn = sqlite3.connect(after)
            try:
                self.assertEqual([(1, 'new'), (2, 'added')],
                                 conn.execute('SELECT id, name FROM items ORDER BY id').fetchall())
                self.assertEqual([(1, 7), (1, 8)],
                                 conn.execute('SELECT item, monster FROM item_drops ORDER BY monster').fetchall())
                self.assertEqual([('item_drops_item',)], conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'item_drops'").fetchall())
            finally:
                conn.close()
            self.assertEqual([], module.keep_missing_tables(before, after))
