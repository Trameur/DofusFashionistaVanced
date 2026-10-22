import collections
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
from chardata.tests_wakfu_effect_groups_resolve_to_known_effects import (  # noqa: E402
    EFFECTS, GROUPS, SETS, STATES, tables)
from chardata.tests_wakfu_client_names_are_written_per_language_from_a_decoded_client import (
    texts)  # noqa: E402
from fashionistapulp import wakfu_db  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'

# Actions a stored effect uses and content.10 has no text for
ACTIONS_WITHOUT_A_TEXT = (
    16, 207, 272, 325, 330, 341, 345, 349, 352, 400, 401, 402, 426, 430, 446, 550, 561, 562,
    563, 566, 570, 571, 572, 666, 667, 668, 803, 839, 843, 844, 859, 865, 877, 909, 910, 911,
    912, 913, 915, 923, 933, 935, 937, 949, 950, 951, 952, 982, 983, 987, 994, 999, 1000, 1001,
    1003, 1008, 1020, 1021, 1030, 1031, 1032, 1033, 1038, 1041, 1047, 1049, 1070, 1076, 1080,
    1093, 1099, 1100, 1101, 1102, 1103, 1201, 1202, 1300)


def actions_without_a_text(conn):
    return [action for (action,) in conn.execute(
        'SELECT DISTINCT action FROM effects WHERE action NOT IN'
        ' (SELECT action FROM action_texts) ORDER BY action')]


class TheWakfuStoredEffectsUseActionsTheClientWordsTests(TestCase):
    def build(self, action_texts):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        wakfu_db.create_tables(conn)
        builder.write_client_tables(
            conn, tables(EFFECTS, GROUPS, STATES, SETS), collections.Counter())
        builder.write_client_texts(
            conn, texts(action_texts={'en': action_texts}), collections.Counter())
        return conn

    def test_an_action_the_texts_leave_out_is_listed(self):
        conn = self.build({330: 'a', 20: 'b', 150: 'c', 40: 'd', 999: 'never stored'})
        self.assertEqual([120, 126], actions_without_a_text(conn))

    def test_every_action_with_a_text_leaves_nothing_to_list(self):
        conn = self.build({330: 'a', 20: 'b', 150: 'c', 40: 'd', 120: 'e', 126: 'f'})
        self.assertEqual([], actions_without_a_text(conn))


class TheWakfuStoredEffectsUseActionsTheClientWordsOrTheOnesPinnedHereTests(TestCase):
    """Guards on the real items_wakfu.db, skipped where it is not built."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = None
        if DATABASE.exists():
            conn = sqlite3.connect('file:%s?mode=ro' % DATABASE.as_posix(), uri=True)
            try:
                filled = conn.execute('SELECT COUNT(*) FROM action_texts').fetchone()[0]
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
            self.skipTest('items_wakfu.db is absent or has no client texts')

    def test_the_stored_effects_use_248_actions_and_170_have_a_text(self):
        self.assertEqual(248, self.conn.execute(
            'SELECT COUNT(DISTINCT action) FROM effects').fetchone()[0])
        self.assertEqual(170, self.conn.execute(
            'SELECT COUNT(DISTINCT action) FROM action_texts').fetchone()[0])
        self.assertEqual([], self.conn.execute(
            'SELECT action FROM action_texts WHERE action NOT IN'
            ' (SELECT action FROM effects)').fetchall())

    def test_the_78_actions_with_no_text_are_the_ones_pinned_and_330_and_400_lead(self):
        self.assertEqual(78, len(ACTIONS_WITHOUT_A_TEXT))
        self.assertEqual(list(ACTIONS_WITHOUT_A_TEXT), actions_without_a_text(self.conn))
        used = dict(self.conn.execute(
            'SELECT action, COUNT(*) FROM effects GROUP BY action').fetchall())
        self.assertEqual(40337, sum(used[action] for action in ACTIONS_WITHOUT_A_TEXT))
        self.assertEqual([330, 400], sorted(
            ACTIONS_WITHOUT_A_TEXT, key=lambda action: -used[action])[:2])
