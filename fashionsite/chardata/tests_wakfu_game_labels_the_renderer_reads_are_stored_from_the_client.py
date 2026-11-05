import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
SCRAPER = str(ROOT / 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import wakfu_client  # noqa: E402

DATABASE = ROOT / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'
CLIENTS = ROOT / 'itemscraper' / 'wakfu_client'
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
CLIENT_LANGUAGES = ('en', 'fr', 'es', 'pt')
WANTED = wakfu_client.LABEL_KEYS | wakfu_client.FIGHTER_WORDS


class TheWakfuLabelReaderTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.jar = Path(self.temp.name) / 'i18n_fr.jar'

    def write(self, lines):
        with zipfile.ZipFile(self.jar, 'w') as jar:
            jar.writestr('texts_fr.properties', '\n'.join(lines).encode('utf-8'))

    def test_every_wanted_key_is_read_under_its_own_key_and_nothing_else_is_kept(self):
        self.write(['%s=text of %s' % (key, key) for key in sorted(WANTED)]
                   + ['critere.a=kept', 'levelShort.other=dropped', 'ally.x=dropped',
                      'notaword=dropped'])
        labels, _nations = wakfu_client.read_labels(self.jar, 'fr')
        self.assertEqual({key: 'text of %s' % key for key in WANTED} | {'critere.a': 'kept'},
                         labels)

    def test_a_wanted_key_the_file_lacks_is_simply_absent(self):
        self.write(['ally=Ally'])
        labels, _nations = wakfu_client.read_labels(self.jar, 'fr')
        self.assertEqual({'ally': 'Ally'}, labels)

    def test_the_wanted_keys_are_the_four_level_and_merged_labels_and_the_fighter_words(self):
        self.assertEqual(4, len(wakfu_client.LABEL_KEYS))
        self.assertEqual(set(), wakfu_client.LABEL_KEYS & wakfu_client.FIGHTER_WORDS)
        self.assertEqual(len(wakfu_client.LABEL_KEYS) + len(wakfu_client.FIGHTER_WORDS),
                         len(WANTED))


class TheWakfuGameLabelsTheRendererReadsAreStoredFromTheClientTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = None
        if DATABASE.exists():
            conn = sqlite3.connect('file:%s?mode=ro' % DATABASE.as_posix(), uri=True)
            try:
                found = conn.execute('SELECT COUNT(*) FROM criteria_labels').fetchone()[0]
            except sqlite3.DatabaseError:
                found = 0
            if found:
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
            self.skipTest('items_wakfu.db is absent or has no criteria labels')

    def stored(self, language):
        return {key: text for key, text in self.conn.execute(
            'SELECT key, text FROM criteria_labels WHERE language = ?', (language,))
            if key in WANTED}

    def test_every_language_stores_the_same_wanted_keys(self):
        english = set(self.stored('en'))
        self.assertTrue(english)
        for language in LANGUAGES:
            self.assertEqual(english, set(self.stored(language)), language)

    def test_the_only_wanted_word_without_a_client_text_is_portal(self):
        self.assertEqual({'portal'}, WANTED - set(self.stored('en')))

    def test_each_stored_key_has_exactly_one_row_per_language(self):
        keys = len(self.stored('en'))
        marks = ','.join('?' * len(WANTED))
        rows = self.conn.execute(
            'SELECT COUNT(*) FROM criteria_labels WHERE key IN (%s)' % marks,
            sorted(WANTED)).fetchone()[0]
        self.assertEqual(keys * len(LANGUAGES), rows)
        self.assertEqual(0, self.conn.execute(
            'SELECT COUNT(*) FROM (SELECT key, language FROM criteria_labels'
            ' GROUP BY key, language HAVING COUNT(*) > 1)').fetchone()[0])

    def test_german_holds_the_english_text_of_each_wanted_key(self):
        self.assertEqual(self.stored('en'), self.stored('de'))

    def test_each_stored_text_is_the_one_the_language_file_of_the_client_holds(self):
        folders = sorted(CLIENTS.glob('*/i18n_en.jar')) if CLIENTS.exists() else []
        if not folders:
            self.skipTest('the decoded client folder is absent')
        folder = folders[-1].parent
        for language in CLIENT_LANGUAGES:
            properties = wakfu_client._properties(folder / ('i18n_%s.jar' % language), language)
            expected = {key: properties[key] for key in WANTED if key in properties}
            self.assertEqual(expected, self.stored(language), language)

    def test_the_level_labels_carry_the_level_slot_and_the_merged_labels_the_value_slot(self):
        for language in LANGUAGES:
            stored = self.stored(language)
            for key in ('levelShort.custom', 'levelShort.customCumulable'):
                self.assertIn('[#1]', stored[key], (language, key))
            for key in ('effect.description.merged.resistance',
                        'effect.description.merged.mastery'):
                self.assertIn('[#1]', stored[key], (language, key))
