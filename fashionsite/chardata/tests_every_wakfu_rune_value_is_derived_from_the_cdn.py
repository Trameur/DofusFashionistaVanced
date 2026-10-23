"""Every rune value of the database equals a derivation from the open data and the client.

Control values: the tier 11 table of MethodWakfu, "L'Enchantement" by Martin - Kocka
(https://methodwakfu.com/optimisation/enchantement, page of 25 May 2026). It is a control
only, the values come from the game files.
"""
import io
import json
import math
import os
import sqlite3
import sys
from pathlib import Path

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import get_wakfu_client  # noqa: E402
from fashionistapulp import wakfu_runes  # noqa: E402
from fashionistapulp.wakfu_slots import EQUIPMENT_POSITION_IDS  # noqa: E402

RUNE_TYPE = 811
SOCKET_POSITIONS = ('HEAD', 'NECK', 'CHEST', 'SHOULDERS', 'BACK', 'BELT', 'LEGS',
                    'LEFT_HAND', 'RIGHT_HAND', 'FIRST_WEAPON')
MELEE = 27097
MELEE_SINGLE = [1, 3, 4, 6, 7, 10, 15, 19, 24, 30, 33]
# The 15 effects of the MethodWakfu table at tier 11, by rune id (the page names the effect)
METHOD_WAKFU_TIER_11 = {
    27105: 27, 27106: 27, 27107: 27, 27108: 27,
    27097: 33, 27098: 33, 27099: 33, 27100: 33, 27101: 33, 27110: 33,
    27104: 44, 27103: 66, 27102: 66, 27109: 88, 27094: 22,
}
_cache = {}


def read(path):
    if path not in _cache:
        with io.open(path, encoding='utf-8') as handle:
            _cache[path] = json.load(handle)
    return _cache[path]


class EveryWakfuRuneValueIsDerivedFromTheCdnTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reason = None
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        cls.db = get_items_db_path('wakfu')
        dump = Path(SCRAPER) / 'transformed_wakfu.json'
        found = sorted(Path(SCRAPER).glob('wakfu_client/*/tables.json'),
                       key=lambda path: get_wakfu_client.version_key(path.parent.name))
        if not os.path.exists(cls.db) or not dump.exists() or not found:
            cls.reason = 'no Wakfu database, dump or decoded client'
            return
        version = read(dump)['version']
        items = Path(SCRAPER) / 'wakfu_raw' / version / 'items.json'
        if not items.exists():
            cls.reason = 'no CDN mirror of Wakfu %s' % version
            return
        cls.structure = get_structure('wakfu')
        if not cls.structure.shards:
            cls.reason = 'the database holds no rune table'
            return
        cls.cdn = {}
        for row in read(items):
            base = row['definition']['item']
            if base['baseParameters']['itemTypeId'] == RUNE_TYPE:
                cls.cdn[base['id']] = (base['shardsParameters'],
                                       row['definition']['equipEffects'])
        wanted = {effect['effect']['definition']['id']
                  for _shard, effects in cls.cdn.values() for effect in effects}
        cls.ranges = {effect['id']: (effect['min_level'], effect['max_level'])
                      for effect in read(found[-1])['effects'] if effect['id'] in wanted}

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def test_the_database_holds_every_type_811_item_of_the_open_data(self):
        self.assertEqual(17, len(self.cdn))
        self.assertEqual(set(self.cdn), set(self.structure.shards))

    def test_colour_curve_requirement_and_double_positions_equal_the_open_data(self):
        for ident, (shard, _effects) in self.cdn.items():
            rune = self.structure.shards[ident]
            self.assertEqual(
                (shard['color'], tuple(shard['shardLevelingCurve']),
                 tuple(shard['shardLevelRequirement']),
                 {EQUIPMENT_POSITION_IDS[number] for number in shard['doubleBonusPosition']}),
                (rune.colour, rune.costs, rune.requirements, set(rune.doubles)), ident)

    def test_a_rune_with_a_stat_has_exactly_one_line_at_every_tier(self):
        for ident, rune in wakfu_runes.valued(self.structure).items():
            for tier in range(1, len(rune.costs) + 1):
                holding = [line for line in rune.lines if line[1] <= tier <= line[2]]
                self.assertEqual(1, len(holding), (ident, tier))

    def test_the_value_at_every_tier_and_position_is_the_floored_line_doubled_on_its_positions(
            self):
        by_name = {name: number for number, name in EQUIPMENT_POSITION_IDS.items()}
        checked = 0
        for ident, rune in wakfu_runes.valued(self.structure).items():
            shard, effects = self.cdn[ident]
            for tier in range(1, 12):
                holding = []
                for entry in effects:
                    spec = entry['effect']['definition']
                    low, high = self.ranges[spec['id']]
                    if low <= tier <= high:
                        holding.append(spec['params'])
                self.assertEqual(1, len(holding), (ident, tier))
                raw = math.floor(holding[0][0] + holding[0][1] * tier)
                for position in SOCKET_POSITIONS:
                    doubled = by_name[position] in shard['doubleBonusPosition']
                    self.assertEqual(
                        raw * 2 if doubled else raw,
                        wakfu_runes.value(rune, tier, position in rune.doubles),
                        (ident, tier, position))
                    checked += 1
        self.assertEqual(15 * 11 * 10, checked)

    def test_melee_mastery_gives_the_values_worked_out_by_hand_single_and_doubled(self):
        rune = self.structure.shards[MELEE]
        self.assertEqual(MELEE_SINGLE, [wakfu_runes.value(rune, tier, False)
                                        for tier in range(1, 12)])
        self.assertEqual([2 * number for number in MELEE_SINGLE],
                         [wakfu_runes.value(rune, tier, True) for tier in range(1, 12)])
        self.assertEqual(66, wakfu_runes.value(rune, 11, True))

    def test_the_fifteen_tier_11_values_of_the_methodwakfu_table_hold(self):
        valued = wakfu_runes.valued(self.structure)
        self.assertEqual(15, len(valued))
        self.assertEqual(METHOD_WAKFU_TIER_11, {
            ident: wakfu_runes.value(rune, 11, False) for ident, rune in valued.items()})

    def test_the_two_runes_with_action_400_give_nothing_at_any_tier(self):
        for ident in (27095, 27096):
            rune = self.structure.shards[ident]
            self.assertIsNone(rune.stat)
            self.assertEqual(400, self.cdn[ident][1][0]['effect']['definition']['actionId'])
            self.assertEqual({0}, {wakfu_runes.value(rune, tier, True) for tier in range(1, 12)})
        self.assertNotIn(27095, wakfu_runes.valued(self.structure))

    def test_every_double_position_is_a_position_that_holds_sockets(self):
        conn = sqlite3.connect('file:%s?mode=ro' % Path(self.db).as_posix(), uri=True)
        self.addCleanup(conn.close)
        socketed = {row[0] for row in conn.execute(
            'SELECT DISTINCT p.position FROM item_shard_slots s'
            ' JOIN items i ON i.id = s.item'
            ' JOIN item_type_position p ON p.item_type = i.type WHERE s.maximum > 0')}
        for ident, rune in self.structure.shards.items():
            self.assertLessEqual(set(rune.doubles), socketed, ident)

    def test_a_rune_doubled_on_one_hand_is_doubled_on_both(self):
        hands = {'LEFT_HAND', 'RIGHT_HAND'}
        holders = [ident for ident, rune in self.structure.shards.items()
                   if rune.doubles & hands]
        self.assertEqual([27102, 27103], sorted(holders))
        for ident in holders:
            self.assertEqual(hands, set(self.structure.shards[ident].doubles) & hands, ident)
