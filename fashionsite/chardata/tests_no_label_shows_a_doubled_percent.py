# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Aucun libelle ne montre un pour-cent double.

Trouve en comparant deux builds en espagnol. Le tableau se lisait:

    %% Resistencia Neutral
    %% Resistencia Tierra
    %% Resistencia Fuego
    %% Resistencia Agua
    %% Resistencia Aire

**Les deux facons de traduire dans un gabarit ne rendent pas la meme chose.**
`makemessages` echappe le pour-cent quand il extrait une chaine d'un gabarit,
donc le catalogue porte deux entrees pour un meme libelle: `% Neutral Resist`
et `%% Neutral Resist`. Le tag `{% trans %}` demande la premiere, le raccourci
`_("...")` d'une expression de gabarit demande la seconde, et la rend telle
quelle:

    {% trans "% Neutral Resist" %}   ->  % Resistencia Neutral
    _("% Neutral Resist")            ->  %% Resistencia Neutral

**Mesure du 14 septembre 2026**, avant le changement:

| page | libelles doubles | langues |
|------|------------------|---------|
| les poids d'un projet | **13** | les cinq |
| la comparaison de builds | **5** | les cinq |

L'anglais aussi, parce que le msgid lui-meme porte les deux caracteres: ce
n'etait donc pas un defaut de traduction mais de lecture.

**Ce que le lot fait.** Les 25 appels `_("...%...")` des gabarits sont hisses
en `{% trans "..." as variable %}` juste au-dessus de leur usage, ce que
`solution.html` faisait deja pour les memes libelles -- et c'est pourquoi la
page d'une solution, elle, n'a jamais montre de double.

Le parcours vise **la cause**, pas les 25 lignes: n'importe quel gabarit qui
reprendrait le raccourci sur une chaine a pour-cent le fait tomber.
"""
import os
import re

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation

GABARITS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'templates', 'chardata')

#: Le raccourci de gabarit, sur une chaine qui porte un pour-cent.
RACCOURCI = re.compile(r'_\("[^"]*%[^"]*"\)')

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: Un libelle de chaque page touchee, pour que la regle ait un temoin nomme.
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
        """La mesure qui explique la regle. Sans cet ecart, le parcours
        ci-dessus defendrait une preference."""
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
