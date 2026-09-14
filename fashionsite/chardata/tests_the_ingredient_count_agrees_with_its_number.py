# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le compteur d'ingredients s'accorde selon la langue, pas selon l'anglais.

Trouve en lisant l'atelier apres y avoir ajoute un build. **Deux methodes
cohabitaient dans le meme fichier**: le compteur d'objets employait
`blocktrans count`, qui accorde selon la langue, et celui des ingredients un
`{% if kinds == 1 %}`, qui impose la regle anglaise a tout le monde.

Le francais met le **singulier a zero** (`nplurals=2; plural=(n > 1)`): il
faut <<0 ingredient>>, et le `if` donnait <<0 ingredients>>. Les trois autres
langues mettent le pluriel a zero, donc elles n'etaient pas touchees.

**Trois copies de la meme regle.** Balayage des 89 gabarits: un `if == 1` dans
`workshop.html`, et deux `kinds === 1 ?` en JavaScript, dans `workshop.html`
et `solution.html`. Vingt et un autres compteurs employaient deja
`blocktrans count`.

**Pourquoi la phrase est batie cote serveur.** `ngettext` dans la page
n'aurait rien donne: le catalogue JavaScript ne porte que 148 entrees et ce
mot n'en fait pas partie, donc il aurait rendu l'anglais. Le serveur, lui,
connait la regle de chaque langue. La meme phrase sert au premier rendu et au
rafraichissement, donc les deux ne peuvent plus differer.

**Le msgid est la phrase entiere, pas le mot.** <<ingredient>> et
<<ingredients>> existent deja comme deux entrees au singulier; une entree
plurielle sur le meme msgid serait un doublon que msgfmt refuse. La phrase
entiere est un msgid neuf, sur le modele exact du compteur d'objets voisin.

Mesure du 13 septembre 2026:

