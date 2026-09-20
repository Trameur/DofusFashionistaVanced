# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A hub address has one canonical, and it does not follow the browser's language."""
import re

from django.test import TestCase

# The hubs, plus one page per family
CARREFOURS = ('/', '/guides/', '/encyclopedia/', '/encyclopedia/sets/',
              '/encyclopedia/monsters/', '/sharedbuilds/', '/setup/',
              '/guides/getting-started/')
LANGUES = ('fr-FR,fr;q=0.9', 'es-ES,es;q=0.9', 'pt-BR,pt;q=0.9',
           'de-DE,de;q=0.9', 'en-US,en;q=0.9')
NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


class ACanonicalDoesNotNegotiateTests(TestCase):

    def _canonique(self, chemin, langue=None):
        entetes = {'HTTP_USER_AGENT': NAVIGATEUR}
        if langue:
            entetes['HTTP_ACCEPT_LANGUAGE'] = langue
        reponse = self.client.get(chemin, **entetes)
        self.assertEqual(200, reponse.status_code,
                         '%s answered %s' % (chemin, reponse.status_code))
        html = reponse.content.decode('utf-8', 'replace')
        trouve = re.search(
            r'<link[^>]*rel="canonical"[^>]*>', html)
        self.assertIsNotNone(trouve, '%s declares no canonical' % chemin)
        href = re.search(r'href="([^"]+)"', trouve.group(0))
        self.assertIsNotNone(href, '%s canonical has no href' % chemin)
        return href.group(1)

    def test_no_hub_lets_a_header_choose_its_canonical(self):
        derives = []
        for chemin in CARREFOURS:
            vus = {langue: self._canonique(chemin, langue) for langue in LANGUES}
            vus['(aucun)'] = self._canonique(chemin)
            if len(set(vus.values())) > 1:
                derives.append((chemin, vus))
        self.assertFalse(
            derives,
            'these pages change their canonical with Accept-Language: %s'
            % derives[:2])

    def test_the_unprefixed_hub_is_its_own_canonical(self):
        for chemin in ('/guides/', '/encyclopedia/'):
            with self.subTest(chemin=chemin):
                self.assertTrue(
                    self._canonique(chemin, 'fr-FR,fr;q=0.9').endswith(chemin),
                    '%s points its canonical somewhere else' % chemin)

    def test_a_prefixed_hub_keeps_its_prefix(self):
        for prefixe in ('fr', 'es'):
            with self.subTest(langue=prefixe):
                chemin = '/%s/guides/' % prefixe
                self.assertTrue(
                    self._canonique(chemin, 'en-US,en;q=0.9').endswith(chemin),
                    '%s drops its language prefix' % chemin)
