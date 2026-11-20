# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build that wears a rune and an exo says under the draconized card to forge the exo first."""

import pickle
from unittest import mock

from django.template.loader import render_to_string
from django.utils.translation import gettext, override

from chardata.dracorune_fixtures import (OPTIONS, BetaModelTestCase, eligible_items,
                                         element_key, element_move, runes, structure)
from chardata.solution_result import SolutionResult
from fashionistapulp import dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal

NOTE = 'Forge the exo before the Dracorune: it prevents any further smithmagic on the item.'


class TheExoNoteShowsUnderADraconizedCardTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        source, target = element_move()
        self.key = element_key(source, target)
        self.hat, self.cloak = (
            next(item for item in eligible_items(type_name)
                 if self.key in dict(dracorunes.variants(
                     [(structure().get_stat_by_id(stat_id).key, value)
                      for stat_id, value in item.stats], runes())))
            for type_name in ('Hat', 'Cloak'))

    def cards(self, ap_exo=False, stat_overrides=None, draconized=True, exo_assumed=None):
        options = dict(OPTIONS, ap_exo=ap_exo)
        minimal = ModelResultMinimal(
            {'hat': self.hat.id, 'cloak': self.cloak.id},
            {'options': options, 'char_level': 200,
             'base_stats_by_attr': dict({name: 0 for name, _key in STATS_NAMES}, AP=7, MP=3)},
            None)
        if draconized:
            minimal.dracorunes = {'hat': (self.hat.id, self.key)}
        if exo_assumed is not None:
            minimal.exo_assumed = exo_assumed
        result = model_result_from_minimal(pickle.loads(pickle.dumps(minimal)), stat_overrides)
        if exo_assumed is not None:
            result.place_assumed_exos()
        params = SolutionResult(result).get_params()
        return {item.slot: item for item in params['all_items'] if item.item_added}

    def note_shown(self, card):
        return NOTE in render_to_string('chardata/solution_dracorune.html', {'item': card})

    def test_an_exo_option_puts_the_note_under_the_draconized_card_only(self):
        cards = self.cards(ap_exo=True)
        self.assertTrue(cards['hat'].dracorune_exo_note)
        self.assertTrue(self.note_shown(cards['hat']))
        self.assertFalse(cards['cloak'].dracorune_exo_note)
        self.assertFalse(self.note_shown(cards['cloak']))

    def test_an_exo_worn_on_another_piece_puts_the_note_too(self):
        ap = structure().get_stat_by_key('ap').id
        worn = dict(self.cloak.stats).get(ap, 0) + 1
        cards = self.cards(stat_overrides={self.cloak.id: {ap: worn}})
        self.assertEqual({'ap': worn}, cards['cloak'].exo_overrides)
        self.assertTrue(self.note_shown(cards['hat']))

    def test_an_assumed_exo_on_a_worn_piece_puts_the_note_too(self):
        with mock.patch.object(structure().get_item_by_id(self.cloak.id), 'forgeable', True):
            cards = self.cards(exo_assumed={'ap': 1, 'mp': 0, 'range': 0})
        self.assertEqual({'hat': None, 'cloak': 'ap'},
                         {slot: card.assumed_exo for slot, card in cards.items()})
        self.assertFalse(any(getattr(card, 'exo_overrides', None) for card in cards.values()))
        self.assertTrue(cards['hat'].dracorune_exo_note)
        self.assertTrue(self.note_shown(cards['hat']))

    def test_no_exo_no_note(self):
        cards = self.cards()
        self.assertTrue(cards['hat'].dracorune_label)
        self.assertFalse(self.note_shown(cards['hat']))

    def test_no_rune_no_note(self):
        cards = self.cards(ap_exo=True, draconized=False)
        self.assertFalse(any(self.note_shown(card) for card in cards.values()))

    def test_the_note_reads_in_every_language(self):
        for language in ('fr', 'de', 'es', 'pt'):
            with override(language):
                card = self.cards(ap_exo=True)['hat']
                page = render_to_string('chardata/solution_dracorune.html', {'item': card})
                self.assertNotEqual(NOTE, gettext(NOTE), language)
                self.assertIn(gettext(NOTE).split(':')[0], page)
