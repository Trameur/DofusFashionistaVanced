# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""An exo and a transcendence rune on the same AP, MP or range never add up."""

from chardata.dracorune_fixtures import BetaModelTestCase, SmallModel, piece, stat_id, stat_value
from chardata.transcendence_fixtures import exo_input, exo_value, runes_on, stat_runes

EXO_STATS = ('ap', 'mp', 'range')


class RunesAndExosNeverGiveMoreThanOneApMpOrRangeTests(BetaModelTestCase):

    def model(self):
        return SmallModel([piece('Hat', {}), piece('Cloak', {})])

    def test_an_exo_plus_a_rune_on_the_same_stat_is_infeasible(self):
        for key in EXO_STATS:
            with self.subTest(key=key):
                model = self.model()
                model.setup(exo_input({key: 1000, 'vit': 1}, 2, **{'%s_exo' % key: True}))
                (column,) = stat_runes(model, key)
                column.lowBound = 1
                model.problem.pulp_vars['exo_%d' % stat_id(key)].lowBound = 1
                model.run()
                self.assertEqual('Infeasible', model.get_solved_status())

    def test_the_exo_option_and_runes_give_one_point(self):
        for key in EXO_STATS:
            with self.subTest(key=key):
                model = self.model()
                self.solve(model, exo_input({key: 1000, 'vit': 1}, 2, **{'%s_exo' % key: True}))
                self.assertEqual(1, stat_value(model, key))
                self.assertEqual(1, exo_value(model, key) + runes_on(model, key))
                self.assertIn('trans_cap_%s' % key, model.problem.pulp_lp.constraints)

    def test_runes_alone_give_one_point_on_two_pieces(self):
        for key in EXO_STATS:
            with self.subTest(key=key):
                model = self.model()
                self.solve(model, exo_input({key: 1000, 'vit': 1}, 2))
                self.assertEqual(1, stat_value(model, key))
                self.assertEqual(1, runes_on(model, key))

    def test_summon_runes_add_up(self):
        model = self.model()
        self.solve(model, exo_input({'summon': 1000}, 2))
        self.assertEqual(2, stat_value(model, 'summon'))
        self.assertEqual(2, runes_on(model, 'summon'))
