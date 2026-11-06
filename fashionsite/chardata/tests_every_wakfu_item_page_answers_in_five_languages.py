import os

from django.core.cache import cache
from django.test import TestCase

from chardata import wakfu_encyclopedia_data as data
from chardata.official_site import _slugify_name
from chardata.wakfu_flag_for_tests import wakfu_flag

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
UNKNOWN_ID = 999999999


def slug(name):
    return _slugify_name(name, '')


def path_of(language, item, name, item_type='equipment'):
    prefix = '' if language == 'en' else language + '/'
    return '/%swakfu/encyclopedia/item/%s/%d-%s/' % (prefix, item_type, item, slug(name))


class EveryWakfuItemPageAnswersInFiveLanguagesTests(TestCase):
    """One live item of each type answers in each language while the flag is on."""

    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)

    def names_of(self, item):
        return dict(self.conn.execute(
            'SELECT language, name FROM item_names WHERE item = ?', (item,)).fetchall())

    def one_item_per_type(self):
        return [row[0] for row in self.conn.execute(
            'SELECT MIN(id) FROM items WHERE removed = 0 GROUP BY type ORDER BY type')]

    def test_the_sample_covers_every_live_type(self):
        self.assertEqual(
            self.conn.execute(
                'SELECT COUNT(DISTINCT type) FROM items WHERE removed = 0').fetchone()[0],
            len(self.one_item_per_type()))

    def test_each_item_answers_200_in_each_language(self):
        with wakfu_flag(True):
            for item in self.one_item_per_type():
                names = self.names_of(item)
                for language in LANGUAGES:
                    name = names['en' if language == 'de' else language]
                    path = path_of(language, item, name)
                    with self.subTest(path=path):
                        self.assertEqual(200, self.client.get(path).status_code)

    def test_each_item_answers_404_while_the_flag_is_off(self):
        for item in self.one_item_per_type():
            names = self.names_of(item)
            for language in LANGUAGES:
                path = path_of(language, item, names['en' if language == 'de' else language])
                with self.subTest(path=path):
                    self.assertEqual(404, self.client.get(path).status_code)

    def test_a_removed_item_answers_404(self):
        removed = self.conn.execute(
            'SELECT id FROM items WHERE removed = 1 ORDER BY id').fetchone()
        self.assertIsNotNone(removed)
        with wakfu_flag(True):
            for language in LANGUAGES:
                path = path_of(language, removed[0], 'x')
                with self.subTest(path=path):
                    self.assertEqual(404, self.client.get(path).status_code)

    def test_an_unknown_id_answers_404(self):
        self.assertIsNone(self.conn.execute(
            'SELECT id FROM items WHERE id = ?', (UNKNOWN_ID,)).fetchone())
        with wakfu_flag(True):
            for language in LANGUAGES:
                with self.subTest(language=language):
                    self.assertEqual(
                        404, self.client.get(path_of(language, UNKNOWN_ID, 'x')).status_code)

    def test_a_type_other_than_equipment_answers_404(self):
        item = self.one_item_per_type()[0]
        name = self.names_of(item)['en']
        with wakfu_flag(True):
            for other in ('resources', 'monster'):
                with self.subTest(item_type=other):
                    self.assertEqual(
                        404, self.client.get(path_of('en', item, name, other)).status_code)

    def test_a_stale_slug_redirects_inside_each_language(self):
        item = self.one_item_per_type()[0]
        names = self.names_of(item)
        with wakfu_flag(True):
            for language in LANGUAGES:
                expected = path_of(language, item, names['en' if language == 'de' else language])
                with self.subTest(language=language):
                    response = self.client.get(path_of(language, item, 'a stale name'))
                    self.assertEqual(301, response.status_code)
                    self.assertEqual(expected, response['Location'])

    def test_each_page_links_the_list_of_its_language_and_declares_the_breadcrumb(self):
        item = self.one_item_per_type()[0]
        names = self.names_of(item)
        with wakfu_flag(True):
            for language in LANGUAGES:
                name = names['en' if language == 'de' else language]
                list_path = '/%swakfu/encyclopedia/' % ('' if language == 'en' else language + '/')
                with self.subTest(language=language):
                    html = self.client.get(path_of(language, item, name)).content.decode('utf-8')
                    self.assertIn('class="encyclopedia-crumbs"', html)
                    self.assertIn('href="%s"' % list_path, html)
                    self.assertIn('"@type": "BreadcrumbList"', html)
                    self.assertIn('https://dofusfashionista.gg%s"' % list_path, html)
