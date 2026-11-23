# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A saved transcendence rune its piece can no longer take is shown without it, with a warning, and the totals leave its bonus out."""
from unittest import mock

from chardata.dracorune_fixtures import BetaModelTestCase, element_key, element_move, runes, stat_id
from chardata.transcendence_card_fixtures import lines_of, minimal_with, piece_in, plain_pieces, rune_of_stat
from fashionistapulp import dracorunes
from fashionistapulp.modelresult import _transcendence_in_slot, model_result_from_minimal
from fashionistapulp.structure import get_structure
from fashionistapulp.transcendence import load_runes
from fashionistapulp.transcendence_terms import ELEMENT_BLOCKED, rune_allowed_on, rune_fits

LOGGER = 'fashionistapulp.modelresult'


class ASavedRuneThePieceCanNoLongerTakeIsShownWithoutItTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.vit = rune_of_stat('vit')
        self.hat, self.other_hat = plain_pieces('Hat', 'beta', 2, self.vit)
        self.entry = (self.hat.id, self.vit['id'])

    def assert_shown_without(self, saved, expected_log, minimal_kwargs=None, overrides=None, slot='hat',
                             item_id=None):
        pieces = {slot: item_id or self.hat.id}
        bare = model_result_from_minimal(minimal_with(pieces, **(minimal_kwargs or {})), overrides)
        with self.assertLogs(LOGGER, level='WARNING') as logs:
            result = model_result_from_minimal(
                minimal_with(pieces, {slot: saved}, **(minimal_kwargs or {})), overrides)
        self.assertTrue(any(expected_log in line for line in logs.output), logs.output)
        self.assertIsNone(result.transcendences)
        self.assertIsNone(piece_in(result, slot).transcendence_rune)
        self.assertEqual(bare.get_stats_total(), result.get_stats_total())

    def test_an_unreadable_entry(self):
        self.assert_shown_without('junk', 'Unreadable transcendence rune')

    def test_an_unhashable_rune_id(self):
        self.assert_shown_without((self.hat.id, [1]), 'is no longer in the runes file')

    def test_a_dracorune_key_no_one_can_read(self):
        with self.assertLogs(LOGGER, level='WARNING') as logs:
            rune = _transcendence_in_slot('hat', self.hat, self.entry, {self.vit['id']: self.vit}, 7)
        self.assertIsNone(rune)
        self.assertTrue(any('Unreadable dracorune' in line for line in logs.output), logs.output)

    def test_saved_transcendences_that_are_not_a_mapping(self):
        result = model_result_from_minimal(minimal_with({'hat': self.hat.id}, ['junk']))
        self.assertIsNone(result.transcendences)
        self.assertIsNone(piece_in(result, 'hat').transcendence_rune)

    def test_a_slot_that_now_holds_another_item(self):
        self.assert_shown_without((self.other_hat.id, self.vit['id']), 'no longer holds item')

    def test_a_version_without_runes(self):
        with mock.patch('fashionistapulp.modelresult.load_transcendence_runes', return_value=[]):
            self.assert_shown_without(self.entry, 'has no transcendence runes')

    def test_a_runes_file_that_cannot_be_read(self):
        with mock.patch('fashionistapulp.modelresult.load_transcendence_runes', side_effect=OSError('gone')):
            self.assert_shown_without(self.entry, 'has no transcendence runes')

    def test_a_rune_id_no_longer_in_the_file(self):
        self.assert_shown_without((self.hat.id, 999999999), 'no longer in the runes file')

    def test_a_dracorune_kind_that_now_blocks_the_stat(self):
        blocked = next(rune for rune in load_runes('beta')
                       if rune['stat_key'] in ELEMENT_BLOCKED and rune['rank'] == 1
                       and not rune_allowed_on('element', rune['stat_key'])
                       and rune_fits(rune, lines_of(self.hat).get(rune['stat_key'])))
        source, target = element_move()
        key = element_key(source, target)
        item = next(item for item in plain_pieces('Hat', 'beta', 4000, blocked)
                    if lines_of(item).get(source, 0) > 0
                    and key in dict(dracorunes.variants(list(lines_of(item).items()), runes())))
        self.assert_shown_without((item.id, blocked['id']), 'now blocks the transcendence rune',
                                  {'saved_dracorunes': {'hat': (item.id, key)}}, item_id=item.id)

    def test_a_piece_that_became_overed(self):
        line = self.vit['stat_key']
        overrides = {self.hat.id: {stat_id(line): lines_of(self.hat).get(line, 0) + 3}}
        self.assert_shown_without(self.entry, 'no longer takes the transcendence rune', overrides=overrides)

    def test_a_piece_that_became_an_exo_carrier(self):
        overrides = {self.hat.id: {stat_id('ap'): lines_of(self.hat).get('ap', 0) + 1}}
        self.assert_shown_without(self.entry, 'no longer takes the transcendence rune', overrides=overrides)

    def test_a_type_that_takes_no_rune(self):
        found = get_structure('beta')
        dofus = next(item for item in sorted(found.get_available_items_list(), key=lambda one: one.id)
                     if found.get_type_name_by_id(item.type) == 'Dofus')
        self.assert_shown_without((dofus.id, self.vit['id']), 'no longer takes the transcendence rune',
                                  slot='dofus1', item_id=dofus.id)

    def test_a_line_that_no_longer_fits(self):
        found = get_structure('beta')
        pair = next((item, rune) for rune in load_runes('beta') if rune['rank'] == 1
                    for item in sorted(found.get_available_items_list(), key=lambda one: one.id)
                    if found.get_type_name_by_id(item.type) == 'Hat' and item.set is None
                    and not rune_fits(rune, lines_of(item).get(rune['stat_key'])))
        item, rune = pair
        self.assert_shown_without((item.id, rune['id']), 'no longer takes the transcendence rune',
                                  item_id=item.id)
