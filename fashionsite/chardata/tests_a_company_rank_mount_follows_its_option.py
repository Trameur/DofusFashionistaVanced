import os

from django.test import SimpleTestCase

BOOWOLVES = (19555, 19556, 19557, 19558)
LEVEL = 100


class ACompanyRankMountFollowsItsOptionTests(SimpleTestCase):
    """The shipped Wakfu database; skipped when it is absent."""

    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.structure = get_structure('wakfu')
        if self.structure.get_item_by_id(BOOWOLVES[0]) is None:
            self.skipTest('the Wakfu database has no Boowolf mounts')

    def test_the_four_boowolf_mounts_need_company_rank_5(self):
        for ident in BOOWOLVES:
            conditions = self.structure.get_item_by_id(ident).state_conditions
            self.assertEqual([('company_rank', None, '>=', 5)],
                             [(one.option, one.nation, one.operator, one.value)
                              for one in conditions], ident)

    def test_a_lock_on_a_boowolf_is_refused_at_company_rank_0(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        with self.assertRaises(ValueError) as caught:
            WakfuBuild(self.structure, LEVEL, {'hp': 1}, locked=[(BOOWOLVES[0], None)])
        self.assertIn('company_rank >= 5', str(caught.exception))

    def test_a_lock_on_a_boowolf_is_worn_at_company_rank_5(self):
        from fashionistapulp import wakfu_criteria
        from fashionistapulp.wakfu_model import WakfuBuild
        state = wakfu_criteria.player_state(self.structure, company_rank=5)
        build = WakfuBuild(self.structure, LEVEL, {'hp': 1},
                           locked=[(BOOWOLVES[0], None)], state=state)
        worn = build.build().solve()
        self.assertEqual(BOOWOLVES[0], worn['MOUNT'].id)

    def test_a_boowolf_worn_at_company_rank_0_breaks_the_player_state_rule(self):
        from fashionistapulp import wakfu_legality
        boowolf = self.structure.get_item_by_id(BOOWOLVES[0])
        found = wakfu_legality.violations(self.structure, LEVEL, {'MOUNT': boowolf})
        self.assertIn(wakfu_legality.STATE, {rule for rule, _text in found})

    def test_company_rank_0_lists_the_boowolf_mounts_among_the_state_unlocks(self):
        from fashionistapulp import wakfu_criteria
        pool = [self.structure.get_item_by_id(ident) for ident in BOOWOLVES]
        unlocks = dict(wakfu_criteria.state_unlocks(pool, wakfu_criteria.start_state()))
        self.assertEqual({ident: {'company_rank': 5} for ident in BOOWOLVES}, unlocks)
