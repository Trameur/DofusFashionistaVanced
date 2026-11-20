# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The license page credits both fonts and their licence, and every credit string reads in each of the five languages."""
import re

from django.test import TestCase
from django.utils import translation
from django.utils.translation import gettext

LANGUAGES = ('de', 'en', 'es', 'fr', 'pt')
LICENCE_NAME = 'SIL Open Font License, version 1.1'
CREDITS = ('Fonts:', 'SIL Open Font License, version 1.1',
           'The fonts are hosted on this site, so your browser asks no other server for them.')


class TheFontCreditsReadInEveryLanguageTests(TestCase):

    def _page(self, language):
        response = self.client.get('/license/', HTTP_ACCEPT_LANGUAGE=language,
                                   HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0')
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')

    def test_each_credit_is_translated_in_the_four_other_languages(self):
        for language in LANGUAGES:
            with translation.override(language):
                for credit in CREDITS:
                    with self.subTest(language=language, credit=credit):
                        text = gettext(credit)
                        self.assertTrue(text)
                        if language != 'en' and credit != LICENCE_NAME:
                            self.assertNotEqual(credit, text)

    def test_the_five_translations_of_each_credit_differ_where_the_languages_differ(self):
        for credit in CREDITS[:1] + CREDITS[2:]:
            seen = {}
            for language in LANGUAGES:
                with translation.override(language):
                    seen[language] = gettext(credit)
            with self.subTest(credit=credit):
                self.assertEqual(5, len(set(seen.values())), seen)

    def test_the_license_page_shows_both_credits_and_both_licence_links_in_each_language(self):
        for language in LANGUAGES:
            html = self._page(language)
            with translation.override(language):
                with self.subTest(language=language):
                    self.assertIn('IM Fell English SC', html)
                    self.assertIn('Igino Marini', html)
                    self.assertIn('Barlow', html)
                    self.assertIn('Jeremy Tribby', html)
                    for credit in CREDITS:
                        self.assertIn(gettext(credit), html)
                    self.assertEqual(2, len(re.findall(r'font/OFL-[A-Za-z]+(?:\.[0-9a-f]+)?\.txt', html)))

    def test_a_french_reader_does_not_get_the_english_credit(self):
        html = self._page('fr')
        self.assertNotIn('The fonts are hosted on this site', html)
        self.assertIn('Polices', html)
