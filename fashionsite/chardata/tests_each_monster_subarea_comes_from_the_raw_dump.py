# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus 3 and Beta monster subareas are the rows the version's own client dump gives."""
import os
import sqlite3

from django.test import SimpleTestCase

import fashionista_version
from fashionistapulp.fashionista_config import get_items_db_path

TAGS = {'beta': fashionista_version.FASHIONISTA_BETA_VERSION,
        'dofus3': fashionista_version.FASHIONISTA_VERSION}


def _store():
    from chardata.tests import itemscraper_module
    return itemscraper_module('store_monster_subareas')


def _table_rows(version):
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        return list(conn.execute('SELECT * FROM monster_subareas'))
    finally:
        conn.close()


def _known_ids(version):
    conn = sqlite3.connect(get_items_db_path(version))
    try:
        return {row[0] for row in conn.execute('SELECT DISTINCT monster_ankama_id FROM monster_names')}
    finally:
        conn.close()


class EachMonsterSubareaComesFromTheRawDumpTests(SimpleTestCase):

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
                rows, _ = store.build_rows(*store.read_dump(folder), _known_ids(version))
                table = _table_rows(version)
                self.assertEqual(set(rows), set(table))
                self.assertEqual(len(rows), len(table))

    def test_every_subarea_the_dump_names_reaches_the_table(self):
        store = _store()
        for version, tag in TAGS.items():
            with self.subTest(version=version):
                folder = self.dump_dir(store, tag)
                labels = store._labels(folder)
                subareas = store._table(os.path.join(folder, 'subareas.json'))
                monsters = store._table(os.path.join(folder, 'monsters.json'))
                stored = {}
                for monster_id, language, _position, name in _table_rows(version):
                    stored.setdefault((monster_id, language), set()).add(name)
                known = _known_ids(version)
                for monster_id, monster in monsters.items():
                    ids = (monster.get('subareas') or {}).get('Array') or []
                    if monster_id not in known or not ids:
                        continue
                    for language in store.LANGUAGES:
                        for subarea_id in ids:
                            if subarea_id not in subareas:
                                continue
                            name = store.clean_display_name(
                                labels[language].get(str(subareas[subarea_id].get('nameId'))))
                            if name:
                                self.assertIn(name, stored.get((monster_id, language), set()),
                                              (monster_id, language, subarea_id))
                for monster_id, _language in stored:
                    ids = (monsters[monster_id].get('subareas') or {}).get('Array') or []
                    self.assertTrue(ids, monster_id)

    def test_rows_follow_the_array_order_and_skip_what_the_dump_cannot_name(self):
        store = _store()
        names = {
            1: {'fr': 'Plaine', 'en': 'Plain', 'es': 'Llanura', 'pt': 'Planicie', 'de': 'Ebene'},
            2: {'fr': 'Foret', 'en': 'Forest', 'es': None, 'pt': 'Floresta', 'de': 'Wald'},
            3: {'fr': 'Plaine', 'en': '[!] Plain', 'es': '[!] Llanura', 'pt': 'Planicie', 'de': 'Ebene'},
            4: {'fr': 'Cave', 'en': '[!] Cave', 'es': None, 'pt': None, 'de': None},
        }
        monster_subareas = {20: [2, 1, 3, 99], 10: [4, 1], 30: [1]}
        rows, unresolved = store.build_rows(names, monster_subareas, {10, 20})
        self.assertEqual([(20, 99)], unresolved)
        by_key = {}
        for monster_id, language, position, name in rows:
            by_key.setdefault((monster_id, language), []).append((position, name))
        self.assertEqual({10, 20}, {key[0] for key in by_key})
        self.assertEqual([(0, 'Foret'), (1, 'Plaine')], by_key[(20, 'fr')])
        self.assertEqual([(0, 'Forest'), (1, 'Plain')], by_key[(20, 'en')])
        self.assertEqual([(0, 'Llanura')], by_key[(20, 'es')])
        self.assertEqual([(0, 'Cave'), (1, 'Plaine')], by_key[(10, 'fr')])
        self.assertEqual([(0, 'Cave'), (1, 'Plain')], by_key[(10, 'en')])
        self.assertEqual([(0, 'Planicie')], by_key[(10, 'pt')])
        self.assertEqual([(0, 'Ebene')], by_key[(10, 'de')])
        self.assertEqual([(0, 'Llanura')], by_key[(10, 'es')])
        self.assertEqual([monster for monster, *_ in rows], sorted(monster for monster, *_ in rows))

    def test_too_few_rows_refuse_to_replace_the_table(self):
        store = _store()
        with self.assertRaises(ValueError):
            store.check_rows([(1, 'fr', 0, 'Plaine')] * (store.MIN_ROWS - 1))
        store.check_rows([(1, 'fr', 0, 'Plaine')] * store.MIN_ROWS)

    def test_the_store_reads_no_third_party_host(self):
        store = _store()
        with open(store.__file__, encoding='utf-8') as handle:
            source = handle.read().lower()
        self.assertNotIn('http', source)
        self.assertNotIn('dofusdb', source)
