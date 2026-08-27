# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Whether the translation sets a page declares agree with each other.

The rule Google applies is stronger than "the other page mentions me". A
hreflang set is a group, and every member must declare the SAME group. If the
English page lists five languages and the German one lists three, the set is
inconsistent and the whole group is dropped -- not just the German entry. So a
page can point back correctly and still be ignored.

The pages are discovered from the hubs rather than written down. The slugs are
localised and change with the game data, and a hard-coded list only ever covers
what someone thought of on the day.
"""
import re

from django.test import TestCase

BASE = 'https://dofusfashionista.gg'

#: Un carrefour et le motif du lien de detail qu'on y cherche.
FAMILLES = (
    ('objet', '/encyclopedia/', '/encyclopedia/item/'),
    ('panoplie', '/encyclopedia/sets/', '/encyclopedia/set/'),
    ('monstre', '/encyclopedia/monsters/', '/encyclopedia/monster/'),
    # Les guides portent leur langue dans le slug comme les fiches, mais leur
    # texte est ecrit a la main : c'est la famille ou une traduction peut
    # manquer sans que rien d'automatique ne le signale.
    ('guide', '/guides/', '/guides/'),
)

#: Les carrefours eux-memes, qui sont publies par langue.
CARREFOURS = ('/encyclopedia/', '/encyclopedia/sets/',
              '/encyclopedia/monsters/', '/encyclopedia/most-used/')

NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


class ATranslationSetAgreesWithItselfTests(TestCase):
    """One page, one set, and every member of the set says the same thing.

    The existing reciprocity test checks a single French item page and asks
    only whether its alternates point back. That catches a link that goes
    nowhere; it does not catch two pages of the same group declaring different
    groups, which is the failure that makes Google drop the set entirely.
    """

    def _html(self, chemin):
        reponse = self.client.get(chemin, HTTP_ACCEPT_LANGUAGE='en',
                                  HTTP_USER_AGENT=NAVIGATEUR)
        self.assertEqual(reponse.status_code, 200,
                         '%s answered %s' % (chemin, reponse.status_code))
        return reponse.content.decode('utf-8', 'replace')

    @staticmethod
    def _ensemble(html):
        """The page's hreflang map, language to path, x-default excluded.

        The minifier reorders attributes, so each tag is matched whole and its
        two attributes read separately. A pattern expecting hreflang before
        href finds nothing and passes.
        """
        trouve = {}
        for tag in re.findall('<link[^>]*hreflang=[^>]*>', html):
            langue = re.search('hreflang="([^"]+)"', tag)
            href = re.search('href="([^"]+)"', tag)
            if langue and href and langue.group(1) != 'x-default':
                trouve[langue.group(1)] = href.group(1).replace(BASE, '')
        return trouve

    def _premier_lien(self, carrefour, motif):
        """A detail page found on the hub, so the slug is never hard-coded."""
        html = self._html(carrefour)
        for href in re.findall('href="([^"]+)"', html):
            # Plus long que le carrefour lui-meme : sans cette condition
            # le lien "retour au carrefour" que porte chaque page passe pour
            # une fiche, et on compare le carrefour avec lui-meme.
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
            # Compte PAR FAMILLE et pas en tout : un seuil global est atteint
            # par les seules fiches d'objet, et une famille qui ne declare
            # aucun groupe passerait sans que rien ne le dise.
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

    def test_a_page_that_declares_a_set_is_in_its_own_set(self):
        """A group whose member does not name itself is incomplete.

        This is the half the reciprocity test cannot see: it follows the links
        outward and never asks whether the page it started from appears in its
        own list.
        """
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
