# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A translated address in the sitemap implies its English twin is submitted too."""
import re

from django.test import TestCase


class EveryTranslatedUrlHasAnEnglishTwinTests(TestCase):

    def _adresses(self):
        index = self.client.get('/sitemap.xml')
        self.assertEqual(200, index.status_code)
        sections = re.findall(r'<loc>([^<]+)</loc>',
                              index.content.decode('utf-8', 'replace'))
        self.assertTrue(sections, 'the sitemap index lists no section')
        chemins = set()
        for url in sections:
            chemin = re.sub(r'^https?://[^/]+', '', url)
            corps = self.client.get(chemin).content.decode('utf-8', 'replace')
            for loc in re.findall(r'<loc>([^<]+)</loc>', corps):
                chemins.add(re.sub(r'^https?://[^/]+', '', loc))
        return chemins

    def test_no_translated_page_is_submitted_without_its_english_twin(self):
        from django.conf import settings

        chemins = self._adresses()
        codes = tuple('/%s/' % code for code, _nom in settings.LANGUAGES
                      if code != settings.LANGUAGE_CODE)
        prefixes = [c for c in chemins if c.startswith(codes)]
        # Positive control: without a prefixed address the loop below runs on nothing
        self.assertTrue(
            prefixes,
            'no translated url is submitted at all, so this test proves '
            'nothing about their english twins')

        orphelines = []
        for chemin in sorted(prefixes):
            anglais = '/' + chemin.split('/', 2)[2]
            if anglais not in chemins:
                orphelines.append(chemin)
        self.assertFalse(
            orphelines,
            '%d translated urls are submitted while their english twin is '
            'not: %s' % (len(orphelines), orphelines[:6]))

