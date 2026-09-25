# -*- coding: utf-8 -*-
"""Every hub (a page with no name of its own, like /setup/) must answer under every language prefix."""
from django.test import TestCase

from fashionsite.urls import HUB_PATHS, _SITEMAP_LANGUAGES


def _lang_of(html):
    import re
    m = re.search(r'<html[^>]*\slang="([^"]+)"', html)
    return m.group(1) if m else None


class EveryHubSpeaksEveryLanguage(TestCase):

    def test_there_are_hubs_and_languages_to_walk(self):
        """An empty product is a green test that checked nothing."""
        self.assertGreaterEqual(len(HUB_PATHS), 5)
        self.assertGreaterEqual(len(_SITEMAP_LANGUAGES), 3)
        self.assertIn('/setup/', HUB_PATHS)

    def test_each_hub_answers_unprefixed(self):
        for hub in HUB_PATHS:
            with self.subTest(hub=hub):
                self.assertEqual(self.client.get(hub).status_code, 200)

    def test_each_hub_answers_under_each_language(self):
        missing = []
        for language in _SITEMAP_LANGUAGES:
            for hub in HUB_PATHS:
                path = '/%s%s' % (language, hub)
                if self.client.get(path).status_code != 200:
                    missing.append(path)
        self.assertEqual(missing, [])

    def test_the_prefix_actually_changes_the_language(self):
        """A route that resolves but ignores its prefix looks translated while reading English to the reader."""
        wrong = []
        for language in _SITEMAP_LANGUAGES:
            for hub in HUB_PATHS:
                page = self.client.get('/%s%s' % (language, hub))
                if _lang_of(page.content.decode('utf-8', 'replace')) != language:
                    wrong.append('/%s%s' % (language, hub))
        self.assertEqual(wrong, [])

    def test_a_prefix_that_is_not_a_language_is_still_a_404(self):
        for hub in HUB_PATHS:
            with self.subTest(hub=hub):
                self.assertEqual(self.client.get('/xx%s' % hub).status_code,
                                 404)
