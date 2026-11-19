# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A sheet is read as a Dracorune only when its lines, laid over the piece's own, equal exactly one variant."""

from unittest import mock

from django.test import TestCase

from chardata import dofusbook_import
from chardata.dofusbook_rune_fixtures import (LINK, RESISTANCE_KEY, code_of, lines_of, opener,
                                              piece, public_payload, runes, slot_code,
                                              stand_in_runes, structure, variant_lines)
from fashionistapulp import dracorune_terms
from fashionistapulp.structure import set_current_game_version


class _Sheet(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        stand_in_runes(self)
        self.hat = piece('Hat', RESISTANCE_KEY)

    def read(self, sheet):
        payload = public_payload([(slot_code('Hat'), self.hat, lines_of(self.hat))])
        payload['fmItems'][slot_code('Hat')] = sheet
        return dofusbook_import.read_build(LINK, opener=opener(payload))


class PartOfARuneIsNotTheRuneTests(_Sheet):

    def test_a_sheet_that_only_removes_the_line_the_rune_removes_is_not_the_rune(self):
        lu = self.read({'rnp': 0})
        self.assertNotIn('dracorunes', lu)
        self.assertNotIn('dracorunes_unread', lu)

    def test_a_sheet_that_only_adds_the_line_the_rune_adds_is_not_the_rune(self):
        lu = self.read({'rtp': variant_lines(self.hat, RESISTANCE_KEY)['earthresper']})
        self.assertNotIn('dracorunes', lu)
        self.assertIn(self.hat.id, lu['rolls'])

    def test_a_sheet_that_writes_out_the_pieces_own_lines_is_not_a_rune(self):
        sheet = {code_of(key): value for key, value in lines_of(self.hat).items() if value}
        lu = self.read(sheet)
        self.assertNotIn('dracorunes', lu)
        self.assertNotIn('dracorunes_unread', lu)

    def test_the_whole_rune_written_out_is_the_rune(self):
        sheet = {code_of(key): value for key, value in variant_lines(self.hat, RESISTANCE_KEY).items()}
        sheet['rnp'] = 0
        lu = self.read(sheet)
        self.assertEqual([(self.hat.id, RESISTANCE_KEY)], lu['dracorunes'])


class TwoVariantsOnOneSheetAreNotGuessedTests(_Sheet):

    def twins(self):
        real = dracorune_terms.item_variants(self.hat, runes(), structure())
        one = next(variant for variant in real if variant.key == RESISTANCE_KEY)
        return [one, dracorune_terms.Variant('twin:' + one.key, one.delta)]

    def test_the_slot_is_left_unread_and_named(self):
        sheet = {'rnp': 0, 'rtp': variant_lines(self.hat, RESISTANCE_KEY)['earthresper']}
        with mock.patch('fashionistapulp.dracorune_terms.item_variants', return_value=self.twins()):
            lu = self.read(sheet)
        self.assertNotIn('dracorunes', lu)
        self.assertEqual([self.hat.id], lu['dracorunes_unread'])
