from django.test import SimpleTestCase

from chardata.wakfu_invented_sublimations import (
    BLUE, GREEN, RED, WHITE, Piece, Structure, block, socket_row, state, use_block)
from fashionistapulp import wakfu_legality, wakfu_runes, wakfu_sublimations

LEVEL = 100
PATTERN = (RED, GREEN, BLUE)
SUBLIMATIONS = {
    100: (1, 1, 'normal', PATTERN),
    101: (1, 1, 'normal', (RED, 0, BLUE)),
    102: (1, 1, 'normal', (GREEN,)),
}
RUNE = wakfu_runes.Rune(900, RED, 3, (), (1,), (0,), [(1, 1, 1, 10, 0)], {})
GREEN_RUNE = wakfu_runes.Rune(901, GREEN, 3, (), (1,), (0,), [(1, 1, 1, 10, 0)], {})


def rules(structure, worn, **given):
    found = wakfu_legality.violations(structure, LEVEL, worn, class_id=1, **given)
    return [rule for rule, _text in found]


class ThePatternFitsTheSocketsInOrderTests(SimpleTestCase):
    def test_the_pattern_sits_at_offset_zero_or_one_of_four_sockets(self):
        self.assertTrue(wakfu_sublimations.pattern_fits(PATTERN, (RED, GREEN, BLUE, RED)))
        self.assertTrue(wakfu_sublimations.pattern_fits(PATTERN, (BLUE, RED, GREEN, BLUE)))

    def test_the_pattern_does_not_wrap_past_the_last_socket(self):
        self.assertFalse(wakfu_sublimations.pattern_fits(PATTERN, (GREEN, BLUE, RED)))
        self.assertFalse(wakfu_sublimations.pattern_fits(PATTERN, (BLUE, RED, GREEN)))

    def test_three_sockets_in_the_wrong_order_do_not_hold_it(self):
        self.assertFalse(wakfu_sublimations.pattern_fits(PATTERN, (BLUE, GREEN, RED)))

    def test_two_sockets_cannot_hold_a_pattern_of_three(self):
        self.assertFalse(wakfu_sublimations.pattern_fits(PATTERN, (RED, GREEN)))
        self.assertFalse(wakfu_sublimations.pattern_fits(PATTERN, ()))

    def test_a_white_socket_stands_for_any_colour(self):
        self.assertTrue(wakfu_sublimations.pattern_fits(PATTERN, (RED, WHITE, BLUE)))
        self.assertTrue(wakfu_sublimations.pattern_fits(PATTERN, (WHITE, WHITE, WHITE)))
        self.assertFalse(wakfu_sublimations.pattern_fits(PATTERN, (RED, WHITE, GREEN)))

    def test_a_pattern_colour_of_zero_matches_any_socket(self):
        pattern = (RED, 0, BLUE)
        self.assertTrue(wakfu_sublimations.pattern_fits(pattern, (RED, GREEN, BLUE)))
        self.assertTrue(wakfu_sublimations.pattern_fits(pattern, (RED, RED, BLUE)))
        self.assertFalse(wakfu_sublimations.pattern_fits(pattern, (RED, RED, RED)))

    def test_an_empty_pattern_fits_every_row(self):
        self.assertTrue(wakfu_sublimations.pattern_fits((), ()))
        self.assertTrue(wakfu_sublimations.pattern_fits((), (RED,)))

    def test_the_colours_a_pattern_needs_leave_out_its_jokers(self):
        self.assertEqual({RED: 1, BLUE: 1}, dict(wakfu_sublimations.colour_needs((RED, 0, BLUE))))
        self.assertEqual({GREEN: 2}, dict(wakfu_sublimations.colour_needs((GREEN, GREEN))))
        self.assertEqual({}, dict(wakfu_sublimations.colour_needs(())))


class TheCheckerReadsThePatternOnTheRenderedSocketsTests(SimpleTestCase):
    def setUp(self):
        self.structure = Structure([Piece(10, 1, sockets=4), Piece(11, 2, sockets=2)])
        self.structure.shards = {900: RUNE, 901: GREEN_RUNE}
        self.block = block(states={1: state(lines=[('A', 'dmg_in_percent', 0, 5, ())], cap=2)},
                           sublimations=SUBLIMATIONS)
        use_block(self, self.block)

    def check(self, ident, colours, position='HEAD', piece=10):
        return rules(self.structure, {position: self.structure.pieces[piece]},
                     sublimations={position: ident}, runes={position: socket_row(*colours)})

    def test_every_chosen_pattern_that_fits_its_rendered_sockets_is_legal(self):
        for ident, row in ((100, (RED, GREEN, BLUE, RED)), (100, (WHITE, RED, GREEN, BLUE)),
                           (101, (RED, RED, BLUE, GREEN)), (102, (BLUE, BLUE, GREEN, RED))):
            with self.subTest(ident=ident, row=row):
                self.assertEqual([], self.check(ident, row))

    def test_a_pattern_out_of_order_is_flagged(self):
        self.assertEqual([wakfu_legality.SUBLIMATION_PATTERN],
                         self.check(100, (BLUE, GREEN, RED, RED)))

    def test_a_white_socket_in_the_middle_keeps_the_set_legal(self):
        self.assertEqual([], self.check(100, (RED, WHITE, BLUE, BLUE)))

    def test_a_piece_with_two_sockets_holds_no_pattern_of_three(self):
        self.assertEqual([wakfu_legality.SUBLIMATION_SOCKETS],
                         self.check(100, (RED, GREEN), position='NECK', piece=11))

    def test_a_piece_with_no_rendered_sockets_holds_no_pattern(self):
        found = rules(self.structure, {'HEAD': self.structure.pieces[10]},
                      sublimations={'HEAD': 100}, runes={})
        self.assertEqual([wakfu_legality.SUBLIMATION_PATTERN], found)

    def test_a_red_rune_in_a_green_pattern_socket_is_flagged_as_a_rune_colour(self):
        found = rules(self.structure, {'HEAD': self.structure.pieces[10]},
                      sublimations={'HEAD': 102},
                      runes={'HEAD': [(GREEN, 900, 1)]})
        self.assertEqual([wakfu_legality.RUNE_COLOUR], found)

    def test_a_rune_in_the_colour_of_its_pattern_socket_is_legal(self):
        found = rules(self.structure, {'HEAD': self.structure.pieces[10]},
                      sublimations={'HEAD': 102}, runes={'HEAD': [(GREEN, 901, 1)]})
        self.assertEqual([], found)

    def test_a_sublimation_the_tables_do_not_hold_is_flagged(self):
        self.assertEqual([wakfu_legality.SUBLIMATION_UNKNOWN],
                         self.check(999, (RED, GREEN, BLUE, RED)))

    def test_a_sublimation_where_nothing_is_worn_is_flagged(self):
        found = rules(self.structure, {'HEAD': self.structure.pieces[10]},
                      sublimations={'NECK': 100}, runes={})
        self.assertEqual([wakfu_legality.SUBLIMATION_SOCKETS], found)

    def test_two_normal_sublimations_on_one_piece_are_flagged(self):
        found = rules(self.structure, {'HEAD': self.structure.pieces[10]},
                      sublimations={'HEAD': [100, 102]},
                      runes={'HEAD': socket_row(RED, GREEN, BLUE, RED)})
        self.assertEqual([wakfu_legality.SUBLIMATION_PER_ITEM], found)

    def test_a_set_with_no_sublimation_argument_is_checked_as_before(self):
        found = rules(self.structure, {'HEAD': self.structure.pieces[10]})
        self.assertEqual([], found)
