import argparse
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import get_wakfu_client  # noqa: E402
import update_audit  # noqa: E402

GUI = get_wakfu_client.GUI_JAR.rsplit('/', 1)[1]


def name_of(path):
    return path.rsplit('/', 1)[-1]


class TheWakfuClientReusesAndPrunesItsPictureArchiveTests(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def folder(self, name, files=None):
        folder = self.root / name
        folder.mkdir()
        for path in files or ():
            (folder / name_of(path)).write_bytes(b'content of ' + path.encode())
        return folder

    def entries_of(self, folder):
        entries = {}
        for path in get_wakfu_client.FILES:
            blob = (folder / name_of(path)).read_bytes()
            entries[path] = {'size': len(blob), 'hash': get_wakfu_client.sha1_of(blob)}
        return entries

    def test_both_new_files_are_part_of_the_client(self):
        self.assertIn(get_wakfu_client.GUI_JAR, get_wakfu_client.FILES)
        self.assertIn(get_wakfu_client.CONFIG, get_wakfu_client.FILES)
        self.assertIn(get_wakfu_client.CODE_JAR, get_wakfu_client.FILES)
        self.assertEqual(20, len(get_wakfu_client.FILES))

    def test_a_file_with_the_same_sha1_in_another_folder_is_reused_without_a_fetch(self):
        old = self.folder('6.0_1.93.1.5312.334', get_wakfu_client.FILES)
        new = self.folder('6.0_1.93.2.5400.335')
        entries = self.entries_of(old)
        args = argparse.Namespace(from_install=None)
        with mock.patch.object(get_wakfu_client.cytrus_cdn, 'find_file',
                               lambda _manifest, path: entries[path]), \
                mock.patch.object(get_wakfu_client, 'from_cytrus',
                                  side_effect=AssertionError('fetched')):
            hashes = get_wakfu_client.place_files(args, new, b'manifest')
        self.assertEqual(set(get_wakfu_client.FILES), set(hashes))
        for path in get_wakfu_client.FILES:
            self.assertEqual((old / name_of(path)).read_bytes(),
                             (new / name_of(path)).read_bytes(), path)
        self.assertEqual([], list(new.glob('*.part')))

    def test_a_file_that_differs_is_fetched(self):
        old = self.folder('6.0_1.93.1.5312.334', get_wakfu_client.FILES)
        new = self.folder('6.0_1.93.2.5400.335')
        entries = self.entries_of(old)
        fresh = b'a newer picture archive'
        entries[get_wakfu_client.GUI_JAR] = {
            'size': len(fresh), 'hash': get_wakfu_client.sha1_of(fresh)}
        fetched = []

        def fetch(entry, target):
            fetched.append(target.name)
            target.write_bytes(fresh)

        with mock.patch.object(get_wakfu_client.cytrus_cdn, 'find_file',
                               lambda _manifest, path: entries[path]), \
                mock.patch.object(get_wakfu_client, 'from_cytrus', fetch):
            get_wakfu_client.place_files(argparse.Namespace(from_install=None), new, b'm')
        self.assertEqual([GUI], fetched)
        self.assertEqual(fresh, (new / GUI).read_bytes())

    def test_prune_drops_the_picture_archive_from_older_folders_only(self):
        for name in ('1.88.0', '1.93.0', '1.99.5', '1.100.0'):
            self.folder(name, [get_wakfu_client.GUI_JAR, get_wakfu_client.ITEMS_JAR])
        get_wakfu_client.prune(self.root, '1.100.0')
        self.assertEqual(['1.100.0', '1.99.5'], sorted(path.name for path in self.root.iterdir()))
        self.assertTrue((self.root / '1.100.0' / GUI).is_file())
        self.assertFalse((self.root / '1.99.5' / GUI).exists())
        self.assertTrue((self.root / '1.99.5' / '35.jar').is_file())

    def test_prune_keeps_the_archive_of_the_folder_it_was_told_to_keep(self):
        for name in ('1.93.0', '1.100.0'):
            self.folder(name, [get_wakfu_client.GUI_JAR])
        get_wakfu_client.prune(self.root, '1.93.0')
        self.assertTrue((self.root / '1.93.0' / GUI).is_file())

    def test_the_audit_counts_a_client_version_folder_as_a_cache(self):
        self.assertTrue(update_audit.is_cached(
            'itemscraper/wakfu_client/6.0_1.93.1.5312.334/gui.jar'))
        self.assertTrue(update_audit.is_cached('itemscraper/wakfu_raw/1.93.1.62/recipes.json'))
        self.assertFalse(update_audit.is_cached('itemscraper/wakfu_client/readme.txt'))

    def test_the_audit_backs_up_the_new_picture_folders(self):
        for name in ('states', 'abilities', 'classes'):
            self.assertIn(name, update_audit.IMAGE_DIRECTORIES)
