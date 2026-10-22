import os
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import get_wakfu_client  # noqa: E402


class TheWakfuClientPruneKeepsTheNewestVersionsByNumberTests(SimpleTestCase):
    def folders(self, names):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for name in names:
            (Path(temp.name) / name).mkdir()
        return Path(temp.name)

    def left(self, root):
        return sorted(path.name for path in root.iterdir())

    def test_a_three_digit_minor_sorts_after_a_two_digit_one(self):
        names = ['1.93.0', '1.100.0', '1.9.1', '1.99.5']
        ordered = sorted(names, key=get_wakfu_client.version_key)
        self.assertEqual(['1.9.1', '1.93.0', '1.99.5', '1.100.0'], ordered)

    def test_prune_removes_the_oldest_by_number_and_not_by_name(self):
        root = self.folders(['1.93.0', '1.100.0', '1.99.5', '1.88.0'])
        get_wakfu_client.prune(root, '1.100.0')
        self.assertEqual(['1.100.0', '1.99.5'], self.left(root))

    def test_the_kept_version_survives_even_when_it_is_the_oldest(self):
        root = self.folders(['1.93.0', '1.100.0', '1.99.5'])
        get_wakfu_client.prune(root, '1.93.0')
        self.assertEqual(['1.100.0', '1.93.0', '1.99.5'], self.left(root))

    def test_a_folder_name_with_letters_is_ordered_without_an_error(self):
        names = ['1.93.0', 'old', '1.100.0-beta', '1.100.0']
        ordered = sorted(names, key=get_wakfu_client.version_key)
        self.assertEqual('1.93.0', ordered[0])
        self.assertEqual('old', ordered[-1])
