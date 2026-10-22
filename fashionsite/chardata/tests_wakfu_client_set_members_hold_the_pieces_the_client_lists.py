import collections
import json
import os
import sqlite3
import sys
from pathlib import Path
from unittest import TestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import build_wakfu_db as builder  # noqa: E402
from chardata.tests_wakfu_effect_groups_resolve_to_known_effects import tables  # noqa: E402
from fashionistapulp import wakfu_db  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CLIENTS = ROOT / 'itemscraper' / 'wakfu_client'
DATABASE = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'

# Client sets with a gear piece the open data links to no set, 66 pieces in all
SETS_THE_OPEN_DATA_DOES_NOT_LINK = (
    242, 277, 281, 331, 562, 563, 573, 585, 599, 611, 612, 613, 614, 637, 638)
# Sets with a piece the client's item table lacks, and how many
MEMBERS_WITH_NO_CLIENT_ITEM = {110: 1, 208: 2, 539: 4, 540: 11, 641: 1}
# The 19 piece ids the client lists that its item table lacks
ABSENT_FROM_THE_ITEM_TABLE = (
    6575, 6577, 16692, 16693, 16694, 16695, 18083, 18084, 18086, 18087, 18092, 18228,
    18229, 18230, 18231, 18311, 18312, 19371, 19526)
SETS_WITHOUT_A_MEMBER = (551, 604, 619)


def newest(root, name):
    found = sorted(root.glob('*/' + name)) if root.exists() else []
    return found[-1] if found else None


class TheWakfuClientSetMembersAreWrittenInTheClientsOrderTests(TestCase):
    def fill(self, sets, item_ids):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        wakfu_db.create_tables(conn)
        counts = collections.Counter()
        builder.write_client_tables(conn, tables([], [], sets=sets, item_ids=item_ids), counts)
        return conn, counts

    def test_a_member_is_stored_at_its_position_in_the_sets_own_list(self):
        conn, counts = self.fill(
            [{'id': 5, 'elG': 1, 'item_ids': [30, 10, 20], 'bonuses': []},
             {'id': 6, 'elG': 1, 'item_ids': [10], 'bonuses': []}], (10, 20, 30))
        self.assertEqual(
            [(5, 0, 30), (5, 1, 10), (5, 2, 20), (6, 0, 10)],
            conn.execute('SELECT item_set, position, item FROM client_set_members'
                         ' ORDER BY item_set, position').fetchall())
        self.assertEqual(4, counts['client set members'])
        self.assertEqual(0, counts['client set members with no client item'])

    def test_a_piece_the_client_item_table_lacks_is_stored_as_the_client_lists_it(self):
        conn, counts = self.fill(
            [{'id': 5, 'elG': 1, 'item_ids': [10, 99], 'bonuses': []}], (10,))
        self.assertEqual([(0, 10), (1, 99)], conn.execute(
            'SELECT position, item FROM client_set_members').fetchall())
        self.assertEqual(1, counts['client set members with no client item'])

    def test_a_set_with_no_piece_has_no_member_row_and_every_member_has_its_set(self):
        conn, _counts = self.fill(
            [{'id': 5, 'elG': 1, 'item_ids': [], 'bonuses': []},
             {'id': 6, 'elG': 1, 'item_ids': [10], 'bonuses': []}], (10,))
        self.assertEqual([(6,)], conn.execute(
            'SELECT DISTINCT item_set FROM client_set_members').fetchall())
        self.assertEqual([], conn.execute('PRAGMA foreign_key_check').fetchall())

    def test_the_member_count_of_a_set_is_its_item_count(self):
        conn, _counts = self.fill(
            [{'id': 5, 'elG': 1, 'item_ids': [10, 20, 30], 'bonuses': []}], (10, 20))
        self.assertEqual([(3, 3)], conn.execute(
            'SELECT item_count, (SELECT COUNT(*) FROM client_set_members'
            ' WHERE item_set = id) FROM client_sets').fetchall())


