# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The export decides what their field can hold with the char's level, with or without runes."""

from unittest import mock

from django.test import TestCase

from chardata import dofusbook_export
from chardata.dofusbook_rune_fixtures import (RESISTANCE_KEY, draconize, export_page, piece,
                                              stand_in_runes, worn_by)
from fashionistapulp.structure import set_current_game_version


class TheLevelReachesTheFieldTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        stand_in_runes(self)
        self.hat = piece('Hat', RESISTANCE_KEY)
        self.char = worn_by(self.client, [self.hat])

    def levels(self):
        real = dofusbook_export.carriable_forge
        with mock.patch.object(dofusbook_export, 'carriable_forge', wraps=real) as spy:
            export_page(self.client, self.char)
        self.assertTrue(spy.called)
        return {call.args[2] if len(call.args) > 2 else call.kwargs.get('level')
                for call in spy.call_args_list}

    def test_a_build_without_runes(self):
        self.assertEqual({self.char.level}, self.levels())

    def test_a_build_with_a_rune(self):
        draconize(self.char, [(self.hat, RESISTANCE_KEY)])
        self.assertEqual({self.char.level}, self.levels())
