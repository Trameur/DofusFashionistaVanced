import sqlite3

from chardata.wakfu_invented_aptitudes import NeedsTheRealTables

MAJOR_CATEGORY = 6
MAJOR_LEVELS = (25, 75, 125, 175, 225)
TOP_LEVEL = 245
HP_BOUND = 80000


class TheWakfuAptitudeBudgetMatchesTheGameTableAtEveryLevelTests(NeedsTheRealTables):
    def raw_budgets(self, level):
        from fashionistapulp.fashionista_config import get_items_db_path
        connection = sqlite3.connect('file:%s?mode=ro' % get_items_db_path('wakfu'), uri=True)
        try:
            return dict(connection.execute(
                'SELECT c.id, COUNT(u.value) FROM ability_categories c '
                'LEFT JOIN json_each(c.unlock_levels) u ON u.value <= ? GROUP BY c.id',
                (level,)))
        finally:
            connection.close()

    def build_at(self, level):
        from fashionistapulp.wakfu_exclusions import default_exclusions
        from fashionistapulp.wakfu_model import SOLVE, WakfuBuild
        return WakfuBuild(self.real, level, {'hp': 1}, default_exclusions(self.real), True,
                          aptitudes=SOLVE).build()

    def test_the_budget_of_every_category_counts_the_levels_reached_at_each_level(self):
        from fashionistapulp import wakfu_aptitudes
        for level in range(1, TOP_LEVEL + 1):
            self.assertEqual(self.raw_budgets(level),
                             wakfu_aptitudes.budgets(self.real, level), 'level %d' % level)

    def test_a_level_unlocking_a_point_adds_exactly_that_point(self):
        from fashionistapulp import wakfu_aptitudes
        for level in MAJOR_LEVELS:
            now = wakfu_aptitudes.budgets(self.real, level)[MAJOR_CATEGORY]
            before = wakfu_aptitudes.budgets(self.real, level - 1)[MAJOR_CATEGORY]
            self.assertEqual(1, now - before, 'level %d' % level)
        self.assertEqual(0, wakfu_aptitudes.budgets(self.real, 24)[MAJOR_CATEGORY])
        self.assertEqual(5, wakfu_aptitudes.budgets(self.real, TOP_LEVEL)[MAJOR_CATEGORY])

    def test_the_model_rows_hold_the_budget_of_the_level(self):
        for level in (20, 75, 200):
            build = self.build_at(level)
            rows = {row.name: row.rhs for row in build.problem.rows()
                    if (row.name or '').startswith('aptitude_budget_')}
            with self.subTest(level=level):
                expected = {'aptitude_budget_%d' % category: points
                            for category, points in self.raw_budgets(level).items()
                            if points and any(
                                name.startswith('ab_') and self.real.aptitude_abilities[
                                    int(name[3:])][0] == category
                                for name in build.problem.variable_names())}
                self.assertEqual(expected, rows)

    def test_the_budget_of_a_level_two_hundred_build_is_the_game_table(self):
        from fashionistapulp import wakfu_aptitudes
        budgets = wakfu_aptitudes.budgets(self.real, 200)
        self.assertEqual({2: 50, 3: 50, 4: 50, 5: 49, 6: 4},
                         {category: budgets[category] for category in (2, 3, 4, 5, 6)})

    def test_the_health_bound_of_the_top_level_with_aptitudes_stays_under_the_guard(self):
        build = self.build_at(TOP_LEVEL)
        total = build.stat_total_expr('hp')
        self.assertLess(total.high + total.highest, HP_BOUND)
        self.assertGreater(total.high + total.highest, 0)
