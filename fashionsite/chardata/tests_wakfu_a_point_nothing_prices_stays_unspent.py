from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    AP_AMULET, AP_CHEST, AP_HELM, LEVEL)
from chardata.wakfu_invented_aptitudes import AptitudeCase, add_ability, add_category

PRICED_CATEGORY, UNPRICED_CATEGORY = 2, 3
PRICED, UNPRICED = 31, 32


class TheWakfuAPointNothingPricesStaysUnspentTests(AptitudeCase):
    @classmethod
    def aptitude_rows(cls, structure):
        add_category(structure, PRICED_CATEGORY, [1, 2])
        add_category(structure, UNPRICED_CATEGORY, [1, 2, 3])
        add_ability(structure, PRICED, PRICED_CATEGORY, 0, hp=10)
        add_ability(structure, UNPRICED, UNPRICED_CATEGORY, 0, dodge=5)

    def test_the_points_of_a_category_that_buys_no_weighted_stat_stay_unspent(self):
        from fashionistapulp import wakfu_solve
        result = wakfu_solve.solve_weights(
            self.structure, level=LEVEL, weights={'hp': 1}, seconds=60)
        self.assertEqual({PRICED: 2}, result.aptitudes)
        self.assertEqual({PRICED_CATEGORY: 0, UNPRICED_CATEGORY: 3}, result.unspent)

    def test_a_result_without_a_set_does_not_share_its_aptitude_dicts(self):
        from fashionistapulp import wakfu_solve
        over_the_ap_cap = [(AP_HELM, None), (AP_AMULET, None), (AP_CHEST, None)]
        results = [wakfu_solve.solve_weights(
            self.structure, level=LEVEL, weights={'hp': 1}, seconds=60,
            locked=over_the_ap_cap) for _ in range(2)]
        self.assertIsNone(results[0].worn)
        self.assertEqual({}, results[0].aptitudes)
        self.assertEqual({}, results[0].unspent)
        self.assertIsNot(results[0].aptitudes, results[1].aptitudes)
        self.assertIsNot(results[0].unspent, results[1].unspent)
        self.assertEqual({}, wakfu_solve.WakfuResult(*[None] * 16).aptitudes)
        with self.assertRaises(TypeError):
            wakfu_solve.WakfuResult(*[None] * 16).aptitudes[PRICED] = 1
