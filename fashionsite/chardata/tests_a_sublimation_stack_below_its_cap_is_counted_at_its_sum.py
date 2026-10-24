from chardata.wakfu_invented_sublimation_model import SublimationModelCase, state

# A state with a malus per level and a cap no position set can reach
STATES = {1: state(lines=[('A', 'hp', 500, 0, ()), ('A', 'ferocity', 0, -10, ())], cap=100)}
SUBLIMATIONS = {110: (1, 2, 'normal', ())}
WEIGHTS = {'hp': 1, 'ferocity': 1}


class AStackBelowItsCapIsCountedAtItsSumTests(SublimationModelCase):
    def setUp(self):
        self.invent(STATES, SUBLIMATIONS)
        self.build, self.worn = self.sublimate(WEIGHTS)

    def test_the_sublimation_is_placed_for_its_hit_points(self):
        self.assertEqual(1, len(self.worn.sublimations))

    def test_the_level_counted_is_the_level_placed_and_not_a_lower_one(self):
        self.assertEqual(2, self.worn.states[1].counted)

    def test_the_malus_is_charged_at_the_counted_level(self):
        gain = self.worn.totals['ferocity'] - self.worn.sheet_totals['ferocity']
        self.assertEqual(-20, gain)

    def test_the_objective_of_the_model_is_read_back_from_the_set(self):
        self.assert_objective_is_read_back(self.build, self.worn)

    def test_the_checker_agrees_with_the_counted_level(self):
        self.assertEqual([], self.rules_broken(self.worn, states=self.worn.states))