| langue | 0 | 1 | 2 |
|--------|---|---|---|
| en | 0 ingredients | 1 ingredient | 2 ingredients |
| fr | **0 ingredient** | 1 ingredient | 2 ingredients |
| es | 0 ingredientes | 1 ingrediente | 2 ingredientes |
| pt | 0 ingredientes | 1 ingrediente | 2 ingredientes |
| de | 0 Zutaten | 1 Zutat | 2 Zutaten |
"""

import io
import os
import re

from django.test import SimpleTestCase

from chardata.workshop_view import _ingredients_payload

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: Ce que chaque langue doit dire a zero, a un et a deux. Le mot seul, pour
#: que le test ne se casse pas sur la ponctuation.
_ACCORD = {
    'en': ('ingredients', 'ingredient', 'ingredients'),
    'fr': ('ingrédient', 'ingrédient', 'ingrédients'),
    'es': ('ingredientes', 'ingrediente', 'ingredientes'),
    'pt': ('ingredientes', 'ingrediente', 'ingredientes'),
    'de': ('Zutaten', 'Zutat', 'Zutaten'),
}

#: Combien de compteurs employaient deja la bonne forme quand ce lot a ete
#: ecrit. Si ce nombre s'effondrait, quelqu'un serait reparti en arriere.
_DEJA_BONS = 21

_GABARITS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'templates', 'chardata')

#: Un `{% if ... == 1 %}` suivi d'un `{% trans %}` sur la meme ligne.
_CHOIX_GABARIT = re.compile(r'\{%\s*if[^%]*==\s*1\s*%\}.*?\{%\s*trans', re.S)
#: Le meme choix en JavaScript.
_CHOIX_JS = re.compile(r'===?\s*1\s*\?')
_BONNE_FORME = re.compile(r'\{%\s*blocktrans[^%]*\bcount\b')


def _recette(combien):
    return {'ingredients': [{'quantity': 1} for _ in range(combien)],
            'recipes_available': True}


def _phrase(combien, langue):
    return _ingredients_payload(_recette(combien), langue)['ingredients_meta']


class TheCountAgreesWithItsNumberTests(SimpleTestCase):

    def test_french_says_the_singular_at_zero(self):
        """Le test qui aurait attrape le defaut.

        Le francais est la seule des cinq langues ou zero prend le singulier,
        et c'est la seule que le `if == 1` rendait fausse.
        """
        self.assertIn('0 ingrédient ·', _phrase(0, 'fr'))
        self.assertNotIn('ingrédients', _phrase(0, 'fr'))

    def test_every_language_follows_its_own_rule(self):
        for langue, (zero, un, deux) in _ACCORD.items():
            for combien, attendu in ((0, zero), (1, un), (2, deux)):
                with self.subTest(langue=langue, combien=combien):
                    phrase = _phrase(combien, langue)
                    self.assertIn('%d %s ' % (combien, attendu), phrase)

    def test_the_five_catalogues_carry_the_plural_entry(self):
        """Sans l'entree, `ngettext` rendrait le msgid anglais et le test
        ci-dessus tomberait pour quatre langues sur cinq."""
        for langue in LANGUES:
            with self.subTest(langue=langue):
                chemin = os.path.join(
                    os.path.dirname(os.path.dirname(
                        os.path.abspath(__file__))),
                    'locale', langue, 'LC_MESSAGES', 'django.po')
                with io.open(chemin, encoding='utf-8') as fichier:
                    contenu = fichier.read()
                self.assertIn('msgid "%(kinds)s ingredient', contenu)
                self.assertIn('msgid_plural "%(kinds)s ingredients', contenu)


class NoPageChoosesTheWordItselfTests(SimpleTestCase):
    """L'invariant qui manquait: une page qui teste `== 1` decide pour toutes
    les langues, et seul le francais le disait."""

    def _gabarits(self):
        for nom in sorted(os.listdir(_GABARITS)):
            if not nom.endswith('.html'):
                continue
            with io.open(os.path.join(_GABARITS, nom), encoding='utf-8',
                         newline='') as fichier:
                yield nom, fichier.read()

    def test_no_template_picks_a_word_with_an_equals_one(self):
        fautifs = []
        for nom, contenu in self._gabarits():
            for numero, ligne in enumerate(contenu.split('\n'), 1):
                if _CHOIX_GABARIT.search(ligne):
                    fautifs.append((nom, numero, ligne.strip()[:90]))
        self.assertEqual(
            [], fautifs,
            'these choose a word with the English rule: %s' % fautifs)

    def test_no_script_picks_a_word_with_an_equals_one(self):
        fautifs = []
        for nom, contenu in self._gabarits():
            for numero, ligne in enumerate(contenu.split('\n'), 1):
                if _CHOIX_JS.search(ligne):
                    fautifs.append((nom, numero, ligne.strip()[:90]))
        self.assertEqual(
            [], fautifs,
            'these choose a word with the English rule, in JavaScript: %s'
            % fautifs)

    def test_the_counters_that_were_already_right_still_are(self):
        """Le plancher: sans lui, supprimer tous les compteurs ferait passer
        les deux tests ci-dessus."""
        bons = sum(len(_BONNE_FORME.findall(contenu))
                   for _nom, contenu in self._gabarits())
        self.assertGreaterEqual(
            bons, _DEJA_BONS,
            'the site had %d counters agreeing by language and now has %d'
            % (_DEJA_BONS, bons))


class TheFirstRenderAndTheRefreshCannotDifferTests(SimpleTestCase):
    """Les deux venaient de deux endroits; ils viennent du meme."""

    def _source(self, nom, dossier=None):
        base = dossier or os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(base, nom), encoding='utf-8') as fichier:
            return fichier.read()

    def test_both_json_endpoints_answer_with_the_shared_payload(self):
        source = self._source('workshop_view.py')
        self.assertEqual(
            2, source.count('JsonResponse(_ingredients_payload('),
            'one of the two ingredient endpoints builds its own answer again')

    def test_the_page_prints_what_the_server_computed(self):
        source = self._source('workshop.html', _GABARITS)
        self.assertIn('{{ ingredients_meta }}', source)
        for nom in ('workshop.html', 'solution.html'):
            with self.subTest(gabarit=nom):
                self.assertIn('resp.ingredients_meta',
                              self._source(nom, _GABARITS))
