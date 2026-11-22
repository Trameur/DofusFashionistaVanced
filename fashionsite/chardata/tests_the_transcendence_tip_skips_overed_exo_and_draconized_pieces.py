# -*- coding: utf-8 -*-
"""A recorded over, an exo or a Dracorune closes the piece to a transcendence rune."""
from unittest import mock

from django.test import SimpleTestCase

from chardata.solution_result import attach_transcendence
from chardata.transcendence_advice import best_transcendence
from fashionistapulp.structure import set_current_game_version


class Piece(object):
    item_added = True
    type = 'Ring'
    id = None
    stats = {}
    base_stats = None
    exo_overrides = None
    assumed_exo = None
    dracorune = None


class TheTipSkipsClosedPiecesTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')

    def _tip(self, **changes):
        piece = Piece()
        for name, value in changes.items():
            setattr(piece, name, value)
        attach_transcendence(piece, {'int': 10})
        return piece.transcendence

    def test_a_clean_piece_gets_its_tip(self):
        self.assertTrue(self._tip(stats={'vit': 10}, base_stats={'vit': 10}))

    def test_a_recorded_exo_closes_the_piece(self):
        self.assertIsNone(self._tip(exo_overrides={'ap': 1}))

    def test_an_assumed_exo_closes_the_piece(self):
        self.assertIsNone(self._tip(assumed_exo='ap'))

    def test_a_dracorune_closes_the_piece(self):
        self.assertIsNone(self._tip(dracorune={'key': 'x'}))

    def test_a_recorded_over_closes_the_piece(self):
        self.assertIsNone(self._tip(stats={'vit': 260}, base_stats={'vit': 250}))

    def test_the_locked_flag_closes_the_piece(self):
        self.assertIsNone(best_transcendence('dofus3', {}, {'int': 10}, 'Ring',
                                             None, True))

    def test_a_lower_roll_keeps_its_tip(self):
        self.assertTrue(self._tip(stats={'vit': 180}, base_stats={'vit': 200}))

    def test_a_negative_line_weighs_nothing_in_the_fit(self):
        heavy = [{'stat_key': 'int', 'bonus': 10, 'weight': 110}]
        with mock.patch('chardata.transcendence_advice.get_transcendence_runes',
                        return_value=heavy):
            self.assertIsNone(best_transcendence('dofus3', {'int': -50},
                                                 {'int': 10}, 'Ring'))
