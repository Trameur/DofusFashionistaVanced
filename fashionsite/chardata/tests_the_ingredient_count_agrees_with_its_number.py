# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The ingredient counter agrees per language; French takes the singular at zero."""

import io
import os
import re

from django.test import SimpleTestCase

from chardata.workshop_view import _ingredients_payload

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# The bare word each language says at zero, one and two
_ACCORD = {
    'en': ('ingredients', 'ingredient', 'ingredients'),
    'fr': ('ingrédient', 'ingrédient', 'ingrédients'),
    'es': ('ingredientes', 'ingrediente', 'ingredientes'),
    'pt': ('ingredientes', 'ingrediente', 'ingredientes'),
    'de': ('Zutaten', 'Zutat', 'Zutaten'),
}

# Counters already on the plural-aware form; the floor below guards them
_DEJA_BONS = 21

_GABARITS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'templates', 'chardata')

# A {% if ... == 1 %} followed by a {% trans %} on the same line
_CHOIX_GABARIT = re.compile(r'\{%\s*if[^%]*==\s*1\s*%\}.*?\{%\s*trans', re.S)
# The same choice in JavaScript
_CHOIX_JS = re.compile(r'===?\s*1\s*\?')
_BONNE_FORME = re.compile(r'\{%\s*blocktrans[^%]*\bcount\b')


def _recette(combien):
    return {'ingredients': [{'quantity': 1} for _ in range(combien)],
            'recipes_available': True}


def _phrase(combien, langue):
    return _ingredients_payload(_recette(combien), langue)['ingredients_meta']


class TheCountAgreesWithItsNumberTests(SimpleTestCase):

    def test_french_says_the_singular_at_zero(self):
        self.assertIn('0 ingrédient ·', _phrase(0, 'fr'))
        self.assertNotIn('ingrédients', _phrase(0, 'fr'))

    def test_every_language_follows_its_own_rule(self):
        for langue, (zero, un, deux) in _ACCORD.items():
            for combien, attendu in ((0, zero), (1, un), (2, deux)):
                with self.subTest(langue=langue, combien=combien):
                    phrase = _phrase(combien, langue)
                    self.assertIn('%d %s ' % (combien, attendu), phrase)

    def test_the_five_catalogues_carry_the_plural_entry(self):
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
        bons = sum(len(_BONNE_FORME.findall(contenu))
                   for _nom, contenu in self._gabarits())
        self.assertGreaterEqual(
            bons, _DEJA_BONS,
            'the site had %d counters agreeing by language and now has %d'
            % (_DEJA_BONS, bons))


class TheFirstRenderAndTheRefreshCannotDifferTests(SimpleTestCase):

    def _source(self, nom, dossier=None):
        base = dossier or os.path.dirname(os.path.abspath(__file__))
        with io.open(os.path.join(base, nom), encoding='utf-8') as fichier:
            return fichier.read()

    def test_both_json_endpoints_answer_with_the_shared_payload(self):
        source = self._source('workshop_view.py')
        self.assertEqual(
            2, source.count('JsonResponse(_ingredients_payload('),
            'one of the two ingredient endpoints builds its own answer again')

    def test_the_solution_panel_prints_what_the_server_computed(self):
        # solution.html still refreshes its ingredient panel over AJAX and
        # has to echo back the same phrase the server rendered on load.
        self.assertIn('resp.ingredients_meta',
                      self._source('solution.html', _GABARITS))

    def test_the_workshop_page_never_refetches_its_totals(self):
        # The workshop card rows and the shopping list totals now come from
        # one breakdown embedded once via json_script, so there is no second
        # request that could answer with a different number.
        source = self._source('workshop.html', _GABARITS)
        self.assertIn('workshop_resource_totals|json_script', source)
        self.assertNotIn('/workshop/ingredients/', source)
        view_source = self._source('workshop_view.py')
        self.assertEqual(
            1, view_source.count('_breakdown_for_user(request.user, game_version)'),
            'workshop() should build the card rows and the resource totals '
            'from one breakdown call, not two that could disagree')
