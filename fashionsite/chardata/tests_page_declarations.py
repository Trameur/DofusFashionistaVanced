# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Ce qu'une page declare sur elle-meme doit etre lisible, et vrai.

Deux defauts de la meme famille, trouves le meme jour sur la production :

  - le fil d'Ariane des pages « objet indisponible » publiait DEUX entrees
    consecutives portant exactement la meme URL, celle du carrefour. La feuille
    disait donc que la page est son propre parent ;

  - `provenance.html` remplissait `{% block meta_robots %}` avec une balise
    complete, alors que ce bloc remplit un attribut `content=`. Le rendu donnait
    `content="<meta name="` et **la page ne portait plus aucune directive** --
    une page d'administration qui se croyait `noindex` et ne l'etait pas.

Les deux passent une validation HTML sans un mot : le premier produit du JSON
valide qui affirme une fausseté, le second de l'attribut mal ferme qu'un
navigateur avale. Ce sont des declarations, et une declaration ne se verifie
qu'en la lisant.
"""
import json
import re

from django.test import TestCase

CARREFOURS = ('/', '/encyclopedia/', '/encyclopedia/sets/',
              '/encyclopedia/monsters/', '/guides/', '/sharedbuilds/',
              '/setup/', '/encyclopedia/most-used/')
#: L'adresse qui rend vraiment la reponse « indisponible ». La premiere
#: version de ce module interrogeait /encyclopedia/item/<mot>/ : cette route
#: exige un ID NUMERIQUE, donc le routeur rendait un 404 nu et la vue
#: corrigee n'etait jamais atteinte. Un test juste sur un correctif juste,
#: sans un seul contact entre les deux -- et il aurait vire au VERT.
INTROUVABLE = '/encyclopedia/monster/99999999-rien/'
NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


class APageDeclaresItselfLegiblyTests(TestCase):

    def _html(self, chemin, attendu=200):
        reponse = self.client.get(chemin, HTTP_USER_AGENT=NAVIGATEUR,
                                  HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(attendu, reponse.status_code,
                         '%s answered %s' % (chemin, reponse.status_code))
        return reponse.content.decode('utf-8', 'replace')

    def _fils(self, html):
        """Les BreadcrumbList de la page, decodes."""
        fils = []
        for bloc in re.findall(
                r'<script type="application/ld\+json">(.*?)</script>',
                html, re.S):
            try:
                donnee = json.loads(bloc)
            except ValueError:
                self.fail('a ld+json block does not parse: %s' % bloc[:120])
            if donnee.get('@type') == 'BreadcrumbList':
                fils.append(donnee)
        return fils

    def test_no_breadcrumb_names_the_same_url_twice(self):
        doubles = []
        vus = 0
        for chemin, attendu in [(c, 200) for c in CARREFOURS] + [
                (INTROUVABLE, 404)]:
            for fil in self._fils(self._html(chemin, attendu)):
                vus += 1
                urls = [e.get('item') for e in fil.get('itemListElement', [])
                        if e.get('item')]
                if len(urls) != len(set(urls)):
                    doubles.append((chemin, urls))
        self.assertFalse(
            doubles, 'these breadcrumbs name a url twice, so a leaf points at '
                     'its own parent: %s' % doubles[:3])
        # Un plancher MESURE, pas suppose : /, /guides/ et /setup/ n'emettent
        # aucun fil, ce qui est correct pour une racine. La premiere version
        # exigeait un fil par carrefour et condamnait trois pages saines.
        self.assertGreaterEqual(vus, 5, 'only %d breadcrumbs found' % vus)

    def test_the_missing_page_still_publishes_a_trail(self):
        """Le controle positif du test au-dessus.

        Retirer le fil entier ferait disparaitre le doublon, et le premier test
        passerait. Celui-ci exige que le fil existe encore, et qu'il nomme le
        carrefour.
        """
        fils = self._fils(self._html(INTROUVABLE, 404))
        self.assertEqual(1, len(fils), 'the missing page publishes %d trails'
                                       % len(fils))
        urls = [e.get('item') for e in fils[0].get('itemListElement', [])]
        self.assertEqual(2, len(urls), urls)
        self.assertTrue(urls[1].endswith('/encyclopedia/'), urls)

    def test_no_page_puts_markup_in_its_robots_directive(self):
        """`content=` prend une directive, pas une balise.

        Une balise complete dans ce bloc coupe l'attribut a son premier
        guillemet : la page perd sa directive sans que rien ne le signale, et un
        validateur HTML ne s'en emeut pas non plus.
        """
        casses = []
        for chemin in CARREFOURS + (INTROUVABLE,):
            attendu = 404 if chemin == INTROUVABLE else 200
            html = self._html(chemin, attendu)
            for balise in re.findall(r'<meta[^>]*name="robots"[^>]*>', html):
                contenu = re.search(r'content="([^"]*)"', balise)
                if contenu is None or '<' in contenu.group(1):
                    casses.append((chemin, balise[:70]))
        self.assertFalse(
            casses, 'these robots directives carry markup: %s' % casses[:3])

    def test_an_admin_page_keeps_its_noindex_too(self):
        """La page qui portait le defaut n'etait dans aucune population.

        Le test au-dessus promene ses carrefours publics, et il restait VERT
        avec la balise imbriquee remise en place : `/admin-tools/provenance/`
        demande une session d'administration, donc il ne l'ouvrait jamais. Un
        garde ecrit POUR une page, qui ne l'ouvre pas -- pour la troisieme fois
        dans la journee, et cette fois dans le module qui raconte la faute.

        C'est aussi la page ou ca coute le plus cher : une page d'administration
        qui se croit `noindex` et ne l'est pas est precisement celle qu'on ne
        voudrait pas voir indexee.
        """
        import hashlib

        from django.core.management import call_command

        call_command('create_local_admin', username='localadmin',
                     email='la@test.local', password='a-solid-pw-42')
        prehash = hashlib.sha256(
            ('dofusfashionista' + 'a-solid-pw-42').encode()).hexdigest()
        self.assertEqual(200, self.client.post(
            '/local_login/', {'username': 'localadmin',
                              'password': prehash}).status_code)

        page = self._html('/admin-tools/provenance/')
        balises = re.findall(r'<meta[^>]*name="robots"[^>]*>', page)
        self.assertTrue(balises, 'the provenance page declares no robots rule')
        # Un seul message pour les deux moities : la falsification cherche un
        # mot dans la sortie, et deux messages differents lui font rater le
        # rouge selon laquelle des deux assertions tombe la premiere.
        for balise in balises:
            contenu = re.search(r'content="([^"]*)"', balise)
            faute = ('the robots directive is not a directive: %s'
                     % balise)
            self.assertIsNotNone(contenu, faute)
            valeur = contenu.group(1)
            self.assertNotIn('<', valeur, faute)
            self.assertIn('noindex', valeur, faute)
