# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every exo the solver counts takes a forgeable copy no rune is on."""

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, element_move, piece,
                                         stat_id, stat_value)
from chardata.transcendence_fixtures import (exo_input, exo_value, forgeable_weapon, plain_piece,
                                              stat_runes)

EXO_STATS = ('ap', 'mp', 'range')


class EveryExoLandsOnAPieceWithoutARuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.hat, self.cloak = piece('Hat', {}), piece('Cloak', {})

    def exos(self, model):
        return sum(exo_value(model, key) for key in EXO_STATS)

    def test_runes_and_exos_share_the_forgeable_copies_worn(self):
        model = SmallModel([self.hat, self.cloak, forgeable_weapon()])
        self.solve(model, exo_input({'ap': 1000, 'mp': 1000, 'vit': 1}, 2,
                                    ap_exo=True, mp_exo=True))
        self.assertEqual(1, stat_value(model, 'ap'))
        self.assertEqual(1, stat_value(model, 'mp'))
        self.assertEqual(3, len(model.chosen_transcendences()) + self.exos(model))

    def test_a_worn_carrier_holds_its_exo_whatever_its_type(self):
        shield = plain_piece('Shield', {})
        model = SmallModel([shield, self.cloak], stat_overrides={shield.id: {stat_id('ap'): 1}})
        self.solve(model, exo_input({'ap': 1000, 'vit': 1}, 2))
        self.assertEqual(1, exo_value(model, 'ap'))
        self.assertEqual(1, len(model.chosen_transcendences()))

    def test_a_carrier_whose_exo_does_not_count_lends_no_copy(self):
        model = SmallModel([self.hat, self.cloak], stat_overrides={self.hat.id: {stat_id('ap'): 1}})
        model.setup(exo_input({'mp': 1000, 'vit': 1}, 2, mp_exo=True))
        model.problem.pulp_vars['exo_%d' % stat_id('ap')].upBound = 0
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        self.assertEqual(1, len(model.chosen_transcendences()) + exo_value(model, 'mp'))

    def test_a_draconized_copy_still_takes_an_exo(self):
        source, target = element_move()
        model = SmallModel([piece('Hat', {source: 50})])
        model.setup(exo_input({target: 10, 'ap': 1000, 'vit': 1}, 1, 1, ap_exo=True))
        for column in stat_runes(model, 'ap'):
            column.upBound = 0
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        self.assertEqual(1, len(model.chosen_dracorunes()))
        self.assertEqual(1, exo_value(model, 'ap'))
        self.assertEqual([], model.chosen_transcendences())

    def test_without_an_exo_to_count_no_pieces_row_is_written(self):
        model = SmallModel([self.hat, self.cloak])
        model.setup(exo_input({'vit': 1}, 2))
        self.assertNotIn('trans_pieces', model.problem.pulp_lp.constraints)
