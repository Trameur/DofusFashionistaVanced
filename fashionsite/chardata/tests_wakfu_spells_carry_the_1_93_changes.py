import io
import json
import os
import sqlite3
import sys
from unittest import mock

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.append(SCRAPER)
import build_wakfu_spells as spell_tables  # noqa: E402

ROUBLARD_CLASS = 13


class WakfuSpellsCarryThe193ChangesTests(SimpleTestCase):
    """The Wakfu spell tables hold the costs, ranges and always-landing damage of 1.93."""

    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        path = get_items_db_path('wakfu')
        if not os.path.exists(path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        dump = os.path.join(SCRAPER, 'transformed_wakfu.json')
        if not os.path.exists(dump):
            self.skipTest('no decoded Wakfu dump; run itemscraper/get_items_wakfu.py')
        with io.open(dump, encoding='utf-8') as handle:
            self.build = json.load(handle).get('version') or ''
        if not self.build.startswith('1.93.'):
            self.skipTest('these are the 1.93 values, the mirror holds %s' % self.build)
        self.conn = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        self.addCleanup(self.conn.close)
        if not self.conn.execute('SELECT COUNT(*) FROM spells').fetchone()[0]:
            self.skipTest('no Wakfu spells imported yet')

    def test_the_tables_hold_what_the_1_93_notes_say(self):
        version, noted = spell_tables.noted_for(self.build)
        self.assertEqual('1.93', version)
        self.assertGreater(len(noted), 15)
        self.assertEqual([], spell_tables.noted_mismatches(self.conn, self.build))

    def test_every_roublard_element_spell_reaches_closer_than_three_cells(self):
        ranges = self.conn.execute(
            'SELECT id, range FROM spells WHERE class = ? AND element IS NOT NULL',
            (ROUBLARD_CLASS,)).fetchall()
        self.assertGreater(len(ranges), 10)
        for spell_id, reach in ranges:
            with self.subTest(spell=spell_id):
                self.assertLess(int(reach.split('-')[0]), 3)


class TheNotesCheckNamesWhatTheTablesContradictTests(SimpleTestCase):
    """noted_mismatches reports each figure the tables hold against the notes."""

    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.executescript(
            'CREATE TABLE spells (id INTEGER, class INTEGER, element TEXT,'
            ' ap INTEGER, mp INTEGER, wp INTEGER, range TEXT);'
            'CREATE TABLE spell_text (spell INTEGER, language TEXT,'
            ' normal TEXT, critical TEXT);'
            'CREATE TABLE spell_effects (spell INTEGER, level INTEGER,'
            ' position INTEGER, kind TEXT, element TEXT, value INTEGER,'
            ' is_percent INTEGER, conditional INTEGER);')

    def add(self, spell_id, ap, wp, reach, text='', damage=()):
        self.conn.execute('INSERT INTO spells VALUES (?, 12, ?, ?, 0, ?, ?)',
                          (spell_id, 'EARTH', ap, wp, reach))
        self.conn.execute("INSERT INTO spell_text VALUES (?, 'fr', ?, '')",
                          (spell_id, text))
        for position, conditional in enumerate(damage):
            self.conn.execute(
                "INSERT INTO spell_effects VALUES (?, 245, ?, 'damage', 'EARTH',"
                ' 100, 0, ?)', (spell_id, position, conditional))

    def notes(self, spells):
        patcher = mock.patch.object(spell_tables, 'NOTED', {'1.93': spells})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_tables_that_agree_give_no_line(self):
        self.notes({1: {'ap': 4, 'wp': None, 'range': '1 - 4', 'text': 'max',
                        'lands': True}, 2: {'lands': False}})
        self.add(1, 4, None, '1 - 4', '30 % max', damage=(1, 0))
        self.add(2, 1, 1, '1 - 3', damage=(1,))
        self.assertEqual([], spell_tables.noted_mismatches(self.conn, '1.93.1.62'))

    def test_each_contradicted_figure_is_one_line(self):
        self.notes({1: {'ap': 4, 'range': '1 - 4', 'text': 'par PM',
                        'lands': True}, 2: {'lands': False}, 3: {'ap': 2}})
        self.add(1, 4, None, '1 - 2', 'old text', damage=(1,))
        self.add(2, 1, 1, '1 - 3')
        lines = spell_tables.noted_mismatches(self.conn, '1.93.1.62')
        self.assertEqual(5, len(lines), lines)
        for line in lines:
            self.assertTrue(line.startswith('mismatch: spell '), line)
        self.assertIn("mismatch: spell 1 range is '1 - 2', the 1.93 notes say '1 - 4'",
                      lines)
        self.assertIn('mismatch: spell 2 lands is None, the 1.93 notes say False',
                      lines)
        self.assertIn('mismatch: spell 3, which the 1.93 notes change, is not in '
                      'the tables', lines)

    def test_another_build_is_not_held_to_these_notes(self):
        self.notes({1: {'ap': 4}})
        self.assertEqual([], spell_tables.noted_mismatches(self.conn, '1.94.0.1'))
        self.assertEqual([], spell_tables.noted_mismatches(self.conn, '1.930.0.1'))
