# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A shared build page offers a visitor no link that answers 403."""

import re

from django.test import TestCase

LANGUES = ('en', 'fr', 'es', 'pt', 'de')

# The header cell of the column, with what it holds
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
        char = self._build()
        page = self.client.get(self._adresse_partagee(char),
                               follow=True).content.decode('utf-8')
        liens = sorted({lien for lien in INTERNE.findall(page)
                        if not lien.startswith(('/static/', '/media/'))})
        self.assertTrue(liens, 'the page carries no internal link')
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
        self.assertIsNotNone(cellule, 'the Base column disappeared from the page')
        self.assertNotIn('<a ', cellule.group(0))
        self.assertNotIn('/setup/', cellule.group(0))


class TheAuthorKeepsTheirDoorTests(_BuildPartage):

    def test_the_owner_still_reaches_their_base_characteristics(self):
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
