# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Two builds that differ only by a resource ban have different memory keys, and the same ban gives the same key."""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import resource_ban
from chardata.coaching_view import create_build
from chardata.fashion_action import _model_input
from chardata.min_stats import set_min_stats
from chardata.options import set_setup_choices
from chardata.stats_weights import set_stats_weights
from fashionistapulp.structure import set_current_game_version

CRIMSON_PEBBLE = '12737:resources'
ANOTHER_RESOURCE = '757:resources'


class TheBanIsPartOfTheMemoryKeyTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('keyban', 'kb@test.local', 'pw-key-ban-1')
        self.request = RequestFactory().get('/')
        self.request.user = self.owner
        self.request.game_version = 'dofus3'

    def build(self, keys=None):
        char = create_build(self.request, 'Feca', 120, {'cha'}, 'dofus3')
        set_min_stats(char, {})
        set_stats_weights(char, {'vit': 1})
        if keys is not None:
            set_setup_choices(char, {resource_ban.OPTION_KEY: keys})
        return char

    def key(self, char):
        return _model_input(self.request, char, {'vit': 1}).cache_key()

    def test_a_ban_changes_the_key(self):
        self.assertNotEqual(self.key(self.build()), self.key(self.build([CRIMSON_PEBBLE])))

    def test_two_different_bans_have_two_keys(self):
        self.assertNotEqual(self.key(self.build([CRIMSON_PEBBLE])),
                            self.key(self.build([ANOTHER_RESOURCE])))

    def test_the_same_ban_gives_the_same_key(self):
        self.assertEqual(self.key(self.build([CRIMSON_PEBBLE])),
                         self.key(self.build([CRIMSON_PEBBLE])))

    def test_the_order_the_ban_was_written_in_does_not_matter(self):
        self.assertEqual(self.key(self.build([CRIMSON_PEBBLE, ANOTHER_RESOURCE])),
                         self.key(self.build([ANOTHER_RESOURCE, CRIMSON_PEBBLE])))
