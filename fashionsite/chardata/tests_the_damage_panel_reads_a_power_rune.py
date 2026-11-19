# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The best turn panel of a build with the power rune reads the lines the rune leaves, like a piece that had them."""

import math
import pickle
from copy import deepcopy
from decimal import Decimal

from chardata.dracorune_fixtures import (OPTIONS, BetaModelTestCase, eligible_items, runes,
                                         stat_id, structure)
from chardata.spells_view import _best_combo
from fashionistapulp import dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import ModelResult, ModelResultMinimal, model_result_from_minimal

POWER = 'power'
INPUT = {'options': dict(OPTIONS), 'char_level': 200,
         'base_stats_by_attr': dict({name: 0 for name, _key in STATS_NAMES}, AP=7, MP=3)}


class _Char(object):

    def __init__(self, name):
        self.id = 'power-rune-%s' % name
        self.char_class = 'Iop'
        self.level = 200
        self.game_version = 'beta'


def lines_of(item):
    lines = {}
    for line_id, value in item.stats:
        key = structure().get_stat_by_id(line_id).key
        lines[key] = lines.get(key, 0) + value
    return lines


class TheDamagePanelReadsAPowerRuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.rune = dracorunes.rune_of(POWER, runes())
        self.assertIsNotNone(self.rune)
        self.hat = next(
            item for item in eligible_items('Hat')
            if lines_of(item).get('str', 0) > 0 and 'pow' not in lines_of(item)
            and POWER in dict(dracorunes.variants(list(lines_of(item).items()), runes())))
        self.lines = dict(dict(dracorunes.variants(
            list(lines_of(self.hat).items()), runes()))[POWER])

    def draconized(self):
        minimal = ModelResultMinimal({'hat': self.hat.id}, deepcopy(INPUT), None)
        minimal.dracorunes = {'hat': (self.hat.id, POWER)}
        return model_result_from_minimal(pickle.loads(pickle.dumps(minimal)))

    def undraconized(self):
        return model_result_from_minimal(
            ModelResultMinimal({'hat': self.hat.id}, deepcopy(INPUT), None))

    def with_the_lines_written(self):
        piece = deepcopy(self.hat)
        piece.stats = [(stat_id(key), value) for key, value in self.lines.items()]
        result = ModelResult(deepcopy(INPUT))
        result.add_item_at_slot(piece, 'hat')
        for slot in list(result.open_slots):
            result.add_item_at_slot(None, slot)
        result.calculate_stats()
        return result

    def test_the_rune_is_the_ebony_one_of_the_game(self):
        self.assertEqual('power', self.rune['kind'])
        self.assertEqual('Ebony Dracorune', self.rune['names']['en'])

    def test_the_totals_take_the_power_and_drop_the_characteristic(self):
        keep = self.rune['keep']
        strength = lines_of(self.hat)['str']
        base = self.undraconized().get_stats_total()
        total = self.draconized().get_stats_total()
        self.assertEqual(base['str'] - strength, total['str'])
        self.assertEqual(self.lines['pow'], total['pow'] - base['pow'])
        highest = max(value for key, value in lines_of(self.hat).items()
                      if key in dracorunes.STAT_TO_DAMAGE and value > 0)
        self.assertEqual('floor', runes()['rounding'])
        self.assertEqual(math.floor(Decimal(highest) * Decimal(str(keep))), self.lines['pow'])
        self.assertEqual(self.with_the_lines_written().get_stats_total(), total)

    def test_the_best_turn_is_the_one_of_a_piece_with_those_lines(self):
        draconized = _best_combo(_Char('rune'), self.draconized(), 'beta')
        written = _best_combo(_Char('written'), self.with_the_lines_written(), 'beta')
        undraconized = _best_combo(_Char('base'), self.undraconized(), 'beta')
        self.assertIsNotNone(draconized)
        self.assertEqual(written['total'], draconized['total'])
        self.assertEqual([cast['damage'] for cast in written['casts']],
                         [cast['damage'] for cast in draconized['casts']])
        self.assertNotEqual(undraconized['total'], draconized['total'])
