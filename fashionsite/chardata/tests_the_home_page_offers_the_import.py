# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The home page offers an import link to a reader who already has a build."""

import re

from django.test import SimpleTestCase, TestCase

QUESTION = 'Already have a build?'
LIEN = 'Import it from a link, text or screenshots'
# Without any other build site enabled (build_sites.py), the link is not offered.
SANS_LIEN = 'Import it from text or screenshots'


def _ancre(page):
    debut = page.find('home-import-build')
    assert debut != -1, 'no import link on the home page'
    return page[page.rfind('<a', 0, debut):page.find('</a>', debut)]


class TheHomePageOffersTheImportTests(TestCase):

    def test_the_link_goes_to_the_import_of_this_version(self):
        page = self.client.get('/', HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        ancre = _ancre(page)
        self.assertIn('href="/import/text/"', ancre)
        self.assertIn(LIEN, ancre)
        self.assertIn(QUESTION, page)

    def test_a_touch_home_keeps_the_reader_on_touch(self):
        page = self.client.get('/touch/', HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertIn('href="/touch/import/text/"', _ancre(page))

    def test_the_sentence_speaks_the_language_of_the_reader(self):
        page = self.client.get('/', HTTP_ACCEPT_LANGUAGE='fr').content.decode('utf-8')
        self.assertNotIn(QUESTION, page)
        self.assertNotIn(LIEN, page)
        self.assertIn('Tu as déjà un build ?', page)
        self.assertIn('captures d’écran', _ancre(page))

    def test_the_line_is_not_faded(self):
        """A faded paragraph would fail the contrast floor the footer links already meet."""
        page = self.client.get('/', HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        debut = page.find('home-import-build')
        paragraphe = page[page.rfind('<p', 0, debut):debut]
        self.assertNotIn('opacity', paragraphe)

    def test_no_link_is_promised_while_no_site_is_read(self):
        from django.test import override_settings
        with override_settings(BUILD_SITES_ENABLED=()):
            page = self.client.get('/', HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertIn(SANS_LIEN, _ancre(page))
        self.assertNotIn(LIEN, page)

    def test_the_page_it_sends_to_answers_a_stranger(self):
        for chemin in ('/import/text/', '/touch/import/text/'):
            self.assertEqual(200, self.client.get(chemin).status_code, chemin)


class TheTwoSentencesAreInEveryCatalogueTests(SimpleTestCase):

    def test_four_native_translations_each(self):
        import gettext
        import os
        from django.conf import settings
        for msgid in (QUESTION, LIEN, SANS_LIEN):
            vues = set()
            for langue in ('fr', 'es', 'pt', 'de'):
                phrase = gettext.translation(
                    'django', os.path.join(settings.BASE_DIR, 'locale'),
                    languages=[langue]).gettext(msgid)
                self.assertNotEqual(msgid, phrase, (langue, msgid))
                self.assertFalse(re.search('\u2014|\u2013', phrase), (langue, msgid))
                vues.add(phrase)
            self.assertEqual(4, len(vues), msgid)
