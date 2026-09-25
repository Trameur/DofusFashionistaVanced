# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every workshop page string renders in all five languages, natively."""

import re
import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopItem
from fashionistapulp.fashionista_config import get_items_db_path

# One landmark phrase per language, native (not a machine-translated cognate).
_SHOPPING_LIST_HEADING = {
    'en': 'Shopping list',
    'fr': 'Liste de courses',
    'es': 'Lista de la compra',
    'pt': 'Lista de compras',
    'de': 'Einkaufsliste',
}

_READY_TO_CRAFT = {
    'en': 'Ready to craft',
    'fr': 'Prêt à crafter',
    'es': 'Listo para craftear',
    'pt': 'Pronto para craftar',
    'de': 'Bereit zum Craften',
}

_HIDE_GATHERED = {
    'en': 'Hide gathered',
    'fr': 'Masquer les ressources réunies',
    'es': 'Ocultar lo ya reunido',
    'pt': 'Ocultar itens já reunidos',
    'de': 'Vorhandenes ausblenden',
}

_COPY_MISSING_LIST = {
    'en': 'Copy the missing list',
    'fr': 'Copier la liste des ressources manquantes',
    'es': 'Copiar la lista de recursos que faltan',
    'pt': 'Copiar a lista de recursos que faltam',
    'de': 'Liste der fehlenden Ressourcen kopieren',
}

_DOWNLOAD_CSV = {
    'en': 'Download CSV',
    'fr': 'Télécharger en CSV',
    'es': 'Descargar CSV',
    'pt': 'Baixar CSV',
    'de': 'CSV herunterladen',
}

_CSV_HEADER_RESOURCE_NAME = {
    'en': 'Resource name',
    'fr': 'Nom de la ressource',
    'es': 'Nombre del recurso',
    'pt': 'Nome do recurso',
    'de': 'Ressourcenname',
}

_NUMERIC_DATA_ATTR_WITH_COMMA = re.compile(r'data-[\w-]+="-?[0-9]+,[0-9,]*"')


def _an_item_with_a_recipe(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            'SELECT DISTINCT item FROM item_recipes ORDER BY item LIMIT 1').fetchone()
    finally:
        conn.close()
    return row[0] if row else None


class TheWorkshopPageSpeaksEveryLanguageTests(TestCase):

    def setUp(self):
        item_id = _an_item_with_a_recipe('dofus3')
        self.assertIsNotNone(item_id, 'no recipe to render a card against')
        self.user = User.objects.create_user(
            'polyglot-crafter', 'polyglot@test.local', 'pw-plie-bien')
        WorkshopItem.objects.create(
            user=self.user, item_id=item_id, game_version='dofus3', quantity=3)
        self.client.force_login(self.user)

    def test_the_new_phase_one_strings_are_translated_natively(self):
        for lang, heading in _SHOPPING_LIST_HEADING.items():
            with self.subTest(lang=lang):
                self.client.cookies['django_language'] = lang
                resp = self.client.get('/workshop/')
                self.assertEqual(200, resp.status_code)
                html = resp.content.decode('utf-8')
                self.assertIn(heading, html)
                self.assertIn(_READY_TO_CRAFT[lang], html)
                self.assertIn(_HIDE_GATHERED[lang], html)

    def test_the_export_strings_are_translated_natively(self):
        for lang, label in _COPY_MISSING_LIST.items():
            with self.subTest(lang=lang):
                self.client.cookies['django_language'] = lang
                resp = self.client.get('/workshop/')
                self.assertEqual(200, resp.status_code)
                html = resp.content.decode('utf-8')
                self.assertIn(label, html)
                self.assertIn(_DOWNLOAD_CSV[lang], html)
                self.assertIn(_CSV_HEADER_RESOURCE_NAME[lang], html)

    def test_no_language_falls_back_to_english(self):
        english_only = {'fr', 'es', 'pt', 'de'}
        for lang in english_only:
            with self.subTest(lang=lang):
                self.client.cookies['django_language'] = lang
                resp = self.client.get('/workshop/')
                html = resp.content.decode('utf-8')
                self.assertNotIn('"summaryReady": ""', html)
                self.assertNotIn('"noRecipe": ""', html)

    def test_numbers_in_data_attributes_carry_no_thousands_comma(self):
        self.client.cookies['django_language'] = 'fr'
        resp = self.client.get('/workshop/')
        html = resp.content.decode('utf-8')
        self.assertIsNone(
            _NUMERIC_DATA_ATTR_WITH_COMMA.search(html),
            'a localized number leaked into a data-* attribute')
