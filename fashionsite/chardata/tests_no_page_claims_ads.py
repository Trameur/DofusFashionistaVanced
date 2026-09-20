# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""No page claims an advertisement the site does not serve; every public page is checked."""
from unittest import mock

from django.test import TestCase

# The module, not the class: importing a test class makes it discoverable here too
from chardata import tests as _tests

# Only its values: a module name bound to a test class collects it here as well
_CLAUSES = _tests.PrivacyPolicyDescribesWhatActuallyHappensTests.CLAUSES
_SANS = _tests.PrivacyPolicyDescribesWhatActuallyHappensTests.SANS_PUB
_AVEC = _tests.PrivacyPolicyDescribesWhatActuallyHappensTests.AVEC_PUB

# The hardcoded pages plus one discovered page per family
PAGES = ('/', '/about/', '/faq/', '/privacy/', '/license/', '/support/',
         '/contact/', '/guides/', '/encyclopedia/', '/encyclopedia/sets/',
         '/encyclopedia/monsters/', '/sharedbuilds/', '/setup/',
         '/forgemagie/')
FAMILLES = (('/encyclopedia/', '/encyclopedia/item/'),
            ('/encyclopedia/sets/', '/encyclopedia/set/'),
            ('/guides/', '/guides/'))
NAVIGATEUR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')


class NoPageClaimsAdvertisingItDoesNotServeTests(TestCase):

    CLAUSES = _CLAUSES
    SANS_PUB = _SANS
    AVEC_PUB = _AVEC

    def _html(self, chemin, pubs):
        with mock.patch('chardata.context_processors.ad_config',
                        return_value=dict(pubs)):
            reponse = self.client.get(chemin, HTTP_USER_AGENT=NAVIGATEUR,
                                      HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, reponse.status_code,
                         '%s answered %s' % (chemin, reponse.status_code))
        return reponse.content.decode('utf-8', 'replace')

    def _population(self):
        trouve = list(PAGES)
        for carrefour, prefixe in FAMILLES:
            html = self._html(carrefour, self.SANS_PUB)
            import re
            lien = next((h for h in re.findall('href="([^"]+)"', html)
                         if h.startswith(prefixe) and len(h) > len(carrefour) + 1),
                        None)
            self.assertIsNotNone(
                lien, 'no %s page linked from %s' % (prefixe, carrefour))
            trouve.append(lien)
        return trouve

    def test_the_clause_list_is_the_one_the_policy_guard_uses(self):
        self.assertTrue(self.CLAUSES, 'the clause list came back empty')
        self.assertIn('AdSense', self.CLAUSES)

    def test_no_page_describes_advertising_while_none_is_served(self):
        fautives = []
        vues = 0
        for chemin in self._population():
            html = self._html(chemin, self.SANS_PUB)
            vues += 1
            for clause in self.CLAUSES:
                if clause in html:
                    fautives.append((chemin, clause))
        self.assertFalse(
            fautives, 'these pages describe advertising that is not served: %s'
            % fautives[:4])
        self.assertGreaterEqual(vues, len(PAGES) + len(FAMILLES),
                                'only %d pages examined' % vues)

    def test_at_least_one_page_says_it_again_when_ads_return(self):
        dit = []
        for chemin in ('/privacy/', '/license/'):
            html = self._html(chemin, self.AVEC_PUB)
            dit += [(chemin, c) for c in self.CLAUSES if c in html]
        self.assertTrue(
            dit, 'no page mentions advertising even when it is served, so the '
                 'other test proves nothing')
