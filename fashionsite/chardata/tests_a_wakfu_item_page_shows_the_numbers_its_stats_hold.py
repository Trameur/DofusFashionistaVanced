import collections
import os

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data as data
from chardata import wakfu_game_text

ARMOR_ACTIONS = (39, 40)
ARMOR_RECEIVED_CHARACTERISTIC = 121.0
PERCENT_OF_LEVEL_ACTION = 999


class AWakfuItemPageShowsTheNumbersItsStatsHoldTests(SimpleTestCase):
    """The value a rendered effect shows, at the level the page uses, is the stored stat value."""

    def setUp(self):
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)

    def test_every_rendered_stat_value_of_a_live_item_equals_its_stored_stat(self):
        by_action = collections.defaultdict(list)
        for stat, action, positive, negative, _primary in self.conn.execute(
                'SELECT * FROM stat_actions'):
            by_action[action].append((stat, positive, negative))
        keys = dict(self.conn.execute('SELECT id, key FROM stats'))
        received = next(stat for stat, key in keys.items() if key == 'armor_received_percent')
        given = next(stat for stat, key in keys.items() if key == 'armor_given_percent')
        stored = collections.defaultdict(collections.Counter)
        for item, stat, value in self.conn.execute(
                'SELECT item, stat, value FROM stats_of_item'):
            stored[item][stat] += value
        members = collections.defaultdict(list)
        for group, effect in self.conn.execute(
                'SELECT group_id, effect FROM effect_groups ORDER BY position'):
            members[group].append(effect)
        effects = {row[0]: wakfu_game_text._effect_of_row(row) for row in self.conn.execute(
            'SELECT %s FROM effects' % wakfu_game_text.EFFECT_COLUMNS)}
        never = {row[0] for row in self.conn.execute(
            "SELECT id FROM effects WHERE criterion = 'False'")}

        def expand(effect_id):
            found = [effects[effect_id]]
            for member in members.get(effect_id, ()):
                found.extend(expand(member))
            return found

        levels = data.display_levels(self.conn)
        worn = wakfu_game_text.worn_effects_by_item(self.conn)
        wrong = []
        live = [row[0] for row in self.conn.execute('SELECT id FROM items WHERE removed = 0')]
        self.assertTrue(live)
        for item in live:
            shown = collections.Counter()
            for root in worn.get(item, ()):
                if root.action == PERCENT_OF_LEVEL_ACTION:
                    continue
                for effect in expand(root.id):
                    if effect.action not in by_action or effect.id in never:
                        continue
                    value = wakfu_game_text.arguments(effect.params, levels[item])[0].whole
                    if effect.action in ARMOR_ACTIONS:
                        stat = received if effect.params[4] == ARMOR_RECEIVED_CHARACTERISTIC \
                            else given
                    else:
                        stat = by_action[effect.action][0][0]
                    only_negative = by_action[effect.action][0][1] == 0 \
                        and by_action[effect.action][0][2] > 0
                    shown[stat] += -value if only_negative else value
            if {k: v for k, v in shown.items() if v} != \
                    {k: v for k, v in stored[item].items() if v}:
                wrong.append(item)
        self.assertEqual(wrong, [])

    def test_a_pet_or_mount_with_a_stored_cap_is_shown_at_the_cap(self):
        rows = self.conn.execute(
            'SELECT c.item, MAX(c.cap), i.level FROM item_level_caps c JOIN items i'
            ' ON i.id = c.item WHERE i.removed = 0 GROUP BY c.item').fetchall()
        self.assertTrue(rows)
        for item, cap, level in rows:
            detail = data.item_detail(item, 'fr')
            self.assertEqual(detail.display_level, max(level or 0, cap or 0), item)

    def test_an_item_without_a_stored_cap_is_shown_at_its_own_level(self):
        row = self.conn.execute(
            'SELECT i.id, i.level FROM items i WHERE i.removed = 0 AND NOT EXISTS'
            ' (SELECT 1 FROM item_level_caps c WHERE c.item = i.id) LIMIT 1').fetchone()
        self.assertEqual(data.item_detail(row[0], 'fr').display_level, row[1] or 0)
