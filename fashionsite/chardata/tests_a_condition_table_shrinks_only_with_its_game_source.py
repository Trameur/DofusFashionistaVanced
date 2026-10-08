# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest import TestCase, mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'itemscraper'))
import update_audit as audit  # noqa: E402

COUNTS = {'item_criteria': 349, 'item_class_conditions': 4, 'item_sex_conditions': 6,
          'item_name_conditions': 5, 'item_weird_conditions': 87, 'max_level_to_equip': 1,
          'unusable_items': 14, 'items_not_worn_together': 0}
CLASS_WARNING = ('item_class_conditions: 4 -> 2 rows, the Ankama source items.json '
                 '(pieces whose criteria carry class) shrank too (4 -> 2)')
CLASS_ERROR = 'item_class_conditions: lost more than 3% or table deleted (4 -> 2)'


def inventory(tables, counts, tag):
    return {'version': 'dofus3', 'integrity': ['ok'],
            'tables': dict({key: 100 for key in ('items', 'stats', 'stats_of_item', 'sets',
                                                 'weapon_hits', 'weapon_ap')}, **tables),
            'stats': {}, 'items': {}, 'legacy_ids': {}, 'spells': {}, 'orphaned': {},
            'images': {'problems': {}},
            'criteria_source': {'file': 'itemscraper/raw/%s/items.json' % tag, 'counts': dict(COUNTS, **counts)}}


def pair(table_before, table_after, source_before, source_after, table='item_class_conditions'):
    return (inventory({table: table_before}, {table: source_before}, '3.6.12.16'),
            inventory({table: table_after}, {table: source_after}, '3.7.4.4'))


class AConditionTableShrinksOnlyWithItsGameSourceTests(TestCase):
    def test_a_condition_table_that_shrinks_with_its_source_is_a_warning_naming_both_counts(self):
        result = audit.compare(*pair(4, 2, 4, 2))
        self.assertEqual([], result['errors'])
        self.assertIn(CLASS_WARNING, result['warnings'])

    def test_each_condition_table_names_the_kinds_its_source_count_reads(self):
        cases = {'item_criteria': ((350, 327), (349, 326), 'items.json (pieces with criteria) shrank too (349 -> 326)'),
                 'item_sex_conditions': ((6, 4), (6, 4), 'items.json (pieces whose criteria carry sex) shrank too (6 -> 4)'),
                 'item_weird_conditions': ((112, 98), (87, 73), 'items.json (pieces whose criteria carry set_bonus '
                                                                 'or sets_equipped) shrank too (87 -> 73)')}
        for table, (rows, source, words) in cases.items():
            with self.subTest(table=table):
                result = audit.compare(*pair(*rows, *source, table=table))
                self.assertEqual([], result['errors'])
                self.assertIn('%s: %d -> %d rows, the Ankama source %s' % ((table,) + rows + (words,)),
                              result['warnings'])

    def test_a_shrink_its_source_does_not_explain_is_still_an_error(self):
        for source_before, source_after in ((4, 4), (4, 5), (100, 98), (4, 3)):
            with self.subTest(source=(source_before, source_after)):
                result = audit.compare(*pair(4, 2, source_before, source_after))
                self.assertIn(CLASS_ERROR, result['errors'])
                self.assertFalse(any('Ankama source' in warning for warning in result['warnings']))

    def test_rows_lost_past_the_pieces_the_source_lost_and_the_tolerance_are_an_error(self):
        result = audit.compare(*pair(112, 95, 87, 73, table='item_weird_conditions'))
        self.assertEqual([], result['errors'])
        for rows in (94, 91):
            with self.subTest(rows=rows):
                result = audit.compare(*pair(112, rows, 87, 73, table='item_weird_conditions'))
                self.assertIn('item_weird_conditions: lost more than 3%% or table deleted (112 -> %d)' % rows,
                              result['errors'])

    def test_a_deleted_condition_table_stays_an_error_even_when_its_source_emptied(self):
        before, after = pair(4, 0, 4, 0)
        del after['tables']['item_class_conditions']
        self.assertIn('item_class_conditions: lost more than 3% or table deleted (4 -> 0)',
                      audit.compare(before, after)['errors'])

    def test_a_table_outside_the_condition_tables_is_not_explained_by_criteria(self):
        before, after = pair(4, 2, 4, 2, table='item_drops')
        self.assertIn('item_drops: lost more than 3% or table deleted (4 -> 2)', audit.compare(before, after)['errors'])

    def test_an_old_snapshot_without_source_counts_keeps_the_error(self):
        for missing in ('before', 'after', 'both'):
            with self.subTest(missing=missing):
                before, after = pair(4, 2, 4, 2)
                for name, snapshot in (('before', before), ('after', after)):
                    if missing in (name, 'both'):
                        del snapshot['criteria_source']
                result = audit.compare(before, after)
                self.assertIn(CLASS_ERROR, result['errors'])
                self.assertEqual([], [line for line in result['warnings'] if 'Criteria source' in line
                                      or 'Ankama source' in line])


