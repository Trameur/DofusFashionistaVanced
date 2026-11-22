# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The answer to saving the exclusions has the same shape as the state the exclusions page embeds."""
import json

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import Char
from fashionistapulp.structure import get_structure, set_current_game_version


class _AnExclusionsPage(TestCase):

    VERSION = 'dofus3'
    PREFIX = ''
    LEVEL = 200

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(self.VERSION)
        self.structure = get_structure(self.VERSION)
        self.owner = User.objects.create_user('exclshape', 'es@test.local', 'pw-excl-shape-1')
        self.char = Char.objects.create(
            name='Shape', char_name='shape', char_class='Iop', char_build='build',
            level=self.LEVEL, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'', owner=self.owner,
            link_shared=False, game_version=self.VERSION)
        self.client.force_login(self.owner)

    def _some_item_ids(self, count=3):
        type_id = self.structure.get_type_id_by_name('Boots')
        return [item.id for item in self.structure.get_concatenated_items_lists()
                if item.type == type_id and not item.removed][:count]

    def _save_then_open_the_page(self, item_ids):
        saved = self.client.post('%s/exclusionspost/%d/' % (self.PREFIX, self.char.pk),
                                 {'exclusions': json.dumps(item_ids)})
        self.assertEqual(200, saved.status_code, saved.content)
        page = self.client.get('%s/exclusions/%d/' % (self.PREFIX, self.char.pk))
        self.assertEqual(200, page.status_code)
        return json.loads(saved.content), json.loads(page.context['exclusions'])


class TheSaveAnswerIsThePageStateTests(_AnExclusionsPage):

    def test_the_answer_equals_the_list_the_page_embeds(self):
        answer, embedded = self._save_then_open_the_page(self._some_item_ids())

        self.assertTrue(embedded)
        self.assertEqual(embedded, answer)

    def test_each_entry_has_an_id_and_a_name(self):
        answer, _ = self._save_then_open_the_page(self._some_item_ids())

        self.assertTrue(answer)
        for entry in answer:
            with self.subTest(entry=entry):
                self.assertIsInstance(entry, dict)
                self.assertIn('id', entry)
                self.assertTrue(entry.get('name'))


class TheSaveAnswerOnATouchBuildTests(_AnExclusionsPage):

    VERSION = 'touch'
    PREFIX = '/touch'
    LEVEL = 60

    def test_the_answer_equals_the_list_the_page_embeds(self):
        answer, embedded = self._save_then_open_the_page(self._some_item_ids())

        self.assertTrue(embedded)
        self.assertEqual(embedded, answer)
        for entry in answer:
            self.assertTrue(entry['name'])


class TheSaveAnswerInFrenchTests(_AnExclusionsPage):

    PREFIX = '/fr'

    def test_the_names_are_the_french_names_the_page_embeds(self):
        answer, embedded = self._save_then_open_the_page(self._some_item_ids())

        self.assertEqual(embedded, answer)
        english = {item.id: item.name for item in self.structure.get_concatenated_items_lists()}
        french = [entry['name'] for entry in answer]
        self.assertTrue(all(french))
        self.assertNotEqual([english[entry['id']] for entry in answer], french)
