# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An item the game files dropped comes back from the copy taken before the rebuild, hidden, with its rows."""
import os
import sqlite3
import tempfile

from django.test import SimpleTestCase

from chardata.tests_a_partial_item_rebuild_keeps_the_tables_it_does_not_write import keep_db_tables

SCHEMA = ('CREATE TABLE sets (id INTEGER PRIMARY KEY, name TEXT);'
          'CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, item_set INTEGER, removed INTEGER);'
          'CREATE TABLE stats_of_item (item INTEGER, stat INTEGER, value INTEGER);'
          'CREATE TABLE item_names (item INTEGER, language TEXT, name TEXT);'
          'CREATE TABLE set_bonus (item_set INTEGER, stat INTEGER);')
UPDATE_TOUCH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            'update_data_touch.py')


class AnItemThatLeftTheGameFilesStaysHiddenTests(SimpleTestCase):

    def database(self, path, script):
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA + script)
        conn.commit()
        conn.close()

    def rebuild(self, work):
        before = os.path.join(work, 'before.db')
        after = os.path.join(work, 'after.db')
        self.database(before, "INSERT INTO sets VALUES (5, 'gone set'), (6, 'kept set');"
                              "INSERT INTO items VALUES (1, 'kept', 6, NULL), (2, 'dropped', 5, NULL),"
                              " (3, 'dropped too', 6, NULL);"
                              'INSERT INTO stats_of_item VALUES (1, 10, 4), (2, 10, 7), (3, 11, 2);'
                              "INSERT INTO item_names VALUES (2, 'fr', 'parti');")
        self.database(after, "INSERT INTO sets VALUES (6, 'kept set');"
                             "INSERT INTO items VALUES (1, 'kept', 6, NULL), (4, 'added', NULL, NULL);"
                             'INSERT INTO stats_of_item VALUES (1, 10, 5), (4, 12, 1);')
        return before, after

    def test_the_dropped_items_come_back_hidden_with_their_rows(self):
        module = keep_db_tables()
        with tempfile.TemporaryDirectory() as work:
            before, after = self.rebuild(work)
            self.assertEqual([2, 3], module.keep_retired_items(before, after))
            conn = sqlite3.connect(after)
            try:
                self.assertEqual([(1, 'kept', 6, None), (2, 'dropped', None, 1), (3, 'dropped too', 6, 1),
                                  (4, 'added', None, None)],
                                 conn.execute('SELECT id, name, item_set, removed FROM items ORDER BY id').fetchall())
                self.assertEqual([(1, 10, 5), (2, 10, 7), (3, 11, 2), (4, 12, 1)],
                                 conn.execute('SELECT * FROM stats_of_item ORDER BY item').fetchall())
                self.assertEqual([(2, 'fr', 'parti')], conn.execute('SELECT * FROM item_names').fetchall())
            finally:
                conn.close()
            self.assertEqual([], module.keep_retired_items(before, after))

    def test_a_first_build_has_nothing_to_keep(self):
        module = keep_db_tables()
        with tempfile.TemporaryDirectory() as work:
            _before, after = self.rebuild(work)
            self.assertEqual([], module.keep_retired_items(os.path.join(work, 'missing.db'), after))

    def test_the_touch_pipeline_keeps_them_around_the_database_load(self):
        with open(UPDATE_TOUCH, encoding='utf-8') as handle:
            text = handle.read()
        save, load, retire = (text.index('"items/keep-save"'), text.index('"items/load-db"'),
                              text.index('"items/keep-retired"'))
        self.assertLess(save, load)
        self.assertLess(load, retire)
