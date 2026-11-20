# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A draconized piece can no longer be forgemaged, so its card drops the Smithmagic link and keeps it without the rune."""
import pickle

from django.template.loader import render_to_string

from chardata.dracorune_fixtures import (OPTIONS, BetaModelTestCase, eligible_items,
                                         element_key, element_move, runes, structure)
from chardata.solution_result import SolutionResult
from fashionistapulp import dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal


class TheSmithmagicLinkFollowsTheRuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        source, target = element_move()
        self.key = element_key(source, target)
        self.hat = next(item for item in eligible_items('Hat')
                        if self.key in dict(dracorunes.variants(
                            [(structure().get_stat_by_id(stat_id).key, value)
                             for stat_id, value in item.stats], runes())))

    def card(self, draconized):
        minimal = ModelResultMinimal(
            {'hat': self.hat.id},
            {'options': dict(OPTIONS), 'char_level': 200,
             'base_stats_by_attr': dict({name: 0 for name, _key in STATS_NAMES}, AP=7, MP=3)},
            None)
        if draconized:
            minimal.dracorunes = {'hat': (self.hat.id, self.key)}
        result = model_result_from_minimal(pickle.loads(pickle.dumps(minimal)))
        params = SolutionResult(result).get_params()
        return next(item for item in params['all_items'] if item.slot == 'hat')

    def has_link(self, card):
        html = render_to_string('chardata/solution_item.html', {'item': card})
        return '?item=%d' % self.hat.id in html

    def test_the_same_card_shows_the_link_without_the_rune(self):
        card = self.card(False)
        self.assertTrue(card.mageable)
        self.assertFalse(card.dracorune_label)
        self.assertTrue(self.has_link(card))

    def test_a_draconized_card_has_no_link(self):
        card = self.card(True)
        self.assertTrue(card.dracorune_label)
        self.assertFalse(self.has_link(card))
