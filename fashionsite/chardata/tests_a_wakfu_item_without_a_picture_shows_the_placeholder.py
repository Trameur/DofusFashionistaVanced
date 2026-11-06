import contextlib
import os
import shutil
import tempfile

from django.core.cache import cache
from django.test import TestCase, override_settings

from chardata import wakfu_encyclopedia_data as data
from chardata.wakfu_flag_for_tests import wakfu_flag

PLACEHOLDER = 'chardata/QuestionMark-lighttheme.png'


class AWakfuItemWithoutAPictureShowsThePlaceholderTests(TestCase):
    """With one picture on disk, that item shows it and every other item shows the placeholder."""

    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        with contextlib.closing(data.connect()) as conn:
            self.pairs = conn.execute(
                'SELECT i.id, p.gfx FROM items i JOIN item_picture p ON p.item = i.id'
                ' WHERE i.removed = 0 AND p.gfx IN (SELECT gfx FROM item_picture GROUP BY gfx'
                ' HAVING COUNT(*) = 1) ORDER BY i.id LIMIT 2').fetchall()
        (self.shown, self.gfx), (self.hidden, _gfx) = self.pairs
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        picture = os.path.join(self.folder, 'chardata', 'items', 'wakfu', '64')
        os.makedirs(picture)
        with open(os.path.join(picture, '%d.webp' % self.gfx), 'wb') as handle:
            handle.write(b'RIFF')

    def html_of(self, item_id):
        with wakfu_flag(True):
            response = self.client.get('/wakfu/encyclopedia/item/equipment/%d-x/' % item_id,
                                       follow=True)
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')

    def test_an_item_whose_picture_exists_shows_it(self):
        with override_settings(STATICFILES_DIRS=[self.folder]):
            html = self.html_of(self.shown)
        self.assertIn('chardata/items/wakfu/64/%d.webp' % self.gfx, html)
        self.assertNotIn('wakfu-picture-dark', html)

    def test_an_item_whose_picture_is_missing_shows_the_placeholder_pair(self):
        with override_settings(STATICFILES_DIRS=[self.folder]):
            html = self.html_of(self.hidden)
        self.assertIn(PLACEHOLDER, html)
        self.assertIn('QuestionMark-darktheme.png', html)
        self.assertNotIn('chardata/items/wakfu/64/%d.webp' % self.gfx, html)
