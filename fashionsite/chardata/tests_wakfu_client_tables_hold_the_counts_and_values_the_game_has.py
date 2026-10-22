import json
import sqlite3
from pathlib import Path
from unittest import TestCase

from fashionistapulp import wakfu_db

DATABASE = Path(__file__).resolve().parents[2] / 'fashionistapulp' / 'fashionistapulp' \
    / 'items_wakfu.db'

# Actions that run something else or nothing: a group runner (330), a state
# applied to the wearer (304) and the empty effect (400)
NOT_A_BONUS = {330, 304, 400}
APPLY_STATE = 304


class TheWakfuClientTablesHoldTheCountsAndValuesTheGameHasTests(TestCase):
    """Guards on the real items_wakfu.db, skipped where it is not built."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = None
        if DATABASE.exists():
            conn = sqlite3.connect('file:%s?mode=ro' % DATABASE.as_posix(), uri=True)
            try:
                found = conn.execute('SELECT COUNT(*) FROM sqlite_master'
                                     " WHERE name = 'effects'").fetchone()[0]
                filled = found and conn.execute('SELECT COUNT(*) FROM effects').fetchone()[0]
            except sqlite3.DatabaseError:
                filled = 0
            if filled:
                cls.conn = conn
            else:
                conn.close()

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.close()
        super().tearDownClass()

    def setUp(self):
        if self.conn is None:
            self.skipTest('no Wakfu database with the client tables; run '
                          'itemscraper/get_wakfu_client.py then build_wakfu_db.py')

    def count(self, table):
        return self.conn.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]

    def state_effects(self, state_id):
        return [row for one in wakfu_db.effects_of(self.conn, 'STATE', state_id)
                for row in wakfu_db.expand_effect(self.conn, one.id)]

    def applied_level(self, item_id, state_id):
        """The state level an item applies, from its action 304 effect."""
        levels = {wakfu_db.effect_value(row.params, 1, 0)
                  for row in wakfu_db.effects_of(self.conn, 'ITEM_EQUIP', item_id)
                  if row.action == APPLY_STATE and row.params[0] == state_id}
        self.assertEqual(1, len(levels), (item_id, state_id))
        return int(levels.pop())

    def state_value(self, state_id, action, level):
        values = [wakfu_db.effect_value(row.params, 0, level)
                  for row in self.state_effects(state_id) if row.action == action]
        self.assertEqual(1, len(values), (state_id, action))
        return values[0]

    def test_the_client_holds_6129_states_and_31_abilities_in_5_categories(self):
        self.assertEqual(6129, self.count('states'))
        self.assertEqual(31, self.count('abilities'))
        self.assertEqual(5, self.count('ability_categories'))
        self.assertEqual(0, self.conn.execute(
            'SELECT COUNT(*) FROM abilities WHERE category NOT IN'
            ' (SELECT id FROM ability_categories)').fetchone()[0])

    def test_category_2_unlocks_at_62_levels_ending_at_243(self):
        rows = dict(self.conn.execute(
            'SELECT id, unlock_levels FROM ability_categories').fetchall())
        self.assertEqual({2, 3, 4, 5, 6}, set(rows))
        levels = json.loads(rows[2])
        self.assertEqual(62, len(levels))
        self.assertEqual((2, 6, 243), (levels[0], levels[1], levels[-1]))
        self.assertEqual(sorted(levels), levels)

    def test_355_sets_exist_and_only_the_15_new_id_sets_give_a_bonus(self):
        self.assertEqual(355, self.count('client_sets'))
        listed = {row[0] for row in self.conn.execute(
            'SELECT DISTINCT item_set FROM set_bonuses')}
        self.assertEqual(17, len(listed))
        giving = {item_set for item_set in listed if self.set_gives_something(item_set)}
        self.assertEqual(set(range(620, 635)), giving)
        # Set 290 applies a state that holds an empty effect, set 643 a group of one
        self.assertEqual({290, 643}, listed - giving)

    def set_gives_something(self, item_set):
        for (effect_id,) in self.conn.execute(
                'SELECT effect FROM set_bonuses WHERE item_set = ?', (item_set,)):
            for row in self.walk(effect_id):
                if row.action not in NOT_A_BONUS:
                    return True
        return False

    def walk(self, effect_id, seen=()):
        """The effect, its group's effects, and the effects of a state it applies."""
        for row in wakfu_db.expand_effect(self.conn, effect_id):
            yield row
            if row.action == APPLY_STATE and row.id not in seen:
                state_id = int(row.params[0])
                for state_effect in wakfu_db.effects_of(self.conn, 'STATE', state_id):
                    yield from self.walk(state_effect.id, seen + (row.id,))

    def tier(self, item_set, pieces):
        """{action: value} of the leaves of one bonus tier."""
        out = {}
        for (effect_id,) in self.conn.execute(
                'SELECT effect FROM set_bonuses WHERE item_set = ? AND pieces = ?',
                (item_set, pieces)):
            for row in self.walk(effect_id):
                if row.action not in NOT_A_BONUS and row.params:
                    out[row.action] = wakfu_db.effect_value(row.params, 0, 1)
        return out

    def test_a_new_id_set_has_a_3_piece_and_a_6_piece_bonus_that_add_up(self):
        for item_set in range(620, 635):
            tiers = [row[0] for row in self.conn.execute(
                'SELECT DISTINCT pieces FROM set_bonuses WHERE item_set = ?'
                ' ORDER BY pieces', (item_set,))]
            self.assertEqual([3, 6], tiers, item_set)
            roots = [row[0] for row in self.conn.execute(
                'SELECT effect FROM set_bonuses WHERE item_set = ?', (item_set,))]
            self.assertEqual(len(roots), len(set(roots)), item_set)
        # Warrior ID 80: the 6 piece tier holds its own dodge, the 3 piece one stays
        self.assertEqual({150: 10.0, 180: 50.0, 175: 50.0}, self.tier(620, 3))
        self.assertEqual({126: 10.0, 120: 50.0, 175: 50.0}, self.tier(620, 6))
        dodge = sum(self.tier(620, pieces)[175] for pieces in (3, 6))
        self.assertEqual(100.0, dodge)

    def test_a_state_applied_at_level_l_gives_what_the_tooltip_shows_at_l_plus_1(self):
        ruine = [(28822, 1, 5.0), (27111, 2, 10.0), (28823, 3, 15.0)]
        for item_id, level, value in ruine:
            self.assertEqual(level, self.applied_level(item_id, 5980), item_id)
            self.assertEqual(value, self.state_value(5980, 39, level), item_id)

    def test_vivacity_at_level_80_gives_80_and_fortification_at_level_20_gives_20(self):
        self.assertEqual(80, self.applied_level(23992, 2514))
        self.assertEqual(80.0, self.state_value(2514, 120, 80))
        self.assertEqual(20.0, self.state_value(2504, 80, 20))

    def test_a_use_effect_is_split_into_normal_and_critical(self):
        kinds = {row[0] for row in self.conn.execute(
            "SELECT DISTINCT normal_or_critical FROM effects WHERE container_type = 'ITEM_USE'")}
        self.assertEqual({'NORMAL', 'CRITICAL'}, kinds)

    def test_every_group_and_every_listed_effect_points_at_a_stored_effect(self):
        for query in (
                'SELECT COUNT(*) FROM effect_groups WHERE effect NOT IN (SELECT id FROM effects)',
                'SELECT COUNT(*) FROM effect_groups WHERE group_id NOT IN (SELECT id FROM effects)',
                'SELECT COUNT(*) FROM set_bonuses WHERE effect NOT IN (SELECT id FROM effects)'):
            self.assertEqual(0, self.conn.execute(query).fetchone()[0], query)
