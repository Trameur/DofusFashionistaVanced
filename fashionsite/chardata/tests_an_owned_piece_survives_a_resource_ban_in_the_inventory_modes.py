# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece the player owns in the build's inventory folder is spared by a resource ban in the modes mixed and only."""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import resource_ban
from chardata.coaching_view import create_build
from chardata.fashion_action import _model_input
from chardata.min_stats import set_min_stats
from chardata.models import InventoryFolder, InventoryItem
from chardata.options import set_setup_choices
from chardata.stats_weights import set_stats_weights
from fashionistapulp.structure import set_current_game_version

CRIMSON_PEBBLE = '12737:resources'
MINOR_LOCKER = 12622
LOCKER = 12623


class AnOwnedPieceIsSparedTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        owner = User.objects.create_user('ownban', 'ow@test.local', 'pw-own-ban-1')
        self.request = RequestFactory().get('/')
        self.request.user = owner
        self.request.game_version = 'dofus3'
        self.char = create_build(self.request, 'Feca', 120, {'cha'}, 'dofus3')
        set_min_stats(self.char, {})
        set_stats_weights(self.char, {'vit': 1})
        self.folder = InventoryFolder.objects.create(
            user=owner, name='Stock', game_version='dofus3')
        InventoryItem.objects.create(folder=self.folder, item_id=LOCKER)
        set_setup_choices(self.char, {resource_ban.OPTION_KEY: [CRIMSON_PEBBLE]})

    def forbidden(self, mode):
        set_setup_choices(self.char, {'inventory_mode': mode,
                                      'inventory_folder': self.folder.id})
        return _model_input(self.request, self.char, {'vit': 1}).forbidden_equips

    def test_without_an_inventory_mode_the_ban_forbids_both_pieces(self):
        forbidden = self.forbidden('all')
        self.assertIn(LOCKER, forbidden)
        self.assertIn(MINOR_LOCKER, forbidden)

    def test_mixed_spares_the_owned_piece_only(self):
        forbidden = self.forbidden('mixed')
        self.assertNotIn(LOCKER, forbidden)
        self.assertIn(MINOR_LOCKER, forbidden)

    def test_only_spares_the_owned_piece_and_forbids_the_rest(self):
        forbidden = self.forbidden('only')
        self.assertNotIn(LOCKER, forbidden)
        self.assertIn(MINOR_LOCKER, forbidden)

    def test_a_folder_of_another_version_spares_nothing(self):
        self.folder.game_version = 'retro'
        self.folder.save()
        self.assertIn(LOCKER, self.forbidden('mixed'))
