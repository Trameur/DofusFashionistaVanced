import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import build_wakfu_db as builder  # noqa: E402
import get_wakfu_client  # noqa: E402
import get_wakfu_images  # noqa: E402
import wakfu_client  # noqa: E402
import wakfu_client_code  # noqa: E402

CLIENT_DIR = Path(SCRAPER) / 'wakfu_client'
RARITIES = {'COMMON': 0, 'UNUSUAL': 1, 'RARE': 2, 'ADMIN': 10}
FILES = {'COMMON': 'old', 'UNUSUAL': 'common', 'RARE': 'rare', 'ADMIN': 'admin'}
NAMES = {
    'en': {'item.rarity.COMMON': 'Old Item', 'item.rarity.UNUSUAL': 'Common',
           'item.rarity.RARE': 'Rare', 'item.rarity.ADMIN': 'Administrator',
           'item.rarity.TRASH': 'Trash'},
    'fr': {'item.rarity.COMMON': 'Ancien objet', 'item.rarity.UNUSUAL': 'Commun',
           'item.rarity.RARE': 'Rare', 'item.rarity.ADMIN': 'Administrateur'},
}


def newest_folder():
    found = sorted((path for path in CLIENT_DIR.glob('*') if (path / 'tables.json').exists()),
                   key=lambda path: get_wakfu_client.version_key(path.name))
    return found[-1] if found else None


class TheRarityNamesAreTheClientsLanguageKeysOfItsRarityEnumTests(SimpleTestCase):
    def test_the_language_reader_keeps_the_item_rarity_keys_under_their_whole_key(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'i18n_en.jar'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('texts_en.properties',
                                 'item.rarity.COMMON=Old Item\nitem.rarity=Rarity\n'
                                 'title.rarity.0=Common\n')
            read = wakfu_client.read_texts(path, 'en')
        self.assertEqual({'item.rarity.COMMON': 'Old Item'}, read['rarity_names'])

    def test_the_family_is_one_of_the_families_a_decoded_folder_must_hold(self):
        self.assertIn('rarity_names', wakfu_client.ALL_TEXT_FAMILIES)

    def test_every_rarity_of_the_enum_is_named_in_the_five_languages_german_from_english(self):
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE rarity_names (rarity INTEGER, language TEXT, name TEXT)')
        names = {language: NAMES['en'] for language in ('en', 'fr', 'es', 'pt')}
        names['fr'] = NAMES['fr']
        counts = _Counter()
        builder.write_rarity_names(conn, {'texts': {'rarity_names': names}},
                                   {'rarities': RARITIES}, counts)
        stored = {(rarity, language): name for rarity, language, name in conn.execute(
            'SELECT rarity, language, name FROM rarity_names')}
        self.assertEqual(len(RARITIES) * len(builder.LANGUAGES), len(stored))
        self.assertEqual(len(stored), counts['rarity names'])
        self.assertEqual('Old Item', stored[(0, 'de')])
        self.assertEqual('Ancien objet', stored[(0, 'fr')])
        self.assertEqual('Administrator', stored[(10, 'en')])

    def test_a_rarity_the_client_leaves_unnamed_in_a_language_stops_the_build(self):
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE rarity_names (rarity INTEGER, language TEXT, name TEXT)')
        fr = {key: text for key, text in NAMES['fr'].items() if 'ADMIN' not in key}
        names = {'en': NAMES['en'], 'fr': fr, 'es': NAMES['en'], 'pt': NAMES['en']}
        with self.assertRaisesMessage(ValueError, 'ADMIN in fr'):
            builder.write_rarity_names(conn, {'texts': {'rarity_names': names}},
                                       {'rarities': RARITIES}, _Counter())


class _Counter(dict):
    def __missing__(self, key):
        return 0


class TheStoredRarityNamesHoldOneRowPerRarityAndLanguageTests(SimpleTestCase):
    def setUp(self):
        self.folder = newest_folder()
        if self.folder is None or not builder.WAKFU_DB.exists():
            self.skipTest('no decoded Wakfu client or database')
        self.db = sqlite3.connect('file:%s?mode=ro' % builder.WAKFU_DB, uri=True)
        self.addCleanup(self.db.close)
        try:
            self.db.execute('SELECT 1 FROM rarity_names LIMIT 1')
        except sqlite3.OperationalError:
            self.skipTest('the database predates rarity_names')
        self.code = json.loads((self.folder / 'client_code.json').read_text(encoding='utf-8'))
        self.texts = json.loads((self.folder / 'texts.json').read_text(encoding='utf-8'))

    def test_the_stored_rows_are_the_enum_times_the_five_languages(self):
        count = self.db.execute('SELECT COUNT(*) FROM rarity_names').fetchone()[0]
        self.assertEqual(len(self.code['rarities']) * len(builder.LANGUAGES), count)

    def test_every_stored_name_is_the_language_file_text_of_its_enum_key(self):
        by_id = {rarity: enum for enum, rarity in self.code['rarities'].items()}
        wrong = []
        for rarity, language, name in self.db.execute(
                'SELECT rarity, language, name FROM rarity_names'):
            source = 'en' if language == 'de' else language
            expected = self.texts['texts']['rarity_names'][source]['item.rarity.' + by_id[rarity]]
            if name != expected:
                wrong.append((rarity, language))
        self.assertEqual([], wrong)

    def test_every_rarity_an_item_has_is_named(self):
        unnamed = self.db.execute(
            'SELECT DISTINCT rarity FROM item_rarity WHERE rarity NOT IN'
            ' (SELECT rarity FROM rarity_names)').fetchall()
        self.assertEqual([], unnamed)

    def test_the_rarity_names_are_unique_per_rarity_and_language(self):
        total, distinct = self.db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT rarity || language) FROM rarity_names").fetchone()
        self.assertEqual(total, distinct)