class TheSnapshotReadsTheArchiveCriteriaTests(TestCase):
    PIECES = {10: 'PG=3', 11: 'PS=1&CS>10', 12: 'Pk<3', 13: 'pk<2&PN~Bob', 14: '', 15: 'PG=1|PG=2'}

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        patcher = mock.patch.object(audit, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.archive({ankama: text for ankama, text in self.PIECES.items()})
        modifiers = self.root / 'fashionsite/chardata/spell_modifiers/dofus3.json'
        modifiers.parent.mkdir(parents=True)
        modifiers.write_text(json.dumps({'game_version': 'dofus3', 'data_version': '9.9.9.9'}), encoding='utf-8')

    def archive(self, criteria):
        path = self.root / 'itemscraper/raw/9.9.9.9/items.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        records = [{'data': {'id': ankama, 'criterions': text}} for ankama, text in criteria.items()]
        path.write_text(json.dumps({'references': {'RefIds': records}}), encoding='utf-8')

    def read(self, stored=None, extra_pieces=()):
        stored = {**{ankama: text for ankama, text in self.PIECES.items() if text}, **(stored or {})}
        connection = sqlite3.connect(':memory:')
        self.addCleanup(connection.close)
        connection.execute('CREATE TABLE items (id INTEGER, ankama_id INTEGER, ankama_type TEXT, removed INTEGER)')
        connection.execute('CREATE TABLE item_criteria (item INTEGER, criteria TEXT)')
        pieces = [(ankama, ankama, 'equipment', None) for ankama in list(self.PIECES) + list(extra_pieces)]
        connection.executemany('INSERT INTO items VALUES (?, ?, ?, ?)',
                               pieces + [(1000010, 10, 'mounts', None)])
        connection.executemany('INSERT INTO item_criteria VALUES (?, ?)',
                               [(item, text) for item, text in stored.items() if text] + [(1000010, 'PE=51')])
        return audit.criteria_source('dofus3', connection, {'items', 'item_criteria'})

    def test_the_snapshot_counts_the_pieces_whose_archive_criteria_carry_each_kind(self):
        self.assertEqual({'file': 'itemscraper/raw/9.9.9.9/items.json',
                          'counts': {'item_criteria': 5, 'item_class_conditions': 2, 'item_sex_conditions': 1,
                                     'item_name_conditions': 1, 'item_weird_conditions': 2,
                                     'max_level_to_equip': 0, 'unusable_items': 0, 'items_not_worn_together': 0}},
                         self.read())

    def test_criteria_that_differ_from_the_archive_get_no_counts(self):
        for stored, extra in (({10: 'PG=4'}, ()), ({14: 'PG=3'}, ()), ({}, (16,))):
            with self.subTest(stored=stored, extra=extra):
                record = self.read(stored, extra)
                self.assertNotIn('counts', record)
                self.assertIn('pieces whose criteria differ from the file', record['refused'])

    def test_a_criteria_kind_the_reader_does_not_know_gets_no_counts(self):
        self.PIECES = {**self.PIECES, 12: 'Zz<3'}
        self.archive(self.PIECES)
        record = self.read()
        self.assertNotIn('counts', record)
        self.assertIn('Zz<', record['refused'])

    def test_unreadable_criteria_get_no_counts(self):
        self.PIECES = {**self.PIECES, 12: 'PG=3&(PS=1'}
        self.archive(self.PIECES)
        record = self.read()
        self.assertNotIn('counts', record)
        self.assertIn('unreadable', record['refused'])

    def test_a_refused_source_keeps_the_error_and_says_why(self):
        refused = self.read({10: 'PG=4'})
        before, after = pair(4, 2, 4, 2)
        after['criteria_source'] = refused
        result = audit.compare(before, after)
        self.assertIn(CLASS_ERROR, result['errors'])
        self.assertIn('Criteria source not used after the import: itemscraper/raw/9.9.9.9/items.json, '
                      + refused['refused'], result['warnings'])

    def test_a_version_without_an_archive_tag_records_nothing(self):
        (self.root / 'fashionsite/chardata/spell_modifiers/dofus3.json').unlink()
        self.assertEqual({}, self.read())
        self.assertEqual({}, audit.empty_snapshot('dofus3')['criteria_source'])
