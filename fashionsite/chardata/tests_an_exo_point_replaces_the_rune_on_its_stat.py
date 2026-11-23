# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A transcendence rune on a stat the page already gives an exo point is swapped for that point, so the page counts it once."""

from fashionistapulp.modelresult import exo_points_shown, model_result_from_minimal

from chardata.dracorune_fixtures import BetaModelTestCase, SmallModel, piece, stat_id
from chardata.transcendence_fixtures import exo_input, stat_runes

WEIGHTS = {'ap': 1000, 'vit': 1}
OPTIONS = {'ap_exo': False, 'range_exo': False, 'mp_exo': False}


class AnExoPointReplacesTheRuneOnItsStatTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.hat = piece('Hat', {'vit': 100})
        self.carrier = piece('Amulet', {'vit': 10})

    def solved(self, ap_exo, overrides=None, items=None):
        """(model, minimal result) with an AP rune forced onto the hat."""
        model = SmallModel(items or [self.hat], (), overrides)
        model.setup(exo_input(WEIGHTS, 4, ap_exo=ap_exo))
        (column,) = stat_runes(model, 'ap')
        model.problem.pulp_lp.addConstraint(column >= 1, 'force_the_rune')
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        self.assertEqual(1, len(model.chosen_transcendences()))
        del model.problem.pulp_lp.constraints['force_the_rune']
        return model, model.get_result_minimal()

    def lp_ap(self, model):
        return model.problem.pulp_vars['stat_%d' % stat_id('ap')].varValue

    def test_the_ap_exo_option_leaves_no_ap_rune_and_the_page_counts_ap_once(self):
        model, result = self.solved(True)
        self.assertIsNone(result.transcendences)
        page = model_result_from_minimal(result)
        self.assertEqual(self.lp_ap(model), page.get_stats_total()['ap'])

    def test_a_worn_ap_carrier_leaves_no_ap_rune(self):
        overrides = {self.carrier.id: {stat_id('ap'): 1}}
        model, result = self.solved(False, overrides, [self.hat, self.carrier])
        self.assertEqual(self.carrier.id, result.item_per_slot['amulet'])
        self.assertIsNone(result.transcendences)

    def test_without_the_option_the_ap_rune_stays(self):
        model, result = self.solved(False)
        ((_number, rune_id),) = model.chosen_transcendences()
        self.assertEqual({'hat': (self.hat.id, rune_id)}, result.transcendences)

    def test_the_page_adds_the_same_exo_points_as_before(self):
        table = (
            (dict(OPTIONS), (), set()),
            (dict(OPTIONS, ap_exo=True), (), {'ap'}),
            (dict(OPTIONS, range_exo=True), (), {'range'}),
            (dict(OPTIONS, mp_exo=True), (), {'mp'}),
            (dict(OPTIONS, mp_exo='gelano'), (), set()),
            (dict(OPTIONS), ('ap',), {'ap'}),
            (dict(OPTIONS), ('range', 'mp'), {'range', 'mp'}),
            (dict(OPTIONS, ap_exo=True, range_exo=True, mp_exo=True), ('ap',), {'ap', 'range', 'mp'}),
            ({'ap_exo': True, 'mp_exo': False}, (), {'ap'}),
        )
        for options, worn, expected in table:
            with self.subTest(options=options, worn=worn):
                self.assertEqual(expected, exo_points_shown(options, set(worn)))
