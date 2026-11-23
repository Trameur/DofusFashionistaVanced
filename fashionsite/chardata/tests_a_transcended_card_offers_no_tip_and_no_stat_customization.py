# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A transcended card suggests no further rune and offers no stat customization; a build solved with the option suggests none anywhere."""
import os

from django.conf import settings

from chardata.dracorune_fixtures import OPTIONS, BetaModelTestCase
from chardata.solution_result import SolutionResult, attach_transcendence
from chardata.transcendence_card_fixtures import (card_of, minimal_with, plain_pieces,
                                                  rune_of_stat)
from fashionistapulp.model import TRANSCENDENCE_OPTION
from fashionistapulp.modelresult import model_result_from_minimal

WEIGHTS = {'vit': 1, 'int': 10}
BUTTON = 'id="stat-override-btn-sol-hat"'


class ATranscendedCardOffersNoTipAndNoStatCustomizationTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.rune = rune_of_stat('vit')
        self.hat = plain_pieces('Hat', 'beta', 1, self.rune)[0]

    def result(self, rune=True, options=None):
        saved = {'hat': (self.hat.id, self.rune['id'])} if rune else None
        return model_result_from_minimal(minimal_with({'hat': self.hat.id}, saved, options=options))

    def params_tip(self, result, weights=WEIGHTS):
        params = SolutionResult(result, weights=weights).get_params()
        return next(item for item in params['all_items'] if item.slot == 'hat').transcendence

    def test_a_plain_piece_gets_its_tip(self):
        self.assertTrue(self.params_tip(self.result(rune=False)))

    def test_the_tip_is_off_on_a_transcended_piece(self):
        self.assertIsNone(self.params_tip(self.result()))

    def test_the_tip_is_off_everywhere_when_the_build_was_solved_with_the_option(self):
        options = dict(OPTIONS, **{TRANSCENDENCE_OPTION: 2})
        self.assertIsNone(self.params_tip(self.result(rune=False, options=options)))

    def test_the_tip_stays_on_when_the_option_is_off(self):
        for allowed in (0, None):
            with self.subTest(allowed=allowed):
                options = dict(OPTIONS, **{TRANSCENDENCE_OPTION: allowed})
                self.assertTrue(self.params_tip(self.result(rune=False, options=options)))

    def test_the_attach_function_hides_the_tip_when_told_the_build_used_runes(self):
        piece = next(item for item in self.result(rune=False).item_list if item.slot == 'hat')
        attach_transcendence(piece, WEIGHTS, solved_with_runes=True)
        self.assertIsNone(piece.transcendence)
        attach_transcendence(piece, WEIGHTS)
        self.assertTrue(piece.transcendence)

    def test_a_transcended_card_has_no_customize_stats_button(self):
        _piece, page = card_of(self.result(), 'hat')
        self.assertNotIn(BUTTON, page)

    def test_a_plain_card_keeps_its_customize_stats_button(self):
        _piece, page = card_of(self.result(rune=False), 'hat')
        self.assertIn(BUTTON, page)

    def test_the_page_script_keeps_its_guard_line_before_rebuilding_stats(self):
        path = os.path.join(settings.BASE_DIR, 'chardata', 'templates', 'chardata', 'solution.html')
        with open(path, encoding='utf-8') as page:
            script = page.read()
        self.assertIn('if (!$("#dracorune-" + slot).length && !$("#transcendence-" + slot).length) '
                      'rebuildStatsDisplay(', script)
