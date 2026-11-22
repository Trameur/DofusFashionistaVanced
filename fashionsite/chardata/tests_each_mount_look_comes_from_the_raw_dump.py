# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 3 and Beta mount looks are the rows the version's own client dump gives."""
import os
import sqlite3
import tempfile
from unittest import mock

from django.test import SimpleTestCase

import fashionista_version
from fashionistapulp.fashionista_config import get_items_db_path

from chardata.tests import itemscraper_module

TAGS = {'beta': fashionista_version.FASHIONISTA_BETA_VERSION,
        'dofus3': fashionista_version.FASHIONISTA_VERSION}


def _store():
    return itemscraper_module('store_mount_looks')


def _names(stem):
    return tuple(stem + language for language in ('fr', 'en', 'es', 'pt', 'de'))


def _our_items(version):
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        return dict(conn.execute("SELECT ankama_id, id FROM items WHERE ankama_type = 'mounts'"))
    finally:
        conn.close()


def _table_rows(version):
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        return sorted(conn.execute('SELECT * FROM mount_looks'))
    finally:
        conn.close()


class EachMountLookComesFromTheRawDumpTests(SimpleTestCase):

    def dump_dir(self, store, tag):
        folder = os.path.join(store.RAW_ROOT, tag)
        if not all(os.path.isfile(os.path.join(folder, name)) for name in store.FILES):
            self.skipTest('raw/%s not fetched on this machine' % tag)
        return folder

    def test_the_table_holds_the_rows_the_dump_gives(self):
        store = _store()
        for version, tag in TAGS.items():
            with self.subTest(version=version):
                folder = self.dump_dir(store, tag)
                rows, notices = store.build_rows(*store.read_dump(folder), _our_items(version))
                self.assertEqual(rows, _table_rows(version))
                self.assertEqual([], notices)

    def test_every_mount_named_like_one_item_gives_that_item_its_look(self):
        store = _store()
        for version, tag in TAGS.items():
            with self.subTest(version=version):
                folder = self.dump_dir(store, tag)
                mounts, item_names = store.read_dump(folder)
                ours = _our_items(version)
                expected = {}
                for mount_id, (key, look) in mounts.items():
                    owners = [ankama_id for ankama_id in ours if item_names.get(ankama_id) == key]
                    self.assertLessEqual(len(owners), 1, mount_id)
                    self.assertIsNotNone(store.parse_look(look), mount_id)
                    if owners:
                        bone, colours, scale = store.parse_look(look)
                        expected[ours[owners[0]]] = (bone, colours, scale)
                stored = {item: (bone, colours.split(',') if colours else [], scale)
                          for item, bone, colours, scale in _table_rows(version)}
                self.assertEqual(expected, stored)

    def test_a_shared_name_or_an_unreadable_look_stores_no_look_and_warns(self):
        store = _store()
        mounts = {1: (_names('a'), '{639||1=16772045,2=#00ff00|120}'),
                  2: (_names('b'), '{3588||1=1|90}'),
                  3: (_names('b'), '{3588||1=2|90}'),
                  4: (_names('c'), 'bad'),
                  5: (_names('d'), '{5023||1=3|100}'),
                  6: (('x', 'zen', 'y', 'z', 'w'), '{5023||1=4|100}')}
        item_names = {10: _names('a'), 11: _names('b'), 12: _names('c'), 13: _names('d'), 14: _names('d'),
                      15: ('q', 'zen', 'r', 's', 't'), 16: _names('none')}
        ours = {ankama_id: 1000000 + ankama_id for ankama_id in item_names}
        rows, notices = store.build_rows(mounts, item_names, ours)
        self.assertEqual([(1000010, 639, 'ffebcd,00ff00', 120)], rows)
        self.assertTrue(all(line.startswith('warning:') for line in notices))
        self.assertEqual(4, len(notices))
        text = '\n'.join(notices)
        self.assertIn('mount 5 has the names of items [13, 14]', text)
        self.assertIn('mounts [2, 3] share one name', text)
        self.assertIn("mount 4 has an unsupported look 'bad'", text)
        self.assertIn('item 15 and mount 6 share their en name only', text)

    def test_the_rows_come_out_sorted_by_item_not_by_mount(self):
        store = _store()
        mounts = {1: (_names('a'), '{639||1=1|100}'), 2: (_names('b'), '{3588||1=2|90}')}
        item_names = {10: _names('b'), 11: _names('a')}
        ours = {10: 1000010, 11: 1000011}
        rows, notices = store.build_rows(mounts, item_names, ours)
        self.assertEqual([(1000010, 3588, '000002', 90), (1000011, 639, '000001', 100)], rows)
        self.assertEqual([], notices)

    def test_the_name_key_holds_the_name_in_every_language_in_order(self):
        store = _store()
        labels = {language: {'7': 'Name ' + language.upper()} for language in store.LANGUAGES}
        key = store.name_key(labels, 7)
        self.assertEqual(len(store.LANGUAGES), len(key))
        self.assertEqual(tuple('name ' + language for language in store.LANGUAGES), key)
        labels['de']['7'] = 'Other'
        self.assertNotEqual(key, store.name_key(labels, 7))
        self.assertEqual(('', '', '', '', ''), store.name_key({language: {} for language in store.LANGUAGES}, 7))

    def test_a_mount_and_an_item_with_no_name_in_any_language_pair_with_nothing(self):
        store = _store()
        blank = ('',) * len(store.LANGUAGES)
        rows, notices = store.build_rows({1: (blank, '{639||1=1|100}')}, {10: blank}, {10: 1000010})
        self.assertEqual([], rows)
        self.assertEqual([], notices)

    def test_an_item_missing_from_the_dump_pairs_with_nothing(self):
        store = _store()
        rows, notices = store.build_rows({1: (_names('a'), '{639||1=1|100}')}, {}, {10: 1000010})
        self.assertEqual([], rows)
        self.assertEqual([], notices)

    def test_a_look_without_a_scale_is_drawn_at_full_size(self):
        self.assertEqual((639, ['000001'], 100), _store().parse_look('{639||1=1|}'))

    def test_too_few_rows_refuse_to_replace_the_table(self):
        store = _store()
        row = (1000010, 639, 'ffebcd', 120)
        with self.assertRaises(ValueError):
            store.check_rows([row] * (store.MIN_ROWS - 1))
        store.check_rows([row] * store.MIN_ROWS)

    def run_main(self, mounts, item_names, min_rows):
        store = _store()
        obtainment = itemscraper_module('store_item_obtainment')
        with tempfile.TemporaryDirectory() as folder:
            db_path = os.path.join(folder, 'items.db')
            dump_path = os.path.join(folder, 'items.dump')
            conn = sqlite3.connect(db_path)
            conn.execute('CREATE TABLE items (id INTEGER PRIMARY KEY, ankama_id INTEGER, ankama_type TEXT)')
            conn.executemany('INSERT INTO items VALUES (?, ?, ?)',
                             [(1000000 + ankama_id, ankama_id, 'mounts') for ankama_id in item_names])
            conn.execute('CREATE TABLE mount_looks (item INTEGER PRIMARY KEY, bone INTEGER, colors TEXT, scale INTEGER)')
            conn.execute("INSERT INTO mount_looks VALUES (5, 1, 'aaaaaa', 100)")
            conn.commit()
            conn.close()
            with mock.patch.object(store, 'read_dump', return_value=(mounts, item_names)),                     mock.patch.object(store, 'get_items_db_path', return_value=db_path),                     mock.patch.object(obtainment, '_get_items_dump_path', return_value=dump_path),                     mock.patch.object(store, 'MIN_ROWS', min_rows),                     mock.patch('builtins.print'):
                try:
                    store.main(['--tag', 'x'])
                    error = None
                except ValueError as caught:
                    error = caught
            conn = sqlite3.connect(db_path)
            table = sorted(conn.execute('SELECT * FROM mount_looks'))
            conn.close()
            return error, table, os.path.isfile(dump_path)

    def test_a_run_with_too_few_rows_leaves_the_table_and_the_dump_alone(self):
        mounts = {1: (_names('a'), '{639||1=1|100}')}
        error, table, dumped = self.run_main(mounts, {10: _names('a')}, 2)
        self.assertIsInstance(error, ValueError)
        self.assertEqual([(5, 1, 'aaaaaa', 100)], table)
        self.assertFalse(dumped)

    def test_a_good_run_rewrites_the_table_and_the_dump(self):
        mounts = {1: (_names('a'), '{639||1=1|100}'), 2: (_names('b'), '{3588||1=2|90}')}
        error, table, dumped = self.run_main(mounts, {10: _names('a'), 11: _names('b')}, 2)
        self.assertIsNone(error)
        self.assertEqual([(1000010, 639, '000001', 100), (1000011, 3588, '000002', 90)], table)
        self.assertTrue(dumped)

    def test_the_store_reads_no_third_party_host(self):
        store = _store()
        with open(store.__file__, encoding='utf-8') as handle:
            source = handle.read().lower()
        self.assertNotIn('http', source)
        self.assertNotIn('dofusdb', source)
