# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The about page credit line is translated, not a hardcoded English sentence."""

from django.test import TestCase

WORD = {
    'fr': 'Traduit par',
    'es': 'Traducido por',
    'pt': 'Traduzido por',
    'de': 'Übersetzt von',
}


class TheAboutPageCreditsTranslatorsInEveryLanguageTests(TestCase):

    def test_each_language_shows_its_own_credit_wording(self):
        for langue, mot in WORD.items():
            prefixe = '' if langue == 'en' else '/%s' % langue
            page = self.client.get(
                '%s/about/' % prefixe).content.decode('utf-8')
            with self.subTest(langue=langue):
                self.assertIn(mot, page)
                self.assertNotIn('version by:', page)

    def test_the_english_page_credits_no_translator(self):
        page = self.client.get('/about/').content.decode('utf-8')
        self.assertNotIn('Translated by', page)
        self.assertNotIn('version by:', page)
