import collections
import os
import sqlite3
import sys

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import build_wakfu_db as builder  # noqa: E402
from fashionistapulp import wakfu_db  # noqa: E402


def effect(ident, action, container_type, container, params=(), kind='NORMAL'):
    return {'id': ident, 'action_id': action, 'container_id': container,
            'container_type': container_type, 'root_container_type': container_type,
            'normal_or_critical': kind, 'area_shape': 1, 'area_size': [],
            'params': list(params)}


def tables(effects, groups, states=(), sets=(), abilities=(), categories=(),
           item_ids=(7, 8)):
    return {'item_ids': list(item_ids), 'effects': effects, 'groups': [{'id': one, 'effect_ids': members}
                                           for one, members in groups],
            'states': list(states), 'sets': list(sets), 'abilities': list(abilities),
            'ability_categories': list(categories)}


def state(ident, effect_ids):
    return {'id': ident, 'bcw': 'state%d' % ident, 'effect_ids': effect_ids}


# Item 7 wears effect 100, which runs group 100, whose effect 101 runs group 101;
# effect 102 is a leaf of group 100. Item 8 uses effect 200 twice over, normal and
# critical. Effect 900 belongs to a spell no item, state or set reaches.
EFFECTS = [
    effect(100, 330, 'ITEM_EQUIP', 7), effect(101, 330, 'GROUP', 100),
    effect(102, 20, 'GROUP', 100, [0.0, 10.0]), effect(103, 150, 'GROUP', 101, [3.0, 0.0]),
    effect(200, 40, 'ITEM_USE', 8, [1.0, 0.0]),
    effect(201, 40, 'ITEM_USE', 8, [2.0, 0.0], 'CRITICAL'),
    effect(300, 120, 'STATE', 5, [0.0, 1.0]), effect(400, 126, 'SET', 620, [10.0, 0.0]),
    effect(900, 1, 'SPELL', 3),
]
GROUPS = [(100, [101, 102]), (101, [103])]
STATES = [state(5, [300])]
SETS = [{'id': 620, 'elG': 1, 'item_ids': [7, 8], 'bonuses': [(3, [400])]},
        {'id': 621, 'elG': 1, 'item_ids': [], 'bonuses': []}]


class TheWakfuEffectGroupsResolveToKnownEffectsTests(SimpleTestCase):
    def fill(self, payload):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        wakfu_db.create_tables(conn)
        counts = collections.Counter()
        builder.write_client_tables(conn, payload, counts)
        return conn, counts

    def ids(self, rows):
        return [row.id for row in rows]

    def test_only_what_an_item_a_state_or_a_set_reaches_is_stored_groups_expanded(self):
        conn, counts = self.fill(tables(EFFECTS, GROUPS, STATES, SETS))
        stored = [row[0] for row in conn.execute('SELECT id FROM effects ORDER BY id')]
        self.assertEqual([100, 101, 102, 103, 200, 201, 300, 400], stored)
        self.assertEqual(8, counts['effects'])
        self.assertEqual(2, counts['effect groups'])
        self.assertEqual(3, counts['effects in groups'])
        self.assertEqual((1, 1), (counts['sets with a bonus entry'], counts['set bonus effects']))
        self.assertEqual(2, counts['client sets'])

    def test_every_group_member_is_a_stored_effect(self):
        conn, _counts = self.fill(tables(EFFECTS, GROUPS, STATES, SETS))
        orphans = conn.execute(
            'SELECT group_id, effect FROM effect_groups'
            ' WHERE effect NOT IN (SELECT id FROM effects)'
            ' OR group_id NOT IN (SELECT id FROM effects)').fetchall()
        self.assertEqual([], orphans)

    def test_an_effect_whose_id_is_a_group_expands_recursively_in_order(self):
        conn, _counts = self.fill(tables(EFFECTS, GROUPS, STATES, SETS))
        self.assertEqual([100, 101, 103, 102],
                         self.ids(wakfu_db.expand_effect(conn, 100)))
        self.assertEqual([102], self.ids(wakfu_db.expand_effect(conn, 102)))
        with self.assertRaises(KeyError):
            wakfu_db.expand_effect(conn, 999)

    def test_a_group_that_contains_itself_is_refused_when_expanded(self):
        conn, _counts = self.fill(tables(EFFECTS, [(100, [101]), (101, [100])]))
        with self.assertRaisesRegex(ValueError, 'contains itself'):
            wakfu_db.expand_effect(conn, 100)

    def test_a_group_naming_an_effect_the_table_lacks_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, 'effect 555 is listed'):
            self.fill(tables(EFFECTS, [(100, [101, 555])]))

    def test_a_state_set_or_ability_naming_an_unknown_effect_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, 'effect 77 is listed'):
            self.fill(tables(EFFECTS, GROUPS, [state(6, [77])]))
        with self.assertRaisesRegex(ValueError, 'effect 78 is listed'):
            self.fill(tables(EFFECTS, GROUPS, sets=[
                {'id': 1, 'elG': 0, 'item_ids': [], 'bonuses': [(2, [78])]}]))
        with self.assertRaisesRegex(ValueError, 'in no category'):
            self.fill(tables(EFFECTS, GROUPS, abilities=[
                {'id': 1, 'category': 9, 'ddL': 0, 'cgI': 0, 'effect_ids': []}]))

    def test_the_effects_of_a_container_split_normal_from_critical(self):
        conn, _counts = self.fill(tables(EFFECTS, GROUPS, STATES, SETS))
        used = wakfu_db.effects_of(conn, 'ITEM_USE', 8)
        self.assertEqual([(200, 'NORMAL'), (201, 'CRITICAL')],
                         [(row.id, row.normal_or_critical) for row in used])
        self.assertEqual([], wakfu_db.effects_of(conn, 'ITEM_USE', 7))

    def test_an_item_the_client_does_not_list_brings_no_effect(self):
        conn, _counts = self.fill(tables(EFFECTS, GROUPS, STATES, SETS, item_ids=(8,)))
        stored = [row[0] for row in conn.execute('SELECT id FROM effects ORDER BY id')]
        self.assertEqual([200, 201, 300, 400], stored)

    def test_a_value_at_a_level_is_the_float32_of_the_first_plus_the_slope_times_it(self):
        self.assertEqual(15.0, wakfu_db.effect_value([0.0, 5.0], 0, 3))
        self.assertEqual(80.0, wakfu_db.effect_value([0.0, 1.0], 0, 80))
        self.assertEqual(3.0, wakfu_db.effect_value([3.0, 0.0], 0, 99))
        # The level of an applied state is the second pair
        self.assertEqual(2.0, wakfu_db.effect_value([5980.0, 0.0, 1.0, 1.0], 1, 1))
        slope = wakfu_db.float32(0.4)
        self.assertEqual(60.0, wakfu_db.effect_value([0.0, slope], 0, 150))
        self.assertEqual(wakfu_db.float32(0.4), wakfu_db.effect_value([0.0, slope], 0, 1))
