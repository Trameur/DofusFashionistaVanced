from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, AP_AMULET, AP_CHEST, AP_HELM, BELT, CATALOGUE, CLOAK, item)
from chardata.wakfu_invented_aptitudes import AptitudeCase, add_ability, add_category

MAJOR_CATEGORY, MAJOR_AP = 6, 2
BELT_UNDER_ELEVEN, BELT_OVER_TWELVE, CLOAK_SIX = 3001, 3002, 3003
OTHER_AP = [AP_AMULET, AP_CHEST]


class AnAptitudeApCountsTowardTheApCapAndItemGatesTests(AptitudeCase):
    @classmethod
    def catalogue(cls):
        return CATALOGUE + [
            item(BELT_UNDER_ELEVEN, BELT, 'Belt Under Eleven',
                 criteria='GetCharac("AP") <= 11', hp=800),
            item(BELT_OVER_TWELVE, BELT, 'Belt Over Twelve',
                 criteria='GetCharac("AP") >= 13', hp=900),
            item(CLOAK_SIX, CLOAK, 'Cloak Six', hp=1, ap=6),
        ]

    @classmethod
    def aptitude_rows(cls, structure):
        add_category(structure, MAJOR_CATEGORY, [25, 75, 125, 175, 225])
        add_ability(structure, MAJOR_AP, MAJOR_CATEGORY, 1, ap=1)

    def worn_ids(self, worn):
        return {one.id for one in worn.values()}

    def test_a_belt_needing_thirteen_ap_is_worn_with_the_major_point_only(self):
        forbidden = [AP_HELM, AP_AMULET, AP_CHEST, BELT_UNDER_ELEVEN]
        locked = [(CLOAK_SIX, None)]
        _build, solved = self.solve({'hp': 1}, forbidden, locked, class_id=ALPHA)
        self.assertIn(BELT_OVER_TWELVE, self.worn_ids(solved))
        self.assertEqual({MAJOR_AP: 1}, solved.aptitudes)
        for left_out in (None, {}):
            with self.subTest(aptitudes=left_out):
                _build, bare = self.solve({'hp': 1}, forbidden, locked, class_id=ALPHA,
                                          aptitudes=left_out)
                self.assertNotIn(BELT_OVER_TWELVE, self.worn_ids(bare))
        _build, fixed = self.solve({'hp': 1}, forbidden, locked, class_id=ALPHA,
                                   aptitudes={MAJOR_AP: 1})
        self.assertIn(BELT_OVER_TWELVE, self.worn_ids(fixed))

    def test_the_gate_row_of_a_belt_holds_the_aptitude_variable(self):
        build, _worn = self.solve({'hp': 1}, [], [], class_id=ALPHA)
        row = build.problem.row('gate_%d_ap_min' % BELT_OVER_TWELVE)
        self.assertIn('ab_%d' % MAJOR_AP, [name for _coefficient, name in row.terms])

    def test_a_belt_capping_the_ap_is_dropped_when_the_major_point_is_worth_more(self):
        forbidden = [AP_AMULET, AP_CHEST, BELT_OVER_TWELVE, CLOAK_SIX]
        locked = [(AP_HELM, None)]
        for hp_weight, belt_worn in ((1, True), (0.01, False)):
            with self.subTest(hp_weight=hp_weight):
                _build, worn = self.solve({'hp': hp_weight, 'ap': 100}, forbidden, locked,
                                          class_id=ALPHA)
                self.assertEqual(belt_worn, BELT_UNDER_ELEVEN in self.worn_ids(worn))
                self.assertEqual({} if belt_worn else {MAJOR_AP: 1}, worn.aptitudes)

    def test_a_belt_capping_the_ap_reads_the_aptitude_point_in_the_checker(self):
        worn = {'HEAD': AP_HELM, 'BELT': BELT_UNDER_ELEVEN}
        self.assertEqual(set(), self.rules(worn, class_id=ALPHA, aptitudes={}))
        self.assertEqual({'condition'}, self.rules(worn, class_id=ALPHA,
                                                    aptitudes={MAJOR_AP: 1}))

    def test_the_point_of_the_major_counts_toward_the_ap_cap(self):
        worn = {'HEAD': AP_HELM, 'NECK': AP_AMULET}
        self.assertEqual(set(), self.rules(worn, class_id=ALPHA, aptitudes={}))
        self.assertEqual({'cap'}, self.rules(worn, class_id=ALPHA,
                                             aptitudes={MAJOR_AP: 1}))
        build, solved = self.solve({'ap': 100, 'hp': 1}, [BELT_UNDER_ELEVEN,
                                                           BELT_OVER_TWELVE, CLOAK_SIX],
                                   [(AP_HELM, None), (AP_AMULET, None)], class_id=ALPHA)
        self.assertEqual({}, solved.aptitudes)
        self.assertEqual(16, build.totals(solved)['ap'])

    def test_a_major_point_is_infeasible_beside_two_locked_ap_pieces(self):
        _build, solved = self.solve(
            {'hp': 1}, [], [(AP_HELM, None), (AP_AMULET, None)], class_id=ALPHA,
            aptitudes={MAJOR_AP: 1})
        self.assertIsNone(solved)
