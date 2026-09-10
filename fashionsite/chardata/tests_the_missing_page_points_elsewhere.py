# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La page <<indisponible dans cette version>> nomme les versions qui l'ont.

Mesure du 10 septembre 2026: cette page est 49 % de ce que l'essaim de
robots frappe, et un lecteur qui y arrive depuis un moteur de recherche n'y
trouvait qu'une chose, le carrefour de la version qui n'a PAS l'objet. Les
versions qui l'ont sont a une recherche de distance, la meme que celle du
selecteur de version d'une vraie fiche.

Les cas sont trouves dans les donnees, jamais ecrits en dur: un identifiant
choisi a la main est vrai le jour ou on l'ecrit et faux a la mise a jour
suivante, et le test dirait alors <<rien a signaler>> sur une page qu'il n'a
plus regardee.
"""

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
        """L'adresse telle que le site la construit, avec le VRAI slug.

        Un slug invente comme <<x>> n'est pas neutre: Retro a un objet qui
        s'appelle X (9120), et la vue rattrape un id inconnu par le slug,
        donc `14063-x` rendait la fiche de X avec son canonique, jamais la
        page d'absence.
        """
        from chardata.official_site import get_item_link
        return get_item_link(ankama_type, ankama_id, nom, game_version=version)

    def _item_absent_de(self, version_absente, version_presente):
        """Un id porte par `version_presente` et par aucune fiche de
        `version_absente`."""
        la = vue._version_item_keys(version_presente)
        # Absent au sens de la VUE, et de personne d'autre: elle resout un id
        # par des chemins que ni la table `items` ni la structure ne
        # reproduisent (deux tentatives ici ont rendu une vraie fiche Retro,
        # 9120 <<Chapeau Shika>>, pour un id que les deux disaient absent).
        # La seule mesure fiable est de lui demander, et de garder le premier
        # id qu'elle refuse. Borne a quarante essais pour rester rapide.
        # Des ids les plus hauts vers les plus bas: les bas sont les objets de
        # depart, que Retro porte sous le meme id (le plan l'a mesure, un
        # build Retro se resout entier sous dofus3 et touch), et les quarante
        # premiers dans l'ordre du dictionnaire rendaient tous une fiche.
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
        """Un lien sous <<il existe dans>> qui rend 404 serait la faute que
        cette page existe pour reparer."""
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
    """Les identifiants ne sont pas une identite partagee de part et d'autre
    de la coupure Retro/moderne. Sans nom dans la version courante pour
    trancher, la regle est: tous d'accord, ou le slug de l'adresse decide, ou
    personne."""

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
