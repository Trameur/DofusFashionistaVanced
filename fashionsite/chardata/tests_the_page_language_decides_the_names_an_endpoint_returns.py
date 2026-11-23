# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An unprefixed endpoint answers in the language of the page that called it."""

import json

from django.test import TestCase
from django.utils import translation

from chardata.translation_util import localized_stat_name
from chardata.url_language import page_language_from_header
from fashionistapulp.structure import (_current_game_version, get_structure,
                                       set_current_game_version)

LANGUAGES = ('en', 'fr', 'de', 'es', 'pt')


def _item_with_a_translated_stat():
    structure = get_structure('dofus3')
    for item in structure.get_items_list():
        if not item.stats:
            continue
        names = {}
        for language in LANGUAGES:
            with translation.override(language):
                names[language] = [localized_stat_name(structure.get_stat_by_id(stat_id).name)
                                   for stat_id, _value in item.stats
                                   if structure.get_stat_by_id(stat_id) is not None]
        if len({tuple(values) for values in names.values()}) == len(LANGUAGES):
            return item, names
    raise AssertionError('no item whose stat names differ in every language')


class ThePageLanguageDecidesTheNamesAnEndpointReturnsTests(TestCase):

    def setUp(self):
        previous = getattr(_current_game_version, 'version', 'dofus3')
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, previous)

    @classmethod
    def setUpTestData(cls):
        cls.item, cls.expected = _item_with_a_translated_stat()

    def _names(self, page_language, **extra):
        response = self.client.post('/getitemdetails/', {'item': self.item.id}, **extra)
        self.assertEqual(200, response.status_code)
        return [stat['name'] for stat in json.loads(response.content)['stats']]

    def test_the_page_language_wins_over_accept_language_and_cookie(self):
        for page in LANGUAGES:
            browser = 'fr' if page != 'fr' else 'de'
            self.client.cookies['django_language'] = browser
            with self.subTest(page=page):
                names = self._names(page, HTTP_ACCEPT_LANGUAGE=browser,
                                    HTTP_X_PAGE_LANGUAGE=page)
                self.assertEqual(self.expected[page], names)

    def test_without_the_header_the_browser_language_still_decides(self):
        self.client.cookies.clear()
        names = self._names('fr', HTTP_ACCEPT_LANGUAGE='fr')
        self.assertEqual(self.expected['fr'], names)

    def test_an_unknown_page_language_falls_back_to_the_browser(self):
        self.client.cookies.clear()
        for junk in ('xx', '', 'fr-evil', '../de'):
            with self.subTest(header=junk):
                names = self._names('de', HTTP_ACCEPT_LANGUAGE='es', HTTP_X_PAGE_LANGUAGE=junk)
                self.assertEqual(self.expected['es'], names)

    def test_a_cache_is_told_the_answer_depends_on_the_header(self):
        response = self.client.post('/getitemdetails/', {'item': self.item.id},
                                    HTTP_X_PAGE_LANGUAGE='de')
        self.assertIn('X-Page-Language', response.get('Vary', ''))

    def test_an_unprefixed_answer_without_the_header_still_varies_on_it(self):
        response = self.client.post('/getitemdetails/', {'item': self.item.id})
        self.assertIn('X-Page-Language', response.get('Vary', ''))

    def test_a_prefixed_answer_does_not_vary_on_the_header(self):
        response = self.client.post('/de/getitemdetails/', {'item': self.item.id},
                                    HTTP_X_PAGE_LANGUAGE='fr')
        self.assertEqual(200, response.status_code)
        self.assertNotIn('X-Page-Language', response.get('Vary', ''))
        self.assertEqual(self.expected['de'], [stat['name'] for stat in json.loads(response.content)['stats']])

    def test_the_header_reads_only_a_served_language(self):
        class Request:
            META = {'HTTP_X_PAGE_LANGUAGE': ' DE '}
        self.assertEqual('de', page_language_from_header(Request))
        Request.META = {'HTTP_X_PAGE_LANGUAGE': 'zz'}
        self.assertIsNone(page_language_from_header(Request))