class TheWakfuClientSetMembersHoldThePiecesTheClientListsTests(TestCase):
    """Guards on the real items_wakfu.db, skipped where it is not built."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = None
        if DATABASE.exists():
            conn = sqlite3.connect('file:%s?mode=ro' % DATABASE.as_posix(), uri=True)
            try:
                filled = conn.execute('SELECT COUNT(*) FROM client_set_members').fetchone()[0]
            except sqlite3.DatabaseError:
                filled = 0
            if filled:
                cls.conn = conn
            else:
                conn.close()

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.close()
        super().tearDownClass()

    def setUp(self):
        if self.conn is None:
            self.skipTest('items_wakfu.db is absent or has no client set members')

    def one(self, sql):
        return self.conn.execute(sql).fetchone()[0]

    def test_the_client_lists_1836_pieces_of_352_sets_and_no_piece_is_null(self):
        self.assertEqual(1836, self.one('SELECT COUNT(*) FROM client_set_members'))
        self.assertEqual(1836, self.one(
            'SELECT COUNT(*) FROM client_set_members WHERE item IS NOT NULL'))
        self.assertEqual(352, self.one(
            'SELECT COUNT(DISTINCT item_set) FROM client_set_members'))
        self.assertEqual(1836, self.one('SELECT SUM(item_count) FROM client_sets'))

    def test_every_set_lists_as_many_pieces_as_it_counts_and_three_list_none(self):
        self.assertEqual([], self.conn.execute(
            'SELECT id FROM client_sets s WHERE item_count != (SELECT COUNT(*)'
            ' FROM client_set_members WHERE item_set = s.id)').fetchall())
        self.assertEqual(
            [(ident,) for ident in SETS_WITHOUT_A_MEMBER], self.conn.execute(
                'SELECT id FROM client_sets WHERE id NOT IN'
                ' (SELECT item_set FROM client_set_members) ORDER BY id').fetchall())

    def test_the_pieces_the_client_item_table_lacks_are_the_known_ones(self):
        self.assertEqual(
            sorted(MEMBERS_WITH_NO_CLIENT_ITEM.items()), self.conn.execute(
                'SELECT item_set, COUNT(*) FROM client_set_members WHERE item IN (%s)'
                ' GROUP BY item_set ORDER BY item_set'
                % ', '.join(str(ident) for ident in ABSENT_FROM_THE_ITEM_TABLE)).fetchall())

    def test_those_19_ids_are_in_no_item_table_of_the_client_nor_in_the_database(self):
        path = newest(CLIENTS, 'decoded.json')
        if path is None:
            self.skipTest('no decoded client')
        known = {int(ident) for ident in json.loads(path.read_text(encoding='utf-8'))['items']}
        listed = {ident for (ident,) in self.conn.execute(
            'SELECT item FROM client_set_members')}
        self.assertEqual(set(ABSENT_FROM_THE_ITEM_TABLE), listed - known)
        for table, column in (('items', 'ankama_id'), ('pets', 'item'), ('mounts', 'item')):
            self.assertEqual(0, self.one(
                'SELECT COUNT(*) FROM %s WHERE %s IN (%s)' % (
                    table, column, ', '.join(str(one) for one in ABSENT_FROM_THE_ITEM_TABLE))),
                table)

    def test_a_gear_item_the_open_data_puts_in_a_set_is_in_the_same_client_set(self):
        self.assertEqual(1105, self.one(
            'SELECT COUNT(*) FROM client_set_members m'
            ' JOIN items i ON i.ankama_id = m.item'))
        self.assertEqual(0, self.one(
            'SELECT COUNT(*) FROM client_set_members m JOIN items i ON i.ankama_id = m.item'
            ' WHERE i.item_set IS NOT NULL AND i.item_set != m.item_set'))
        self.assertEqual(0, self.one(
            'SELECT COUNT(*) FROM items WHERE item_set IS NOT NULL AND ankama_id NOT IN'
            ' (SELECT item FROM client_set_members WHERE item IS NOT NULL)'))

    def test_the_66_gear_items_the_open_data_links_to_no_set_have_their_set(self):
        rows = self.conn.execute(
            'SELECT m.item_set, COUNT(*) FROM client_set_members m'
            ' JOIN items i ON i.ankama_id = m.item WHERE i.item_set IS NULL'
            ' GROUP BY m.item_set ORDER BY m.item_set').fetchall()
        self.assertEqual(
            list(SETS_THE_OPEN_DATA_DOES_NOT_LINK), [ident for ident, _count in rows])
        self.assertEqual(66, sum(count for _ident, count in rows))
        self.assertEqual(0, self.one(
            'SELECT COUNT(*) FROM sets WHERE id IN (%s)'
            % ', '.join(str(ident) for ident in SETS_THE_OPEN_DATA_DOES_NOT_LINK)))

    def test_no_member_is_left_without_its_set(self):
        self.assertEqual([], self.conn.execute('PRAGMA foreign_key_check').fetchall())
