import collections
import os
import sqlite3
import sys

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import build_wakfu_db as builder  # noqa: E402
from fashionistapulp import wakfu_db  # noqa: E402

DECODED = {'items': {'2021': {'gfx': 1202021}, '2022': {'gfx': 1202021},
                     '9': {'gfx': 0}, '30': {'gfx': 77}}}
TABLES = {
    'spells': [{'id': 548, 'icon': 3}, {'id': 4822, 'icon': 604}, {'id': 1, 'icon': 0}],
    'states': [{'id': 21, 'bcw': 'malus_portee'}, {'id': 22, 'bcw': ''}],
    'abilities': [{'id': 1, 'cgI': 1}],
    'monsters': [{'id': 4168, 'family': 68, 'picture': 143604168},
                 {'id': 2, 'family': 68, 'picture': 100200002},
                 {'id': 3, 'family': 70, 'picture': 0}],
}


class TheWakfuClientPicturesAreWrittenFromADecodedClientTests(SimpleTestCase):
    def fill(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        wakfu_db.create_tables(conn)
        conn.execute('INSERT INTO breeds (id, name) VALUES (10, "FECA")')
        conn.execute('INSERT INTO item_picture (item, gfx) VALUES (2021, 1202021)')
        conn.execute('INSERT INTO item_picture (item, gfx) VALUES (555, 888)')
        counts = collections.Counter()
        builder.write_client_pictures(conn, TABLES, DECODED, counts)
        return conn, counts

    def rows(self, conn, family):
        return conn.execute('SELECT id, picture FROM client_pictures WHERE family = ?'
                            ' ORDER BY id', (family,)).fetchall()

    def test_every_client_item_with_a_gfx_is_a_row_and_a_gfx_of_zero_names_no_file(self):
        conn, _counts = self.fill()
        self.assertEqual([(30, '77'), (555, '888'), (2021, '1202021'), (2022, '1202021')],
                         self.rows(conn, 'item'))

    def test_an_item_the_client_lacks_keeps_the_gfx_the_database_had(self):
        conn, counts = self.fill()
        self.assertIn((555, '888'), self.rows(conn, 'item'))
        self.assertEqual(4, counts['pictures: item'])

    def test_a_spell_keeps_its_icon_even_when_the_icon_is_zero(self):
        conn, _counts = self.fill()
        self.assertEqual([(1, '0'), (548, '3'), (4822, '604')], self.rows(conn, 'spell'))

    def test_a_state_is_named_by_its_key_and_an_empty_key_is_left_out(self):
        conn, _counts = self.fill()
        self.assertEqual([(21, 'malus_portee')], self.rows(conn, 'state'))

    def test_abilities_monsters_families_and_classes_have_their_rows(self):
        conn, _counts = self.fill()
        self.assertEqual([(1, '1')], self.rows(conn, 'ability'))
        self.assertEqual([(2, '100200002'), (4168, '143604168')], self.rows(conn, 'monster'))
        self.assertEqual([(68, '68'), (70, '70')], self.rows(conn, 'monster_family'))
        self.assertEqual([(10, '10')], self.rows(conn, 'class'))

    def test_the_table_is_among_the_ones_the_build_owns(self):
        source = open(os.path.join(SCRAPER, 'build_wakfu_db.py'), encoding='utf-8').read()
        self.assertIn('INSERT INTO client_pictures', source)
