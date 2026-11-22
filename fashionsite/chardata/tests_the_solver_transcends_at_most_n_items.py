# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solver puts at most N transcendence runes, one per worn copy, the biggest its line leaves room for."""

from unittest import mock

from fashionistapulp.model import Model
from fashionistapulp.transcendence_terms import rune_fits

from chardata.dracorune_fixtures import NOT_ASKED, BetaModelTestCase, SmallModel, piece, stat_value
from chardata.transcendence_fixtures import (beta_rune, plain_piece, trans_columns,
                                             trans_input, with_transcendence)

SEVEN = (('Hat', 0), ('Cloak', 0), ('Amulet', 0), ('Ring', 0), ('Ring', 1), ('Belt', 0),
         ('Boots', 0))


class TheSolverTranscendsAtMostNItemsTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.pieces = [piece(type_name, {}, number) for type_name, number in SEVEN]
        self.weapon = plain_piece('Weapon', {})
        self.shield = plain_piece('Shield', {})

    def model(self, pieces=None):
        return SmallModel(list(pieces or self.pieces) + [self.weapon, self.shield])

    def test_the_build_takes_exactly_n_runes_up_to_its_seven_pieces(self):
        for allowed in (1, 2, 7, 9):
            with self.subTest(allowed=allowed):
                model = self.model()
                self.solve(model, trans_input({'vit': 1}, allowed))
                taken = min(allowed, 7)
                self.assertEqual(taken, len(model.chosen_transcendences()))
                self.assertEqual(taken * beta_rune('vit', 3)['bonus'], stat_value(model, 'vit'))
                total = model.problem.pulp_lp.constraints['trans_total']
                self.assertEqual(allowed, -total.constant)

    def test_weapons_and_shields_never_take_one(self):
        model = self.model()
        model.setup(trans_input({'vit': 1}, 9))
        members = {item_id for ids in model.transcendence_classes.values() for item_id in ids}
        self.assertEqual({item.id for item in self.pieces}, members)
        self.assertNotIn(self.weapon.id, model.transcendence_candidates)
        self.assertNotIn(self.shield.id, model.transcendence_candidates)

    def test_each_piece_takes_the_biggest_rune_its_line_leaves_room_for(self):
        lines = (('Hat', 0), ('Cloak', 150), ('Amulet', 250), ('Belt', 400))
        pieces = [piece(type_name, {'vit': line}) for type_name, line in lines]
        rata, pata, ta = (beta_rune('vit', rank) for rank in (3, 2, 1))
        self.assertTrue(rune_fits(rata, 0))
        self.assertTrue(rune_fits(pata, 150) and not rune_fits(rata, 150))
        self.assertTrue(rune_fits(ta, 250) and not rune_fits(pata, 250))
        self.assertFalse(rune_fits(ta, 400))
        model = self.model(pieces)
        self.solve(model, trans_input({'vit': 1}, 4))
        self.assertEqual({rata['id'], pata['id'], ta['id']},
                         {rune_id for _number, rune_id in model.chosen_transcendences()})
        self.assertEqual(3, len(model.chosen_transcendences()))
        self.assertEqual(800 + rata['bonus'] + pata['bonus'] + ta['bonus'],
                         stat_value(model, 'vit'))
        self.assertEqual(3, len(model.transcendence_classes))
        model = self.model(pieces)
        self.solve(model, trans_input({'vit': 1}, 2))
        self.assertEqual({rata['id'], pata['id']},
                         {rune_id for _number, rune_id in model.chosen_transcendences()})

    def test_a_doubled_ring_takes_a_rune_on_each_copy(self):
        ring = piece('Ring', {})
        model = SmallModel([ring])
        self.solve(model, trans_input({'vit': 1}, 2))
        self.assertEqual(2, model.problem.pulp_vars['x_%s' % str(ring.id).replace('-', '_')].varValue)
        self.assertEqual(2, len(model.chosen_transcendences()))

    def test_a_retry_on_a_changed_objective_keeps_the_runes_and_their_count(self):
        model = self.model()
        model.setup(trans_input({'vit': 1}, 2))
        before = trans_columns(model)
        original = Model._add_transcendence_terms
        with mock.patch.object(Model, '_add_transcendence_terms', autospec=True,
                               side_effect=original) as rebuilt:
            model.run(change_of=True)
        self.assertEqual(1, rebuilt.call_count)
        self.assertEqual('Optimal', model.get_solved_status())
        self.assertEqual(before, trans_columns(model))
        self.assertTrue(before)
        total = model.problem.pulp_lp.constraints['trans_total']
        self.assertEqual(2, -total.constant)
        self.assertEqual(2, len(model.chosen_transcendences()))

    def test_no_option_or_an_off_value_puts_no_rune(self):
        for allowed in (NOT_ASKED, 0, None, False, True, '2', -1, 2.0):
            with self.subTest(allowed=allowed):
                model = self.model()
                self.solve(model, with_transcendence(trans_input({'vit': 1}), allowed))
                self.assertEqual([], trans_columns(model))
                self.assertNotIn('trans_total', model.problem.pulp_lp.constraints)
                self.assertEqual(0, stat_value(model, 'vit'))
                self.assertEqual([], model.chosen_transcendences())
