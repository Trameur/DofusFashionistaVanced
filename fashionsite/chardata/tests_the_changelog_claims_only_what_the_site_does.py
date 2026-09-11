# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le changelog nomme ce qui a ete livre en septembre, et rien de plus.

Le 10 septembre 2026, dix-huit commits de fonctionnalites etaient en ligne
et l'entree la plus recente du changelog disait <<August 2026>>. Ce module
garde deux choses: que l'entree de septembre est la, traduite phrase par
phrase dans les quatre langues; et que chaque phrase qui nomme une chose du
site (un libelle, une page, un chiffre du guide) nomme une chose qui existe
encore, pour qu'un retrait ulterieur fasse tomber la promesse avec lui.
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


class TheSeptemberEntryIsThereAndTranslatedTests(SimpleTestCase):

    def test_the_newest_entries_are_dated_this_month(self):
        entrees = _entrees()
        self.assertEqual(MOIS, entrees[0][0])
        de_ce_mois = [e for e in entrees if e[0] == MOIS]
        # Trois entrees le 10, une quatrieme le 11 pour les sections 23 a 30.
        self.assertEqual(4, len(de_ce_mois), [e[1] for e in de_ce_mois])
        self.assertEqual('From the encyclopedia to the solver', entrees[0][1])

    def test_every_sentence_of_this_month_is_translated_natively(self):
        """Chaque chaine, pas seulement le titre: une puce oubliee sort en
        anglais sur une page francaise. La date allemande est le seul cas ou
        le mot natif est le mot anglais."""
        phrases = set()
        for date, titre, puces in _entrees():
            if date != MOIS:
                continue
            phrases.update([date, titre] + puces)
        self.assertGreaterEqual(len(phrases), 15)
        for langue in LANGUES:
            catalogue = _catalogue(langue)
            for phrase in phrases:
                cle = phrase.replace('"', '\\"')
                self.assertIn(cle, catalogue, (langue, phrase))
                msgstr = catalogue[cle]
                self.assertTrue(msgstr, (langue, phrase))
                if not (langue == 'de' and phrase == MOIS):
                    self.assertNotEqual(msgstr, cle, (langue, phrase))
                # Tiret cadratin et demi-cadratin, ecrits en echappement:
                # le depot en interdit le caractere lui-meme.
                self.assertNotIn('\u2014', msgstr, (langue, phrase))
                self.assertNotIn('\u2013', msgstr, (langue, phrase))

    def test_the_english_catalogue_carries_the_ids(self):
        catalogue = _catalogue('en')
        self.assertIn(MOIS, catalogue)
        self.assertIn('Proof, not guesswork', catalogue)


class TheClaimsPointAtThingsThatExistTests(TestCase):
    """Chaque phrase du changelog qui nomme une chose du site est verifiee
    contre cette chose, pas contre une supposition."""

    def _template(self, nom):
        chemin = os.path.join(settings.BASE_DIR, 'chardata', 'templates',
                              'chardata', nom)
        return io.open(chemin, encoding='utf-8').read()

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

    def test_the_buttons_the_footer_and_the_counter(self):
        self.assertIn('Optimize my build', self._template('coaching.html'))
        self.assertIn('solver answers', self._template('sidebar-stats.html'))
        base = self._template('base.html')
        self.assertIn('2012', base)

    def test_the_guide_carries_the_four_sizes(self):
        from chardata.guides_content import GUIDES
        corps = GUIDES['how-it-works']['i18n']['en']['body']
        self.assertIn('10 to the power of 37', corps)
        self.assertIn('10 to the power of 36', corps)
        self.assertIn('10 to the power of 28', corps)
        for version in ('Dofus 3', 'Touch', 'Dofus 2', 'Retro'):
            self.assertIn(version, corps)

    def test_the_pages_the_entry_sends_readers_to_exist(self):
        for nom in ('text_build_import', 'shared_builds', 'privacy',
                    'inventory'):
            self.assertTrue(reverse(nom), nom)
        self.assertTrue(reverse('dofusbook_export', args=[1]))
        self.assertTrue(reverse('guide', args=['how-it-works']))

    def test_the_labels_the_entry_quotes(self):
        solution = self._template('solution.html')
        self.assertIn('Copy as text', solution)
        self.assertIn('Open on DofusBook', solution)
        self.assertIn('ocr_whole_build', self._template('inventory.html'))
        self.assertIn('shot-file', self._template('text_build.html'))

    def test_dofusbook_export_covers_the_three_versions_named(self):
        from chardata.dofusbook_export import HOSTS
        self.assertEqual({'dofus3', 'touch', 'retro'}, set(HOSTS))

    def test_the_privacy_page_names_dofusbook(self):
        self.assertIn('DofusBook', self._template('privacy.html'))

    def test_the_missing_page_knows_the_other_versions(self):
        from chardata.encyclopedia_view import _versions_carrying  # noqa
        self.assertIn('missing_available_in',
                      io.open(os.path.join(settings.BASE_DIR, 'chardata',
                                           'encyclopedia_view.py'),
                              encoding='utf-8').read())

    def test_the_fourth_entry_names_things_that_exist(self):
        """Sections 23 a 30: chaque phrase de l'entree du 11 septembre est
        adossee au code qui la porte."""
        from chardata.coaching_view import included_item_for, included_set_for  # noqa
        self.assertIn('encyclopedia-build-around',
                      self._template('encyclopedia_item.html'))
        self.assertIn('encyclopedia-build-around-set',
                      self._template('encyclopedia_set.html'))
        self.assertIn('home-import-build', self._template('home.html'))
        base = self._template('base.html')
        self.assertIn('{% load capture %}', base)
        self.assertIn('{{ page_title }}', base)
        from chardata.solution_view import _build_og_description  # noqa: F401
        self.assertIn('screenshot', self._template('text_build.html'))
        self.assertIn("('/import/text/', 'monthly', '0.7')",
                      io.open(os.path.join(settings.BASE_DIR, 'fashionsite',
                                           'urls.py'), encoding='utf-8').read())
        from chardata.SocialAuthExceptionMiddleware import SOCIAL_FAILED_PARAM  # noqa
        self.assertIn('social-login-failed', self._template('login.html'))

    def test_retro_and_touch_spell_icons_are_all_there(self):
        """251 icones: Retro 10 -> 109 sur 109, Touch 27 -> 179 sur 179
        (lot 0 du plan). Le changelog dit <<toutes>>: on compte. Le
        plancher est la, pour que le test ne soit pas vrai sur une liste
        vide; les pages de degats demandent 106 et 174 noms, le lot 0
        comptait les fichiers sur le disque."""
        from urllib.parse import unquote
        from chardata.spell_buffs import get_damage_spells_for_version
        from chardata.spells_view import _spell_image_url
        static = os.path.join(settings.BASE_DIR, 'chardata', 'static')
        planchers = {'retro': 100, 'touch': 170}
        for version, plancher in planchers.items():
            noms = set()
            for sorts in get_damage_spells_for_version(version).values():
                for sort in sorts:
                    nom = (sort.get('name') if isinstance(sort, dict)
                           else getattr(sort, 'name', None))
                    if nom:
                        noms.add(nom)
            absents = sorted(
                nom for nom in noms
                if not os.path.exists(os.path.join(
                    static,
                    unquote(_spell_image_url(nom, version))
                    .split('/static/', 1)[-1].replace('/', os.sep))))
            with self.subTest(version=version):
                self.assertGreaterEqual(len(noms), plancher)
                self.assertEqual([], absents)
