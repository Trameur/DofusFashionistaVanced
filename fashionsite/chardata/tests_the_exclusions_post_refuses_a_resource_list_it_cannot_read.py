# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The exclusions post answers 400 to a resource list it cannot read, keeps the ban when the field is absent, and saves nothing when nothing changed."""
import json

from django.contrib.auth.models import User
from django.test import TestCase

from chardata import resource_ban
from chardata.models import Char
from fashionistapulp.structure import set_current_game_version

CRIMSON_PEBBLE = '12737:resources'
ANOTHER_RESOURCE = '757:resources'
NOT_A_RESOURCE = '999999999:resources'
ABSENT = object()


class AResourceListTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('refban', 'rb@test.local', 'pw-ref-ban-1')
        self.char = Char.objects.create(
            name='Refuse', char_name='refuse', char_class='Iop', char_build='build',
            level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
            options=b'', inclusions=b'', exclusions=b'', owner=owner,
            link_shared=False, game_version='dofus3')
        self.client.force_login(owner)

    def post(self, resources=ABSENT):
        payload = {'exclusions': '[]'}
        if resources is not ABSENT:
            payload['resources'] = resources
        return self.client.post('/exclusionspost/%d/' % self.char.pk, payload)

    def stored(self):
        return Char.objects.get(pk=self.char.pk)

    def banned(self):
        return resource_ban.banned_resource_keys(self.stored())

    def test_a_list_it_cannot_read_is_a_bad_request(self):
        too_many = json.dumps(['%d:resources' % number
                               for number in range(resource_ban.MAX_BANNED_RESOURCES + 1)])
        for raw in ('not json', '{"a": 1}', '5', 'null', '"12737:resources"', '[1]',
                    '[null]', '[["12737:resources"]]', '["12737"]', '["12737:Resources"]',
                    '["x:resources"]', '["1234567890:resources"]', too_many):
            with self.subTest(resources=raw[:40]):
                self.assertEqual(400, self.post(raw).status_code)
        self.assertEqual([], self.banned())

    def test_a_list_nested_beyond_the_parser_is_a_bad_request_in_both_fields(self):
        deep = '[' * 100000
        self.assertEqual(400, self.post(deep).status_code)
        response = self.client.post('/exclusionspost/%d/' % self.char.pk,
                                    {'exclusions': deep})
        self.assertEqual(400, response.status_code)

    def test_a_refused_list_saves_nothing_else(self):
        before = self.stored().modified_time
        self.assertEqual(400, self.post('not json').status_code)
        self.assertEqual(before, self.stored().modified_time)

    def test_a_missing_field_leaves_the_ban_untouched(self):
        self.assertEqual(200, self.post(json.dumps([CRIMSON_PEBBLE])).status_code)
        self.assertEqual(200, self.post().status_code)
        self.assertEqual([CRIMSON_PEBBLE], self.banned())

    def test_a_key_the_version_does_not_know_is_dropped_and_the_rest_is_saved(self):
        response = self.post(json.dumps([NOT_A_RESOURCE, CRIMSON_PEBBLE]))
        self.assertEqual(200, response.status_code)
        self.assertEqual([CRIMSON_PEBBLE], self.banned())

    def test_the_list_is_stored_sorted_and_without_repeats(self):
        self.post(json.dumps([ANOTHER_RESOURCE, CRIMSON_PEBBLE, ANOTHER_RESOURCE]))
        self.assertEqual(sorted([ANOTHER_RESOURCE, CRIMSON_PEBBLE]), self.banned())

    def test_an_unchanged_post_saves_nothing(self):
        self.assertEqual(200, self.post(json.dumps([CRIMSON_PEBBLE])).status_code)
        stored = self.stored()

        self.assertEqual(200, self.post(json.dumps([CRIMSON_PEBBLE])).status_code)

        again = self.stored()
        self.assertEqual(stored.modified_time, again.modified_time)
        self.assertEqual(stored.options, again.options)
        self.assertEqual(stored.exclusions, again.exclusions)

    def test_lifting_a_ban_that_was_never_set_saves_nothing(self):
        self.assertEqual(200, self.post().status_code)
        before = self.stored().modified_time
        self.assertEqual(200, self.post('[]').status_code)
        self.assertEqual(before, self.stored().modified_time)
