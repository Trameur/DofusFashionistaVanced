from fashionistapulp import wakfu_runes
from chardata.wakfu_invented_sublimation_model import (
    BLUE, GREEN, RED, SublimationModelCase, state)

PATTERN = (RED, RED, GREEN)
STATES = {1: state(lines=[('A', 'ferocity', 0, 10, ())])}
SUBLIMATIONS = {110: (1, 1, 'normal', PATTERN)}
WEIGHTS = {'ferocity': 1, 'hp': 0.001}


class TheModelAsksEachPatternColourOfItsSocketsTests(SublimationModelCase):
    def setUp(self):
        self.invent(STATES, SUBLIMATIONS)
        self.build, self.worn = self.sublimate(WEIGHTS)

    def pattern_rows(self):
        """{(position, colour): coefficient of the sublimation column} of the colour rows."""
        found = {}
        for row in self.build.problem.rows():
            if row.name.startswith('colour_') and row.name.endswith('_pattern'):
                position, colour = row.name[len('colour_'):-len('_pattern')].rsplit('_', 1)
                coefficients = [coefficient for coefficient, *_name in row.terms
                                if coefficient > 0]
                found[(position, int(colour))] = coefficients
        return found

    def test_a_placed_pattern_has_a_row_for_each_colour_it_names(self):
        positions = set(self.worn.sublimations)
        self.assertTrue(positions)
        for position in positions:
            colours = {colour for (at, colour) in self.pattern_rows() if at == position}
            self.assertEqual({RED, GREEN}, colours)

    def test_each_row_asks_as_many_sockets_as_the_pattern_has_of_that_colour(self):
        rows = self.pattern_rows()
        self.assertTrue(rows)
        for (_position, colour), coefficients in rows.items():
            self.assertEqual([PATTERN.count(colour)], coefficients, wakfu_runes.RUNE_COLOURS)

    def test_no_row_asks_for_a_colour_the_pattern_lacks(self):
        self.assertNotIn(BLUE, {colour for (_position, colour) in self.pattern_rows()})
