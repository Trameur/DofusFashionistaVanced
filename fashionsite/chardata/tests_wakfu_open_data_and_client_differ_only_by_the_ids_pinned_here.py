import json
import sqlite3
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
DATABASE = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'
MIRRORS = ROOT / 'itemscraper' / 'wakfu_raw'
CLIENTS = ROOT / 'itemscraper' / 'wakfu_client'

PET_TYPE = 582
RUNE_TYPE = 811
SUBLIMATION_TYPE = 812

# Pet items the client has in its item table and the open data lacks
PETS_THE_OPEN_DATA_LACKS = (18365, 24293, 31450, 32245, 32246, 32704, 32705, 32706, 32707)

# The sets the open data names, as first and last id of each run
NAMED_SET_RUNS = (
    (41, 41), (44, 44), (80, 80), (82, 83), (231, 231), (234, 236), (243, 245), (258, 258),
    (261, 261), (273, 273), (291, 291), (293, 296), (302, 302), (314, 314), (316, 318),
    (339, 339), (347, 347), (349, 349), (351, 353), (358, 361), (365, 367), (371, 373),
    (376, 376), (379, 381), (390, 390), (392, 399), (405, 406), (408, 408), (416, 417),
    (419, 421), (424, 424), (427, 427), (429, 429), (431, 432), (435, 436), (439, 441),
    (443, 446), (453, 454), (465, 465), (475, 475), (490, 490), (495, 498), (501, 501),
    (503, 505), (508, 513), (515, 529), (532, 538), (541, 545), (547, 550), (553, 556),
    (558, 561), (564, 571), (576, 584), (586, 588), (592, 598), (600, 603), (605, 610),
    (615, 618), (620, 636), (639, 640), (642, 642))
NAMED_SETS = tuple(ident for first, last in NAMED_SET_RUNS for ident in range(first, last + 1))

RUNES_ONLY_THE_CLIENT_HAS = (27083, 27093, 30804)
# Not in the client's item table: no drop, no loot row, and 7 of 10 are marked as left out of
# the in-game encyclopedia (property 24) where 3 of the 467 shared ones are
SUBLIMATIONS_ONLY_THE_OPEN_DATA_HAS = (
    27134, 27282, 28865, 30949, 30951, 30964, 30966, 31660, 31661, 31662)


def newest(root, name):
    found = sorted(root.glob('*/' + name)) if root.exists() else []
    return found[-1] if found else None


class TheWakfuOpenDataAndTheClientDifferOnlyByTheIdsPinnedHereTests(TestCase):
    """Guards on the real db, the open data mirror and the decoded client, each skipped when
    absent."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = None
        if DATABASE.exists():
            conn = sqlite3.connect('file:%s?mode=ro' % DATABASE.as_posix(), uri=True)
            try:
                filled = conn.execute('SELECT COUNT(*) FROM client_sets').fetchone()[0]
            except sqlite3.DatabaseError:
                filled = 0
            if filled:
                cls.conn = conn
            else:
                conn.close()
        path = newest(MIRRORS, 'items.json')
        cls.open_types = None
        if path is not None:
            cls.open_types = {
                one['definition']['item']['id']:
                    one['definition']['item']['baseParameters']['itemTypeId']
                for one in json.loads(path.read_text(encoding='utf-8'))}
        path = newest(CLIENTS, 'decoded.json')
        cls.client_types = None
        if path is not None:
            cls.client_types = {
                int(ident): item['type'] for ident, item
                in json.loads(path.read_text(encoding='utf-8'))['items'].items()}

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.close()
        super().tearDownClass()

    def need_db(self):
        if self.conn is None:
            self.skipTest('items_wakfu.db is absent or has no client tables')

    def need_both(self):
        if self.open_types is None or self.client_types is None:
            self.skipTest('no open data mirror or no decoded client')

    def ids_of(self, types, wanted):
        return {ident for ident, kind in types.items() if kind == wanted}

    def test_the_client_has_126_pets_and_the_open_data_117_and_9_are_pinned(self):
        self.need_db()
        self.need_both()
        pets = {ident: item for ident, item in self.conn.execute('SELECT id, item FROM pets')}
        self.assertEqual(126, len(pets))
        self.assertNotIn(None, pets.values())
        in_open_data = self.ids_of(self.open_types, PET_TYPE)
        self.assertEqual(117, len(in_open_data))
        self.assertEqual(set(), in_open_data - set(pets.values()))
        self.assertEqual(
            list(PETS_THE_OPEN_DATA_LACKS), sorted(set(pets.values()) - in_open_data))

    def test_the_open_data_names_195_of_the_355_client_sets_and_each_id_is_pinned(self):
        self.need_db()
        self.assertEqual(195, len(NAMED_SETS))
        self.assertEqual(
            list(NAMED_SETS), [ident for (ident,) in self.conn.execute(
                'SELECT id FROM sets ORDER BY id')])
        self.assertEqual(355, self.conn.execute('SELECT COUNT(*) FROM client_sets').fetchone()[0])
        self.assertEqual(0, self.conn.execute(
            'SELECT COUNT(*) FROM sets WHERE id NOT IN (SELECT id FROM client_sets)').fetchone()[0])

    def test_the_client_has_20_runes_and_the_open_data_17_of_them(self):
        self.need_both()
        client = self.ids_of(self.client_types, RUNE_TYPE)
        open_data = self.ids_of(self.open_types, RUNE_TYPE)
        self.assertEqual((20, 17), (len(client), len(open_data)))
        self.assertEqual(set(), open_data - client)
        self.assertEqual(list(RUNES_ONLY_THE_CLIENT_HAS), sorted(client - open_data))

    def test_the_client_has_467_sublimations_and_the_open_data_477_of_which_10_are_pinned(self):
        self.need_both()
        client = self.ids_of(self.client_types, SUBLIMATION_TYPE)
        open_data = self.ids_of(self.open_types, SUBLIMATION_TYPE)
        self.assertEqual((467, 477), (len(client), len(open_data)))
        self.assertEqual(set(), client - open_data)
        self.assertEqual(
            list(SUBLIMATIONS_ONLY_THE_OPEN_DATA_HAS), sorted(open_data - client))

    def test_a_sublimation_only_the_open_data_has_is_dropped_by_no_monster_and_no_list(self):
        self.need_db()
        extra = ', '.join(str(ident) for ident in SUBLIMATIONS_ONLY_THE_OPEN_DATA_HAS)
        self.assertEqual((0, 0), self.conn.execute(
            'SELECT (SELECT COUNT(*) FROM loot_list_rows WHERE item IN (%s)),'
            ' (SELECT COUNT(*) FROM monster_drops WHERE item IN (%s))' % (extra, extra)
        ).fetchone())
