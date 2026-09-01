# -*- coding: utf-8 -*-
"""Every hub must answer under every language prefix, not most of them.

A hub is a page with no name of its own to localise -- the home, the guides
index, the encyclopedia, the create-a-project landing. Their language lives in
a url prefix, and that only works if the route sits inside i18n_patterns.

/setup/ did not. So /fr/retro/setup/ and /es/retro/setup/ answered in their
language while **/fr/setup/ answered 404**: the translated set builder existed
for every game version except the one people actually play, and French is the
market that sends the most impressions by a factor of twenty. Nothing caught it
because nothing walked the combinations.

The last test is the one with teeth: every assertion above passes on a client
that returns 200 for anything, so it demands a 404 for a prefix that is not a
language at all.
"""
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
        """A route that resolves but ignores its prefix is worse than a 404:
        it looks translated in the sitemap and reads English to the reader."""
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
