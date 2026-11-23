# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece with a transcendence rune and a Dracorune lists the rune step first, then the Dracorune step."""

from django.utils.html import escape
from django.utils.translation import override

from chardata.dracorune_fixtures import OPTIONS, BetaModelTestCase
from chardata.solution_result import dracorune_change_label
from chardata.transcendence_card_fixtures import (card_of, draconizable_hat, minimal_with,
                                                  piece_in, rune_of_stat)
from chardata.translation_util import localized_stat_name
from fashionistapulp.modelresult import model_result_from_minimal

ORDER_SENTENCE = 'Transcendence rune first, then the Dracorune.'


class ATranscendedThenDraconizedCardShowsBothStepsInOrderTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.hat, self.key = draconizable_hat()
        self.rune = rune_of_stat('vit')

    def result(self, options=None, with_rune=True, with_dracorune=True):
        saved = {'hat': (self.hat.id, self.rune['id'])} if with_rune else None
        draconized = {'hat': (self.hat.id, self.key)} if with_dracorune else None
        return model_result_from_minimal(minimal_with({'hat': self.hat.id}, saved, draconized, options))

    def card(self, **kwargs):
        with override('en'):
            return card_of(self.result(**kwargs), 'hat')

    def test_the_rune_step_comes_before_the_dracorune_step(self):
        piece, page = self.card()
        rune_at = page.index('id="transcendence-hat"')
        dracorune_at = page.index('id="dracorune-hat"')
        self.assertLess(rune_at, dracorune_at)
        self.assertIn('id="transcendence-hat">1. %s' % escape(piece.transcendence_label), page)
        self.assertIn('id="dracorune-hat">2. %s' % escape(piece.dracorune_label), page)

    def test_the_order_sentence_comes_before_both_steps(self):
        _piece, page = self.card()
        self.assertLess(page.index(ORDER_SENTENCE), page.index('id="transcendence-hat"'))

    def test_the_rune_alone_carries_no_number_and_no_order_sentence(self):
        piece, page = self.card(with_dracorune=False)
        self.assertIn('id="transcendence-hat">%s' % escape(piece.transcendence_label), page)
        self.assertNotIn('id="dracorune-hat"', page)
        self.assertNotIn(ORDER_SENTENCE, page)

    def test_the_dracorune_alone_carries_no_number(self):
        piece, page = self.card(with_rune=False)
        self.assertIn('id="dracorune-hat">%s' % escape(piece.dracorune_label), page)
        self.assertNotIn('id="transcendence-hat"', page)
        self.assertNotIn(ORDER_SENTENCE, page)

    def test_each_step_names_only_its_own_lines(self):
        piece, _page = self.card()
        worn = piece_in(self.result(), 'hat')
        self.assertEqual(self.rune['bonus'], worn.undraconized_stats['vit'])
        self.assertEqual(dracorune_change_label(worn.dracorune['name'], worn.undraconized_stats, worn.stats),
                         piece.dracorune_label)
        vitality = localized_stat_name('Vitality')
        self.assertIn(vitality, piece.transcendence_label)
        self.assertNotIn(vitality, piece.dracorune_label)

    def test_the_rune_line_is_highlighted(self):
        piece, _page = self.card()
        line = next(line for line in piece.stats_lines if line.text.startswith('%d ' % self.rune['bonus']))
        self.assertEqual('#b', line.formatting)

    def test_the_exo_note_stays_off_a_transcended_card(self):
        options = dict(OPTIONS, ap_exo=True)
        piece, page = self.card(options=options)
        self.assertFalse(piece.dracorune_exo_note)
        self.assertNotIn('Forge the exo before the Dracorune', page)

    def test_the_exo_note_still_shows_under_a_card_without_the_rune(self):
        options = dict(OPTIONS, ap_exo=True)
        piece, page = self.card(options=options, with_rune=False)
        self.assertTrue(piece.dracorune_exo_note)
        self.assertIn('Forge the exo before the Dracorune', page)
