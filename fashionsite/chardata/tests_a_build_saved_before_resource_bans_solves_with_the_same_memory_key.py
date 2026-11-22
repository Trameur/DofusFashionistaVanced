# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build with no ban keeps its solver input and memory key, and an unreadable ban value reads as no ban."""
import pickle

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import resource_ban
from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.fashion_action import _model_input
from chardata.inventory_solver import apply_inventory_restriction
from chardata.lock_forbid import get_all_exclusions_ids
from chardata.min_stats import set_min_stats
from chardata.models import InventoryFolder, InventoryItem
from chardata.options import set_setup_choices
from chardata.stats_weights import set_stats_weights
from fashionistapulp.structure import set_current_game_version

CRIMSON_PEBBLE = '12737:resources'
MINOR_LOCKER = 12622
LOCKER = 12623
UNREADABLE = ('garbage', 12, {'12737:resources': 1}, ['not a key', 12, None, ''],
              ['999999999:resources'], ['12737:nothing'], ['12737:Resources'])


class _ABuild(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('oldban', 'ob@test.local', 'pw-old-ban-1')
        self.request = RequestFactory().get('/')
        self.request.user = owner
        self.request.game_version = 'dofus3'
        self.char = create_build(self.request, 'Feca', 120, {'cha'}, 'dofus3')
        set_min_stats(self.char, {})
        set_stats_weights(self.char, {'vit': 1})

    def model_input(self):
        return _model_input(self.request, self.char, {'vit': 1})


class ABuildWithoutABanKeepsItsInputTests(_ABuild):

    def test_the_forbidden_set_is_the_stored_exclusions_alone(self):
        model_input = self.model_input()
        self.assertEqual(set(get_all_exclusions_ids(self.char)), model_input.forbidden_equips)
        self.assertEqual([], resource_ban.banned_resource_keys(self.char))

    def test_in_the_only_mode_the_forbidden_set_is_the_inventory_restriction_alone(self):
        folder = InventoryFolder.objects.create(
            user=self.request.user, name='Stock', game_version='dofus3')
        InventoryItem.objects.create(folder=folder, item_id=LOCKER)
        set_setup_choices(self.char, {'inventory_mode': 'only', 'inventory_folder': folder.id})
        expected = set(apply_inventory_restriction(
            self.char, get_all_exclusions_ids(self.char), folder))
        self.assertIn(MINOR_LOCKER, expected)
        self.assertEqual(expected, self.model_input().forbidden_equips)

    def test_lifting_a_ban_gives_back_the_key_of_the_build_that_never_had_one(self):
        before = self.model_input()
        stored = self.char.options
        set_setup_choices(self.char, {resource_ban.OPTION_KEY: [CRIMSON_PEBBLE]})
        self.assertNotEqual(before.cache_key(), self.model_input().cache_key())
        set_setup_choices(self.char, {resource_ban.OPTION_KEY: None})
        after = self.model_input()
        options_before = read_char_blob(stored, None, 'options')
        self.assertIsInstance(options_before, dict)
        self.assertEqual(options_before, read_char_blob(self.char.options, None, 'options'))
        self.assertEqual(before.cache_key(), after.cache_key())
        self.assertEqual(before.forbidden_equips, after.forbidden_equips)


class AnUnreadableBanReadsAsNoBanTests(_ABuild):

    def test_each_unreadable_value_keeps_the_key_of_a_build_without_a_ban(self):
        plain = self.model_input()
        for value in UNREADABLE:
            with self.subTest(value=value):
                set_setup_choices(self.char, {resource_ban.OPTION_KEY: value})
                self.assertEqual([], resource_ban.banned_resource_keys(self.char))
                model_input = self.model_input()
                self.assertEqual(plain.cache_key(), model_input.cache_key())
                self.assertEqual(plain.forbidden_equips, model_input.forbidden_equips)

    def test_an_unreadable_options_blob_reads_as_no_ban(self):
        self.char.options = b'not a pickle'
        self.assertEqual([], resource_ban.banned_resource_keys(self.char))

    def test_options_that_are_not_a_dict_read_as_no_ban(self):
        self.char.options = pickle.dumps(['banned_resources'])
        self.assertEqual([], resource_ban.banned_resource_keys(self.char))

    def test_a_readable_key_among_unreadable_ones_still_bans(self):
        set_setup_choices(self.char, {resource_ban.OPTION_KEY: ['junk', CRIMSON_PEBBLE, 7]})
        self.assertEqual([CRIMSON_PEBBLE], resource_ban.banned_resource_keys(self.char))

    def test_the_list_is_cut_at_the_cap(self):
        known = sorted(resource_ban._items_by_resource('dofus3'))
        set_setup_choices(self.char, {resource_ban.OPTION_KEY:
                                      known[:resource_ban.MAX_BANNED_RESOURCES + 10]})
        self.assertEqual(resource_ban.MAX_BANNED_RESOURCES,
                         len(resource_ban.banned_resource_keys(self.char)))
