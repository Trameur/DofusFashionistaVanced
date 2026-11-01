import os
import sqlite3
import sys
import tempfile

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import build_wakfu_db as builder  # noqa: E402
from chardata.tests_wakfu_database_stores_the_effect_and_state_fields_the_client_reads import (  # noqa: E402,E501
    an_effect, an_item, real_db, real_tables, small_build)


def a_line(stat, action, value):
    return {'stat': stat, 'action': action, 'value': value, 'effect': 1,
            'params': [value, 0.0]}


def description(item, **by_language):
    return {'definition': {'item': {'id': item}}, 'description': by_language}


class TheStatActionsListEveryActionAStatWasFilledByTests(SimpleTestCase):
    def setUp(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        items = [an_item(10, [a_line('ARMOR_GIVEN_PERCENT', 39, 5),
                              a_line('AP', 31, 1)]),
                 an_item(11, [a_line('ARMOR_GIVEN_PERCENT', 39, 7),
                              a_line('ARMOR_GIVEN_PERCENT', 183, 3),
                              a_line('ARMOR_GIVEN_PERCENT', 183, 4),
                              a_line('ARMOR_GIVEN_PERCENT', 40, -2)])]
        db = small_build(temp.name, items, tables={'effects': [an_effect(1)]})
        self.conn = sqlite3.connect(str(db))
        self.addCleanup(self.conn.close)
        self.keys = dict(self.conn.execute('SELECT key, id FROM stats'))

    def rows(self):
        return {(stat, action): rest for stat, action, *rest in self.conn.execute(
            'SELECT stat, action, positive_lines, negative_lines, primary_action'
            ' FROM stat_actions')}

    def test_each_stat_and_action_pair_counts_its_positive_and_negative_lines(self):
        armor, ap = self.keys['armor_given_percent'], self.keys['ap']
        self.assertEqual({(ap, 31): [1, 0, 1], (armor, 39): [2, 0, 1],
                          (armor, 183): [2, 0, 0], (armor, 40): [0, 1, 0]}, self.rows())

    def test_each_stat_has_exactly_one_primary_action_the_one_with_most_positive_lines(self):
        primaries = self.conn.execute(
            'SELECT stat, COUNT(*) FROM stat_actions WHERE primary_action = 1'
            ' GROUP BY stat').fetchall()
        stats = self.conn.execute('SELECT COUNT(DISTINCT stat) FROM stat_actions').fetchone()[0]
        self.assertEqual(stats, len(primaries))
        self.assertEqual({1}, {count for _stat, count in primaries})

    def test_the_line_counts_add_up_to_the_stat_rows_of_the_items(self):
        lines = self.conn.execute(
            'SELECT SUM(positive_lines + negative_lines) FROM stat_actions').fetchone()[0]
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM stats_of_item').fetchone()[0],
                         lines)


class TheStoredStatActionsAreTheRealBuildsTests(SimpleTestCase):
    def setUp(self):
        self.db = real_db()
        if self.db is None:
            self.skipTest('no database with the new columns')
        self.addCleanup(self.db.close)
        try:
            self.db.execute('SELECT 1 FROM stat_actions LIMIT 1')
        except sqlite3.OperationalError:
            self.skipTest('the database predates stat_actions')

    def test_the_line_counts_equal_the_stat_rows_of_the_items_that_are_not_removed(self):
        lines = self.db.execute(
            'SELECT SUM(positive_lines + negative_lines) FROM stat_actions').fetchone()[0]
        rows = self.db.execute(
            'SELECT COUNT(*) FROM stats_of_item WHERE item IN'
            ' (SELECT id FROM items WHERE removed = 0)').fetchone()[0]
        self.assertEqual(rows, lines)
        self.assertGreater(lines, 0)

    def test_every_stat_an_item_carries_has_one_primary_action(self):
        carried = self.db.execute('SELECT COUNT(DISTINCT stat) FROM stat_actions').fetchone()[0]
        primary = self.db.execute(
            'SELECT COUNT(*) FROM (SELECT stat FROM stat_actions WHERE primary_action = 1'
            ' GROUP BY stat HAVING COUNT(*) = 1)').fetchone()[0]
        self.assertEqual(carried, primary)


