# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La page d'un build partage n'offre aucune porte qui refuse le visiteur.

Trouve le 12 septembre 2026 en parcourant le site depuis l'accueil et en
suivant ses propres liens: sur les 28 liens internes d'une page de build
partage, **27 repondaient et un repondait 403**. C'etait l'en-tete de colonne
<<Base>> du tableau des stats, qui pointait vers la page de reglages du
build. Cette page n'appartient qu'a son auteur, donc tout visiteur qui
cliquait le mot <<Base>> recevait un <<403 Interdit>>.

Le menu du haut appliquait deja la bonne regle (`{% if ... and not is_guest %}`)
et cachait ses liens d'auteur. Cette colonne l'avait ratee, et c'est la seule:
verifie sur les deux autres endroits du site qui pointent vers cette page.

La colonne dit maintenant ce qu'elle contient, dans les cinq langues, ce que
ni le visiteur ni l'auteur n'avaient: ce que le personnage a sans equipement,
c'est-a-dire ses parchemins et les points qu'il a depenses. Lu dans
`ModelResult.get_stats_base`, qui additionne les caracteristiques propres du
personnage et les points repartis, sans rien de l'equipement.
"""

import re

from django.test import TestCase

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

#: La cellule d'en-tete de la colonne, avec ce qu'elle contient.
CELLULE = re.compile(
    r'<td class="solution-stat-summary-base-value-header[^>]*>(.{0,300}?)</td>',
    re.S)

INTERNE = re.compile(r'href="(/[^"#?]*)"')


class _BuildPartage(TestCase):

    def _build(self, partage=True):
        from chardata.models import Char
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        noms = []
        for type_name in ('Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            item = next(i for i in structure.types[200][type_name]
                        if not i.removed and i.ankama_id)
            noms.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {
            'text': '\n'.join(noms), 'confirm': '1',
            'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        if partage:
            char.link_shared = True
            char.save()
        return char

    def _adresse_partagee(self, char):
        from chardata.encoded_char_id import encode_char_id
        return '/s/%s/%s/' % (char.char_name or 'shared',
                              encode_char_id(char.id))


class NoLinkRefusesTheVisitorTests(_BuildPartage):

    def test_every_link_of_a_shared_build_answers_the_visitor(self):
        """La garde generale: c'est elle qui prendra la prochaine porte
        d'auteur laissee sur une page publique, pas seulement celle-ci."""
        char = self._build()
        page = self.client.get(self._adresse_partagee(char),
                               follow=True).content.decode('utf-8')
        liens = sorted({lien for lien in INTERNE.findall(page)
                        if not lien.startswith(('/static/', '/media/'))})
        self.assertTrue(liens, 'la page ne porte aucun lien interne')
        refuses = []
        for lien in liens:
            code = self.client.get(lien, follow=True).status_code
            if code >= 400:
                refuses.append((lien, code))
        self.assertEqual([], refuses)

    def test_the_base_header_is_plain_text_for_a_visitor(self):
        char = self._build()
        page = self.client.get(self._adresse_partagee(char),
                               follow=True).content.decode('utf-8')
        cellule = CELLULE.search(page)
        self.assertIsNotNone(cellule, 'la colonne Base a disparu de la page')
        self.assertNotIn('<a ', cellule.group(0))
        self.assertNotIn('/setup/', cellule.group(0))


class TheAuthorKeepsTheirDoorTests(_BuildPartage):

    def test_the_owner_still_reaches_their_base_characteristics(self):
        """Retirer le lien a tout le monde aurait <<corrige>> le 403 en
        enlevant un chemin utile a celui qui en a le droit."""
        from django.contrib.auth.models import User
        auteur = User.objects.create_user('auteur', 'a@x.test', 'pw')
        char = self._build(partage=False)
        char.owner = auteur
        char.save()
        self.client.force_login(auteur)
        page = self.client.get('/solution/%d/' % char.id,
                               follow=True).content.decode('utf-8')
        cellule = CELLULE.search(page)
        self.assertIsNotNone(cellule)
        self.assertIn('/setup/%d/' % char.id, cellule.group(0))
        self.assertEqual(200, self.client.get('/setup/%d/' % char.id).status_code)


class TheColumnSaysWhatItHoldsTests(_BuildPartage):

    def test_it_answers_in_the_five_languages(self):
        char = self._build()
        adresse = self._adresse_partagee(char)
        vus = {}
        for langue in LANGUES:
            page = self.client.get(adresse, HTTP_ACCEPT_LANGUAGE=langue,
                                   follow=True).content.decode('utf-8')
            cellule = CELLULE.search(page)
            self.assertIsNotNone(cellule, langue)
            titre = re.search(r'title="([^"]+)"', cellule.group(0))
            self.assertIsNotNone(titre, langue)
            vus[langue] = titre.group(1)
        for langue, texte in vus.items():
            with self.subTest(langue=langue):
                self.assertTrue(texte)
                if langue != 'en':
                    self.assertNotEqual(vus['en'], texte)

    def test_the_french_reader_is_told_about_scrolls_and_points(self):
        char = self._build()
        page = self.client.get(self._adresse_partagee(char),
                               HTTP_ACCEPT_LANGUAGE='fr',
                               follow=True).content.decode('utf-8')
        cellule = CELLULE.search(page).group(0)
        self.assertIn('parchemins', cellule)
        self.assertIn('points', cellule)
