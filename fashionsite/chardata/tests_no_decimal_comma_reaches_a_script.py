# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A localized decimal comma never reaches a page's JavaScript."""

import io
import os
import re

from django.test import SimpleTestCase, TestCase
from django.template import Context, Template
from django.utils import translation

# The insertions whose value is a float, and the file that carries them; preview_box.scale is 0.909 at 150 % and 1.24 at 200 %
_FLOTTANTS = (
    ('solution.html', 'preview_box.scale'),
    ('compare_sets.html', 'preview_box.scale'),
)

# The pages the sweep can reach without a session or a build
_PAGES = ('/', '/about/', '/faq/', '/guides/', '/sharedbuilds/',
          '/encyclopedia/', '/forgemagie/', '/quickstart/', '/support/',
          '/license/', '/retro/', '/touch/', '/dofus2/', '/beta/',
          '/retro/forgemagie/')

_SCRIPT = re.compile(r'<script\b[^>]*>(.*?)</script\b[^>]*>', re.S | re.I)

# A decimal comma where JavaScript expects a value
_VIRGULE = re.compile(r'[=:([,]\s*(\d+,\d+)')

# Strings: a comma there is text
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
        absents = [(nom, expression) for nom, expression in _FLOTTANTS
                   if expression not in _gabarit(nom)]
        self.assertFalse(absents,
                         'these are named here but gone from the template: %s'
                         % absents)


class NoServedPageCarriesADecimalCommaInAScriptTests(TestCase):

    def test_the_sweep_actually_reads_scripts(self):
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
