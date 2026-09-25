# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every workshop add, craft and filter string ships a real translation, and the page
never leaks a localized number into a data-* attribute JS has to parse."""

import re
import sqlite3

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.models import UserAlias, WorkshopItem
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

LANGUAGES = ('fr', 'es', 'pt', 'de')

NEW_MSGIDS = [
    'Ready',
    'In progress',
    'Status',
    'Sort by',
    'Recently added',
    'Add an item',
    'Type an item name (example: Gelano)',
    'Filter by status',
    'Reset owned counts',
    'Reset every owned count to 0 for this version?',
    'All to 0',
    'All to max',
    'Craft 1',
    'No item found.',
    'Crafted.',
    'Restored.',
    'Undo',
    'Add to workshop',
    'to add this item to the workshop.',
    'Add the set to my workshop',
    'to add this set to the workshop.',
    'For items already in the workshop:',
    "Add only what's missing",
    'Add one more of each',
]

NEW_FORMAT_MSGIDS = [
    ('Set every resource on %(name)s to 0', {'name': 'Wool'}),
    ('Set every resource on %(name)s to its needed amount', {'name': 'Wool'}),
    ('Craft %(name)s', {'name': 'Amulet'}),
]


class NewWorkshopStringsAreTranslatedTests(SimpleTestCase):

    def test_every_new_string_has_a_real_translation(self):
        untranslated = []
        for msgid in NEW_MSGIDS:
            for lang in LANGUAGES:
                with translation.override(lang):
                    translated = gettext(msgid)
                if translated == msgid:
                    untranslated.append((msgid, lang))
        self.assertEqual([], untranslated)

    def test_every_new_format_string_has_a_real_translation(self):
        untranslated = []
        for msgid, params in NEW_FORMAT_MSGIDS:
            for lang in LANGUAGES:
                with translation.override(lang):
                    translated = gettext(msgid) % params
                if translated == msgid % params:
                    untranslated.append((msgid, lang))
        self.assertEqual([], untranslated)

    def test_english_keeps_the_source_text(self):
        for msgid in NEW_MSGIDS:
            with translation.override('en'):
                self.assertEqual(msgid, gettext(msgid))


def _an_item_with_a_recipe(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            'SELECT DISTINCT item FROM item_recipes ORDER BY item LIMIT 1').fetchone()
    finally:
        conn.close()
    return row[0] if row else None


class WorkshopPageRendersTranslatedStringsTests(TestCase):

    def setUp(self):
        item_id = _an_item_with_a_recipe('dofus3')
        self.assertIsNotNone(item_id, 'no recipe item to test against in dofus3')
        self.user = User.objects.create_user(
            'workshopi18n-1', 'workshopi18n-1@test.local', 'pw-7712qz')
        WorkshopItem.objects.create(
            user=self.user, item_id=item_id, game_version='dofus3', quantity=1)
        self.client.force_login(self.user)

    def test_the_new_toolbar_strings_are_translated_away_from_english(self):
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                self.client.cookies['django_language'] = lang
                resp = self.client.get('/workshop/', follow=True)
                self.assertEqual(200, resp.status_code)
                body = resp.content.decode('utf-8')
                self.assertIn('id="ws-reset-stock"', body)
                self.assertNotIn('>Reset owned counts<', body)
                self.assertIn('id="ws-search-input"', body)
                self.assertNotIn('Type an item name (example: Gelano)', body)

    def test_data_level_and_data_order_carry_no_locale_grouping(self):
        self.client.cookies['django_language'] = 'fr'
        resp = self.client.get('/workshop/', follow=True)
        body = resp.content.decode('utf-8')
        levels = re.findall(r'data-level="([^"]*)"', body)
        orders = re.findall(r'data-order="([^"]*)"', body)
        self.assertTrue(levels)
        self.assertTrue(orders)
        for value in levels + orders:
            with self.subTest(value=value):
                self.assertNotIn(',', value)
                self.assertNotIn(' ', value)
                self.assertTrue(value.lstrip('-').isdigit())


class EncyclopediaItemPageRendersTranslatedStringsTests(TestCase):

    def setUp(self):
        item_id = _an_item_with_a_recipe('dofus3')
        self.assertIsNotNone(item_id, 'no recipe item to test against in dofus3')
        structure = get_structure('dofus3')
        self.item = structure.get_item_by_id(item_id)
        self.assertIsNotNone(self.item)
        self.user = User.objects.create_user(
            'workshopi18n-2', 'workshopi18n-2@test.local', 'pw-3391ma')

    def test_the_add_button_is_translated_away_from_english(self):
        from django.utils import translation

        from chardata.official_site import get_item_link
        structure = get_structure('dofus3')
        self.client.force_login(self.user)
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                # A signed-in reader's saved profile language wins over the
                # slug and the cookie, so it has to be set explicitly here.
                UserAlias.objects.update_or_create(
                    user=self.user, defaults={'language': lang})
                with translation.override(lang):
                    localized_name = structure.get_item_name_in_language(
                        self.item, lang)
                    url = get_item_link(self.item.ankama_type,
                                        self.item.ankama_id, localized_name,
                                        'dofus3')
                self.client.cookies['django_language'] = lang
                resp = self.client.get(url, follow=True)
                self.assertEqual(200, resp.status_code)
                body = resp.content.decode('utf-8')
                self.assertIn('id="enc-workshop-add-form"', body)
                self.assertNotIn('>Add to workshop<', body)
