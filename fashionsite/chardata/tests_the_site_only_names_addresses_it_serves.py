# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le site ne montre jamais une adresse qui pretend etre la sienne sans l'etre.

Trouve en exercant la page <<Escolha os sets para comparar>> en portugais sur
Retro. Elle montre au lecteur la forme d'un lien a coller, et cette forme nommait
l'hote `dofusfashionista.com`, ecrit ici sans son schema pour que cette note
ne soit pas elle-meme une adresse:

- ce n'est pas l'adresse du site, qui est `https://dofusfashionista.gg`;
- cet hote n'est meme pas dans `ALLOWED_HOSTS`, donc le site refuserait une
  requete qui le porte;
- et le schema etait `http`, alors que le site est en `https`.

Mesure du 13 septembre 2026 sur les gabarits, le Python et le JavaScript:
**149 mentions d'une adresse a nous, sur 6 hotes**, tous declares dans les
reglages, sauf ces deux lignes-la. Elles etaient les seules.

Le correctif ne remplace pas un domaine par un autre: l'hote vient desormais
de `SITE_URL` et le chemin du routage du site, donc l'exemple porte aussi le
prefixe de version et de langue du lecteur et ne peut plus deriver.

    pt / retro   https://dofusfashionista.gg/pt/retro/solution/12345/
    pt / dofus3  https://dofusfashionista.gg/solution/12345/
    pt / touch   https://dofusfashionista.gg/pt/touch/solution/12345/

Et l'exemple est un exemple qui marche: un lien de cette forme, avec un vrai
numero, est accepte et rend `/pt/retro/compare_sets/89/83`.
"""

import io
import os
import re

from django.test import SimpleTestCase, TestCase

from chardata.compare_sets_view import _process_link
from chardata.url_language import SITE_URL

#: Un hote qui porte notre marque. Ce test ne dit rien des liens externes:
#: github, discord ou Ankama ne pretendent pas etre nous.
NOTRE_MARQUE = re.compile(
    r'https?://([A-Za-z0-9.\-]*'
    r'(?:dofusfashionista|fashionistavanced)[A-Za-z0-9.\-]*)')

_EXTENSIONS = ('.html', '.py', '.js', '.txt', '.json')
_IGNORES = {'staticfiles', '__pycache__', 'locale', 'node_modules'}

#: Combien de fois le site nomme une adresse a lui. Un plancher: si ce nombre
#: s'effondrait, le balayage ci-dessous passerait sans rien avoir regarde.
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
    """Les hotes que les reglages nomment: ceux que le site sert, plus le
    seau de fichiers. Lus dans le fichier et non dans `settings`, parce que
    `ALLOWED_HOSTS` vaut `["*"]` quand DEBUG est vrai."""
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
        """Le test qui aurait attrape le defaut."""
        declares = _hotes_declares()
        self.assertIn('dofusfashionista.gg', declares,
                      'les reglages ne nomment plus le site lui-meme')
        etrangers = []
        for chemin in _fichiers():
            for hote, numero in _hotes_du_fichier(chemin):
                if hote not in declares:
                    etrangers.append('%s:%d %s'
                                     % (chemin[len(_RACINE) + 1:].replace(
                                         os.sep, '/'), numero, hote))
        self.assertEqual([], etrangers[:5],
                         'ces adresses pretendent etre nous: %s' % etrangers[:5])

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
    """L'exemple est le seul endroit du site qui apprend au lecteur la forme
    d'un lien. Il doit porter notre adresse, le prefixe de sa page, et etre
    accepte par l'analyseur qui lira ce qu'il collera."""

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
                                    '%s ne porte pas %s' % (exemple, attendu))

    def test_a_link_of_that_shape_is_understood(self):
        """Un exemple qui ne marcherait pas serait pire que pas d'exemple."""
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
