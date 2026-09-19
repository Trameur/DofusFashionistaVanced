# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every member of a hreflang set declares the same set."""
import re

from django.test import TestCase

BASE = 'https://dofusfashionista.gg'

# (family, hub, detail link prefix)
FAMILLES = (
    ('objet', '/encyclopedia/', '/encyclopedia/item/'),
    ('panoplie', '/encyclopedia/sets/', '/encyclopedia/set/'),
    ('monstre', '/encyclopedia/monsters/', '/encyclopedia/monster/'),
    # Guides are translated by hand
    ('guide', '/guides/', '/guides/'),
)

CARREFOURS = ('/encyclopedia/', '/encyclopedia/sets/',
              '/encyclopedia/monsters/', '/encyclopedia/most-used/')

NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


class ATranslationSetAgreesWithItselfTests(TestCase):
    """One page, one set, and every member of the set says the same thing."""

    def _html(self, chemin):
        reponse = self.client.get(chemin, HTTP_ACCEPT_LANGUAGE='en',
                                  HTTP_USER_AGENT=NAVIGATEUR)
        self.assertEqual(reponse.status_code, 200,
                         '%s answered %s' % (chemin, reponse.status_code))
        return reponse.content.decode('utf-8', 'replace')

    @staticmethod
    def _ensemble(html):
        """The page's hreflang map, language to path, x-default excluded."""
        trouve = {}
        # The minifier sorts attributes, read them one by one
        for tag in re.findall('<link[^>]*hreflang=[^>]*>', html):
            langue = re.search('hreflang="([^"]+)"', tag)
            href = re.search('href="([^"]+)"', tag)
            if langue and href and langue.group(1) != 'x-default':
                trouve[langue.group(1)] = href.group(1).replace(BASE, '')
        return trouve

    def _premier_lien(self, carrefour, motif):
        """A detail page found on the hub."""
        html = self._html(carrefour)
        for href in re.findall('href="([^"]+)"', html):
            # Longer than the hub, or the back-to-hub link matches
            if href.startswith(motif) and len(href) > len(carrefour) + 1:
                return href
        return None

    def _verifier(self, depart):
        """Compare the set of `depart` with the set of each of its members."""
        depart_ensemble = self._ensemble(self._html(depart))
        if not depart_ensemble:
            return 0, []
        desaccords = []
        vus = 1
        for langue, chemin in sorted(depart_ensemble.items()):
            if chemin == depart:
                continue
            autre = self._ensemble(self._html(chemin))
            vus += 1
            if autre != depart_ensemble:
                manquants = set(depart_ensemble) - set(autre)
                differents = {k for k in set(depart_ensemble) & set(autre)
                              if depart_ensemble[k] != autre[k]}
                desaccords.append((depart, chemin, sorted(manquants),
                                   sorted(differents)))
        return vus, desaccords

    def test_a_detail_page_and_its_translations_declare_the_same_set(self):
        desaccords = []
        pages = 0
        familles_vues = 0
        for nom, carrefour, motif in FAMILLES:
            lien = self._premier_lien(carrefour, motif)
            with self.subTest(famille=nom):
                self.assertIsNotNone(
                    lien, 'no %s link found on %s' % (motif, carrefour))
            if lien is None:
                continue
            familles_vues += 1
            vus, mauvais = self._verifier(lien)
            pages += vus
            desaccords.extend(mauvais)
            # Per family: items alone would reach a global floor
            with self.subTest(famille=nom):
                self.assertGreaterEqual(
                    vus, 2, '%s compared %d page(s): %s declares no set'
                    % (nom, vus, lien))
        self.assertFalse(
            desaccords, 'these pages of one group declare different groups '
            '(page, other, missing, differing): %s' % desaccords[:3])
        self.assertEqual(familles_vues, len(FAMILLES))
        self.assertGreaterEqual(
            pages, 2 * len(FAMILLES),
            'only %d pages compared over %d families' % (pages, familles_vues))

    def test_a_hub_and_its_translations_declare_the_same_set(self):
        desaccords = []
        pages = 0
        for carrefour in CARREFOURS:
            vus, mauvais = self._verifier(carrefour)
            pages += vus
            desaccords.extend(mauvais)
        self.assertFalse(
            desaccords, 'these hubs of one group declare different groups '
            '(page, other, missing, differing): %s' % desaccords[:3])
        self.assertGreaterEqual(pages, len(CARREFOURS),
                                'only %d hub pages compared' % pages)

    def test_a_page_declares_the_language_its_url_promises(self):
        """The <html lang> matches the language of the localised slug."""
        faux = []
        verifiees = 0
        for nom, carrefour, motif in FAMILLES:
            lien = self._premier_lien(carrefour, motif)
            if lien is None:
                continue
            for langue, chemin in sorted(self._ensemble(self._html(lien)).items()):
                html = self._html(chemin)
                declare = re.search('<html[^>]*lang="([^"]+)"', html)
                verifiees += 1
                vu = declare.group(1).split('-')[0] if declare else 'absent'
                if vu != langue:
                    faux.append((nom, chemin, langue, vu))
        self.assertFalse(
            faux, 'these pages declare a language their url does not promise '
            '(family, page, promised, declared): %s' % faux[:4])
        # An empty set would check nothing and pass
        self.assertGreaterEqual(
            verifiees, 2 * len(FAMILLES),
            'only %d localised pages checked over %d families'
            % (verifiees, len(FAMILLES)))

    def test_a_page_that_declares_a_set_is_in_its_own_set(self):
        """A page appears in its own set."""
        absentes = []
        examinees = 0
        for chemin in CARREFOURS:
            ensemble = self._ensemble(self._html(chemin))
            if not ensemble:
                continue
            examinees += 1
            if chemin not in ensemble.values():
                absentes.append((chemin, sorted(ensemble.values())[:3]))
        self.assertFalse(absentes,
                         'these pages are missing from their own set: %s'
                         % absentes[:3])
        self.assertGreaterEqual(examinees, 1,
                                'no page declared any set at all')
