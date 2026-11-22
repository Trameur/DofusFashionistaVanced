# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A stored resource the build's version does not know survives a save of the forbid page."""
import json
import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata import resource_ban
from chardata.char_blobs import read_char_blob
from chardata.models import Char
from fashionistapulp.structure import set_current_game_version

CRIMSON_PEBBLE = '12737:resources'
ANOTHER_RESOURCE = '757:resources'
UNKNOWN_HERE = '999999999:resources'


class AnUnknownStoredResourceTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('keepban', 'kb@test.local', 'pw-keep-ban-1')
        self.char = Char.objects.create(
            name='Kept', char_name='kept', char_class='Iop', char_build='build',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=pickle.dumps({resource_ban.OPTION_KEY: [CRIMSON_PEBBLE, UNKNOWN_HERE]}),
            inclusions=pickle.dumps({}), exclusions=pickle.dumps([]), owner=owner,
            link_shared=False, game_version='dofus3')
        self.client.force_login(owner)

    def save(self, resources):
        response = self.client.post('/exclusionspost/%d/' % self.char.pk,
                                    {'exclusions': '[]', 'resources': json.dumps(resources)})
        self.assertEqual(200, response.status_code)
        return response

    def stored_options(self):
        return Char.objects.get(pk=self.char.pk).options

    def stored_keys(self):
        options = read_char_blob(self.stored_options(), {}, 'options')
        return options.get(resource_ban.OPTION_KEY)

    def test_the_page_shows_only_the_key_the_version_knows(self):
        self.assertEqual([CRIMSON_PEBBLE], resource_ban.banned_resource_keys(self.char))

    def test_saving_what_the_page_shows_writes_nothing(self):
        before = bytes(self.stored_options())
        self.save([CRIMSON_PEBBLE])
        self.assertEqual(before, bytes(self.stored_options()))

    def test_an_added_resource_keeps_the_unknown_key(self):
        self.save([CRIMSON_PEBBLE, ANOTHER_RESOURCE])
        self.assertEqual(sorted([CRIMSON_PEBBLE, ANOTHER_RESOURCE, UNKNOWN_HERE]),
                         self.stored_keys())

    def test_lifting_every_shown_resource_keeps_the_unknown_key_and_bans_nothing(self):
        self.save([])
        self.assertEqual([UNKNOWN_HERE], self.stored_keys())
        self.assertEqual([], resource_ban.banned_resource_keys(
            Char.objects.get(pk=self.char.pk)))

    def test_the_answer_lists_only_the_key_the_version_knows(self):
        state = json.loads(self.save([CRIMSON_PEBBLE]).content)
        self.assertEqual([CRIMSON_PEBBLE], [row['key'] for row in state['resources']])