class TheRarityBorderFilesAreTheOnesTheClientsRarityEnumNamesTests(SimpleTestCase):
    MEMBERS = {'theme/images/itemsRarityBorders/%s.tga' % stem for stem in FILES.values()}

    def code_folder(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        (folder / 'client_code.json').write_text(
            json.dumps({'rarities': RARITIES, 'rarity_files': files}), encoding='utf-8')
        return folder

    def test_each_rarity_id_maps_to_the_archive_member_of_the_file_its_enum_constant_names(self):
        found = get_wakfu_images.rarity_borders(self.code_folder(FILES), self.MEMBERS)
        self.assertEqual({0: 'theme/images/itemsRarityBorders/old.tga',
                          1: 'theme/images/itemsRarityBorders/common.tga',
                          2: 'theme/images/itemsRarityBorders/rare.tga',
                          10: 'theme/images/itemsRarityBorders/admin.tga'}, found)

    def test_a_file_the_archive_lacks_stops_the_export(self):
        with self.assertRaisesMessage(wakfu_client.TableError, 'old'):
            get_wakfu_images.rarity_borders(self.code_folder(FILES),
                                            self.MEMBERS - {'theme/images/itemsRarityBorders/old.tga'})

    def test_a_file_name_that_two_archive_members_share_stops_the_export(self):
        twice = self.MEMBERS | {'theme/other/itemsRarityBorders/old.tga'}
        with self.assertRaisesMessage(wakfu_client.TableError, '2 archive members'):
            get_wakfu_images.rarity_borders(self.code_folder(FILES), twice)


class TheClientCodeNamesABorderFileForEveryRarityTests(SimpleTestCase):
    def setUp(self):
        self.folder = newest_folder()
        if self.folder is None or not (self.folder / 'gui.jar').exists() \
                or not (self.folder / 'wakfu-client.jar').exists():
            self.skipTest('no decoded Wakfu client with its archives')

    def test_the_decoded_code_holds_a_file_for_each_rarity_and_the_archive_holds_the_file(self):
        code = json.loads((self.folder / 'client_code.json').read_text(encoding='utf-8'))
        self.assertEqual(set(code['rarities']), set(code['rarity_files']))
        with zipfile.ZipFile(self.folder / 'gui.jar') as archive:
            borders = get_wakfu_images.rarity_borders(self.folder, set(archive.namelist()))
        self.assertEqual(set(code['rarities'].values()), set(borders))

    def test_reading_the_client_code_again_gives_the_decoded_file_names(self):
        code = json.loads((self.folder / 'client_code.json').read_text(encoding='utf-8'))
        read = wakfu_client_code.read_constants(self.folder / 'wakfu-client.jar')
        self.assertEqual(code['rarity_files'], read['rarity_files'])

    def test_the_exported_pictures_are_one_webp_per_rarity_id_when_they_were_exported(self):
        target = get_wakfu_images.STATIC / get_wakfu_images.RARITY_TARGET
        if not target.is_dir():
            self.skipTest('the rarity borders were not exported')
        code = json.loads((self.folder / 'client_code.json').read_text(encoding='utf-8'))
        self.assertEqual({'%d.webp' % rarity for rarity in code['rarities'].values()},
                         {path.name for path in target.iterdir()})
