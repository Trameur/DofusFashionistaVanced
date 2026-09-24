# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The site never shows an address that claims to be its own without being it."""

import io
import os
import re

from django.test import SimpleTestCase, TestCase

from chardata.compare_sets_view import _process_link
from chardata.url_language import SITE_URL

# A host carrying our brand; external links are not us
NOTRE_MARQUE = re.compile(
    r'https?://([A-Za-z0-9.\-]*'
    r'(?:dofusfashionista|fashionistavanced)[A-Za-z0-9.\-]*)')

_EXTENSIONS = ('.html', '.py', '.js', '.txt', '.json')
_IGNORES = {'staticfiles', '__pycache__', 'locale', 'node_modules'}

# How many times the site names an address of its own: a floor for the sweep below
_MENTIONS = 140

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def _fichiers():
    for base in ('fashionsite', 'fashionistapulp'):
        for dossier, sous, noms in os.walk(os.path.join(_RACINE, base)):
            sous[:] = [d for d in sous if d not in _IGNORES]
            for nom in noms:
                if nom.endswith(_EXTENSIONS):
                    yield os.path.join(dossier, nom)


def _hotes_du_fichier(chemin):
    with io.open(chemin, encoding='utf-8', errors='replace') as fichier:
        for numero, ligne in enumerate(fichier, 1):
            for hote in NOTRE_MARQUE.findall(ligne):
                yield hote, numero


def _hotes_declares():
    declares = set()
    for nom in ('settings.py', 'settings_dev.py'):
        chemin = os.path.join(_RACINE, 'fashionsite', 'fashionsite', nom)
        if not os.path.exists(chemin):
            continue
        with io.open(chemin, encoding='utf-8') as fichier:
            contenu = fichier.read()
        declares.update(NOTRE_MARQUE.findall(contenu))
        for trouve in re.findall(r"'\.?([A-Za-z0-9.\-]*"
                                 r"(?:dofusfashionista|fashionistavanced)"
                                 r"[A-Za-z0-9.\-]*)'", contenu):
            declares.add(trouve)
    return declares


class EveryAddressThatClaimsToBeUsIsUsTests(SimpleTestCase):

    def test_no_file_names_a_host_the_settings_do_not(self):
        declares = _hotes_declares()
        self.assertIn('dofusfashionista.gg', declares,
                      'the settings no longer name the site itself')
        etrangers = []
        for chemin in _fichiers():
            for hote, numero in _hotes_du_fichier(chemin):
                if hote not in declares:
                    etrangers.append('%s:%d %s'
                                     % (chemin[len(_RACINE) + 1:].replace(
                                         os.sep, '/'), numero, hote))
        self.assertEqual([], etrangers[:5],
                         'these addresses claim to be us: %s' % etrangers[:5])

    def test_the_site_names_itself_often_enough_for_that_to_mean_something(
            self):
        combien = sum(1 for chemin in _fichiers()
                      for _hote, _n in _hotes_du_fichier(chemin))
        self.assertGreaterEqual(combien, _MENTIONS)

    def test_the_canonical_address_is_the_one_the_settings_serve(self):
        hote = SITE_URL.split('//', 1)[-1]
        self.assertIn(hote, _hotes_declares())
        self.assertTrue(SITE_URL.startswith('https://'), SITE_URL)


class TheComparePageShowsAnExampleThatWorksTests(TestCase):

    def _exemples(self, chemin):
        page = self.client.get(chemin, follow=True).content.decode('utf-8')
        return re.findall(r'class="link-text">([^<]+)</span>', page)

    def test_both_examples_name_our_address(self):
        exemples = self._exemples('/choose_compare_sets/')
        self.assertEqual(2, len(exemples), exemples)
        for exemple in exemples:
            self.assertTrue(exemple.startswith(SITE_URL), exemple)

    def test_the_example_carries_the_readers_own_version(self):
        for prefixe, attendu in (('', ''), ('/retro', '/retro'),
                                 ('/touch', '/touch')):
            with self.subTest(version=prefixe or 'dofus3'):
                exemples = self._exemples('%s/choose_compare_sets/' % prefixe)
                self.assertTrue(exemples)
                for exemple in exemples:
                    chemin = exemple[len(SITE_URL):]
                    self.assertTrue(chemin.startswith(attendu + '/'),
                                    '%s does not carry %s' % (exemple, attendu))

    def test_a_link_of_that_shape_is_understood(self):
        for prefixe in ('', '/retro'):
            with self.subTest(version=prefixe or 'dofus3'):
                modele, partage = self._exemples(
                    '%s/choose_compare_sets/' % prefixe)
                self.assertEqual('12345', _process_link(modele))
                self.assertEqual('AbCdEf_', _process_link(partage))

    def test_no_example_names_a_dead_host(self):
        for prefixe in ('', '/retro', '/beta', '/dofus2', '/touch'):
            with self.subTest(version=prefixe or 'dofus3'):
                for exemple in self._exemples(
                        '%s/choose_compare_sets/' % prefixe):
                    self.assertNotIn('dofusfashionista.com', exemple)
                    self.assertNotIn('http://', exemple)
