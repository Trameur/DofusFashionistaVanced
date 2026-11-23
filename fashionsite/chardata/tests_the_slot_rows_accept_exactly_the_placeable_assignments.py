# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The rows of a one-slot type accept a rune exactly when the worn piece holds it, nested fit sets or not."""

import itertools
import re
from unittest import mock

from fashionistapulp import dracorune_terms, model as slot_model, transcendence_terms as terms
from fashionistapulp.transcendence import load_runes
from fashionistapulp.transcendence_terms import dracorune_kind, rune_allowed_on, rune_fits

from chardata.dracorune_fixtures import VERSION, BetaModelTestCase, SmallModel, element_move, piece
from chardata.transcendence_fixtures import trans_input

KINDS = (None, 'element', 'resistance', 'power')
SLOT_ROW = re.compile(r'trans_(t\d|fit)_\d+(_|$)')
POW_LINES = (0, 15, 25)
STAGGERED_RANKS = {3: (0, 25), 2: (0, 15)}


def _every_variant(pool, _context):
    return {item_id: list(variants) for item_id, variants in pool.items()}, set()


def staggered_fit(rune, line):
    """Real fits, except that pow rank 3 fits the lines 0 and 25 and rank 2 the lines 0 and 15."""
    if rune['stat_key'] == 'pow' and rune['rank'] in STAGGERED_RANKS:
        return (line or 0) in STAGGERED_RANKS[rune['rank']]
    return rune_fits(rune, line)


class _SlotRowsCase(BetaModelTestCase):
    fits = staticmethod(rune_fits)

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.runes = {rune['id']: rune for rune in load_runes(VERSION)}
        self.lines = [{self.source: 50, 'neutres': 10, 'pow': line} for line in POW_LINES]
        pieces = [piece('Hat', lines, number) for number, lines in enumerate(self.lines)]
        with (mock.patch.object(dracorune_terms, 'prune', side_effect=_every_variant),
              mock.patch.object(slot_model, 'rune_fits', self.fits),
              mock.patch.object(terms, 'rune_fits', self.fits)):
            self.model = SmallModel(pieces)
            self.model.setup(trans_input({self.target: 1, 'fireresper': 3, 'pow': 1, 'vit': 0.05},
                                         8, 4))
        self.members = [item.id for item in pieces]

    def var(self, name):
        return self.model.problem.pulp_vars[name]

    def placeable(self, worn, kind, chosen):
        if not chosen:
            return True
        if worn is None or len(chosen) > 1:
            return False
        (rune,) = chosen
        return (self.fits(rune, self.lines[worn].get(rune['stat_key']))
                and rune_allowed_on(kind, rune['stat_key']))

    def check_the_rows(self):
        lp = self.model.problem.pulp_lp
        rows = [row for name, row in lp.constraints.items()
                if SLOT_ROW.match(name) or name.startswith('draco_link_')]
        self.assertTrue(any(name.startswith('trans_fit_0_pow_') for name in lp.constraints))
        columns = [(self.var(name), self.runes[rune_id])
                   for name, (_number, rune_id) in sorted(self.model.transcendence_columns.items())]
        variants = {item_id: {} for item_id in self.members}
        for name, (item_id, key) in self.model.dracorune_columns.items():
            variants[item_id].setdefault(dracorune_kind(key), []).append(self.var(name))
        checked = 0
        for worn in (None,) + tuple(range(len(self.members))):
            for kind in KINDS if worn is not None else (None,):
                for index, item_id in enumerate(self.members):
                    self.var('x_%s' % str(item_id).replace('-', '_')).varValue = int(index == worn)
                    for its_kind, kind_columns in variants[item_id].items():
                        for position, column in enumerate(kind_columns):
                            column.varValue = int(index == worn and position == 0
                                                  and its_kind == kind)
                for values in itertools.product((0, 1), repeat=len(columns)):
                    for (column, _rune), value in zip(columns, values):
                        column.varValue = value
                    chosen = [rune for (_column, rune), value in zip(columns, values) if value]
                    self.assertEqual(self.placeable(worn, kind, chosen),
                                     all(row.valid() for row in rows),
                                     (worn, kind, [rune['id'] for rune in chosen]))
                    checked += 1
        self.assertEqual((1 + len(self.members) * len(KINDS)) * 2 ** len(columns), checked)


class TheSlotRowsAcceptExactlyThePlaceableAssignmentsTests(_SlotRowsCase):

    def test_the_three_hats_share_one_slot_with_a_column_per_pow_rank(self):
        self.assertEqual({0: self.members}, self.model.transcendence_classes)
        ranks = sorted(self.runes[rune_id]['rank'] for _number, rune_id
                       in self.model.transcendence_columns.values()
                       if self.runes[rune_id]['stat_key'] == 'pow')
        self.assertEqual([1, 2, 3], ranks)

    def test_the_rows_accept_exactly_the_placeable_assignments(self):
        self.check_the_rows()


class TheSlotRowsAcceptExactlyTheAssignmentsWhenFitSetsAreNotNestedTests(_SlotRowsCase):
    fits = staticmethod(staggered_fit)

    def test_the_two_pow_ranks_fit_different_hats_without_one_holding_the_other(self):
        ranks = {}
        for rune in self.runes.values():
            if rune['stat_key'] == 'pow' and rune['rank'] in STAGGERED_RANKS:
                ranks[rune['rank']] = {index for index, lines in enumerate(self.lines)
                                       if self.fits(rune, lines['pow'])}
        self.assertEqual({3: {0, 2}, 2: {0, 1}}, ranks)
        self.assertEqual({0: self.members}, self.model.transcendence_classes)
        self.assertEqual([2, 3], sorted(self.runes[rune_id]['rank'] for _number, rune_id
                                        in self.model.transcendence_columns.values()
                                        if self.runes[rune_id]['stat_key'] == 'pow'))

    def test_the_rows_accept_exactly_the_placeable_assignments(self):
        self.check_the_rows()
