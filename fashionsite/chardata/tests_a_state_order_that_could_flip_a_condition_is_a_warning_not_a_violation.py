from django.test import SimpleTestCase

from chardata.wakfu_invented_sublimations import (
    EPIC_RARITY, Piece, Structure, block, socket_row, state, use_block)
from fashionistapulp import wakfu_legality

# State 1 gives 15 final damage while AP is 10 or less; state 2 gives one AP to everyone
STATES = {
    1: state(lines=[('B', 'final_dmg_in_percent', 15, 0, (0,))],
             conditions=[('GetCharacMax', 'ap', '<=', 10)], family='B'),
    2: state(lines=[('A', 'ap', 1, 0, ())]),
    3: state(lines=[('A', 'hp', 5, 0, ())]),
}
SUBLIMATIONS = {10: (1, 1, 'epic', ()), 11: (2, 1, 'normal', ()), 12: (3, 1, 'normal', ())}


class AnotherCountedLineOnTheSameKeyWarnsOfTheOrderTests(SimpleTestCase):
    def setUp(self):
        use_block(self, block(states=STATES, sublimations=SUBLIMATIONS))

    def check(self, ap, normal):
        epic = Piece(10, 1, rarity=EPIC_RARITY, stats=[(1, ap - 6)])
        structure = Structure([epic], bases={1: {'ap': 6}})
        arguments = dict(class_id=1, specials={'HEAD': 10}, sublimations={'HEAD': normal},
                         runes={'HEAD': socket_row()})
        found = wakfu_legality.violations(structure, 100, {'HEAD': epic}, **arguments)
        return ([rule for rule, _text in found],
                [rule for rule, _text in wakfu_legality.warnings(
                    structure, 100, {'HEAD': epic}, **arguments)])

    def test_a_line_on_the_key_of_the_condition_that_flips_it_is_a_warning(self):
        violations, warnings = self.check(10, 11)
        self.assertEqual([], violations)
        self.assertEqual([wakfu_legality.ORDER], warnings)

    def test_a_line_that_leaves_the_condition_as_it_is_gives_no_warning(self):
        self.assertEqual(([], []), self.check(8, 11))

    def test_a_line_on_another_key_gives_no_warning(self):
        self.assertEqual(([], []), self.check(10, 12))

    def test_a_set_with_no_sublimation_argument_has_nothing_to_warn_of(self):
        epic = Piece(10, 1, rarity=EPIC_RARITY)
        structure = Structure([epic], bases={1: {'ap': 6}})
        self.assertEqual([], wakfu_legality.warnings(structure, 100, {'HEAD': epic}, class_id=1))

    def test_a_warning_is_a_pair_of_the_order_rule_and_a_text(self):
        epic = Piece(10, 1, rarity=EPIC_RARITY, stats=[(1, 4)])
        structure = Structure([epic], bases={1: {'ap': 6}})
        found = wakfu_legality.warnings(
            structure, 100, {'HEAD': epic}, class_id=1, specials={'HEAD': 10},
            sublimations={'HEAD': 11}, runes={'HEAD': socket_row()})
        self.assertEqual(1, len(found))
        self.assertEqual(wakfu_legality.ORDER, found[0][0])
        self.assertIn('state 1', found[0][1])
