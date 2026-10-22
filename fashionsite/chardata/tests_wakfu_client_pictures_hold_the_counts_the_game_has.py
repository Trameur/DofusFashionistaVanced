import sqlite3
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'

# family: (rows, distinct pictures) in client_pictures of the 1.93.1 client
COUNTS = {
    'item': (20233, 10908), 'spell': (4143, 1131), 'state': (6067, 1370),
    'ability': (31, 29), 'monster': (2853, 1466), 'monster_family': (398, 398),
    'class': (18, 18),
}
# family, id, picture
SPOT_VALUES = (
    ('item', 2021, '1202021'), ('spell', 548, '3'), ('spell', 4822, '604'),
    ('state', 21, '21'), ('state', 3, 'malus_portee'), ('monster', 4168, '143604168'),
    ('monster', 2, '100200002'), ('monster_family', 68, '68'), ('class', 10, '10'),
)


class TheWakfuClientPicturesHoldTheCountsTheGameHasTests(TestCase):
    """Guards on the real items_wakfu.db, skipped where it is not built."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = None
        if DATABASE.exists():
            conn = sqlite3.connect('file:%s?mode=ro' % DATABASE.as_posix(), uri=True)
            try:
                filled = conn.execute('SELECT COUNT(*) FROM client_pictures').fetchone()[0]
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
            self.skipTest('items_wakfu.db is absent or has no client pictures')

    def test_every_family_has_the_rows_and_the_distinct_pictures_the_client_gives(self):
        found = {family: (rows, pictures) for family, rows, pictures in self.conn.execute(
            'SELECT family, COUNT(*), COUNT(DISTINCT picture) FROM client_pictures'
            ' GROUP BY family')}
        self.assertEqual(COUNTS, found)

    def test_one_entry_per_family_is_the_picture_the_game_draws(self):
        for family, ident, picture in SPOT_VALUES:
            row = self.conn.execute(
                'SELECT picture FROM client_pictures WHERE family = ? AND id = ?',
                (family, ident)).fetchone()
            self.assertEqual((picture,), row, (family, ident))

    def test_item_picture_equals_the_client_on_every_item_and_twelve_are_not_in_the_client(self):
        self.assertEqual(
            (7738, 7738), self.conn.execute(
                'SELECT COUNT(*), SUM(cp.picture = CAST(ip.gfx AS TEXT)) FROM item_picture ip'
                " JOIN client_pictures cp ON cp.family = 'item' AND cp.id = ip.item"
            ).fetchone())
        self.assertEqual((7726,), self.conn.execute(
            'SELECT COUNT(*) FROM items i JOIN item_picture ip ON ip.item = i.id'
            " JOIN client_pictures cp ON cp.family = 'item' AND cp.id = i.id"
            ' AND cp.picture = CAST(ip.gfx AS TEXT) WHERE i.removed = 0').fetchone())
        self.assertEqual((12,), self.conn.execute(
            'SELECT COUNT(*) FROM items WHERE removed = 1').fetchone())

    def test_class_spells_use_625_icons_and_every_state_key_is_the_states_own_key(self):
        self.assertEqual((722, 625), self.conn.execute(
            'SELECT COUNT(*), COUNT(DISTINCT cp.picture) FROM client_pictures cp'
            " JOIN client_spells s ON s.id = cp.id WHERE cp.family = 'spell' AND s.breed > 0"
        ).fetchone())
        self.assertEqual((6067, 62), (
            self.conn.execute(
                'SELECT COUNT(*) FROM client_pictures cp JOIN states s ON s.id = cp.id'
                " WHERE cp.family = 'state' AND cp.picture = s.key").fetchone()[0],
            self.conn.execute("SELECT COUNT(*) FROM states WHERE key = ''").fetchone()[0]))

    def test_no_picture_is_empty_and_the_monster_pictures_are_positive(self):
        self.assertEqual((0,), self.conn.execute(
            "SELECT COUNT(*) FROM client_pictures WHERE picture = ''").fetchone())
        self.assertEqual((0,), self.conn.execute(
            "SELECT COUNT(*) FROM client_pictures WHERE family IN ('monster', 'item')"
            ' AND CAST(picture AS INTEGER) <= 0').fetchone())
