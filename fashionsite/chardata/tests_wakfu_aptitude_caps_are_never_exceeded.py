from chardata.wakfu_invented_aptitudes import AptitudeCase, add_ability, add_category

BIG_CATEGORY, MAJOR_CATEGORY = 2, 6
CAPPED, OPEN, MAJOR = 31, 32, 41


class TheWakfuAptitudeCapsAreNeverExceededTests(AptitudeCase):
    @classmethod
    def aptitude_rows(cls, structure):
        add_category(structure, BIG_CATEGORY, [1, 2, 3, 4, 5, 300])
        add_category(structure, MAJOR_CATEGORY, [50, 60, 70, 150])
        add_ability(structure, CAPPED, BIG_CATEGORY, 3, hp=10)
        add_ability(structure, OPEN, BIG_CATEGORY, 0, hp=4)
        add_ability(structure, MAJOR, MAJOR_CATEGORY, 2, hp=100)

    def test_a_variable_is_bounded_by_the_cap_of_the_ability_or_the_budget(self):
        build, _worn = self.solve({'hp': 1})
        spec = build.problem.variable_spec
        self.assertEqual((0, 3), tuple(spec('ab_%d' % CAPPED))[:2])
        self.assertEqual((0, 5), tuple(spec('ab_%d' % OPEN))[:2])
        self.assertEqual((0, 2), tuple(spec('ab_%d' % MAJOR))[:2])

    def test_the_points_of_a_solve_stop_at_each_cap_and_each_budget(self):
        _build, worn = self.solve({'hp': 1})
        self.assertEqual({CAPPED: 3, OPEN: 2, MAJOR: 2}, worn.aptitudes)

    def test_the_checker_flags_one_point_over_a_cap_and_one_over_a_budget(self):
        from fashionistapulp import wakfu_legality as rule
        check = rule.aptitude_violations
        names = lambda points: [name for name, _text in check(self.structure, 100, points)]
        self.assertEqual([], names({CAPPED: 3, OPEN: 2, MAJOR: 2}))
        self.assertEqual([rule.APTITUDE_CAP], names({CAPPED: 4}))
        self.assertEqual([rule.APTITUDE_CAP], names({MAJOR: 3}))
        self.assertEqual([rule.APTITUDE_BUDGET], names({CAPPED: 3, OPEN: 3}))
        self.assertEqual([rule.APTITUDE_CAP, rule.APTITUDE_BUDGET], names({OPEN: 6}))
        self.assertEqual([rule.APTITUDE_UNKNOWN], names({999: 1}))

    def test_a_category_not_yet_unlocked_takes_no_point(self):
        build, worn = self.solve({'hp': 1}, level=40)
        self.assertNotIn('ab_%d' % MAJOR, build.problem.variable_names())
        self.assertNotIn(MAJOR, worn.aptitudes)

    def test_a_category_gives_its_point_at_the_unlock_level_and_not_a_level_before(self):
        from fashionistapulp import wakfu_legality as rule
        check = rule.aptitude_violations
        names = lambda level: [name for name, _text in check(self.structure, level,
                                                              {MAJOR: 1})]
        self.assertEqual([rule.APTITUDE_BUDGET], names(49))
        self.assertEqual([], names(50))

    def test_the_table_gives_an_ability_with_no_cap_of_its_own_the_budget_of_its_category(self):
        from fashionistapulp import wakfu_aptitudes
        caps = wakfu_aptitudes.caps(self.structure, 100)
        self.assertEqual({CAPPED: 3, OPEN: 5, MAJOR: 2}, caps)
        table = wakfu_aptitudes.table(self.structure, 100, False)
        self.assertEqual({CAPPED: 3, OPEN: 5, MAJOR: 2},
                         {ident: row[1] for ident, row in table.abilities.items()})
