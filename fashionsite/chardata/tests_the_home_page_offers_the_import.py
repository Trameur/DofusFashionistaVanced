# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""L'accueil propose l'import a qui a deja son build.

Mesure du 11 septembre 2026: l'accueil offrait quatre departs (demarrage
rapide, build en une phrase, build au hasard, guides) et trois gros boutons
(creer, charger ou se connecter, FAQ), tous des departs de zero. Un joueur
qui a deja son stuff, et qui vient voir si le solveur fait mieux, entre
par l'import (texte ou captures, section 9.10 du plan), et rien sur
l'accueil ne le lui disait: il fallait ouvrir le menu.
"""

import re

from django.test import SimpleTestCase, TestCase

QUESTION = 'Already have a build?'
LIEN = 'Import it from text or screenshots'


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
        self.assertIn('Vous avez déjà un build ?', page)
        self.assertIn('captures d’écran', _ancre(page))

    def test_the_line_is_not_faded(self):
        """La ligne portait `opacity: 0.8`: ses liens tombaient a 3,3:1 en
        classique clair et 3,6:1 en moderne clair, sous les 4,5:1 que le
        lot B a refuses pour le pied de page. A pleine force, 4,6:1 et
        5,3:1 (couleurs de lien mesurees sur le fond rgb(228, 230, 188))."""
        page = self.client.get('/', HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        debut = page.find('home-import-build')
        paragraphe = page[page.rfind('<p', 0, debut):debut]
        self.assertNotIn('opacity', paragraphe)

    def test_the_page_it_sends_to_answers_a_stranger(self):
        for chemin in ('/import/text/', '/touch/import/text/'):
            self.assertEqual(200, self.client.get(chemin).status_code, chemin)


class TheTwoSentencesAreInEveryCatalogueTests(SimpleTestCase):

    def test_four_native_translations_each(self):
        import gettext
        import os
        from django.conf import settings
        for msgid in (QUESTION, LIEN):
            vues = set()
            for langue in ('fr', 'es', 'pt', 'de'):
                phrase = gettext.translation(
                    'django', os.path.join(settings.BASE_DIR, 'locale'),
                    languages=[langue]).gettext(msgid)
                self.assertNotEqual(msgid, phrase, (langue, msgid))
                self.assertFalse(re.search('\u2014|\u2013', phrase), (langue, msgid))
                vues.add(phrase)
            self.assertEqual(4, len(vues), msgid)
