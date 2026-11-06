import contextlib
import os
from html.parser import HTMLParser

from django.core.cache import cache
from django.test import TestCase

from chardata import wakfu_encyclopedia_data as data
from chardata.official_site import _slugify_name
from chardata.wakfu_flag_for_tests import wakfu_flag

AMULET = 2021
ORIGIN = 'https://dofusfashionista.gg'
PATH = '/%swakfu/encyclopedia/item/equipment/%d-%s/'


class _Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.canonical = None
        self.alternates = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag != 'link':
            return
        if attrs.get('rel') == 'canonical':
            self.canonical = attrs['href']
        elif attrs.get('rel') == 'alternate' and attrs.get('hreflang'):
            self.alternates[attrs['hreflang']] = attrs['href']


class AGermanWakfuPageKeepsItsLanguageTests(TestCase):
    """The language of a Wakfu item page is the one in the URL, and German keeps the English
    game texts the data holds, marked as English."""

    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        with contextlib.closing(data.connect()) as conn:
            self.names = dict(conn.execute(
                'SELECT language, name FROM item_names WHERE item = ?', (AMULET,)).fetchall())

    def slug_of(self, language):
        return _slugify_name(self.names[language], '')

    def get(self, language, slug):
        prefix = '' if language == 'en' else language + '/'
        with wakfu_flag(True):
            return self.client.get(PATH % (prefix, AMULET, slug))

    def test_the_german_url_with_the_english_slug_answers_in_german_without_a_redirect(self):
        response = self.get('de', self.slug_of('en'))
        self.assertEqual(200, response.status_code)
        self.assertIn('<html lang="de"', response.content.decode('utf-8'))

    def test_the_game_texts_are_english_inside_a_marked_span(self):
        html = self.get('de', self.slug_of('en')).content.decode('utf-8')
        self.assertIn('<span lang="en">%s</span>' % self.names['en'], html)
        self.assertIn('wakfu-game-text-notice', html)
        self.assertNotIn(self.names['fr'], html)

    def test_no_other_language_marks_its_game_texts(self):
        for language in ('en', 'fr', 'es', 'pt'):
            html = self.get(language, self.slug_of(language)).content.decode('utf-8')
            self.assertNotIn('<span lang="en">', html, language)
            self.assertNotIn('wakfu-game-text-notice', html, language)

    def test_a_wrong_slug_redirects_inside_the_german_prefix(self):
        response = self.get('de', 'not-the-name')
        self.assertEqual(301, response.status_code)
        self.assertEqual(PATH % ('de/', AMULET, self.slug_of('en')), response['Location'])

    def test_the_german_alternates_use_the_english_slug(self):
        links = _Links(self.get('de', self.slug_of('en')).content.decode('utf-8'))
        english = '/wakfu/encyclopedia/item/equipment/%d-%s/' % (AMULET, self.slug_of('en'))
        self.assertEqual(ORIGIN + '/de' + english, links.canonical)
        self.assertEqual(ORIGIN + '/de' + english, links.alternates['de'])
        self.assertEqual(ORIGIN + english, links.alternates['en'])
        self.assertEqual(ORIGIN + english, links.alternates['x-default'])
        for language in ('fr', 'es', 'pt'):
            self.assertEqual(
                '%s/%s/wakfu/encyclopedia/item/equipment/%d-%s/' % (
                    ORIGIN, language, AMULET, self.slug_of(language)),
                links.alternates[language])
