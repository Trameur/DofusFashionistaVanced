# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un nombre a virgule ne doit pas atteindre le JavaScript d'une page.

Le site formate ses nombres selon la langue du lecteur (`USE_L10N`). Rendu
dans un script, un flottant sort donc en **<<0,909>>** en francais, et le
script s'arrete la. Le filtre `unlocalize` l'en empeche.

**Mesure du 13 septembre 2026**, faite en rendant la meme ligne deux fois:

    avec unlocalize   var drawScale = 0.909;
    sans              var drawScale = 0,909;

Le piege a deja coute une fois. Rien ne gardait la classe: un seul test
verifiait la sortie du filtre sur un champ, ce qui ne dit rien du prochain
flottant ecrit ailleurs.

**Ce que ces tests couvrent, et ce qu'ils ne couvrent pas.** Le balayage des
gabarits trouve 64 insertions de variables dans des scripts; les enumerer
serait une liste tenue a la main, qui ne repondrait qu'a la question posee ce
jour-la. Les deux gardes visent donc autre chose:

- les deux insertions **connues comme flottantes** gardent leur filtre, nommees
  une par une parce que ce sont les seules dont le type est un flottant;
- **aucune page servie** ne porte de virgule decimale dans un script, en
  francais, la langue ou le defaut se voit.

Le second ne couvre que les chemins de code **reellement rendus**: le bloc de
previsualisation du build, par exemple, n'est pas rendu pour un build sans
apparence, et une virgule qui y naitrait ne serait pas vue par lui. C'est
precisement pour cela que le premier existe.
"""

import io
import os
import re

from django.test import SimpleTestCase, TestCase
from django.template import Context, Template
from django.utils import translation

#: Les insertions dont la valeur est un flottant, et le fichier qui les porte.
#: `preview_box.scale` vaut 0.909 a 150 % et 1.24 a 200 %.
_FLOTTANTS = (
    ('solution.html', 'preview_box.scale'),
    ('compare_sets.html', 'preview_box.scale'),
)

#: Les pages que le balayage peut atteindre sans session ni build.
_PAGES = ('/', '/about/', '/faq/', '/guides/', '/sharedbuilds/',
          '/encyclopedia/', '/forgemagie/', '/quickstart/', '/support/',
          '/license/', '/retro/', '/touch/', '/dofus2/', '/beta/',
          '/retro/forgemagie/')

_SCRIPT = re.compile(r'<script\b[^>]*>(.*?)</script>', re.S | re.I)

#: Un nombre a virgule la ou JavaScript attend une valeur.
_VIRGULE = re.compile(r'[=:([,]\s*(\d+,\d+)')

#: Les chaines: une virgule y est du texte.
_CHAINE = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'')


def _gabarit(nom):
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'templates', 'chardata', nom)
    with io.open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


def _sans_chaines(source):
    return _CHAINE.sub('""', source)


class TheKnownFloatsKeepTheirFilterTests(SimpleTestCase):

    def test_the_filter_is_what_makes_the_difference(self):
        """Le symptome, montre plutot qu'affirme.

        Si Django cessait un jour de localiser les flottants, ce test
        tomberait et dirait que les filtres ci-dessous ne servent plus a rien,
        au lieu de les laisser vieillir en decor.
        """
        sans = Template('{% load l10n %}{{ v }}')
        avec = Template('{% load l10n %}{{ v|unlocalize }}')
        with translation.override('fr'):
            self.assertEqual('0,909', sans.render(Context({'v': 0.909})))
            self.assertEqual('0.909', avec.render(Context({'v': 0.909})))

    def test_every_float_inserted_in_a_script_carries_unlocalize(self):
        manquants = []
        for nom, expression in _FLOTTANTS:
            source = _gabarit(nom)
            for bloc in _SCRIPT.finditer(source):
                for m in re.finditer(
                        r'\{\{\s*' + re.escape(expression) + r'\s*([^}]*)\}\}',
                        bloc.group(1)):
                    if 'unlocalize' not in m.group(1):
                        manquants.append((nom, m.group(0)))
        self.assertFalse(
            manquants,
            'these render a float into JavaScript, which French writes with a '
            'comma and the script stops there: %s' % manquants)

    def test_the_named_floats_are_still_in_those_templates(self):
        """Une liste qui ne designe plus rien ne garde rien."""
        absents = [(nom, expression) for nom, expression in _FLOTTANTS
                   if expression not in _gabarit(nom)]
        self.assertFalse(absents,
                         'these are named here but gone from the template: %s'
                         % absents)


class NoServedPageCarriesADecimalCommaInAScriptTests(TestCase):

    def test_the_sweep_actually_reads_scripts(self):
        """Le plancher: un balayage qui ne lit aucun script ne garde rien."""
        blocs = 0
        for chemin in _PAGES:
            reponse = self.client.get(chemin, headers={'accept-language': 'fr'},
                                      follow=True)
            if reponse.status_code != 200:
                continue
            blocs += len(_SCRIPT.findall(reponse.content.decode('utf-8')))
        self.assertGreater(blocs, 50,
                           'only %d script blocks read; the sweep sees almost '
                           'nothing' % blocs)

    def test_no_page_serves_a_decimal_comma_in_a_script(self):
        fautifs = []
        for chemin in _PAGES:
            reponse = self.client.get(chemin, headers={'accept-language': 'fr'},
                                      follow=True)
            if reponse.status_code != 200:
                continue
            corps = reponse.content.decode('utf-8')
            for bloc in _SCRIPT.finditer(corps):
                code = _sans_chaines(bloc.group(1))
                for m in _VIRGULE.finditer(code):
                    debut = max(0, m.start() - 40)
                    fautifs.append((chemin,
                                    code[debut:m.end()].strip()[-60:]))
        self.assertFalse(
            fautifs,
            'these serve a number with a decimal comma inside a script, so '
            'the script stops there for a French reader: %s' % fautifs[:4])
