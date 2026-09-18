# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The workshop names an item type in the reader's language."""

import io
import os
import re

from django.test import SimpleTestCase, TestCase

from chardata.workshop_view import _localized_type
from fashionistapulp.structure import get_structure

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
LANGUES = ('en', 'fr', 'es', 'pt', 'de')

_TYPES_TRADUITS = {
    'Amulet': {'fr': 'Amulette', 'es': 'Amuleto', 'pt': 'Amuleto',
               'de': 'Amulett'},
    'Weapon': {'fr': 'Arme', 'es': 'Arma', 'pt': 'Arma', 'de': 'Waffe'},
    'Boots': {'fr': 'Bottes', 'de': 'Stiefel'},
    'Ring': {'fr': 'Anneau', 'es': 'Anillo', 'pt': 'Anel'},
    'Hat': {'fr': 'Coiffe', 'de': 'Hut'},
    'Cloak': {'fr': 'Cape', 'de': 'Mantel'},
    'Belt': {'fr': 'Ceinture', 'de': 'Gürtel'},
    'Shield': {'fr': 'Bouclier', 'de': 'Schild'},
    'Pet': {'fr': 'Familier', 'de': 'Haustier'},
}

_IDENTIQUES = {
    'Dofus': "le mot du jeu, le meme dans les cinq langues",
    ('Ring', 'de'): "Ring est le mot allemand pour un anneau",
}

_VUES_QUI_TRADUISAIENT = ('inventory_view.py', 'forgemagie_view.py',
                          'encyclopedia_view.py')


def _source(nom):
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), nom)
    with io.open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


class TheWorkshopTranslatesTheTypeTests(SimpleTestCase):

    def test_each_type_comes_out_in_the_readers_language(self):
        for type_name, attendus in _TYPES_TRADUITS.items():
            for langue, attendu in attendus.items():
                with self.subTest(type=type_name, langue=langue):
                    self.assertEqual(attendu,
                                     _localized_type(type_name, langue))

    def test_english_gets_the_canonical_word_back(self):
        for type_name in _TYPES_TRADUITS:
            with self.subTest(type=type_name):
                self.assertEqual(type_name, _localized_type(type_name, 'en'))

    def test_an_item_with_no_type_stays_empty(self):
        self.assertEqual('', _localized_type('', 'fr'))
        self.assertEqual('', _localized_type(None, 'de'))


class EveryTypeTheSiteCanShowIsCoveredTests(SimpleTestCase):

    def test_the_site_shows_no_type_the_guard_has_not_read(self):
        vus = set()
        for version in VERSIONS:
            structure = get_structure(version)
            for item in structure.get_available_items_list():
                nom = structure.get_type_name_by_id(item.type)
                if nom:
                    vus.add(nom)
        connus = set(_TYPES_TRADUITS) | {'Dofus'}
        self.assertEqual(
            set(), vus - connus,
            'these types can reach the workshop and nobody read them against '
            'the catalogue: %s' % sorted(vus - connus))

    def test_only_the_two_named_types_come_out_unchanged(self):
        inchanges = []
        for type_name in set(_TYPES_TRADUITS) | {'Dofus'}:
            for langue in ('fr', 'es', 'pt', 'de'):
                if _localized_type(type_name, langue) != type_name:
                    continue
                if type_name == 'Dofus' or (type_name, langue) in _IDENTIQUES:
                    continue
                inchanges.append((type_name, langue))
        self.assertEqual(
            [], inchanges,
            'these types come out in English with no reason recorded: %s'
            % inchanges)


class TheCanonicalNameStillFindsTheImageTests(SimpleTestCase):

    def test_the_image_url_is_built_from_the_canonical_type(self):
        source = _source('workshop_view.py')
        self.assertIn('get_image_url(type_name, item.name)', source)
        self.assertNotIn('get_image_url(_localized_type', source)

    def test_the_three_sister_pages_already_translated(self):
        for nom in _VUES_QUI_TRADUISAIENT:
            with self.subTest(vue=nom):
                self.assertIn('_localized_label(type_name', _source(nom))


class TheShippedPageCarriesTheTranslatedTypeTests(TestCase):

    def test_a_workshop_row_ships_the_readers_word(self):
        from django.contrib.auth.models import User
        from chardata.models import WorkshopItem
        structure = get_structure('dofus3')
        amulette = next(
            item for item in structure.get_available_items_list()
            if structure.get_type_name_by_id(item.type) == 'Amulet')
        user = User.objects.create_user('atelier', 'atelier@test.local',
                                        'pw-1234')
        WorkshopItem.objects.create(user=user, item_id=amulette.id,
                                    game_version='dofus3', quantity=1)
        self.client.force_login(user)
        self.client.cookies['django_language'] = 'fr'
        page = self.client.get('/workshop/', follow=True)
        self.assertEqual(200, page.status_code)
        corps = page.content.decode('utf-8')
        meta = re.search(r'workshop-row-meta[^>]*>([^<]*)<', corps)
        self.assertIsNotNone(meta, 'the page ships no workshop row')
        self.assertIn('Amulette', meta.group(1))
        self.assertNotIn('Amulet ', meta.group(1))


class TheViewActuallyAsksForTheTranslationTests(SimpleTestCase):

    def test_the_row_is_built_with_the_translated_type(self):
        source = _source('workshop_view.py')
        debut = source.index('def _items_for_user(')
        corps = source[debut:debut + 2600]
        self.assertIn("'type_name': _localized_type(type_name, language),",
                      corps)
        self.assertNotIn("'type_name': type_name,", corps)
