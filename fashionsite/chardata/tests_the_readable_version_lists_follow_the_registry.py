# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The sentences that count and name the versions follow the versions readers can reach, in the five languages."""
import re
from unittest import mock

from django.test import SimpleTestCase, TestCase

from chardata import guides_content, readable_versions
from fashionistapulp import game_versions
from fashionistapulp.game_versions import GAME_VERSIONS, reader_dofus_versions

LANGUAGES = ('en', 'fr', 'de', 'es', 'pt')
NUMBER_WORDS = {
    'en': ('two', 'three', 'four', 'five', 'six', 'seven'),
    'fr': ('deux', 'trois', 'quatre', 'cinq', 'six', 'sept'),
    'de': ('zwei', 'drei', 'vier', 'fünf', 'sechs', 'sieben'),
    'es': ('dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete'),
    'pt': ('dois', 'três', 'quatro', 'cinco', 'seis', 'sete'),
}


def _hidden_dofus_versions():
    return [key for key in game_versions.dofus_versions() if GAME_VERSIONS[key].experimental]


def _readable(key):
    return mock.patch.object(GAME_VERSIONS[key], 'experimental', False)


def _home(client, language):
    prefix = '' if language == 'en' else '/%s' % language
    response = client.get(prefix + '/')
    assert response.status_code == 200, (language, response.status_code)
    return response.content.decode('utf-8')


class TheCountAndTheNamesComeFromTheRegistryTests(SimpleTestCase):

    def test_the_count_is_the_number_of_readable_dofus_versions(self):
        count = len(reader_dofus_versions())
        for language in LANGUAGES:
            self.assertEqual(NUMBER_WORDS[language][count - 2], readable_versions.count_word(language), language)

    def test_the_names_are_the_registrys_names_in_page_order(self):
        for language in LANGUAGES:
            listed = readable_versions.version_names(language, conjunction='')
            self.assertEqual([GAME_VERSIONS[key].game_name for key in reader_dofus_versions()], listed.split(', '))
            short = readable_versions.version_names(language, short=True, conjunction='')
            self.assertEqual([GAME_VERSIONS[key].label for key in reader_dofus_versions()], short.split(', '))

    def test_the_last_name_follows_the_conjunction_of_the_language(self):
        for language, word in (('en', 'and'), ('fr', 'et'), ('de', 'und'), ('es', 'y'), ('pt', 'e')):
            last = GAME_VERSIONS[reader_dofus_versions()[-1]].game_name
            self.assertTrue(readable_versions.version_names(language).endswith(' %s %s' % (word, last)), language)

    def test_an_experimental_version_is_in_neither(self):
        for key in _hidden_dofus_versions():
            for language in LANGUAGES:
                self.assertNotIn(GAME_VERSIONS[key].game_name, readable_versions.version_names(language))
                self.assertNotIn(GAME_VERSIONS[key].label, readable_versions.version_names(language, short=True).split(', '))

    def test_a_version_that_goes_live_is_counted_and_named_by_itself(self):
        for key in _hidden_dofus_versions():
            before = {language: readable_versions.count_word(language) for language in LANGUAGES}
            with _readable(key):
                for language in LANGUAGES:
                    self.assertNotEqual(before[language], readable_versions.count_word(language), (key, language))
                    self.assertIn(GAME_VERSIONS[key].game_name, readable_versions.version_names(language), (key, language))
                    self.assertIn(GAME_VERSIONS[key].label, readable_versions.version_names(language, short=True), (key, language))


class ThePagesSayWhatTheRegistrySaysTests(TestCase):

    def _check_home(self, language):
        html = _home(self.client, language)
        self.assertIn(readable_versions.version_names(language), html, language)
        self.assertIn('(%s)' % readable_versions.version_names(language, native=True), html, language)
        self.assertIn(' %s ' % readable_versions.count_word(language), html, language)
        return html

    def test_the_home_page_names_the_readable_versions_in_every_language(self):
        for language in LANGUAGES:
            self._check_home(language)

    def test_the_home_page_names_a_version_once_it_goes_live(self):
        for key in _hidden_dofus_versions():
            for language in LANGUAGES:
                with self.subTest(version=key, language=language):
                    self.assertNotIn(GAME_VERSIONS[key].game_name, self._check_home(language))
                    with _readable(key):
                        self.assertIn(GAME_VERSIONS[key].game_name, self._check_home(language))

    def test_the_faq_and_the_guides_page_name_the_readable_versions(self):
        for language in LANGUAGES:
            prefix = '' if language == 'en' else '/%s' % language
            faq = self.client.get(prefix + '/faq/').content.decode('utf-8')
            self.assertIn(readable_versions.version_names(language, short=True, conjunction='or'), faq, language)
            guides = self.client.get(prefix + '/guides/').content.decode('utf-8')
            self.assertIn(readable_versions.version_names(language, short=True, native=True), guides, language)


class TheGuidesSayWhatTheRegistrySaysTests(SimpleTestCase):

    SLUG = 'versions-explained'

    def _guide(self, language):
        return guides_content.get_guide(self.SLUG, language)

    def test_no_token_is_left_in_any_guide(self):
        for slug in guides_content.GUIDES:
            for language in LANGUAGES:
                guide = guides_content.get_guide(slug, language)
                for field in ('title', 'desc', 'lead', 'body'):
                    self.assertIsNone(re.search(r'\[\[(versions|if-readable|/if-readable)', guide.get(field, '')),
                                      (slug, language, field))

    def test_the_title_lists_the_readable_versions(self):
        for language in LANGUAGES:
            plain = readable_versions.version_names(language, short=True, conjunction='', native=True)
            self.assertTrue(self._guide(language)['title'].startswith(plain), language)

    def test_the_lead_counts_them(self):
        for language in LANGUAGES:
            self.assertIn(readable_versions.count_word(language), self._guide(language)['lead'], language)

    def test_a_hidden_version_has_no_section_and_a_live_one_has_its_own(self):
        for key in _hidden_dofus_versions():
            label = GAME_VERSIONS[key].label
            for language in LANGUAGES:
                with self.subTest(version=key, language=language):
                    self.assertNotRegex(self._guide(language)['body'], r'<h2>%s' % re.escape(label[:7]))
                    with _readable(key):
                        self.assertRegex(self._guide(language)['body'], r'<h2>%s' % re.escape(label[:7]))
