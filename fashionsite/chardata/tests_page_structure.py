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
              '/encyclopedia/most-used/',  # ni carrefour ni fiche : sans
              # cette ligne la population du module ne la contenait pas, et le garde
              # ecrit pour ELLE passait au vert sans jamais l'ouvrir.
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

    def test_every_page_offers_a_way_past_the_sidebar(self):
        """A keyboard reader without a screen reader has no landmark to jump to.

        The roles added alongside this help software that understands them; a
        reader who simply cannot hold a mouse tabs through the whole sidebar on
        every page. The link stays off-screen until it takes focus, so it is
        invisible to a mouse and changes nothing on screen.

        The target is checked as well as the link: one that points at an id
        which does not exist moves focus nowhere, and is worse than none
        because it looks like the problem was handled.
        """
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
        # Un lien d'evitement en anglais sur une page francaise est lu par une
        # synthese vocale francaise, qui prononce l'anglais avec les regles du
        # francais : le lecteur entend une bouillie a la premiere tabulation.
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
        """base.html already opens the column and the content panel.

        A child template that opens them again is drawn INSIDE the first: the
        content shifts another 200 pixels right on a desktop and sits in a
        second bordered, padded panel. Nothing errors, the page renders, and
        only an eye on a wide screen notices -- which is why it survived.
        """
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
        """The markup grew and the stylesheet did not.

        Keeping one page in ten plus its neighbours took the pagination from
        five children to twenty-seven, in a flex row with no wrapping. At 375
        pixels the row is over a thousand wide, and overflow-x: hidden cuts it
        instead of letting it scroll: the last pages become unreachable on a
        phone.

        The two halves are asserted together because the defect is exactly
        their disagreement -- either alone looks fine.
        """
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
        """One inbound link is one template edit away from none.

        The page counting what players wear is the one thing here no wiki can
        copy, and it hung off a single link on the encyclopedia hub -- itself
        inside an {% if %}. It is computed from the shared builds, whose own hub
        did not mention it.

        The count is what this asserts, not the identity of the hubs: naming
        them would turn a linking rule into a spelling rule, and the day a third
        hub links to it the test would still say two.
        """
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
