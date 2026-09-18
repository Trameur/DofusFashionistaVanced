# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Headings, landmarks and skip link on hubs and detail pages."""
import re

from django.test import TestCase

CARREFOURS = ('/', '/encyclopedia/', '/encyclopedia/sets/',
              '/encyclopedia/monsters/', '/sharedbuilds/', '/guides/',
              '/encyclopedia/most-used/',
              '/setup/')
# (hub, detail link prefix): detail pages are found on the hub
FAMILLES = (('/encyclopedia/', '/encyclopedia/item/'),
            ('/encyclopedia/sets/', '/encyclopedia/set/'),
            ('/encyclopedia/monsters/', '/encyclopedia/monster/'),
            ('/guides/', '/guides/'))
REPERES = ('main', 'navigation', 'contentinfo')
NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


class EveryPageHasAShapeTests(TestCase):
    """One main heading, no gap in the levels, and the three landmarks."""

    def _html(self, chemin):
        reponse = self.client.get(chemin, HTTP_ACCEPT_LANGUAGE='en',
                                  HTTP_USER_AGENT=NAVIGATEUR)
        self.assertEqual(reponse.status_code, 200,
                         '%s answered %s' % (chemin, reponse.status_code))
        return reponse.content.decode('utf-8', 'replace')

    def _pages(self):
        """The hubs, plus one detail page discovered on each of them."""
        trouve = list(CARREFOURS)
        for carrefour, prefixe in FAMILLES:
            html = self._html(carrefour)
            lien = next((href for href in re.findall('href="([^"]+)"', html)
                         if href.startswith(prefixe)
                         and len(href) > len(carrefour) + 1), None)
            self.assertIsNotNone(
                lien, 'no %s page linked from %s' % (prefixe, carrefour))
            trouve.append(lien)
        return trouve

    def test_every_page_carries_exactly_one_main_heading(self):
        sans, plusieurs, vues = [], [], 0
        for chemin in self._pages():
            combien = len(re.findall('<h1[ >]', self._html(chemin)))
            vues += 1
            if combien == 0:
                sans.append(chemin)
            elif combien > 1:
                plusieurs.append((chemin, combien))
        self.assertFalse(sans, 'these pages carry no main heading: %s' % sans)
        self.assertFalse(plusieurs,
                         'these pages carry several: %s' % plusieurs)
        self.assertGreaterEqual(
            vues, len(CARREFOURS) + len(FAMILLES),
            'only %d pages examined' % vues)

    def test_no_page_skips_a_heading_level(self):
        sauts = []
        for chemin in self._pages():
            niveaux = [int(n) for n
                       in re.findall('<h([1-6])[ >]', self._html(chemin))]
            for avant, apres in zip(niveaux, niveaux[1:]):
                if apres - avant > 1:
                    sauts.append((chemin, 'h%d -> h%d' % (avant, apres)))
        self.assertFalse(sauts, 'these pages skip a level: %s' % sauts[:4])

    def test_every_page_declares_its_landmarks(self):
        """The roles live in base.html."""
        manquants = []
        for chemin in self._pages():
            html = self._html(chemin)
            for repere in REPERES:
                if 'role="%s"' % repere not in html:
                    manquants.append((chemin, repere))
        self.assertFalse(manquants,
                         'these pages declare no such landmark: %s'
                         % manquants[:6])

    def test_every_page_offers_a_way_past_the_sidebar(self):
        casses, vues = [], 0
        for chemin in self._pages():
            html = self._html(chemin)
            lien = re.search('<a class="skip-link" href="#([^"]+)"', html)
            vues += 1
            if lien is None:
                casses.append((chemin, 'no skip link'))
            elif ('id="%s"' % lien.group(1)) not in html:
                casses.append((chemin, 'points at #%s which is absent'
                               % lien.group(1)))
        self.assertFalse(casses, 'these pages cannot be skipped past: %s'
                         % casses[:4])
        self.assertGreaterEqual(vues, len(CARREFOURS) + len(FAMILLES))

    def test_the_skip_link_speaks_the_language_of_the_page(self):
        anglais = 'Skip to content'
        for prefixe in ('fr', 'es', 'pt', 'de'):
            chemin = '/%s/encyclopedia/' % prefixe
            with self.subTest(langue=prefixe):
                html = self._html(chemin)
                lien = re.search(
                    '<a class="skip-link"[^>]*>(.*?)</a>', html, re.S)
                self.assertIsNotNone(lien, '%s has no skip link' % chemin)
                self.assertNotEqual(lien.group(1).strip(), anglais,
                                    '%s offers the English wording' % chemin)

    def test_no_page_opens_a_second_page_shell(self):
        """base.html already opens maincolumn and maincontent."""
        doubles = []
        for chemin in self._pages():
            html = self._html(chemin)
            for classe in ('maincolumn', 'maincontent'):
                combien = html.count('class="%s' % classe)
                if combien > 1:
                    doubles.append((chemin, classe, combien))
        self.assertFalse(doubles, 'these pages open a shell twice: %s'
                         % doubles[:4])

    def test_a_row_that_can_hold_thirty_items_is_allowed_to_wrap(self):
        """The .pagination flex row must wrap."""
        import os
        import re
        from chardata.pagination import pagination_items

        class _Paginator(object):
            def __init__(self, n):
                self.num_pages = n

        class _Page(object):
            def __init__(self, number, n):
                self.number = number
                self.paginator = _Paginator(n)

        combien = len(pagination_items(_Page(42, 83)))
        self.assertGreater(combien, 10,
                           'pagination_items returned %d entries; this test no '
                           'longer describes the markup' % combien)

        chemin = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'chardata', 'static', 'chardata',
            'sharedbuilds.css')
        with open(chemin, encoding='utf-8') as fichier:
            feuille = fichier.read()
        debut = feuille.find('.pagination {')
        self.assertNotEqual(-1, debut, 'no .pagination rule in sharedbuilds.css')
        regle = feuille[debut:feuille.find('}', debut)]
        self.assertIn('display: flex', regle)
        self.assertIn('flex-wrap: wrap', regle,
                      'a flex row of %d items with no wrapping' % combien)

    def test_the_flagship_page_is_reachable_from_more_than_one_hub(self):
        cible = '/encyclopedia/most-used/'
        depuis = []
        for carrefour in CARREFOURS:
            if cible in carrefour:
                continue
            if cible in self._html(carrefour):
                depuis.append(carrefour)
        self.assertGreaterEqual(
            len(depuis), 2,
            'only %d hub(s) link to the most-worn page: %s' % (len(depuis),
                                                              depuis))

    def test_a_table_is_either_data_or_declared_decorative(self):
        """A table has a <th> or role="presentation"."""
        nus = []
        for chemin in self._pages():
            html = self._html(chemin)
            for ouvre in re.finditer('<table[ >][^>]*>', html):
                ferme = html.find('</table>', ouvre.end())
                corps = html[ouvre.end():ferme] if ferme != -1 else ''
                if '<th' in corps or 'presentation' in ouvre.group(0):
                    continue
                nus.append((chemin, ' '.join(ouvre.group(0).split())[:48]))
        self.assertFalse(
            nus, 'these tables are neither data nor declared decorative: %s'
            % nus[:4])
