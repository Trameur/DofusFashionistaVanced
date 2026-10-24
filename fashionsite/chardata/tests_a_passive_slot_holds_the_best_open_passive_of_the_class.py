from fashionistapulp import wakfu_sublimations
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, SublimationModelCase)

BETA = 2


def passive(breed, unlock, ferocity):
    return {'name': 'Passive %d' % ferocity, 'breed': breed, 'unlock': unlock, 'family': 'A',
            'lines': [('A', 'ferocity', ferocity, 0, ())], 'conditions': [],
            'conversions': [], 'uncounted': []}


PASSIVES = {701: passive(ALPHA, 10, 5), 702: passive(ALPHA, 30, 7),
            703: passive(ALPHA, 50, 9), 704: passive(ALPHA, 100, 40),
            705: passive(BETA, 10, 100), 706: passive(ALPHA, 40, 11)}
WEIGHTS = {'ferocity': 1, 'hp': 0.001}
LEVEL_FIFTY = 50


class ThePassivesTheModelPicksTests(SublimationModelCase):
    def setUp(self):
        self.invent(passives=PASSIVES)
        self.build, self.worn = self.sublimate(WEIGHTS, sublimations=None, passives='solve',
                                               level=LEVEL_FIFTY)

    def test_three_slots_are_open_at_level_fifty(self):
        self.assertEqual(3, wakfu_sublimations.slots_open(LEVEL_FIFTY))

    def test_the_best_three_open_passives_of_the_class_are_chosen(self):
        self.assertEqual([702, 703, 706], self.worn.passives)

    def test_a_locked_passive_and_another_classs_passive_are_never_chosen(self):
        self.assertNotIn(704, self.worn.passives)
        self.assertNotIn(705, self.worn.passives)
        self.assertEqual([], [name for name in self.columns(self.build, 'ps_')
                              if name in ('ps_704', 'ps_705')])

    def test_the_passives_add_their_ferocity_to_the_fight_total(self):
        self.assertEqual(27, self.worn.totals['ferocity'] - self.worn.sheet_totals['ferocity'])

    def test_the_set_breaks_no_rule_and_its_objective_is_read_back(self):
        self.assertEqual([], self.rules_broken(self.worn, level=LEVEL_FIFTY))
        self.assert_objective_is_read_back(self.build, self.worn)


class ThePassiveModesTests(SublimationModelCase):
    def test_a_build_with_no_class_gets_no_passive_and_a_note(self):
        self.invent(passives=PASSIVES)
        build, worn = self.sublimate(WEIGHTS, sublimations=None, passives='solve',
                                     class_id=None, level=LEVEL_FIFTY)
        self.assertEqual([], worn.passives)
        self.assertTrue(any('class' in note for note in build.notes))

    def test_no_passive_argument_leaves_the_passive_list_unset(self):
        self.invent(passives=PASSIVES)
        build, worn = self.sublimate(WEIGHTS, sublimations=None, passives=None,
                                     level=LEVEL_FIFTY)
        self.assertIsNone(worn.passives)
        self.assertEqual([], self.columns(build, 'ps_'))
