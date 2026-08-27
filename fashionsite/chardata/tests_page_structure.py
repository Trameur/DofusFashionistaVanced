# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What a page offers to someone navigating it without a screen.

A reader using a screen reader moves by headings and by landmarks. The site
offered neither on its largest family: an item page carried no heading of any
level in its whole body -- the item's name lived in a div, and appeared as a
title only in the metadata, which is everywhere except where a reader looks.

The hubs were fine, all eight of them, which is exactly why this went unseen:
a sample that does not contain the guilty family reports a perfect green. The
detail pages here are discovered from their hub rather than listed, so a family
added later arrives already covered.
"""
import re

from django.test import TestCase

CARREFOURS = ('/', '/encyclopedia/', '/encyclopedia/sets/',
              '/encyclopedia/monsters/', '/sharedbuilds/', '/guides/',
              '/setup/')
#: (carrefour, prefixe du lien de detail) -- les fiches sont trouvees, pas ecrites.
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
        # Sans ce compte, un carrefour qui ne lie plus rien reduit la liste aux
        # sept adresses ecrites en dur et le test passe en couvrant moins.
        self.assertGreaterEqual(
            vues, len(CARREFOURS) + len(FAMILLES),
            'only %d pages examined' % vues)

    def test_no_page_skips_a_heading_level(self):
        # Sauter de h1 a h3 laisse un lecteur croire qu'il a rate une section.
        sauts = []
        for chemin in self._pages():
            niveaux = [int(n) for n
                       in re.findall('<h([1-6])[ >]', self._html(chemin))]
            for avant, apres in zip(niveaux, niveaux[1:]):
                if apres - avant > 1:
                    sauts.append((chemin, 'h%d -> h%d' % (avant, apres)))
        self.assertFalse(sauts, 'these pages skip a level: %s' % sauts[:4])

    def test_every_page_declares_its_landmarks(self):
        """Without them there is no way to jump past the sidebar.

        The roles sit on containers that already existed, so this checks that
        base.html still wraps the page: a template that stops extending it
        would lose all three at once and nothing else would say so.
        """
        manquants = []
        for chemin in self._pages():
            html = self._html(chemin)
            for repere in REPERES:
                if 'role="%s"' % repere not in html:
                    manquants.append((chemin, repere))
        self.assertFalse(manquants,
                         'these pages declare no such landmark: %s'
                         % manquants[:6])

    def test_a_table_is_either_data_or_declared_decorative(self):
        """A layout table is announced with its row and column count.

        Two of the five that had no header turned out to carry real column
        headings written as <td>; marking those decorative would have removed
        structure instead of repairing it. So the rule is not "no bare table",
        it is that each one says which of the two it is.
        """
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
