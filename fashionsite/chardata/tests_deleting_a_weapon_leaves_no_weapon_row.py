# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Deleting a weapon clears its rows from every weapon table the database has, range and uses per turn included."""
import os
import shutil
import sqlite3
import tempfile
from unittest import mock

from django.test import SimpleTestCase

EROTEGG_BOW = 32235
OTHER_VERSIONS = ('beta', 'dofus2', 'touch', 'retro')


def _weapon_tables(conn):
    names = [name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
             if name.startswith('weapon_')]
    return sorted(name for name in names
                  if 'item' in [column[1] for column in conn.execute('PRAGMA table_info(%s)' % name)])


def _rows_by_table(path, item_id):
    conn = sqlite3.connect(path)
    try:
        return {table: conn.execute('SELECT COUNT(*) FROM %s WHERE item = ?' % table,
                                    (item_id,)).fetchone()[0]
                for table in _weapon_tables(conn)}
    finally:
        conn.close()


def _first_weapon(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute('SELECT item FROM weapon_ap ORDER BY item LIMIT 1').fetchone()[0]
    finally:
        conn.close()


class DeletingAWeaponLeavesNoWeaponRowTests(SimpleTestCase):

    def _delete_in_a_copy(self, version, item_id=None):
        from fashionistapulp import modify_items_db
        from fashionistapulp.fashionista_config import get_items_db_path
        with tempfile.TemporaryDirectory() as directory:
            copy = os.path.join(directory, 'items.db')
            shutil.copyfile(get_items_db_path(version), copy)
            if item_id is None:
                item_id = _first_weapon(copy)
            before = _rows_by_table(copy, item_id)
            with mock.patch.object(modify_items_db, 'get_items_db_path', return_value=copy), \
                    mock.patch.object(modify_items_db, 'save_items_db_to_dump') as saved:
                modify_items_db.delete_weapon(item_id)
            after = _rows_by_table(copy, item_id)
        self.assertTrue(saved.called)
        return before, after

    def test_a_dofus3_weapon_loses_its_range_and_uses_per_turn_rows(self):
        before, after = self._delete_in_a_copy('dofus3', EROTEGG_BOW)
        self.assertEqual(1, before['weapon_range'])
        self.assertEqual(1, before['weapon_uses_per_turn'])
        self.assertEqual({table: 0 for table in before}, after)

    def test_a_database_without_the_range_table_still_deletes_every_weapon_row(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        for version in OTHER_VERSIONS:
            with self.subTest(version=version):
                conn = sqlite3.connect(get_items_db_path(version))
                try:
                    tables = _weapon_tables(conn)
                finally:
                    conn.close()
                self.assertNotIn('weapon_range', tables)
                before, after = self._delete_in_a_copy(version)
                self.assertTrue(any(before.values()))
                self.assertEqual({table: 0 for table in before}, after)
