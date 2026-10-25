import math

from chardata.tests_a_guarded_epic_state_is_read_on_the_sheet_totals import BASE_HP, WEIGHTS
from chardata.wakfu_invented_sublimation_model import SublimationModelCase, state


class AConversionOfASmallShareIsFlooredInTheSolvedModelTests(SublimationModelCase):
    def moved(self, share):
        self.invent({6: state(conversions=[('hp', 'ferocity', share, 0, 1, ())])},
                    {140: (6, 1, 'normal', ())})
        build, worn = self.sublimate(WEIGHTS)
        return build, worn, worn.totals['ferocity'] - worn.sheet_totals['ferocity']

    def test_each_share_moves_the_floor_of_its_share_of_the_hit_points(self):
        for share in (0.5, 0.37, 0.07):
            with self.subTest(share=share):
                build, worn, gain = self.moved(share)
                self.assertTrue(worn.sublimations)
                self.assertEqual(math.floor((worn.sheet_totals['hp'] + BASE_HP) * share), gain)
                self.assertGreater(gain, 0)
                self.assertEqual([], self.rules_broken(worn))
                self.assert_objective_is_read_back(build, worn)
