# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An item icon found in a doduda image export is read from it, the source answers only for the others."""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRAPER = os.path.join(ROOT, 'itemscraper')

ITEMS = [
    {'name_en': 'Salamuncher Sari', 'w_type': 'Cloak',
     'image_url': 'https://x/img/item/17183-128.png', 'image_url_fallback': 'https://x/img/item/17183-64.png'},
    {'name_en': 'Gelano', 'w_type': 'Ring',
     'image_url': 'https://x/img/item/9001-128.png', 'image_url_fallback': 'https://x/img/item/9001-64.png'},
    {'name_en': 'Bow Meow', 'w_type': 'Pet',
     'image_url': 'https://x/img/item/9002-128.png', 'image_url_fallback': 'https://x/img/item/9002-64.png'},
]


def scraper():
    if SCRAPER not in sys.path:
        sys.path.insert(0, SCRAPER)
    import get_equipments4
    return get_equipments4


class Answer:

    def __init__(self, url):
        self.status_code = 200
        self.content = b'http ' + url.encode()


class Session:

    def __init__(self):
        self.urls = []

    def get(self, url, **options):
        self.urls.append(url)
        return Answer(url)


class ALocalIconExportIsReadBeforeAnyDownloadTests(SimpleTestCase):

    def run_images(self, folder, extra=()):
        module = scraper()
        session = Session()
        stored = {}
        with tempfile.TemporaryDirectory() as work:
            source = os.path.join(work, 'transformed_equipment.json')
            with open(source, 'w', encoding='utf-8') as handle:
                json.dump(ITEMS, handle)
            with mock.patch.object(module, 'make_session', return_value=session), \
                    mock.patch.object(module, 'store_image',
                                      side_effect=lambda content, path: stored.setdefault(
                                          os.path.basename(path), content)), \
                    mock.patch.object(sys, 'argv', ['get_equipments4.py', '--game-version', 'beta',
                                                    '--input-file', source, *extra]), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                code = module.main()
        return code, session.urls, stored, output.getvalue()

    def export(self, folder):
        (folder / '2x').mkdir(parents=True)
        (folder / '1x').mkdir()
        (folder / '2x' / '17183.png').write_bytes(b'local 2x 17183')
        (folder / '1x' / '17183.png').write_bytes(b'local 1x 17183')
        (folder / '1x' / '9001.png').write_bytes(b'local 1x 9001')

    def test_the_sized_url_of_an_item_picks_its_scale_folder(self):
        module = scraper()
        with tempfile.TemporaryDirectory() as work:
            folder = Path(work)
            self.export(folder)
            self.assertEqual(b'local 2x 17183', module.local_icon(ITEMS[0], folder))
            self.assertEqual(b'local 1x 9001', module.local_icon(ITEMS[1], folder))
            self.assertIsNone(module.local_icon(ITEMS[2], folder))
            self.assertIsNone(module.local_icon({'image_url': 'https://x/img/item/17183.png'}, folder))

    def test_only_the_icons_the_export_lacks_are_downloaded(self):
        with tempfile.TemporaryDirectory() as work:
            folder = Path(work) / 'img_item'
            self.export(folder)
            code, urls, stored, output = self.run_images(folder, ['--local-icons', str(folder)])
        self.assertEqual(0, code)
        self.assertEqual([ITEMS[2]['image_url']], urls)
        self.assertEqual(b'local 2x 17183', stored['Salamuncher Sari.png'])
        self.assertEqual(b'local 1x 9001', stored['Gelano.png'])
        self.assertEqual(b'http ' + ITEMS[2]['image_url'].encode(), stored['Bow Meow.png'])
        self.assertIn('2 of 3 images read from', output)

    def test_without_an_export_every_icon_is_downloaded_as_before(self):
        code, urls, stored, output = self.run_images(None)
        self.assertEqual(0, code)
        self.assertEqual([item['image_url'] for item in ITEMS], urls)
        self.assertNotIn('read from', output)
