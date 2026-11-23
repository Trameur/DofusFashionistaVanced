# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Copying a build to another version stores the set without the transcendence runes, as it stores it without the Dracorunes."""
from types import SimpleNamespace
from unittest import mock

from chardata import version_copy
from chardata.dracorune_fixtures import BetaModelTestCase
from chardata.transcendence_card_fixtures import minimal_with, plain_pieces, rune_of_stat


class AVersionCopyLeavesTheTranscendencesBehindTests(BetaModelTestCase):

    def test_the_stored_set_is_a_fresh_minimal_without_runes(self):
        rune = rune_of_stat('vit')
        hat = plain_pieces('Hat', 'beta', 1, rune)[0]
        source = minimal_with({'hat': hat.id}, {'hat': (hat.id, rune['id'])})
        self.assertIsNotNone(source.transcendences)
        char = SimpleNamespace(auto_publish=False, game_version='beta')
        with mock.patch('chardata.solution.get_solution_from_minimal', return_value=None) as read:
            version_copy._store_the_set(char, source, {'hat': hat.id})
        stored = read.call_args.args[1]
        self.assertEqual({'hat': hat.id}, stored.item_per_slot)
        self.assertIsNone(stored.transcendences)
        self.assertIsNone(stored.dracorunes)
