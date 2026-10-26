from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, AMULET, BOOTS, CHEST, HELMET, LEVEL, InventedItemsCase, ids, item)
import os

from fashionistapulp import wakfu_presets, wakfu_turn, wakfu_value

FIRE = ('fire',)
IOP, TOP_LEVEL = 8, 245
DAMAGE_HELM, DAMAGE_AMULET, DAMAGE_CHEST = 3001, 3002, 3003
LIFE_HELM, LIFE_AMULET, LIFE_CHEST = 3011, 3012, 3013
LOCK_BOOTS, PLAIN_BOOTS = 3021, 3022


class TheDamageComesFirstTests(InventedItemsCase):
    @classmethod
    def catalogue(cls):
        return [
            item(DAMAGE_HELM, HELMET, 'Damage Helm', dmg_fire_percent=100, hp=10),
            item(DAMAGE_AMULET, AMULET, 'Damage Amulet', dmg_fire_percent=400, hp=10),
            item(DAMAGE_CHEST, CHEST, 'Damage Chest', dmg_fire_percent=200, hp=10),
            item(LIFE_HELM, HELMET, 'Life Helm', hp=2500),
            item(LIFE_AMULET, AMULET, 'Life Amulet', hp=500),
            item(LIFE_CHEST, CHEST, 'Life Chest', hp=1000),
            item(LOCK_BOOTS, BOOTS, 'Lock Boots', tackle=100),
            item(PLAIN_BOOTS, BOOTS, 'Plain Boots', hp=20),
        ]

    def shipped_tank(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        path = get_items_db_path('wakfu')
        if not os.path.exists(path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        return wakfu_value.Role(FIRE, 'distance', shares=wakfu_presets.shares(
            IOP, 'tank', FIRE, 'pvm', TOP_LEVEL, path))

    def solved(self, role, turn=None):
        found = wakfu_value.solve(self.structure, LEVEL, role, class_id=ALPHA, rounds=4,
                                  turn=turn)
        self.assertIsNotNone(found.best)
        return found.best

    def test_a_role_is_never_valued_on_life_alone(self):
        with self.assertRaisesMessage(ValueError, 'life alone'):
            wakfu_value.Role(FIRE, 'distance', shares={'life': 1})
        self.assertTrue(wakfu_value.Role(FIRE, 'distance', shares={'life': 1, 'lock': 0.1}))

    def test_the_shipped_tank_solve_keeps_at_least_half_the_damage_of_the_damage_solve(self):
        damage = wakfu_value.Role(FIRE, 'distance', shares={'damage': 1, 'life': 0.25})
        tank = self.shipped_tank()
        scales = wakfu_value.stat_scales(self.structure, LEVEL)
        self.assertEqual(100, scales['tackle'])
        best_damage = self.solved(damage)
        best_tank = self.solved(tank, wakfu_turn.RoleTurns(tank, LEVEL, {}, scales))
        damage_of = wakfu_value.turn_damage
        self.assertGreaterEqual(tank.shares['damage'], tank.shares['life'])
        self.assertGreater(damage_of(tank, best_tank.totals), 0)
        self.assertGreaterEqual(damage_of(tank, best_tank.totals),
                                0.5 * damage_of(damage, best_damage.totals))
        self.assertLessEqual(damage_of(tank, best_tank.totals),
                             damage_of(damage, best_damage.totals))

    def test_a_lock_share_picks_the_piece_that_adds_lock(self):
        tank = wakfu_value.Role(FIRE, 'distance',
                                shares={'damage': 0.4, 'life': 0.6, 'lock': 0.2})
        scales = wakfu_value.stat_scales(self.structure, LEVEL)
        best = self.solved(tank, wakfu_turn.RoleTurns(tank, LEVEL, {}, scales))
        self.assertIn(LOCK_BOOTS, ids(best.worn))
        self.assertEqual(100, best.totals['tackle'])
