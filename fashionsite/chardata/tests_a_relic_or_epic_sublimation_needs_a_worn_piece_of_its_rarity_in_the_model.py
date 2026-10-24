from fashionistapulp import wakfu_model
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    EPIC_CHEST, EPIC_SHOULDERS, RELIC_AMULET, RELIC_HELM)
from chardata.wakfu_invented_sublimation_model import SublimationModelCase, state

STATES = {6: state(lines=[('A', 'ferocity', 0, 40, ())]),
          7: state(lines=[('A', 'ferocity', 0, 50, ())]),
          8: state(lines=[('A', 'ferocity', 0, 45, ())])}
SUBLIMATIONS = {140: (6, 1, 'relic', ()), 141: (7, 1, 'epic', ()),
                142: (8, 1, 'relic', ())}
WEIGHTS = {'ferocity': 1, 'hp': 0.001}
RELICS, EPICS = (RELIC_HELM, RELIC_AMULET), (EPIC_CHEST, EPIC_SHOULDERS)


class ARelicAndAnEpicSublimationTests(SublimationModelCase):
    def setUp(self):
        self.invent(STATES, SUBLIMATIONS)

    def test_one_relic_and_one_epic_sublimation_sit_on_pieces_of_their_rarity(self):
        build, worn = self.sublimate(WEIGHTS)
        kinds = sorted(row[2] for row in worn.specials.values())
        self.assertEqual(['epic', 'relic'], kinds)
        for position, (_ident, _state, kind) in worn.specials.items():
            self.assertIn(worn[position].id, EPICS if kind == 'epic' else RELICS)
        self.assertEqual([], self.rules_broken(worn))
        self.assert_objective_is_read_back(build, worn)

    def test_the_better_of_two_relic_sublimations_is_the_one_worn(self):
        _build, worn = self.sublimate(WEIGHTS)
        relics = [row[0] for row in worn.specials.values() if row[2] == 'relic']
        self.assertEqual([142], relics)
        self.assertEqual(50 + 45, worn.totals['ferocity'] - worn.sheet_totals['ferocity'])

    def test_without_a_relic_piece_no_relic_sublimation_is_worn(self):
        build, worn = self.sublimate(WEIGHTS, forbidden=RELICS)
        self.assertEqual(['epic'], [row[2] for row in worn.specials.values()])
        self.assertEqual([], self.rules_broken(worn, forbidden=RELICS))

    def test_two_relic_sublimations_at_once_are_infeasible(self):
        build = wakfu_model.WakfuBuild(self.structure, 100, WEIGHTS, full_set=False,
                                       class_id=1, sublimations='optimistic')
        build.build()
        build.problem.restriction_eq(2, [(1, wakfu_model.SPECIAL, 140),
                                         (1, wakfu_model.SPECIAL, 142)])
        self.assertIsNone(build.solve())
        self.assertEqual(wakfu_model.INFEASIBLE, build.reason)