class TheItemDescriptionsComeFromTheCdnItemFileTests(SimpleTestCase):
    def setUp(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def build(self, descriptions):
        items = [an_item(10), an_item(11), an_item(12)]
        db = small_build(self.temp.name, items, tables={'effects': [an_effect(1)]},
                         descriptions=descriptions)
        conn = sqlite3.connect(str(db))
        self.addCleanup(conn.close)
        return conn

    def test_an_item_with_a_description_gets_one_row_per_language_german_from_english(self):
        conn = self.build([description(10, en='Hat', fr='Chapeau', es='Sombrero', pt='Chapeu')])
        stored = {language: text for language, text in conn.execute(
            'SELECT language, description FROM item_descriptions WHERE item = 10')}
        self.assertEqual({'en': 'Hat', 'fr': 'Chapeau', 'es': 'Sombrero', 'pt': 'Chapeu',
                          'de': 'Hat'}, stored)

    def test_items_without_a_description_get_no_row(self):
        conn = self.build([description(10, en='Hat'),
                           {'definition': {'item': {'id': 11}}}, description(12)])
        self.assertEqual([10], [row[0] for row in conn.execute(
            'SELECT DISTINCT item FROM item_descriptions')])

    def test_a_description_of_an_item_the_dump_lacks_is_not_stored(self):
        conn = self.build([description(999, en='Ghost')])
        self.assertEqual(0, conn.execute('SELECT COUNT(*) FROM item_descriptions').fetchone()[0])

    def test_a_missing_items_json_leaves_the_table_empty(self):
        conn = self.build(None)
        self.assertEqual(0, conn.execute('SELECT COUNT(*) FROM item_descriptions').fetchone()[0])


class TheStoredItemDescriptionsAreTheRealBuildsTests(SimpleTestCase):
    def setUp(self):
        self.db = real_db()
        if self.db is None:
            self.skipTest('no database with the new columns')
        self.addCleanup(self.db.close)

    def test_every_described_item_has_a_row_in_each_of_the_five_languages(self):
        items, rows = self.db.execute(
            'SELECT COUNT(DISTINCT item), COUNT(*) FROM item_descriptions').fetchone()
        self.assertGreater(items, 0)
        self.assertEqual(items * len(builder.LANGUAGES), rows)

    def test_the_german_description_is_the_english_one(self):
        differing = self.db.execute(
            "SELECT COUNT(*) FROM item_descriptions de JOIN item_descriptions en"
            " ON en.item = de.item AND en.language = 'en'"
            " WHERE de.language = 'de' AND de.description != en.description").fetchone()[0]
        self.assertEqual(0, differing)

    def test_every_described_item_is_an_item_of_the_database(self):
        orphans = self.db.execute(
            'SELECT COUNT(*) FROM item_descriptions WHERE item NOT IN (SELECT id FROM items)'
        ).fetchone()[0]
        self.assertEqual(0, orphans)


class TheDataVersionNamesTheDumpAndTheClientTheDatabaseWasBuiltFromTests(SimpleTestCase):
    def test_a_build_stores_one_row_with_the_dump_version_and_its_client_version(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        with tempfile.TemporaryDirectory() as temp:
            db = small_build(temp, [an_item(10)], tables={'effects': [an_effect(1)]},
                             version='1.90.1.7', client_version='6.0_1.90.1.1.2')
            conn = sqlite3.connect(str(db))
            try:
                rows = conn.execute('SELECT version, client_version FROM data_version').fetchall()
            finally:
                conn.close()
        self.assertEqual([('1.90.1.7', '6.0_1.90.1.1.2')], rows)

    def test_the_real_database_holds_one_row_that_the_decoded_tables_agree_with(self):
        db = real_db()
        tables = real_tables()
        if db is None or tables is None:
            self.skipTest('no database with the new columns or no decoded client')
        self.addCleanup(db.close)
        rows = db.execute('SELECT version, client_version FROM data_version').fetchall()
        self.assertEqual(1, len(rows))
        version, client_version = rows[0]
        self.assertTrue(version.startswith(tables['game_version']))
        self.assertEqual(tables['client_version'], client_version)
