import hashlib
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

import cytrus_cdn  # noqa: E402


def sha1(blob):
    return hashlib.sha1(blob).hexdigest()


# Four distinct pieces; bundle a holds p1 p2 side by side and p4 after a gap, bundle b holds
# p3. The file is p1 p2 p3 p2 p4, so p2 sits twice in it and is fetched once.
PIECES = {'p1': b'1' * 40, 'p2': b'2' * 30, 'p3': b'3' * 50, 'p4': b'4' * 20}
BUNDLES = {'a' * 40: b'x' * 5 + PIECES['p1'] + PIECES['p2'] + b'y' * 9 + PIECES['p4'],
           'b' * 40: PIECES['p3']}
PLACEMENT = {'p1': ('a' * 40, 5, 40), 'p2': ('a' * 40, 45, 30), 'p4': ('a' * 40, 84, 20),
             'p3': ('b' * 40, 0, 50)}
ORDER = ('p1', 'p2', 'p3', 'p2', 'p4')


def entry():
    chunks, offset = [], 0
    for name in ORDER:
        chunks.append({'hash': sha1(PIECES[name]), 'size': len(PIECES[name]),
                       'offset': offset})
        offset += len(PIECES[name])
    blob = b''.join(PIECES[name] for name in ORDER)
    return {'name': 'big.jar', 'size': len(blob), 'hash': sha1(blob), 'chunks': chunks,
            'placement': {sha1(PIECES[name]): where for name, where in PLACEMENT.items()}}, blob


class Response:
    def __init__(self, body):
        self.body = body
        self.at = 0

    def read(self, size=-1):
        size = len(self.body) - self.at if size < 0 else size
        piece = self.body[self.at:self.at + size]
        self.at += len(piece)
        return piece

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TheCytrusBigFilesStreamInOneRequestPerBundleTests(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.ranges = []

    def serve(self, bundles):
        def urlopen(request, timeout=None):
            bundle = request.full_url.rsplit('/', 1)[1]
            start, end = (int(one) for one in
                          request.get_header('Range').split('=')[1].split('-'))
            self.ranges.append((bundle[:1], start, end))
            return Response(bundles[bundle][start:end + 1])
        return mock.patch.object(cytrus_cdn.urllib.request, 'urlopen', urlopen)

    def test_a_run_of_side_by_side_chunks_is_one_request_and_a_repeated_chunk_is_fetched_once(self):
        wanted, blob = entry()
        target = self.folder / 'big.jar'
        with self.serve(BUNDLES):
            cytrus_cdn.fetch_file_to(wanted, target, game='wakfu')
        self.assertEqual(blob, target.read_bytes())
        self.assertEqual([('a', 5, 74), ('a', 84, 103), ('b', 0, 49)], sorted(self.ranges))
        self.assertEqual(['big.jar'], [path.name for path in self.folder.iterdir()])

    def test_a_chunk_that_does_not_match_its_hash_leaves_no_file_and_no_part(self):
        wanted, _blob = entry()
        bad = dict(BUNDLES)
        bad['b' * 40] = b'9' * 50
        target = self.folder / 'big.jar'
        with self.serve(bad):
            with self.assertRaisesRegex(ValueError, 'does not match its hash'):
                cytrus_cdn.fetch_file_to(wanted, target, game='wakfu')
        self.assertEqual([], list(self.folder.iterdir()))

    def test_a_whole_file_hash_that_differs_leaves_no_file_and_no_part(self):
        wanted, _blob = entry()
        wanted['hash'] = '0' * 40
        target = self.folder / 'big.jar'
        with self.serve(BUNDLES):
            with self.assertRaisesRegex(ValueError, 'big.jar does not match'):
                cytrus_cdn.fetch_file_to(wanted, target, game='wakfu')
        self.assertEqual([], list(self.folder.iterdir()))

    def test_a_bundle_that_ends_inside_a_chunk_leaves_no_part(self):
        wanted, _blob = entry()
        short = dict(BUNDLES)
        short['b' * 40] = PIECES['p3'][:10]
        target = self.folder / 'big.jar'
        with self.serve(short):
            with self.assertRaisesRegex(ValueError, 'ended inside a chunk'):
                cytrus_cdn.fetch_file_to(wanted, target, game='wakfu')
        self.assertEqual([], list(self.folder.iterdir()))
