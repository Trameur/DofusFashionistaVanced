import collections

from chardata.tests_wakfu_runes_enter_every_total_and_gate import (
    BLUE, DODGE, GREEN, MELEE, RED, TACKLE, ARuneCase)
from fashionistapulp import wakfu_legality, wakfu_runes


class ARuneSitsOnlyInASocketOfItsColourOrWhiteTests(ARuneCase):
    def rules(self, runes):
        _build, worn = self.solve_runes({'hp': 1})
        found = wakfu_legality.violations(self.structure, 100, worn, runes=runes)
        return [rule for rule, _text in found]

    def test_a_rune_in_a_socket_of_another_colour_is_flagged(self):
        self.assertEqual([wakfu_legality.RUNE_COLOUR], self.rules({'HEAD': [(GREEN, MELEE, 1)]}))
        self.assertEqual([wakfu_legality.RUNE_COLOUR], self.rules({'NECK': [(BLUE, DODGE, 1)]}))
        self.assertEqual([wakfu_legality.RUNE_COLOUR] * 2,
                         self.rules({'CHEST': [(RED, DODGE, 1), (RED, TACKLE, 1)]}))

    def test_a_rune_in_a_socket_of_its_own_colour_is_legal(self):
        runes = {'HEAD': [(RED, MELEE, 1)], 'NECK': [(GREEN, DODGE, 2)],
                 'CHEST': [(BLUE, TACKLE, 2)] * 4}
        self.assertEqual([], self.rules(runes))

    def test_a_white_socket_takes_a_rune_of_every_colour(self):
        white = wakfu_runes.WHITE
        runes = {'HEAD': [(white, MELEE, 1), (white, DODGE, 1), (white, TACKLE, 1)]}
        self.assertEqual([], self.rules(runes))

    def test_a_socket_with_no_colour_the_game_has_is_flagged(self):
        for colour in (0, 5, None, 'red'):
            with self.subTest(colour=colour):
                found = self.rules({'HEAD': [(colour, MELEE, 1)]})
                self.assertEqual(wakfu_legality.RUNE_SOCKET, found[0])

    def test_a_rune_the_table_does_not_hold_is_flagged(self):
        self.assertEqual([wakfu_legality.RUNE_UNKNOWN], self.rules({'HEAD': [(RED, 123456, 1)]}))

    def test_a_solved_set_puts_every_rune_in_a_socket_of_its_own_colour_and_none_white(self):
        _build, worn = self.solve_runes({'melee_dmg': 1, 'hp': 1}, minimums={'dodge': 20})
        filled = self.socket_values(worn)
        self.assertEqual({RED, GREEN}, {socket.colour for socket in filled})
        for socket in filled:
            self.assertEqual(self.structure.shards[socket.rune].colour, socket.colour)
            self.assertIn(socket.colour, wakfu_runes.RUNE_COLOURS)
            self.assertNotEqual(wakfu_runes.WHITE, socket.colour)

    def test_the_colours_of_a_set_are_counted_per_position(self):
        _build, worn = self.solve_runes({'melee_dmg': 1})
        expected = collections.Counter({(position, RED): 4 for position in worn.runes})
        self.assertEqual(expected, wakfu_runes.colours(worn.runes))
        triples = {position: [(socket.colour, socket.rune, socket.tier) for socket in sockets
                              if socket.rune is not None]
                   for position, sockets in worn.runes.items()}
        self.assertEqual(expected, wakfu_runes.colours(triples))
        self.assertEqual(collections.Counter(), wakfu_runes.colours({}))
        self.assertEqual(collections.Counter(), wakfu_runes.colours(None))

    def test_the_model_offers_the_columns_of_a_colour_for_the_colour_rows(self):
        build = self.build({'melee_dmg': 1})
        build.build()
        red = build.rune_colour_terms('HEAD', RED)
        self.assertTrue(red)
        self.assertEqual([], build.rune_colour_terms('HEAD', BLUE))
        self.assertEqual([], build.rune_colour_terms('SECOND_WEAPON', RED))
        self.assertEqual({(1, 'rn')}, {(number, category) for number, category, _name in red})
