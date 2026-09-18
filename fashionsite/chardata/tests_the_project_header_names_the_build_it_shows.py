# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The project header names the build the way the rest of the site does."""

from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

_EXEMPLES = ('Str', 'Int', 'Str Glass Cannon', 'Int Crit')

_MOTS_FAUX = (
    ('Build', 'fr', 'Élément', 'element, pas build'),
    ('Build', 'es', 'Elemento', 'element, pas build'),
    ('Build', 'pt', 'Elemento', 'element, pas build'),
    ('Build', 'de', 'Bauen', 'le verbe construire'),
    ('Char', 'de', 'Verkohlen', 'le verbe carboniser'),
    ('Duplicate', 'de', 'Duplikat', 'le nom, sur un bouton'),
)


def _gabarit():
    import os
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', 'main-header.html')
    with open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


class TheHeaderShowsTheTranslatedBuildTests(SimpleTestCase):

    def test_the_header_reads_the_same_source_as_the_page_title(self):
        source = _gabarit()
        self.assertIn('{{wrapped_char.build_string}}', source)
        self.assertNotIn('{{char.char_build}}', source)

    def test_the_internal_name_is_not_what_a_reader_should_see(self):
        from chardata.model_wrappers import translate_build_name
        identiques = []
        for brut in _EXEMPLES:
            for langue in LANGUES:
                with translation.override(langue):
                    if translate_build_name(brut) == brut:
                        identiques.append((langue, brut))
        self.assertFalse(
            identiques,
            'these internal names come out unchanged, so showing them raw '
            'would have been harmless: %s' % identiques)

    def test_every_language_names_the_build_in_its_own_words(self):
        from chardata.model_wrappers import translate_build_name
        vus = {}
        for langue in LANGUES:
            with translation.override(langue):
                vus[langue] = translate_build_name('Str Glass Cannon')
        for langue in ('fr', 'es', 'de'):
            with self.subTest(langue=langue):
                self.assertNotEqual(vus['en'], vus[langue])


class NoHeaderLabelKeepsAWordThatMeansSomethingElseTests(SimpleTestCase):

    def test_the_wrong_words_are_gone_and_stay_gone(self):
        revenus = []
        for msgid, langue, faux, _sens in _MOTS_FAUX:
            with translation.override(langue):
                if gettext(msgid) == faux:
                    revenus.append((langue, msgid, faux))
        self.assertFalse(
            revenus,
            'these labels are back to a word that means something else: %s'
            % revenus)

    def test_the_label_follows_the_word_the_site_already_uses(self):
        for langue in ('fr', 'es', 'pt', 'de'):
            with self.subTest(langue=langue):
                with translation.override(langue):
                    self.assertIn('Build', gettext('Smart Build'))
                    self.assertEqual('Build', gettext('Build'))

    def test_the_german_buttons_are_verbs_like_their_neighbour(self):
        with translation.override('de'):
            self.assertEqual('Bearbeiten', gettext('Edit'))
            self.assertEqual('Duplizieren', gettext('Duplicate'))
            self.assertEqual('Charakter', gettext('Char'))
