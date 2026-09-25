# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The sub-recipe tag's new strings ship a real translation, and its lazy
endpoint keeps the page's own language prefix, like the sources endpoint."""

import sqlite3

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata.models import WorkshopItem
from fashionistapulp.fashionista_config import get_items_db_path

LANGUAGES = ('fr', 'es', 'pt', 'de')

NEW_MSGIDS = [
    'Add as its own card',
    '{name} added as its own card.',
    'No sub-recipe found.',
    'Show the recipe for {name}',
]


class NewSubrecipeStringsAreTranslatedTests(SimpleTestCase):

    def test_every_new_string_has_a_real_translation(self):
        untranslated = []
        for msgid in NEW_MSGIDS:
            for lang in LANGUAGES:
                with translation.override(lang):
                    translated = gettext(msgid)
                if translated == msgid:
                    untranslated.append((msgid, lang))
        self.assertEqual([], untranslated)

    def test_english_keeps_the_source_text(self):
        for msgid in NEW_MSGIDS:
            with translation.override('en'):
                self.assertEqual(msgid, gettext(msgid))


def _a_crafted_item_id(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        return conn.execute('SELECT item FROM item_recipes LIMIT 1').fetchone()[0]
    finally:
        conn.close()


class TheSubrecipeUrlKeepsTheLanguagePrefixTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'subrecipe-i18n', 'subrecipe-i18n@test.local', 'pw-6631ol')
        self.client.force_login(self.user)
        WorkshopItem.objects.create(
            user=self.user, item_id=_a_crafted_item_id('dofus3'),
            game_version='dofus3', quantity=1)

    def test_a_german_page_asks_the_german_endpoint(self):
        page = self.client.get('/de/workshop/').content.decode('utf-8')
        self.assertIn('/de/workshop/subrecipe/', page)

    def test_an_unprefixed_page_asks_the_unprefixed_endpoint(self):
        page = self.client.get('/workshop/').content.decode('utf-8')
        self.assertIn('"/workshop/subrecipe/"', page)
