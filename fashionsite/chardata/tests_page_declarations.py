# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What a page declares about itself, breadcrumbs and robots directives, is readable and true."""
import json
import re

from django.test import TestCase

CARREFOURS = ('/', '/encyclopedia/', '/encyclopedia/sets/',
              '/encyclopedia/monsters/', '/guides/', '/sharedbuilds/',
              '/setup/', '/encyclopedia/most-used/')
# The address that really renders the unavailable answer; /encyclopedia/item/<word>/ needs a numeric id
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
        # A floor: /, /guides/ and /setup/ emit no breadcrumb, which is right for a root
        self.assertGreaterEqual(vus, 5, 'only %d breadcrumbs found' % vus)

    def test_the_missing_page_still_publishes_a_trail(self):
        fils = self._fils(self._html(INTROUVABLE, 404))
        self.assertEqual(1, len(fils), 'the missing page publishes %d trails'
                                       % len(fils))
        urls = [e.get('item') for e in fils[0].get('itemListElement', [])]
        self.assertEqual(2, len(urls), urls)
        self.assertTrue(urls[1].endswith('/encyclopedia/'), urls)

    def test_no_page_puts_markup_in_its_robots_directive(self):
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
        # One message for both halves, so a falsification finds the same word whichever assertion falls first
        for balise in balises:
            contenu = re.search(r'content="([^"]*)"', balise)
            faute = ('the robots directive is not a directive: %s'
                     % balise)
            self.assertIsNotNone(contenu, faute)
            valeur = contenu.group(1)
            self.assertNotIn('<', valeur, faute)
            self.assertIn('noindex', valeur, faute)
