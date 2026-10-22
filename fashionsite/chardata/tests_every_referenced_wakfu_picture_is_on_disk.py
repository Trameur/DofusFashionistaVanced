import sqlite3
import sys
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
SCRAPER = str(ROOT / 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import get_wakfu_images  # noqa: E402

DATABASE = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'
STATIC = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata'

# Pictures the client's archive does not hold for a row it names, by target: the number of
# distinct pictures with no file, and the ids when the list is short. A list that grows
# fails; one that shrinks is a gain to write down here.
KNOWN_MISSING = {
    'items': 46, 'spells': 2, 'states': 10, 'abilities': 0, 'class icons': 0,
    'class portraits': 0, 'monsters': 372, 'monster families': 287,
}
KNOWN_MISSING_IDS = {'spells': {2336, 3094}}


class TheReferencedWakfuPicturesAreOnDiskTests(TestCase):
    """Guards on the real items_wakfu.db and the folders get_wakfu_images.py fills."""

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
        if not (STATIC / 'spells' / 'wakfu').is_dir():
            self.skipTest('get_wakfu_images.py has not run here')

    def missing(self):
        found = {}
        for name, family, _key, folder, _edge, _default in get_wakfu_images.TARGETS:
            stems = get_wakfu_images.wanted(self.conn, name, family)
            found[name] = {ident for stem, ident in stems.items()
                           if not (STATIC / folder / (stem + '.webp')).is_file()}
        return found

    def test_every_target_has_its_placeholder(self):
        for name, _family, _key, folder, _edge, _default in get_wakfu_images.TARGETS:
            self.assertTrue((STATIC / folder / 'default.webp').is_file(), name)

    def test_no_target_misses_more_pictures_than_the_archive_lacks(self):
        found = self.missing()
        for name, limit in KNOWN_MISSING.items():
            self.assertLessEqual(len(found[name]), limit, name)

    def test_the_spells_without_a_file_are_the_two_the_archive_lacks(self):
        self.assertEqual(KNOWN_MISSING_IDS['spells'], self.missing()['spells'])
