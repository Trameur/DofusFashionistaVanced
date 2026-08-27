# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Une adresse a UN canonique, et il ne se negocie pas avec le navigateur.

Servi a un lecteur francais, `/guides/` declarait `rel=canonical` vers
`/fr/guides/` -- tout en restant, dans le meme `<head>`, le `x-default` et le
membre anglais de son propre groupe hreflang. La page se disait a la fois
l'original anglais et une copie du francais.

La cause etait `{% game_url 'guides' %}` : il passe par `reverse()`, qui ajoute
le prefixe de la langue ACTIVE, et la langue active vient de `Accept-Language`.
Les fiches de guides tiraient deja la leur de leur slug ; seul le carrefour
suivait le navigateur.

Ce module n'assure pas « le canonique de /guides/ vaut /guides/ », qui
serait une regle d'orthographe. Il assure que **le canonique ne change pas quand
l'en-tete change**, sur tous les carrefours : la regression suivante ne sera pas
sur la meme page.
"""
import re

from django.test import TestCase

#: Les carrefours, plus une fiche par famille : le defaut ne vivait que sur un
#: carrefour, et un echantillon de fiches seules ne l'aurait jamais vu.
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
        """Sinon le x-default du groupe se declare copie d'un de ses membres.

        C'est le sens du defaut, pas seulement sa forme : une page qui renonce a
        elle-meme au profit d'une traduction demande a etre desindexee.
        """
        for chemin in ('/guides/', '/encyclopedia/'):
            with self.subTest(chemin=chemin):
                self.assertTrue(
                    self._canonique(chemin, 'fr-FR,fr;q=0.9').endswith(chemin),
                    '%s points its canonical somewhere else' % chemin)

    def test_a_prefixed_hub_keeps_its_prefix(self):
        """Le controle positif de la paire.

        Sans lui, un canonique qui laisserait TOMBER le prefixe passerait les
        deux tests precedents : il serait stable, et la version sans prefixe
        serait bien sa propre canonique.
        """
        for prefixe in ('fr', 'es'):
            with self.subTest(langue=prefixe):
                chemin = '/%s/guides/' % prefixe
                self.assertTrue(
                    self._canonique(chemin, 'en-US,en;q=0.9').endswith(chemin),
                    '%s drops its language prefix' % chemin)
