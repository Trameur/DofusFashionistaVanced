# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A saved build wears the same transcendence runes on the same slots, counts each once, and loses one with its piece."""

from chardata.dracorune_fixtures import BetaModelTestCase
from chardata.solution_result import stat_sources
from chardata.transcendence_card_fixtures import (lines_of, minimal_with, piece_in, plain_pieces,
                                                  rune_of_stat)
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal
from fashionistapulp.structure import get_structure
from fashionistapulp.transcendence import load_runes
from fashionistapulp.transcendence_terms import rune_fits


class ASavedBuildKeepsItsTranscendencesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.vit = rune_of_stat('vit')
        self.init = rune_of_stat('init')
        self.hat, self.other_hat = plain_pieces('Hat', 'beta', 2, self.vit)
        self.ring, self.other_ring = plain_pieces('Ring', 'beta', 2, self.init)
        self.pieces = {'hat': self.hat.id, 'ring1': self.ring.id, 'ring2': self.ring.id}
        self.saved = {'hat': (self.hat.id, self.vit['id']),
                      'ring1': (self.ring.id, self.init['id']),
                      'ring2': (self.ring.id, self.init['id'])}

    def result(self, transcendences='saved'):
        saved = self.saved if transcendences == 'saved' else transcendences
        return model_result_from_minimal(minimal_with(self.pieces, saved))

    def test_the_rebuilt_page_wears_the_same_runes_on_the_same_slots(self):
        result = self.result()
        self.assertEqual(self.saved, result.transcendences)
        self.assertEqual(self.vit['id'], piece_in(result, 'hat').transcendence_rune['id'])
        self.assertEqual(self.init['id'], piece_in(result, 'ring1').transcendence_rune['id'])
        self.assertEqual(self.init['id'], piece_in(result, 'ring2').transcendence_rune['id'])

    def test_the_rune_adds_its_bonus_to_the_piece_and_keeps_the_catalogue_base(self):
        worn = piece_in(self.result(), 'hat')
        bare = piece_in(self.result(None), 'hat')
        self.assertEqual(bare.stats.get('vit', 0) + self.vit['bonus'], worn.stats['vit'])
        self.assertEqual(bare.base_stats.get('vit', 0) + self.vit['bonus'], worn.base_stats['vit'])
        self.assertEqual(bare.stats, worn.untranscended_stats)
        self.assertFalse(worn.holds_an_over())

    def test_the_page_totals_count_each_rune_once(self):
        with_runes = self.result().get_stats_total()
        without = self.result(None).get_stats_total()
        self.assertEqual(self.vit['bonus'], with_runes['vit'] - without['vit'])
        self.assertEqual(2 * self.init['bonus'], with_runes['init'] - without['init'])

    def test_a_saved_edit_keeps_the_runes_of_the_pieces_it_kept(self):
        result = self.result()
        saved_again = ModelResultMinimal.from_model_result(result)
        self.assertEqual(self.saved, saved_again.transcendences)
        result.switch_item(self.other_ring, 'ring1')
        edited = ModelResultMinimal.from_model_result(result)
        self.assertEqual({slot: entry for slot, entry in self.saved.items() if slot != 'ring1'},
                         edited.transcendences)
        reloaded = model_result_from_minimal(edited)
        self.assertEqual(edited.transcendences, reloaded.transcendences)

    def test_a_switched_piece_loses_its_rune(self):
        result = self.result()
        switched = result.switch_item(self.other_ring, 'ring2')
        self.assertIsNone(switched.transcendence_rune)
        self.assertNotIn('ring2', result.transcendences)
        self.assertIn('ring1', result.transcendences)

    def test_a_hat_swapped_for_another_hat_of_the_same_class_loses_its_rune(self):
        result = self.result()
        result.switch_item(self.other_hat, 'hat')
        self.assertNotIn('hat', result.transcendences)
        self.assertEqual(self.other_hat.id, piece_in(result, 'hat').id)

    def test_a_build_without_runes_saves_none(self):
        self.assertIsNone(self.result(None).transcendences)
        self.assertIsNone(ModelResultMinimal.from_model_result(self.result(None)).transcendences)

    def test_the_stat_panel_lists_the_rune_as_its_own_item_line(self):
        piece = piece_in(self.result(), 'hat')
        lines = [line for line in stat_sources(self.result())['vit'] if line['kind'] == 'item']
        rune_line = next(line for line in lines if line['label'] == '%s (%s)' % (
            self.vit['names']['en'], piece.localized_name))
        self.assertEqual(self.vit['bonus'], rune_line['value'])
        self.assertEqual(piece.stats['vit'], sum(line['value'] for line in lines))

    def test_a_pair_of_the_same_ring_wears_the_rune_only_where_it_was_saved(self):
        saved = {'ring1': (self.ring.id, self.init['id'])}
        result = self.result(saved)
        self.assertEqual(self.init['id'], piece_in(result, 'ring1').transcendence_rune['id'])
        self.assertIsNone(piece_in(result, 'ring2').transcendence_rune)
        self.assertEqual(saved, result.transcendences)
        without = self.result(None).get_stats_total()
        self.assertEqual(self.init['bonus'], result.get_stats_total()['init'] - without['init'])

    def test_a_rune_on_a_ranged_line_moves_both_ends_of_the_range(self):
        structure = get_structure('beta')
        for item in sorted(structure.get_available_items_list(), key=lambda one: one.id):
            if (structure.get_type_name_by_id(item.type) != 'Amulet' or item.set is not None
                    or item.removed or not getattr(item, 'stat_ranges', None)):
                continue
            lines = lines_of(item)
            for stat_id, (low, high) in item.stat_ranges.items():
                key = structure.get_stat_by_id(stat_id).key
                rune = next((one for one in load_runes('beta') if one['stat_key'] == key
                             and rune_fits(one, lines.get(key))), None)
                if low != high and rune:
                    break
            else:
                continue
            if rune:
                break
        bare = piece_in(model_result_from_minimal(minimal_with({'amulet': item.id})), 'amulet')
        worn = piece_in(model_result_from_minimal(minimal_with(
            {'amulet': item.id}, {'amulet': (item.id, rune['id'])})), 'amulet')
        low, high = bare.stat_ranges[key]
        self.assertLess(low, high)
        self.assertEqual((low + rune['bonus'], high + rune['bonus']), worn.stat_ranges[key])
