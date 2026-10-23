from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import LEVEL
from chardata.wakfu_invented_aptitudes import AptitudeCase, add_ability, add_category

BIG_CATEGORY, MAJOR_CATEGORY = 2, 6
CAPPED, OPEN, MAJOR = 31, 32, 41
LEGAL = {CAPPED: 3, OPEN: 2, MAJOR: 1}


class TheWakfuFixedAptitudesAreCheckedAndKeptTests(AptitudeCase):
    @classmethod
    def aptitude_rows(cls, structure):
        add_category(structure, BIG_CATEGORY, [1, 2, 3, 4, 5, 300])
        add_category(structure, MAJOR_CATEGORY, [50, 60, 70, 150])
        add_ability(structure, CAPPED, BIG_CATEGORY, 3, hp=10)
        add_ability(structure, OPEN, BIG_CATEGORY, 0, hp=4)
        add_ability(structure, MAJOR, MAJOR_CATEGORY, 2, hp=100)

    def solved(self, aptitudes, **options):
        from fashionistapulp import wakfu_solve
        return wakfu_solve.solve_weights(
            self.structure, level=LEVEL, weights={'hp': 1}, seconds=60,
            aptitudes=aptitudes, **options)

    def test_a_legal_fixed_vector_is_returned_unchanged_and_not_distributed(self):
        build, worn = self.solve({'hp': 1}, aptitudes=LEGAL)
        self.assertEqual(LEGAL, worn.aptitudes)
        self.assertEqual([], [name for name in build.problem.variable_names()
                              if name.startswith('ab_')])
        result = self.solved(dict(LEGAL))
        self.assertEqual(LEGAL, result.aptitudes)
        self.assertEqual('fixed', result.aptitude_mode)
        self.assertEqual({BIG_CATEGORY: 0, MAJOR_CATEGORY: 2}, result.unspent)

    def test_the_lines_of_a_fixed_vector_are_in_the_totals(self):
        _build, plain = self.solve({'hp': 1}, aptitudes={})
        build, worn = self.solve({'hp': 1}, aptitudes=LEGAL)
        self.assertEqual(plain, worn)
        gained = build.totals(worn)['hp'] - build.totals(plain)['hp']
        self.assertEqual(3 * 10 + 2 * 4 + 100, gained)

    def test_a_fixed_vector_is_not_improved_by_the_solver(self):
        _build, worn = self.solve({'hp': 1}, aptitudes={CAPPED: 1})
        self.assertEqual({CAPPED: 1}, worn.aptitudes)

    def test_a_fixed_vector_over_a_cap_or_a_budget_is_refused(self):
        for vector in ({CAPPED: 4}, {MAJOR: 3}, {CAPPED: 3, OPEN: 3}):
            with self.subTest(vector=vector), self.assertRaises(ValueError) as caught:
                self.solved(vector)
            self.assertIn('aptitude', str(caught.exception))

    def test_a_fixed_vector_naming_an_unknown_aptitude_is_refused(self):
        with self.assertRaises(ValueError):
            self.solved({999: 1})
        with self.assertRaises(ValueError):
            self.solve({'hp': 1}, aptitudes={999: 1})

    def test_a_fixed_vector_with_a_negative_or_fractional_point_is_refused(self):
        for points in (-1, 1.5, 'a'):
            with self.subTest(points=points), self.assertRaises(ValueError):
                self.solve({'hp': 1}, aptitudes={CAPPED: points})

    def test_an_unknown_aptitude_mode_is_refused(self):
        with self.assertRaises(ValueError):
            self.solved('everything')

    def test_the_checker_reads_the_aptitudes_of_a_set(self):
        from fashionistapulp import wakfu_legality as rule
        self.assertEqual(set(), self.rules({}, aptitudes=LEGAL))
        self.assertEqual({rule.APTITUDE_CAP}, self.rules({}, aptitudes={CAPPED: 4}))
        self.assertEqual({rule.APTITUDE_BUDGET},
                         self.rules({}, aptitudes={CAPPED: 3, OPEN: 3}))

    def test_two_rounds_with_the_same_pieces_and_other_points_have_other_keys(self):
        from fashionistapulp.wakfu_model import WakfuSet
        from fashionistapulp.wakfu_value import ModelRound
        pieces = {'HEAD': self.by_id(1001)}

        def key(points):
            return ModelRound(None, None, WakfuSet(pieces, aptitudes=points), None, 0).key

        self.assertEqual(key({CAPPED: 1}), key({CAPPED: 1}))
        self.assertNotEqual(key({CAPPED: 1}), key({CAPPED: 2}))
        self.assertNotEqual(key({}), key({OPEN: 1}))
