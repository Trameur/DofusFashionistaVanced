# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Aucune page n'affirme une publicite que le site ne sert pas.

La regle existait, elle etait ecrite, et une page l'avait manquee. `/license/`
affirmait sans condition que le site emploie AdSense « to display relevant ads »
et propose une « privacy settings banner » -- pendant que `/support/`, servi par
la meme production, disait « There is no advertising on the site » et qu'aucune
banniere n'existait.

La cause n'est pas la page, c'est la POPULATION du garde : il interrogeait
`/privacy/` et `/support/`, les deux pages auxquelles on avait pense. La liste
de clauses, elle, aurait trouve la phrase de `/license/` si on la lui avait
presentee.

Ce module reprend donc la meme liste de clauses -- importee, pas recopiee, pour
qu'une clause ajoutee la-bas ne manque pas ici -- et la promene sur toutes les
pages publiques, carrefours et fiches decouvertes comprises.
"""
from unittest import mock

from django.test import TestCase

# Le MODULE, pas la classe : importer une classe de test la rend
# decouvrable ici aussi, et les quatre tests de la garde de confidentialite
# tournaient une seconde fois sous ce nom.
from chardata import tests as _tests

# Et on ne garde que ses VALEURS : un nom de module lie a une classe de
# test la fait collecter ici aussi, quel que soit ce nom.
_CLAUSES = _tests.PrivacyPolicyDescribesWhatActuallyHappensTests.CLAUSES
_SANS = _tests.PrivacyPolicyDescribesWhatActuallyHappensTests.SANS_PUB
_AVEC = _tests.PrivacyPolicyDescribesWhatActuallyHappensTests.AVEC_PUB

#: Les pages ecrites en dur, plus une fiche decouverte par famille : une famille
#: ajoutee plus tard arrive couverte sans qu'on y pense.
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
        """Deux listes de clauses, c'est une clause ajoutee d'un seul cote.

        Le test existe pour que l'import reste un import : recopier la liste
        rendrait ce module vert pendant que l'autre attrape quelque chose.
        """
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
        """Le controle positif, et il est indispensable ici.

        Si le simulacre ne prenait pas, les deux etats rendraient la meme page
        sans clause et le test precedent passerait sans rien mesurer. Celui-ci
        echoue dans ce cas.
        """
        dit = []
        for chemin in ('/privacy/', '/license/'):
            html = self._html(chemin, self.AVEC_PUB)
            dit += [(chemin, c) for c in self.CLAUSES if c in html]
        self.assertTrue(
            dit, 'no page mentions advertising even when it is served, so the '
                 'other test proves nothing')
