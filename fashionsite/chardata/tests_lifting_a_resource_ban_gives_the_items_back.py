# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Lifting a resource ban through the exclusions post gives every banned item back and leaves the per-item forbids alone."""
import json

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import resource_ban
from chardata.coaching_view import create_build
from chardata.fashion_action import _model_input
from chardata.lock_forbid import get_all_exclusions_ids
from chardata.min_stats import set_min_stats
from chardata.models import Char
from chardata.stats_weights import set_stats_weights
from fashionistapulp.structure import get_structure, set_current_game_version

CRIMSON_PEBBLE = '12737:resources'
LOCKER = 12623


class LiftingTheBanTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('liftban', 'lf@test.local', 'pw-lift-ban-1')
        self.request = RequestFactory().get('/')
        self.request.user = owner
        self.request.game_version = 'dofus3'
        self.char = create_build(self.request, 'Feca', 120, {'cha'}, 'dofus3')
        set_min_stats(self.char, {})
        set_stats_weights(self.char, {'vit': 1})
        self.client.force_login(owner)
        structure = get_structure('dofus3')
        boots = structure.get_type_id_by_name('Boots')
        self.boots = next(item.id for item in structure.get_concatenated_items_lists()
                          if item.type == boots and not item.removed)

    def post(self, resources):
        payload = {'exclusions': json.dumps([self.boots])}
        if resources is not None:
            payload['resources'] = json.dumps(resources)
        response = self.client.post('/exclusionspost/%d/' % self.char.pk, payload)
        self.assertEqual(200, response.status_code, response.content)
        self.char = Char.objects.get(pk=self.char.pk)
        return json.loads(response.content)

    def forbidden(self):
        return set(_model_input(self.request, self.char, {'vit': 1}).forbidden_equips)

    def test_the_ban_forbids_the_item_and_lifting_it_gives_it_back(self):
        self.post(None)
        before = self.forbidden()
        self.post([CRIMSON_PEBBLE])
        self.assertIn(LOCKER, self.forbidden())
        self.post([])

        self.assertEqual(before, self.forbidden())
        self.assertNotIn(LOCKER, self.forbidden())
        self.assertIn(self.boots, get_all_exclusions_ids(self.char))

    def test_the_stored_exclusions_are_byte_identical_throughout(self):
        self.post(None)
        stored = self.char.exclusions
        self.post([CRIMSON_PEBBLE])
        self.assertEqual(stored, self.char.exclusions)
        self.post([])
        self.assertEqual(stored, self.char.exclusions)

    def test_lifting_the_ban_removes_the_options_key(self):
        self.post([CRIMSON_PEBBLE])
        self.assertEqual([CRIMSON_PEBBLE], resource_ban.banned_resource_keys(self.char))
        self.post([])

        self.assertEqual([], resource_ban.banned_resource_keys(self.char))
        self.assertNotIn(resource_ban.OPTION_KEY.encode(), self.char.options)

    def test_the_answer_lists_the_ban_then_nothing(self):
        banned = self.post([CRIMSON_PEBBLE])
        self.assertEqual([CRIMSON_PEBBLE], [row['key'] for row in banned['resources']])
        self.assertTrue(banned['total_text'])

        lifted = self.post([])
        self.assertEqual([], lifted['resources'])
        self.assertEqual('', lifted['total_text'])
