# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le changelog nomme les grosses fonctionnalites, traduites, et rien d'autre.

Le 10 septembre 2026, dix-huit commits de fonctionnalites etaient en ligne
et l'entree la plus recente du changelog disait <<August 2026>>. Le 11,
Thibaud a lu quatre entrees de septembre et seize puces: <<beaucoup trop
fourni, on ecrit juste l'ajout de grosses nouvelles features, les petits
correctifs et changements ne comptent pas>>. Ce module garde donc trois
choses: que septembre tient en deux entrees courtes; que chaque phrase est
traduite dans les quatre langues; et que chaque phrase nomme une chose qui
existe encore dans le code, pour qu'un retrait ulterieur fasse tomber la
promesse avec lui.
"""

import io
import os
import re

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

MOIS = 'September 2026'
LANGUES = ('fr', 'es', 'pt', 'de')
TEMPLATE = os.path.join(settings.BASE_DIR, 'chardata', 'templates',
                        'chardata', 'changelog_content.html')
_TRANS = re.compile(r'\{%\s*trans\s+"((?:[^"\\]|\\.)*)"\s*%\}')
MAX_PUCES = 4


def _entrees():
    """[(date, titre, [puces])] dans l'ordre du fichier."""
    source = io.open(TEMPLATE, encoding='utf-8').read()
    entrees = []
    for bloc in source.split('<div class="cl-entry">')[1:]:
        chaines = _TRANS.findall(bloc)
        date, titre = chaines[0], chaines[2]
        puces = _TRANS.findall(bloc.split('<ul>', 1)[1])
        entrees.append((date, titre, puces))
    return entrees


def _catalogue(langue):
    chemin = os.path.join(settings.BASE_DIR, 'locale', langue, 'LC_MESSAGES',
                          'django.po')
    texte = io.open(chemin, encoding='utf-8').read()
    return dict(re.findall(r'\nmsgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"\n',
                           texte))


class TheSeptemberEntriesAreFewAndShortTests(SimpleTestCase):

    def test_two_entries_of_at_most_four_bullets(self):
        entrees = _entrees()
        self.assertEqual(MOIS, entrees[0][0])
        de_ce_mois = [e for e in entrees if e[0] == MOIS]
        self.assertEqual(2, len(de_ce_mois), [e[1] for e in de_ce_mois])
        self.assertEqual('Your build, in and out', entrees[0][1])
        for _date, titre, puces in de_ce_mois:
            self.assertLessEqual(len(puces), MAX_PUCES, titre)
            self.assertGreaterEqual(len(puces), 1, titre)

    def test_no_small_fix_is_sold_as_a_feature(self):
        """Les mots d'un correctif: une phrase qui les porte est un
        correctif, pas une fonctionnalite. Liste courte et litterale, pour
        que le prochain qui ecrit <<fixed>> dans le changelog s'arrete."""
        interdits = ('fixed', 'renamed', 'no longer', 'not on an error page',
                     'privacy page', 'sidebar counter', 'search engines')
        for date, titre, puces in _entrees():
            if date != MOIS:
                continue
            for puce in puces:
                bas = puce.lower()
                for mot in interdits:
                    self.assertNotIn(mot, bas, (titre, puce))

    def test_no_third_party_site_is_named(self):
        """Thibaud ne veut pas <<DofusBook>> a plusieurs endroits: le
        changelog dit <<un autre site de builds>>."""
        for date, titre, puces in _entrees():
            if date != MOIS:
                continue
            for phrase in [titre] + puces:
                self.assertNotIn('dofusbook', phrase.lower(), phrase)


class TheSeptemberEntriesAreTranslatedTests(SimpleTestCase):

    def test_every_sentence_of_this_month_is_translated_natively(self):
        phrases = set()
        for date, titre, puces in _entrees():
            if date != MOIS:
                continue
            phrases.update([date, titre] + puces)
        self.assertGreaterEqual(len(phrases), 7)
        for langue in LANGUES:
            catalogue = _catalogue(langue)
            for phrase in phrases:
                cle = phrase.replace('"', '\\"')
                self.assertIn(cle, catalogue, (langue, phrase))
                msgstr = catalogue[cle]
                self.assertTrue(msgstr, (langue, phrase))
                if not (langue == 'de' and phrase == MOIS):
                    self.assertNotEqual(msgstr, cle, (langue, phrase))
                self.assertNotIn('\u2014', msgstr, (langue, phrase))
                self.assertNotIn('\u2013', msgstr, (langue, phrase))

    def test_the_dropped_sentences_left_the_catalogues(self):
        """Dix-sept phrases sont sorties du changelog le 11 septembre; une
        entree orpheline dans un catalogue est une traduction que personne
        ne relit."""
        orphelines = ('The sidebar counter now says solver answers',
                      'From the encyclopedia to the solver',
                      'Icons back, policy honest',
                      'The privacy page names DofusBook')
        for langue in LANGUES + ('en',):
            catalogue = _catalogue(langue)
            for debut in orphelines:
                self.assertFalse(any(k.startswith(debut) for k in catalogue),
                                 (langue, debut))

    def test_the_english_catalogue_carries_the_ids(self):
        catalogue = _catalogue('en')
        self.assertIn(MOIS, catalogue)
        self.assertIn('Your build, in and out', catalogue)


class TheClaimsPointAtThingsThatExistTests(TestCase):
    """Chaque phrase du changelog qui nomme une chose du site est verifiee
    contre cette chose, pas contre une supposition."""

    def _template(self, nom):
        chemin = os.path.join(settings.BASE_DIR, 'chardata', 'templates',
                              'chardata', nom)
        return io.open(chemin, encoding='utf-8').read()

    def test_the_import_reads_names_links_and_screenshots(self):
        page = self._template('text_build.html')
        self.assertIn('shot-file', page)
        self.assertIn('textarea', page)
        from chardata.dofusbook_import import read_build  # noqa: F401
        from chardata.text_build_import import read_items  # noqa: F401
        self.assertTrue(reverse('text_build_import'))

    def test_the_export_reaches_the_three_versions_named(self):
        from chardata.dofusbook_export import HOSTS
        self.assertEqual({'dofus3', 'touch', 'retro'}, set(HOSTS))
        self.assertIn("game_url 'dofusbook_export'", self._template('solution.html'))
        self.assertTrue(reverse('dofusbook_export', args=[1]))

    def test_the_solver_panel_says_what_the_entry_promises(self):
        solution = self._template('solution.html')
        self.assertIn('Proven optimum. The solver checked that no other legal '
                      'combination scores higher on your criteria.', solution)
        self.assertIn('Best set found in {{ limit }} seconds.', solution)
        self.assertIn('items were on offer after your exclusions.', solution)
        self.assertIn('They can be arranged into more than 10 to the power of',
                      solution)

    def test_the_verdict_really_travels(self):
        from chardata.solution_view import _build_share_text  # noqa: F401
        galerie = self._template('shared_builds.html')
        self.assertIn('Proven optimum', galerie)
        self.assertIn('Best found at the time limit, not a proof', galerie)
        from chardata import api_view
        source = io.open(api_view.__file__, encoding='utf-8').read()
        self.assertIn("'proven'", source)

    def test_the_item_and_set_pages_start_a_build(self):
        from chardata.coaching_view import included_item_for, included_set_for  # noqa
        self.assertIn('encyclopedia-build-around',
                      self._template('encyclopedia_item.html'))
        self.assertIn('encyclopedia-build-around-set',
                      self._template('encyclopedia_set.html'))
        self.assertTrue(reverse('quickstart'))
