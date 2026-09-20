# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""No label shows a doubled percent: the template shortcut is refused on a string with a percent."""
import os
import re

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation

GABARITS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'templates', 'chardata')

# The template shortcut, on a string that carries a percent
RACCOURCI = re.compile(r'_\("[^"]*%[^"]*"\)')

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# One label of each page touched, so the rule has a named witness
TEMOINS = ('% Neutral Resist', '% Melee Damage', '% Weapon Damage')


class NoLabelShowsADoubledPercentTests(SimpleTestCase):

    def test_no_template_translates_a_percent_with_the_shortcut(self):
        fautifs = []
        for nom in sorted(os.listdir(GABARITS)):
            if not nom.endswith('.html'):
                continue
            chemin = os.path.join(GABARITS, nom)
            with open(chemin, encoding='utf-8') as fichier:
                for numero, ligne in enumerate(fichier, 1):
                    if RACCOURCI.search(ligne):
                        fautifs.append('%s:%d %s'
                                       % (nom, numero, ligne.strip()[:70]))
        self.assertEqual([], fautifs,
                         'use {%% trans "..." as name %%} instead: the '
                         'shortcut reads the escaped msgid')

    def test_the_two_paths_really_differ(self):
        from django.template.base import Variable
        with translation.override('es'):
            par_tag = Template(
                '{% load i18n %}{% trans "% Neutral Resist" %}'
            ).render(Context({}))
            par_raccourci = str(
                Variable('_("% Neutral Resist")').resolve({}))
        self.assertEqual('% Resistencia Neutral', par_tag)
        self.assertEqual('%% Resistencia Neutral', par_raccourci)

    def test_each_witness_reads_with_one_percent_in_five_languages(self):
        for cle in TEMOINS:
            for langue in LANGUES:
                with translation.override(langue):
                    rendu = Template(
                        '{%% load i18n %%}{%% trans "%s" %%}' % cle
                    ).render(Context({}))
                with self.subTest(cle=cle, langue=langue):
                    self.assertTrue(rendu)
                    self.assertNotIn('%%', rendu)
                    self.assertEqual(1, rendu.count('%'), rendu)
