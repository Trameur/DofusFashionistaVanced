from fashionistapulp.wakfu_model import WakfuBuild
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, CATALOGUE, EMBLEM, EMBLEM_A, RING, SWORD, InventedItemsCase, item)

STATLESS_RING, STATLESS_EMBLEM, NEEDY_SWORD = 4001, 4002, 4003

# No stat piece fits ACCESSORY here, so a statless emblem is the only candidate for it
CONTENT = [one for one in CATALOGUE if one['id'] != EMBLEM_A] + [
    item(STATLESS_RING, RING, 'Plain Ring'),
    item(STATLESS_EMBLEM, EMBLEM, 'Plain Emblem'),
    item(NEEDY_SWORD, SWORD, 'Needy Sword', criteria='HasEquipmentId(%d)' % STATLESS_RING,
         hp=5000),
]


class AStatlessWakfuPieceNeverDisplacesAStatPieceTests(InventedItemsCase):
    @classmethod
    def catalogue(cls):
        return CONTENT

    def candidates(self, forbidden=(), locked=()):
        build = WakfuBuild(self.structure, 100, {'hp': 1}, forbidden, locked=locked)
        return {(one.id, position) for one, position in build._candidates()}

    def test_a_statless_piece_is_no_candidate_where_a_stat_piece_fits(self):
        self.assertEqual([], self.by_id(STATLESS_RING).stats)
        found = self.candidates(forbidden=[NEEDY_SWORD])
        self.assertNotIn((STATLESS_RING, 'LEFT_HAND'), found)
        self.assertNotIn((STATLESS_RING, 'RIGHT_HAND'), found)
        _build, worn = self.solve({'hp': 1}, forbidden=[NEEDY_SWORD])
        self.assertNotIn(STATLESS_RING, {one.id for one in worn.values()})

    def test_a_statless_piece_fills_a_position_no_stat_piece_fits(self):
        self.assertIn((STATLESS_EMBLEM, 'ACCESSORY'), self.candidates())
        _build, worn = self.solve({'hp': 1})
        self.assertEqual(STATLESS_EMBLEM, worn['ACCESSORY'].id)

    def test_a_locked_statless_piece_is_worn(self):
        found = self.candidates(forbidden=[NEEDY_SWORD], locked=[(STATLESS_RING, 'RIGHT_HAND')])
        self.assertIn((STATLESS_RING, 'RIGHT_HAND'), found)
        _build, worn = self.solve({'hp': 1}, forbidden=[NEEDY_SWORD],
                                  locked=[(STATLESS_RING, 'RIGHT_HAND')])
        self.assertEqual(STATLESS_RING, worn['RIGHT_HAND'].id)

    def test_the_ring_a_kept_sword_needs_stays_a_candidate(self):
        found = self.candidates()
        self.assertIn((NEEDY_SWORD, 'FIRST_WEAPON'), found)
        self.assertIn((STATLESS_RING, 'LEFT_HAND'), found)
        self.assertIn((STATLESS_RING, 'RIGHT_HAND'), found)
        _build, worn = self.solve({'hp': 1})
        held = {one.id for one in worn.values()}
        self.assertIn(NEEDY_SWORD, held)
        self.assertIn(STATLESS_RING, held)

    def test_the_ring_of_a_dropped_sword_is_no_candidate(self):
        for found in (self.candidates(forbidden=[NEEDY_SWORD]),
                      self.candidates(forbidden=[NEEDY_SWORD], locked=[])):
            self.assertNotIn(NEEDY_SWORD, {ident for ident, _position in found})
            self.assertNotIn(STATLESS_RING, {ident for ident, _position in found})

    def test_statless_pieces_add_no_objective_term(self):
        build = WakfuBuild(self.structure, 100, {'hp': 1, 'ap': 5})
        build.build()
        statless = {STATLESS_RING, STATLESS_EMBLEM}
        variables = [build._name(one, position) for one, position in build._placements
                     if one.id in statless]
        self.assertGreaterEqual(len(variables), 2)
        self.assertEqual([], [name for name in variables if name in build.problem.obj_vars])
        self.assertTrue(build.problem.obj_vars)

    def test_the_statless_rule_keeps_the_solved_value_of_a_catalogue_without_them(self):
        statless = [STATLESS_RING, STATLESS_EMBLEM, NEEDY_SWORD]
        without, worn_without = self.solve({'hp': 1}, forbidden=statless)
        with_them, worn_with = self.solve({'hp': 1}, forbidden=[NEEDY_SWORD])
        self.assertEqual(without.totals(worn_without)['hp'], with_them.totals(worn_with)['hp'])
        self.assertEqual({position: one.id for position, one in worn_without.items()},
                         {position: one.id for position, one in worn_with.items()
                          if position != 'ACCESSORY'})
