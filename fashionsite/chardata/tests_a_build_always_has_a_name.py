# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un build a toujours un nom qui se lit.

Mesure du 11 septembre 2026 sur la copie de production: **404 des 1980 builds
partages qui ont une solution n'ont pas de nom lisible**, un sur cinq, et
39 784 des 152 862 builds au total. La cause est dans la page de creation: le
champ <<Nom du projet>> est rempli tout seul avec le nom du personnage suivi
du niveau, le nom du personnage n'est pas obligatoire, et le champ rempli
d'une espace et d'un nombre satisfait le `required` du formulaire.

Depuis que les builds neufs sont publics des qu'ils portent un stuff, cette
part n'est plus un detail de la liste personnelle: c'est une carte de galerie
sur cinq qui n'annonce rien.

La base n'est pas reecrite ([[no-retrofit-user-builds]]): l'affichage se
rattrape, et la creation cesse d'en fabriquer.
"""

import pickle

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata.build_name import (cleaned_at_creation, display_name,
                                 is_placeholder)
from chardata.models import Char


class WhatCountsAsNoNameAtAllTests(SimpleTestCase):
    """La regle est etroite exprès: elle ne prend que ce que la page a
    fabrique toute seule, jamais ce que quelqu'un a tape."""

    #: Les formes vraiment rencontrees, avec leur compte du 11 septembre 2026
    #: parmi les builds partages qui ont une solution.
    FABRIQUES = (' 199', ' 160', ' 60', ' 80', ' 150', 'NoName', '', '   ',
                 ' 199 copy', ' 80 copy copy')

    #: Des noms que quelqu'un a tapes, lus dans la meme colonne le meme jour.
    TAPES = ('200 sadi 200', '117', '2', ' 110cha int handmade',
             ' Travitas 130', ' 150 pvp', ' 1999', ' sin', 'Iop 200')

    def test_what_the_page_wrote_alone_is_recognised(self):
        for nom in self.FABRIQUES:
            with self.subTest(nom=nom):
                self.assertTrue(is_placeholder(nom))

    def test_what_a_player_typed_is_left_alone(self):
        """Y compris <<espace 1999>>: le niveau tient sur trois chiffres, donc
        quatre chiffres viennent forcement de quelqu'un."""
        for nom in self.TAPES:
            with self.subTest(nom=nom):
                self.assertFalse(is_placeholder(nom))

    def test_the_fallback_is_two_facts_the_build_carries(self):
        """Pas de phrase inventee: la classe, traduite, et le niveau."""
        from django.utils.translation import override
        with override('en'):
            self.assertEqual('Iop 199',
                             display_name(_Faux(' 199', 'Iop', 199)))
        with override('fr'):
            self.assertEqual('Crâ 60', display_name(_Faux('NoName', 'Cra', 60)))

    def test_a_real_name_is_never_replaced(self):
        self.assertEqual('200 sadi 200',
                         display_name(_Faux('200 sadi 200', 'Sadida', 200)))

    def test_creation_stops_writing_them(self):
        from django.utils.translation import override
        with override('en'):
            self.assertEqual('Iop 199', cleaned_at_creation(' 199', 'Iop', 199))
            self.assertEqual('Iop 199', cleaned_at_creation('NoName', 'Iop', 199))
            self.assertEqual('Mon build',
                             cleaned_at_creation('Mon build', 'Iop', 199))


class _Faux(object):
    def __init__(self, name, char_class, level):
        self.name = name
        self.char_class = char_class
        self.level = level


class TheGalleryNeverShowsANamelessCardTests(TestCase):

    def _build(self, nom, char_class='Iop', level=199):
        """Par la vraie porte: la galerie ecarte un build dont la solution
        stockee n'en est pas une, donc un objet fabrique a la main n'y
        apparait pas et ne prouverait rien."""
        from fashionistapulp.structure import (get_structure,
                                               set_current_game_version)
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        item = next(i for i in structure.types[200]['Hat']
                    if not i.removed and i.ankama_id)
        self.client.post('/import/text/', {
            'text': structure.get_item_name_in_language(item, 'en'),
            'confirm': '1', 'char_class': char_class, 'level': str(level)})
        char = Char.objects.order_by('-id').first()
        char.name = nom
        char.char_name = ''
        char.link_shared = True
        char.save()
        return char

    def test_a_card_whose_build_was_never_named_says_the_class_and_level(self):
        self._build(' 199')
        page = self.client.get('/sharedbuilds/', HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertIn('Iop 199', page)
        self.assertNotIn('<h3 class="build-title"> 199</h3>', page)

    def test_the_same_card_speaks_french(self):
        self._build('NoName', char_class='Cra', level=60)
        page = self.client.get('/sharedbuilds/', HTTP_ACCEPT_LANGUAGE='fr'
                               ).content.decode('utf-8')
        self.assertIn('Crâ 60', page)
        self.assertNotIn('NoName', page)

    def test_a_named_build_keeps_its_name_on_the_card(self):
        self._build('Mon Iop terre')
        page = self.client.get('/sharedbuilds/', HTTP_ACCEPT_LANGUAGE='en'
                               ).content.decode('utf-8')
        self.assertIn('Mon Iop terre', page)

    def test_the_public_api_never_hands_out_an_empty_name(self):
        """Un consommateur de cette API ecrit ce champ tel quel."""
        from chardata.encoded_char_id import encode_char_id
        char = self._build(' 199')
        reponse = self.client.get('/api/v1/shared-builds/%s/'
                                  % encode_char_id(char.id),
                                  HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, reponse.status_code)
        self.assertEqual('Iop 199', reponse.json()['name'])

    def test_the_api_listing_names_them_too(self):
        self._build(' 199')
        reponse = self.client.get('/api/v1/shared-builds/',
                                  HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, reponse.status_code)
        charge = reponse.json()
        noms = [b.get('name') for b in (charge.get('builds')
                                        or charge.get('results') or [])]
        self.assertIn('Iop 199', noms)


class TheCreationPageProposesSomethingReadableTests(TestCase):

    def test_a_project_created_with_no_name_gets_one(self):
        self.client.force_login(User.objects.create_user('a', password='x'))
        self.client.post('/createproject/', {
            'project': ' 199', 'charname': '', 'level': '199',
            'class': 'Iop', 'byhand': 'x'}, HTTP_ACCEPT_LANGUAGE='en')
        char = Char.objects.order_by('-id').first()
        self.assertEqual('Iop 199', char.name)

    def test_a_project_the_author_named_keeps_its_name(self):
        self.client.force_login(User.objects.create_user('b', password='x'))
        self.client.post('/createproject/', {
            'project': 'Mon build', 'charname': 'Moi', 'level': '199',
            'class': 'Iop', 'byhand': 'x'})
        self.assertEqual('Mon build', Char.objects.order_by('-id').first().name)

    def test_the_page_offers_the_class_when_the_character_has_no_name(self):
        """Le script de la page, lu dans le gabarit: sans nom de personnage
        il prend la classe choisie, donc le champ ne vaut plus une espace et
        un nombre."""
        page = self.client.get('/setup/').content.decode('utf-8')
        self.assertIn('proposedProjectName', page)
        self.assertIn('select-char-class option:selected', page)
