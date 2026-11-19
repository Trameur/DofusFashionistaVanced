# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece whose rune variants cannot be built is logged by id and solved without runes."""

from unittest import mock

from fashionistapulp import dracorune_terms, dracorunes

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece, stat_value)

LINE = 40


class APieceWhoseRunesFailTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.broken = piece('Hat', {self.source: 2 * LINE, 'vit': LINE})
        self.sound = piece('Cloak', {self.source: LINE})
        build = dracorune_terms.item_variants

        def failing(item, runes, structure):
            if item.id == self.broken.id:
                raise ValueError('variant power has two different results')
            return build(item, runes, structure)

        with mock.patch.object(dracorune_terms, 'item_variants', failing), \
                self.assertLogs('fashionistapulp.model', 'ERROR') as logged:
            self.model = SmallModel([self.broken, self.sound])
        self.logged = logged.output

    def test_the_failure_is_logged_with_the_item_id(self):
        self.assertEqual(1, len(self.logged))
        self.assertIn(str(self.broken.id), self.logged[0])

    def test_the_piece_gets_no_variant_and_the_others_keep_theirs(self):
        self.assertNotIn(self.broken.id, self.model.dracorune_candidates)
        self.assertIn(self.sound.id, self.model.dracorune_candidates)

    def test_the_build_is_solved_with_the_runes_of_the_other_pieces(self):
        result = self.solve(self.model, build_input({self.target: 1, 'vit': 1}, 2))
        self.assertEqual(self.broken.id, result.item_per_slot['hat'])
        self.assertEqual({'cloak': (self.sound.id, element_key(self.source, self.target))},
                         result.dracorunes)
        self.assertEqual(LINE, stat_value(self.model, self.target))


class ARunesFileTheModuleCannotReadTests(BetaModelTestCase):

    def build_with(self, error):
        hat = piece('Hat', {'vit': 10})

        def unreadable(version):
            raise error

        with mock.patch.object(dracorunes, 'load_runes', unreadable),                 self.assertLogs('fashionistapulp.model', 'ERROR') as logged:
            model = SmallModel([hat])
        return model, logged.output

    def test_an_unknown_rounding_leaves_the_model_without_runes(self):
        for error in (KeyError('bankers'), TypeError('keep'), ValueError('shape')):
            model, logged = self.build_with(error)
            self.assertEqual({}, model.dracorune_candidates)
            self.assertEqual(1, len(logged))

    def test_the_model_is_still_solved_when_a_rune_is_asked_for(self):
        model, _logged = self.build_with(KeyError('bankers'))
        result = self.solve(model, build_input({'vit': 1}, 2))
        self.assertFalse(result.dracorunes)
