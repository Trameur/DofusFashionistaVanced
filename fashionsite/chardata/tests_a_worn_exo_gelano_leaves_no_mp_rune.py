# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build that wears the exo Gelano gets its MP from it and takes no MP rune."""

from copy import deepcopy

from chardata.dracorune_fixtures import BetaModelTestCase, SmallModel, bare, piece, stat_value, structure
from chardata.transcendence_fixtures import exo_input, runes_on


class AWornExoGelanoLeavesNoMpRuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.gelano = bare(deepcopy(structure().get_item_by_name('Gelano (#1)')),
                           {'ap': 1, 'mp': 1})
        self.pieces = [self.gelano, piece('Hat', {}), piece('Cloak', {})]

    def worn(self, model):
        return model.problem.pulp_vars['x_%s' % self.gelano.id].varValue

    def test_the_exo_gelano_is_no_candidate(self):
        self.assertNotIn(self.gelano.id, SmallModel(self.pieces).transcendence_candidates)

    def test_a_build_wearing_the_exo_gelano_takes_no_mp_rune(self):
        model = SmallModel(self.pieces)
        self.solve(model, exo_input({'mp': 1000, 'ap': 500, 'vit': 1}, 2, mp_exo='gelano'))
        self.assertEqual(1, self.worn(model))
        self.assertEqual(0, runes_on(model, 'mp'))
        self.assertEqual(1, stat_value(model, 'mp'))

    def test_without_the_gelano_option_an_mp_rune_gives_the_point(self):
        model = SmallModel(self.pieces)
        self.solve(model, exo_input({'mp': 1000, 'ap': 500, 'vit': 1}, 2, mp_exo=False))
        self.assertEqual(0, self.worn(model))
        self.assertEqual(1, runes_on(model, 'mp'))
        self.assertNotIn('trans_gelano', model.problem.pulp_lp.constraints)
