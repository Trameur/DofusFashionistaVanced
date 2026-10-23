from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, AMULET_A, AP_HELM, BELT, BELT_A, BOOTS_A, CATALOGUE, CHEST_A, CLOAK_A, HELM_A,
    SHIELD_A, SHOULDERS_A, SWORD_A, item)
from chardata.wakfu_invented_aptitudes import (
    BRACKET_80, BRACKET_81_110, AptitudeCase, add_set, add_tier, NeedsTheRealTables)

BODY_SET, GATED_SET = 900, 901
BODY = [HELM_A, AMULET_A, CHEST_A, SHOULDERS_A, CLOAK_A, BELT_A]
GATED = [BOOTS_A, SWORD_A, SHIELD_A]
BELT_UNDER_ELEVEN = 3001
LEVEL_80 = 80
THREE, SIX = 1000, 2000


class TheWakfuSetBonusTiersCountInABattlegroundOnlyTests(AptitudeCase):
    @classmethod
    def catalogue(cls):
        return CATALOGUE + [item(BELT_UNDER_ELEVEN, BELT, 'Belt Under Eleven',
                                 criteria='GetCharac("AP") <= 11', hp=800)]

    @classmethod
    def aptitude_rows(cls, structure):
        add_set(structure, BODY_SET, BODY)
        add_tier(structure, BODY_SET, 3, 8001, BRACKET_80, hp=THREE)
        add_tier(structure, BODY_SET, 6, 8002, BRACKET_80, hp=SIX)
        add_tier(structure, BODY_SET, 3, 8003, BRACKET_81_110, hp=50000)
        add_set(structure, GATED_SET, GATED)
        add_tier(structure, GATED_SET, 3, 8004, BRACKET_80, ap=2)

    def solve80(self, forbidden=(), locked=(), **options):
        return self.solve({'hp': 1}, forbidden, locked, level=LEVEL_80, **options)

    def tier_names(self, build):
        return [name for name in build.problem.variable_names() if name.startswith('st_')]

    def test_no_set_bonus_term_exists_with_the_battleground_off(self):
        build, worn = self.solve80()
        self.assertEqual([], self.tier_names(build))
        self.assertEqual([], [row for row in build.problem.row_names()
                              if str(row).startswith('tier_')])
        self.assertEqual([], worn.set_tiers)
        self.assertEqual([], [term for term in build.stat_total_expr('hp').terms
                              if term[1] == 'st'])

    def test_a_battleground_adds_a_tier_variable_and_two_rows_per_tier(self):
        build, _worn = self.solve80(battleground=True)
        self.assertEqual(['st_900_3', 'st_900_6', 'st_901_3'], sorted(self.tier_names(build)))
        rows = sorted(str(row) for row in build.problem.row_names()
                      if str(row).startswith('tier_'))
        self.assertEqual(6, len(rows), rows)

    def test_six_pieces_reach_both_tiers_and_add_their_lines(self):
        build, worn = self.solve80(battleground=True)
        self.assertTrue(set(BODY) <= {one.id for one in worn.values()})
        self.assertEqual([(900, 3), (900, 6)], [t for t in worn.set_tiers if t[0] == BODY_SET])
        flat, _flat_worn = self.solve80()
        gain = build.totals(worn)['hp'] - flat.totals(worn)['hp']
        self.assertEqual(THREE + SIX, gain)

    def test_three_to_five_pieces_reach_the_first_tier_alone(self):
        for held, left_out in ((3, BODY[3:]), (4, BODY[4:]), (5, BODY[5:])):
            with self.subTest(pieces=held):
                locked = [(ident, None) for ident in BODY[:held]]
                _build, worn = self.solve80(forbidden=left_out, locked=locked,
                                            battleground=True)
                self.assertEqual([(900, 3)], [t for t in worn.set_tiers if t[0] == BODY_SET])

    def test_fewer_than_three_pieces_reach_no_tier(self):
        locked = [(ident, None) for ident in BODY[:2]]
        _build, worn = self.solve80(forbidden=BODY[2:], locked=locked, battleground=True)
        self.assertEqual([], [t for t in worn.set_tiers if t[0] == BODY_SET])

    def test_a_tier_of_another_bracket_adds_nothing(self):
        build, worn = self.solve80(battleground=True)
        self.assertLess(build.totals(worn)['hp'], 50000)
        build, high = self.solve({'hp': 1}, level=100, battleground=True)
        self.assertEqual([(900, 3)], [t for t in high.set_tiers if t[0] == BODY_SET])
        self.assertGreaterEqual(build.totals(high)['hp'], 50000)

    def test_a_tier_is_on_exactly_when_its_pieces_are_worn(self):
        from fashionistapulp import wakfu_aptitudes
        build, worn = self.solve80(battleground=True)
        table = wakfu_aptitudes.table(self.structure, LEVEL_80, True)
        held = wakfu_aptitudes.tiers_reached(table, {one.id for one in worn.values()})
        self.assertEqual(sorted(held), sorted(worn.set_tiers))

    def test_the_solver_cannot_drop_a_forced_tier_to_pass_a_gate(self):
        locked = [(ident, None) for ident in GATED] + [(AP_HELM, None),
                                                      (BELT_UNDER_ELEVEN, None)]
        _build, battleground = self.solve80(locked=locked, class_id=ALPHA, battleground=True)
        self.assertIsNone(battleground)
        _build, outside = self.solve80(locked=locked, class_id=ALPHA)
        self.assertIsNotNone(outside)

    def test_the_checker_counts_a_tier_in_a_battleground_only(self):
        worn = {'HEAD': AP_HELM, 'BELT': BELT_UNDER_ELEVEN, 'LEGS': BOOTS_A,
                'FIRST_WEAPON': SWORD_A, 'SECOND_WEAPON': SHIELD_A}
        self.assertEqual(set(), self.rules(worn, level=LEVEL_80, class_id=ALPHA))
        self.assertEqual({'condition'}, self.rules(worn, level=LEVEL_80, class_id=ALPHA,
                                                    battleground=True))


class TheClientSetMembersAreTheSetsOfTheItemsTests(NeedsTheRealTables):
    def test_the_client_members_of_each_battleground_set_are_the_items_of_the_set(self):
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        connection = sqlite3.connect('file:%s?mode=ro' % get_items_db_path('wakfu'), uri=True)
        try:
            client = {}
            for item_set, member in connection.execute(
                    'SELECT item_set, item FROM client_set_members'):
                client.setdefault(item_set, set()).add(member)
            for item_set in range(620, 635):
                with self.subTest(item_set=item_set):
                    ours = {member for (member,) in connection.execute(
                        'SELECT id FROM items WHERE item_set = ?', (item_set,))}
                    self.assertTrue(client.get(item_set), 'no client member')
                    self.assertEqual(ours, client[item_set])
        finally:
            connection.close()

    def test_no_member_of_a_battleground_set_has_a_stat_gate(self):
        for members in (self.real.aptitude_set_members[item_set]
                        for item_set in range(620, 635)
                        if item_set in self.real.aptitude_set_members):
            for ident in members:
                one = self.real.items_dict[ident]
                with self.subTest(item=ident):
                    self.assertEqual((), tuple(getattr(one, 'min_stats_to_equip', ())))
                    self.assertEqual((), tuple(getattr(one, 'max_stats_to_equip', ())))
