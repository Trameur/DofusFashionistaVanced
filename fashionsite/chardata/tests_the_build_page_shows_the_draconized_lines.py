# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A saved rune shows on its piece: the moved lines, their totals, their range and the rune's game name."""

import pickle
from unittest import mock

from django.template.loader import render_to_string
from django.utils.translation import override

from chardata.dracorune_fixtures import (OPTIONS, BetaModelTestCase, eligible_items,
                                         element_key, element_move, piece, runes, structure)
from chardata.solution_result import SolutionResult, dracorune_label, evolve_result_item
from chardata.translation_util import localized_stat_name
from fashionistapulp import dracorune_terms, dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import (ModelResultItem, ModelResultMinimal,
                                         model_result_from_minimal)


def lines_of(item):
    lines = {}
    for stat_id, value in item.stats:
        key = structure().get_stat_by_id(stat_id).key
        lines[key] = lines.get(key, 0) + value
    return lines


def base_stats():
    return dict({name: 0 for name, _key in STATS_NAMES}, AP=7, MP=3)


def minimal_for(item_per_slot, saved_runes=None):
    minimal = ModelResultMinimal(dict(item_per_slot),
                                 {'options': dict(OPTIONS), 'char_level': 200,
                                  'base_stats_by_attr': base_stats()}, None)
    if saved_runes is not None:
        minimal.dracorunes = saved_runes
    return pickle.loads(pickle.dumps(minimal))


def hat_slot(result):
    return next(item for item in result.item_list if item.slot == 'hat')


class TheBuildPageShowsTheDraconizedLinesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.key = element_key(self.source, self.target)
        source_id = structure().get_stat_by_key(self.source).id
        hats = [item for item in eligible_items('Hat')
                if lines_of(item).get(self.source, 0) > 0
                and dracorunes.STAT_TO_DAMAGE[self.source] not in lines_of(item)
                and source_id in (item.stat_ranges or {})
                and len(item.stat_ranges) > 1
                and self.key in dict(dracorunes.variants(list(lines_of(item).items()), runes()))]
        self.hat, self.other_hat = hats[0], hats[1]
        self.lines = lines_of(self.hat)
        self.moved = dict(dict(dracorunes.variants(list(self.lines.items()), runes()))[self.key])
        self.rune = dracorunes.rune_of(self.key, runes())

    def result(self, saved_runes=None, hat=None):
        return model_result_from_minimal(
            minimal_for({'hat': (hat or self.hat).id}, saved_runes))

    def draconized(self):
        return self.result({'hat': (self.hat.id, self.key)})

    def test_the_piece_wears_the_variant_lines_and_keeps_its_own(self):
        piece = hat_slot(self.draconized())
        self.assertEqual(self.moved, piece.stats)
        self.assertEqual(self.moved, piece.base_stats)
        self.assertEqual(self.lines, piece.undraconized_stats)
        self.assertEqual({'key': self.key, 'item_id': self.rune['item_id'],
                          'name': self.rune['names']['en']}, piece.dracorune)

    def test_the_totals_add_the_moved_lines(self):
        base = self.result().get_stats_total()
        total = self.draconized().get_stats_total()
        moved = self.lines[self.source]
        self.assertEqual(base[self.source] - moved, total[self.source])
        self.assertEqual(base[self.target] + moved, total[self.target])
        self.assertEqual(base['init'], total['init'])

    def test_the_range_moves_with_its_line(self):
        ranges = {structure().get_stat_by_id(stat_id).key: bounds
                  for stat_id, bounds in self.hat.stat_ranges.items()}
        piece = hat_slot(self.draconized())
        self.assertEqual(ranges[self.source], piece.stat_ranges[self.target])
        self.assertNotIn(self.source, piece.stat_ranges)
        for key, bounds in ranges.items():
            if key not in dracorunes.moves(self.key) and bounds[0] != bounds[1]:
                self.assertEqual(bounds, piece.stat_ranges[key])

    def test_the_label_names_the_rune_then_the_moved_stat_then_its_target(self):
        patterns = {'en': '%s: %s → %s', 'fr': '%s : %s → %s', 'de': '%s: %s → %s',
                    'es': '%s: %s → %s', 'pt': '%s: %s → %s'}
        for language, pattern in patterns.items():
            with override(language):
                result = self.draconized()
                piece = hat_slot(result)
                evolve_result_item(piece, result)
                source, target = (localized_stat_name(structure().get_stat_by_key(key).name)
                                  for key in (self.source, self.target))
                self.assertEqual(pattern % (self.rune['names'][language], source, target),
                                 piece.dracorune_label)

    def test_a_line_the_rune_leaves_nothing_of_says_so(self):
        power = next(rune for rune in runes()['runes'] if rune['kind'] == 'power')
        hat = piece('Hat', {self.source: 1, 'vit': 50})
        for language, pattern in (('en', '%s: %s → nothing'), ('fr', '%s : %s → rien'),
                                  ('de', '%s: %s → nichts'), ('es', '%s: %s → nada'),
                                  ('pt', '%s: %s → nada')):
            with override(language):
                worn = ModelResultItem(hat, None, (power['kind'], runes()))
                self.assertEqual({'vit': 50}, worn.stats)
                source = localized_stat_name(structure().get_stat_by_key(self.source).name)
                self.assertEqual(pattern % (power['names'][language], source),
                                 dracorune_label(worn))

    def test_the_card_shows_the_label(self):
        result = self.draconized()
        params = SolutionResult(result).get_params()
        piece = next(item for item in params['all_items'] if item.slot == 'hat')
        page = render_to_string('chardata/solution_item.html', {'item': piece})
        self.assertIn(piece.dracorune_label, page)
        for line in piece.stats_lines:
            self.assertIn(line.text, page)

    def test_a_piece_without_a_rune_has_no_label(self):
        result = self.result()
        piece = hat_slot(result)
        evolve_result_item(piece, result)
        self.assertIsNone(piece.dracorune_label)
        self.assertNotIn('small-explain', render_to_string(
            'chardata/solution_dracorune.html', {'item': piece}))

    def test_a_changed_item_drops_the_rune(self):
        with self.assertLogs('fashionistapulp.modelresult', 'WARNING'):
            result = self.result({'hat': (self.hat.id, self.key)}, hat=self.other_hat)
        piece = hat_slot(result)
        self.assertEqual(lines_of(self.other_hat), piece.stats)
        self.assertIsNone(piece.dracorune)
        self.assertIsNone(result.dracorunes)

    def test_a_piece_whose_type_no_longer_takes_a_rune_drops_it(self):
        worn = structure().get_item_by_id(self.hat.id)
        with mock.patch.object(worn, 'type', structure().get_type_id_by_name('Shield')):
            self.assertFalse(dracorune_terms.is_eligible(worn, structure(), runes()))
            self.assertIn(self.key, dict(dracorunes.variants(list(lines_of(worn).items()), runes())))
            with self.assertLogs('fashionistapulp.modelresult', 'WARNING'):
                result = self.draconized()
        piece = hat_slot(result)
        self.assertEqual(self.lines, piece.stats)
        self.assertIsNone(piece.dracorune)
        self.assertIsNone(result.dracorunes)

    def test_a_variant_the_lines_no_longer_give_drops_the_rune(self):
        with self.assertLogs('fashionistapulp.modelresult', 'WARNING'):
            result = self.result({'hat': (self.hat.id, element_key(self.target, self.source))})
        self.assertEqual(self.lines, hat_slot(result).stats)
        self.assertIsNone(result.dracorunes)

    def test_an_item_switched_by_hand_drops_the_rune(self):
        result = self.draconized()
        self.assertEqual({'hat': (self.hat.id, self.key)}, result.dracorunes)
        result.switch_item(self.other_hat, 'hat')
        self.assertIsNone(ModelResultMinimal.from_model_result(result).dracorunes)

    def test_a_pickle_without_the_attribute_loads_as_before(self):
        minimal = minimal_for({'hat': self.hat.id})
        self.assertNotIn('dracorunes', vars(minimal))
        result = model_result_from_minimal(minimal)
        piece = hat_slot(result)
        self.assertEqual(self.lines, piece.stats)
        self.assertIsNone(piece.dracorune)
        self.assertIsNone(piece.undraconized_stats)
        self.assertIsNone(result.dracorunes)
