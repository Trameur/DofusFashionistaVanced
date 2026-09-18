# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The not-in-this-version page names the versions that have it."""

import re

from django.test import SimpleTestCase, TestCase

from chardata import encyclopedia_view as vue


def _liens(page):
    bloc = re.search(r'class="encyclopedia-missing-elsewhere"(.*?)</div>',
                     page, re.S)
    if not bloc:
        return []
    return re.findall(r'href="([^"]+)"', bloc.group(1))


class AnItemMissingHereLinksToWhereItExistsTests(TestCase):

    def _adresse(self, version, ankama_type, ankama_id, nom):
        from chardata.official_site import get_item_link
        return get_item_link(ankama_type, ankama_id, nom, game_version=version)

    def _item_absent_de(self, version_absente, version_presente):
        la = vue._version_item_keys(version_presente)
        essais = 0
        for (ankama_type, ankama_id), nom in sorted(
                la.items(), key=lambda paire: -int(paire[0][1] or 0)):
            if ankama_type != 'equipment':
                continue
            essais += 1
            if essais > 40:
                break
            reponse = self.client.get(
                self._adresse(version_absente, ankama_type,
                              ankama_id, nom))
            if reponse.status_code == 404:
                return ankama_type, ankama_id, nom
        self.skipTest('no %s item is absent from %s'
                      % (version_presente, version_absente))

    def test_the_version_that_has_it_is_linked(self):
        ankama_type, ankama_id, nom = self._item_absent_de('retro', 'dofus3')
        reponse = self.client.get(
            self._adresse('retro', ankama_type, ankama_id, nom))
        self.assertEqual(404, reponse.status_code)
        page = reponse.content.decode('utf-8')
        liens = _liens(page)
        self.assertTrue(liens, 'the page names no version that carries %s'
                        % nom)
        self.assertTrue(any('/encyclopedia/item/' in l
                            and not l.startswith('/retro/') for l in liens),
                        liens)
        self.assertFalse(any(l.startswith('/retro/') for l in liens),
                         'the page links to the very version that lacks it')

    def test_the_back_to_hub_button_is_still_there(self):
        ankama_type, ankama_id, nom = self._item_absent_de('retro', 'dofus3')
        page = self.client.get(
            self._adresse('retro', ankama_type, ankama_id, nom)).content.decode('utf-8')
        self.assertIn('/retro/encyclopedia/', page)
        self.assertIn('encyclopedia-missing-actions', page)

    def test_every_offered_link_answers_200(self):
        ankama_type, ankama_id, nom = self._item_absent_de('retro', 'dofus3')
        page = self.client.get(
            self._adresse('retro', ankama_type, ankama_id, nom)).content.decode('utf-8')
        for lien in _liens(page):
            self.assertEqual(200, self.client.get(lien).status_code, lien)


class AMonsterMissingHereLinksToWhereItExistsTests(TestCase):

    def test_the_version_that_has_it_is_linked(self):
        chez_dofus3 = vue._get_monster_core_by_id('dofus3')
        chez_retro = vue._get_monster_core_by_id('retro')
        choisi = None
        for monster_id, entry in chez_dofus3.items():
            if monster_id not in chez_retro and (entry.get('names') or {}).get('en'):
                choisi = monster_id
                break
        if choisi is None:
            self.skipTest('every dofus3 monster also exists in retro')
        reponse = self.client.get('/retro/encyclopedia/monster/%d-x/' % choisi)
        self.assertEqual(404, reponse.status_code)
        liens = _liens(reponse.content.decode('utf-8'))
        self.assertTrue(any('/encyclopedia/monster/%d-' % choisi in l
                            for l in liens), liens)


class AnIdThatNamesTwoThingsLinksNothingBlindlyTests(SimpleTestCase):

    def test_agreeing_candidates_are_all_kept(self):
        candidats = [('dofus3', 'Gelano', {'label': 'Dofus 3'}),
                     ('touch', 'Gelano', {'label': 'Touch'})]
        self.assertEqual(2, len(vue._agreeing_candidates(candidats, 'x')))

    def test_disagreeing_candidates_are_settled_by_the_slug(self):
        candidats = [('dofus3', 'Cawwot Set', {'label': 'Dofus 3'}),
                     ('retro', 'Wabbit Set', {'label': 'Retro'})]
        gardes = vue._agreeing_candidates(candidats, 'wabbit-set')
        self.assertEqual(['Retro'], [c[2]['label'] for c in gardes])

    def test_disagreeing_candidates_with_no_slug_link_nobody(self):
        candidats = [('dofus3', 'Cawwot Set', {'label': 'Dofus 3'}),
                     ('retro', 'Wabbit Set', {'label': 'Retro'})]
        self.assertEqual([], vue._agreeing_candidates(candidats, ''))
        self.assertEqual([], vue._agreeing_candidates(candidats, '12'))


class TheLabelExistsInEveryLanguageTests(SimpleTestCase):

    def test_five_languages_carry_the_label(self):
        from django.utils.translation import override
        vus = {}
        for langue in ('en', 'fr', 'es', 'pt', 'de'):
            with override(langue):
                vus[langue] = vue._ui_text().get('missing_available_in')
        self.assertTrue(all(vus.values()), vus)
        self.assertEqual(5, len(set(vus.values())),
                         'two languages share the same label: %s' % vus)
