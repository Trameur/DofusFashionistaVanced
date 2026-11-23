# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build saved before transcendence runes existed loads with no rune and the totals it always had."""

from chardata.dracorune_fixtures import BetaModelTestCase
from chardata.transcendence_card_fixtures import lines_of, minimal_with, piece_in, plain_pieces, rune_of_stat
from fashionistapulp.modelresult import model_result_from_minimal


class ABuildSavedBeforeTranscendencesLoadsAsBeforeTests(BetaModelTestCase):

    def test_a_minimal_without_the_attribute_loads_with_no_rune_and_the_same_totals(self):
        rune = rune_of_stat('vit')
        hat = plain_pieces('Hat', 'beta', 1, rune)[0]
        old = minimal_with({'hat': hat.id})
        self.assertNotIn('transcendences', old.__dict__)
        result = model_result_from_minimal(old)
        self.assertIsNone(result.transcendences)
        worn = piece_in(result, 'hat')
        self.assertIsNone(worn.transcendence_rune)
        self.assertIsNone(worn.untranscended_stats)
        self.assertEqual(lines_of(hat), worn.stats)
        self.assertEqual(result.get_stats_total(),
                         model_result_from_minimal(minimal_with({'hat': hat.id}, None)).get_stats_total())
