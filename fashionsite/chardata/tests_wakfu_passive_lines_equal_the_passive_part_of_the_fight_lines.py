from chardata.wakfu_invented_sublimation_model import SublimationModelCase, state

PASSIVE_A, PASSIVE_B = 10, 11
PASSIVES = {
    PASSIVE_A: {'name': 'Passive A', 'breed': 1, 'unlock': 10, 'family': 'J',
                'lines': [('J', 'ferocity', 7, 0, ())], 'conditions': [], 'conversions': [],
                'uncounted': []},
    PASSIVE_B: {'name': 'Passive B', 'breed': 1, 'unlock': 10, 'family': 'J',
                'lines': [('J', 'ferocity', 3, 0, ()), ('J', 'hp', 100, 0, ())],
                'conditions': [], 'conversions': [], 'uncounted': []},
}
STATES = {1: state(lines=[('A', 'ferocity', 40, 0, ())])}
SUBLIMATIONS = {110: (1, 1, 'normal', ())}


class WakfuPassiveLinesEqualThePassivePartOfTheFightLinesTests(SublimationModelCase):
    def setUp(self):
        self.invent(STATES, SUBLIMATIONS, passives=PASSIVES)
        self.build, self.worn = self.sublimate({'ferocity': 1}, passives='none')

    def passive_part(self, reports):
        from fashionistapulp import wakfu_sublimations
        return {key: report for key, report in reports.items()
                if isinstance(key, tuple) and key[0] == wakfu_sublimations.PASSIVE}

    def test_the_passive_rows_are_the_passive_part_of_the_fight_lines(self):
        self.worn.passives = [PASSIVE_A, PASSIVE_B]
        self.worn.sublimations = {}
        lines, reports = self.build._fight_lines(self.worn)
        alone_lines, alone_reports = self.build.passive_lines(self.worn)
        self.assertEqual(self.passive_part(reports), alone_reports)
        self.assertEqual({'ferocity': 10, 'hp': 100}, alone_lines)
        self.assertEqual(lines, alone_lines)

    def test_the_passive_rows_leave_the_other_sources_out(self):
        self.worn.passives = [PASSIVE_A]
        position = next(iter(self.worn))
        self.worn.sublimations = {position: (110, 1, 1, ())}
        lines, reports = self.build._fight_lines(self.worn)
        alone_lines, alone_reports = self.build.passive_lines(self.worn)
        self.assertEqual(47, lines['ferocity'])
        self.assertEqual({'ferocity': 7}, alone_lines)
        self.assertEqual(self.passive_part(reports), alone_reports)
        self.assertGreater(len(reports), len(alone_reports))

    def test_a_set_with_no_passive_has_no_passive_row(self):
        self.worn.passives = []
        self.assertEqual(({}, {}), self.build.passive_lines(self.worn))
