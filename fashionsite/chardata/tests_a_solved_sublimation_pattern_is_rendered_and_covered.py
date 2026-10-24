from chardata.wakfu_invented_sublimation_model import (
    BLUE, FERO_HELM, GREEN, NARROW_LEGS, RED, SublimationModelCase, state)

PATTERN = (RED, GREEN, BLUE)
STATES = {1: state(lines=[('A', 'ferocity', 0, 10, ())])}
SUBLIMATIONS = {110: (1, 1, 'normal', PATTERN)}
WEIGHTS = {'ferocity': 1, 'hp': 0.001}


class ASolvedSublimationFitsItsSocketsTests(SublimationModelCase):
    def setUp(self):
        self.invent(STATES, SUBLIMATIONS)
        self.build, self.worn = self.sublimate(WEIGHTS)

    def test_a_sublimation_worth_its_ferocity_is_placed(self):
        self.assertTrue(self.worn.sublimations)
        for _position, (ident, state_id, level, pattern) in self.worn.sublimations.items():
            self.assertEqual((110, 1, 1, PATTERN), (ident, state_id, level, pattern))

    def test_the_rendered_sockets_start_with_the_pattern_in_order(self):
        for position in self.worn.sublimations:
            colours = [socket.colour for socket in self.worn.runes[position]]
            self.assertEqual(list(PATTERN), colours[:3])

    def test_the_placed_sublimation_adds_its_ferocity_to_the_fight_total_only(self):
        placed = len(self.worn.sublimations)
        sheet = self.worn.sheet_totals['ferocity']
        self.assertEqual(sheet + 10 * placed, self.worn.totals['ferocity'])
        self.assertEqual(sheet, self.build.sheet_totals(self.worn)['ferocity'])

    def test_the_set_breaks_no_rule(self):
        self.assertEqual([], self.rules_broken(self.worn))

    def test_the_objective_is_read_back_from_the_set(self):
        self.assert_objective_is_read_back(self.build, self.worn)


class ASublimationNeedsAPieceWithEnoughSocketsTests(SublimationModelCase):
    def test_no_column_exists_for_a_position_that_holds_only_two_sockets(self):
        self.invent(STATES, SUBLIMATIONS)
        forbidden = [one for one in (1060, 1212, 9060) if self.by_id(one)]
        build, worn = self.sublimate(WEIGHTS, forbidden=forbidden)
        legs = [position for position, piece in worn.items() if piece.id == NARROW_LEGS]
        self.assertTrue(legs)
        self.assertNotIn('sb_%s_110' % legs[0], self.columns(build, 'sb_'))
        self.assertNotIn(legs[0], worn.sublimations)

    def test_the_helmet_that_holds_four_sockets_keeps_its_column(self):
        self.invent(STATES, SUBLIMATIONS)
        build, worn = self.sublimate(WEIGHTS)
        self.assertTrue(any(piece.id == FERO_HELM for piece in worn.values()))
        self.assertTrue(self.columns(build, 'sb_'))


class APatternKeepsItsColoursAgainstRunesOfOneColourTests(SublimationModelCase):
    def test_runes_of_the_blue_colour_never_outnumber_the_blue_sockets_the_pattern_leaves(self):
        self.invent(STATES, SUBLIMATIONS)
        build, worn = self.sublimate({'ferocity': 10, 'tackle': 1}, runes='optimistic')
        self.assertTrue(worn.sublimations)
        for position in worn.sublimations:
            blue = [socket for socket in worn.runes[position]
                    if socket.rune is not None and socket.colour == BLUE]
            self.assertLessEqual(len(blue), 2, position)
        self.assertEqual([], self.rules_broken(worn))
        self.assert_objective_is_read_back(build, worn)
