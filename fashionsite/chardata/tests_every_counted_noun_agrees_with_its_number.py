# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A noun next to a number agrees with it, in every language."""

import io
import os
import re

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# {{ value }} followed by a fixed {% trans %} word
_NOM_FIGE = re.compile(
    r'\{\{\s*([^}]+?)\s*\}\}\s*(?:</[a-z]+>)?\s*\{%\s*trans\s+'
    r'([\'"])(.+?)\2\s*%\}', re.S)

# pluralize adds an English s to a translated word
_FILTRE_ANGLAIS = re.compile(
    r'\{%\s*trans\s+[\'"](.+?)[\'"]\s*%\}\s*\{\{[^}]*\|pluralize[^}]*\}\}')

# Fixed words next to a number that count nothing
_NE_COMPTE_RIEN = {
    'of': 'preposition de pagination, <<Page 3 of 12>>',
    'lvl': 'abreviation de niveau, pas un compte',
    'build optimized on Dofus Fashionista': 'phrase de description',
    'build optimized on Dofus Fashionista. Like it, comment it, copy it.':
        'phrase de description',
    'damage': 'indenombrable',
    # Follows the set total, and no set has a single piece
    'pieces': 'ratio x/y, dont le y est au moins 2 sur les cinq versions',
}

# "counter" context where the singular already exists as a msgid
_COMPTEURS = (
    ('counter', 'follower', 'followers'),
    ('counter', 'following', 'following'),
    ('counter', 'Like', 'Likes'),
    ('counter', 'Favorite', 'Favorites'),
    ('counter', 'piece', 'pieces'),
    ('counter', 'set', 'sets'),
    (None, 'like received', 'likes received'),
    (None, 'favorite received', 'favorites received'),
    (None, 'view', 'views'),
)

# English plurals glued onto another language
_PLURIELS_INVENTES = {('es', 'seguidors'), ('pt', 'seguidors'),
                      ('de', 'Followers')}


def _gabarits():
    racine = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates')
    for dossier, _sous, noms in os.walk(racine):
        for nom in noms:
            if nom.endswith('.html'):
                yield nom, os.path.join(dossier, nom)


def _rendu(contexte, singulier, pluriel, langue, nombre):
    marque = ' context "%s"' % contexte if contexte else ''
    gabarit = Template(
        '{%% load i18n %%}{%% blocktrans count n=n%s %%}%s{%% plural %%}%s'
        '{%% endblocktrans %%}' % (marque, singulier, pluriel))
    with translation.override(langue):
        return gabarit.render(Context({'n': nombre}))


class NoTemplatePutsAFixedNounNextToANumberTests(SimpleTestCase):

    def test_the_scan_actually_reads_the_templates(self):
        vus = list(_gabarits())
        self.assertGreater(len(vus), 80,
                           'only %d templates found, down from the 90 '
                           'measured on 2026-09-17' % len(vus))

    def test_every_fixed_noun_left_is_one_that_counts_nothing(self):
        inconnus = []
        for nom, chemin in _gabarits():
            texte = io.open(chemin, encoding='utf-8', errors='replace').read()
            for m in _NOM_FIGE.finditer(texte):
                chaine = m.group(3)
                if chaine not in _NE_COMPTE_RIEN:
                    inconnus.append((nom, m.group(1).strip(), chaine))
        self.assertFalse(
            inconnus,
            'these put a fixed word next to a number and nobody decided '
            'whether it counts: %s' % inconnus[:6])

    def test_no_template_appends_an_english_s_to_a_translated_word(self):
        fautifs = []
        for nom, chemin in _gabarits():
            texte = io.open(chemin, encoding='utf-8', errors='replace').read()
            for m in _FILTRE_ANGLAIS.finditer(texte):
                fautifs.append((nom, m.group(1)))
        self.assertFalse(
            fautifs,
            'these build a plural with the English rule on a translated '
            'word: %s' % fautifs)

    def test_the_exemptions_still_describe_something_real(self):
        vues = set()
        for _nom, chemin in _gabarits():
            texte = io.open(chemin, encoding='utf-8', errors='replace').read()
            for m in _NOM_FIGE.finditer(texte):
                vues.add(m.group(3))
        fantomes = sorted(set(_NE_COMPTE_RIEN) - vues)
        self.assertFalse(fantomes,
                         'these exemptions match no template any more: %s'
                         % fantomes)


class EveryCounterHasTwoFormsInEveryLanguageTests(SimpleTestCase):

    def test_one_and_two_are_told_apart_where_the_language_does(self):
        distincts = 0
        for contexte, singulier, pluriel in _COMPTEURS:
            for langue in LANGUES:
                un = _rendu(contexte, singulier, pluriel, langue, 1)
                deux = _rendu(contexte, singulier, pluriel, langue, 2)
                if un != deux:
                    distincts += 1
        self.assertGreater(
            distincts, 30,
            'only %d of the 45 counter-language pairs tell one from two; the '
            'catalogue is not compiled or the entries are gone' % distincts)

    def test_the_english_plural_is_never_glued_onto_another_language(self):
        for langue, forme in sorted(_PLURIELS_INVENTES):
            with self.subTest(langue=langue, forme=forme):
                rendu = _rendu('counter', 'follower', 'followers', langue, 2)
                self.assertNotEqual(forme, rendu)

    def test_the_spanish_and_portuguese_plurals_are_the_real_ones(self):
        for langue in ('es', 'pt'):
            with self.subTest(langue=langue):
                self.assertEqual(
                    'seguidores',
                    _rendu('counter', 'follower', 'followers', langue, 2))
                self.assertEqual(
                    'seguidor',
                    _rendu('counter', 'follower', 'followers', langue, 1))

    def test_each_language_answers_with_its_own_words(self):
        muettes = []
        for contexte, singulier, pluriel in _COMPTEURS:
            anglais = _rendu(contexte, singulier, pluriel, 'en', 2)
            for langue in ('fr', 'es', 'pt', 'de'):
                if _rendu(contexte, singulier, pluriel, langue, 2) == anglais:
                    muettes.append((langue, singulier))
        # "set" is "sets" in es and pt, "Sets" in de
        self.assertLessEqual(
            len(muettes), 3,
            'too many counters answer in English: %s' % muettes)
