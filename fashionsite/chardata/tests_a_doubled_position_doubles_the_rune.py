import os

from django.test import SimpleTestCase

from chardata.tests_wakfu_runes_enter_every_total_and_gate import (
    DODGE, FLAT_SINGLE, MELEE, MELEE_DOUBLED, MELEE_SINGLE, ARuneCase)
from fashionistapulp import wakfu_runes

DOUBLED_ON = ('HEAD', 'BACK')

# The constants of the client enum for equipment positions, in declaration order
CLIENT_POSITION_ORDER = (
    'HEAD', 'HAIR', 'FACE', 'SHOULDERS', 'NECK', 'CHEST', 'ARMS', 'LEFT_HAND', 'RIGHT_HAND',
    'SKIRT', 'BELT', 'TROUSERS', 'LEGS', 'BACK', 'WING', 'FIRST_WEAPON', 'SECOND_WEAPON',
    'ACCESSORY', 'BAG_1', 'BAG_2', 'BAG_3', 'BAG_4', 'PET', 'COSTUME', 'MOUNT')
# The doubled positions the game shows for each rune that gives a stat
DOUBLED_BY_RUNE = {
    27094: {'BACK', 'CHEST'}, 27097: {'BACK', 'HEAD'}, 27098: {'BELT', 'FIRST_WEAPON'},
    27099: {'BACK', 'NECK'}, 27100: {'FIRST_WEAPON', 'SHOULDERS'}, 27101: {'BELT', 'LEGS'},
    27102: {'LEFT_HAND', 'RIGHT_HAND'}, 27103: {'LEFT_HAND', 'RIGHT_HAND'},
    27104: {'BACK', 'NECK'}, 27105: {'BELT', 'CHEST'}, 27106: {'CHEST', 'SHOULDERS'},
    27107: {'CHEST', 'LEGS'}, 27108: {'BACK', 'CHEST'}, 27109: {'FIRST_WEAPON', 'HEAD'},
    27110: {'NECK', 'SHOULDERS'}}


class ADoubledPositionDoublesTheRuneOnInventedRunesTests(ARuneCase):
    def test_a_doubled_value_is_twice_the_single_integer_for_every_rune_and_tier(self):
        valued = wakfu_runes.valued(self.structure)
        self.assertEqual(5, len(valued))
        for ident, rune in valued.items():
            for tier in range(1, len(rune.costs) + 1):
                self.assertEqual(2 * wakfu_runes.value(rune, tier, False),
                                 wakfu_runes.value(rune, tier, True), (ident, tier))

    def test_the_values_follow_the_floor_of_the_line_before_the_doubling(self):
        melee = self.structure.shards[MELEE]
        self.assertEqual(MELEE_SINGLE,
                         tuple(wakfu_runes.value(melee, tier, False) for tier in range(1, 5)))
        self.assertEqual(MELEE_DOUBLED,
                         tuple(wakfu_runes.value(melee, tier, True) for tier in range(1, 5)))
        dodge = self.structure.shards[DODGE]
        self.assertEqual(FLAT_SINGLE,
                         tuple(wakfu_runes.value(dodge, tier, False) for tier in range(1, 5)))

    def test_the_doubled_positions_are_the_ones_the_data_names(self):
        self.assertEqual(frozenset(DOUBLED_ON), self.structure.shards[MELEE].doubles)

    def test_head_and_back_hold_four_doubled_melee_runes_and_the_rest_single_ones(self):
        _build, worn = self.solve_runes({'melee_dmg': 1})
        for position, sockets in worn.runes.items():
            doubled = position in DOUBLED_ON
            for socket in sockets:
                self.assertEqual(MELEE, socket.rune, position)
                self.assertEqual(doubled, socket.doubled, position)
                self.assertEqual(6 if doubled else 3, socket.value, position)
                self.assertEqual(2, socket.tier, position)

    def test_the_totals_and_the_checker_count_the_doubled_value(self):
        build, worn = self.solve_runes({'melee_dmg': 1})
        # Two doubled positions of four sockets at 6, eight others of four at 3
        expected = 2 * 4 * 6 + 8 * 4 * 3
        self.assertEqual(expected, build.totals(worn)['melee_dmg'])
        self.assertEqual([], self.violations(worn, minimums={'melee_dmg': expected}))
        found = self.violations(worn, minimums={'melee_dmg': expected + 1})
        self.assertEqual(['minimum'], [rule for rule, _text in found])
        self.assertEqual(expected, build.stat_total_expr('melee_dmg').highest)

    def test_the_model_prices_a_doubled_column_at_twice_the_single_one(self):
        build = self.build({'melee_dmg': 1})
        build.build()
        by_position = {}
        for (position, _ident, _band), (_name, number, _key) in build._rune_columns.items():
            by_position[position] = number
        self.assertEqual({'HEAD': 6, 'BACK': 6}, {place: by_position[place]
                                                  for place in DOUBLED_ON})
        self.assertEqual({3}, {number for place, number in by_position.items()
                               if place not in DOUBLED_ON})


class TheEquipmentPositionIdsAreTheOrdinalsOfTheClientEnumTests(SimpleTestCase):
    def test_every_id_names_the_position_the_client_enum_puts_at_that_ordinal(self):
        from fashionistapulp.wakfu_slots import EQUIPMENT_POSITION_IDS
        self.assertEqual(dict(enumerate(CLIENT_POSITION_ORDER)), EQUIPMENT_POSITION_IDS)


class ADoubledPositionDoublesTheRuneInTheGameTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        cls.shards = {}
        if os.path.exists(get_items_db_path('wakfu')):
            cls.shards = get_structure('wakfu').shards

    def setUp(self):
        if not self.shards:
            self.skipTest('no Wakfu database with the rune tables')

    def test_every_rune_the_game_values_doubles_at_every_tier(self):
        valued = [rune for rune in self.shards.values() if rune.stat is not None]
        self.assertEqual(15, len(valued))
        for rune in valued:
            for tier in range(1, len(rune.costs) + 1):
                self.assertEqual(2 * wakfu_runes.value(rune, tier, False),
                                 wakfu_runes.value(rune, tier, True), (rune.id, tier))

    def test_every_valued_rune_doubles_on_the_two_pieces_the_game_names(self):
        found = {rune.id: set(rune.doubles) for rune in self.shards.values()
                 if rune.stat is not None}
        self.assertEqual(DOUBLED_BY_RUNE, found)

    def test_melee_mastery_doubles_on_the_head_and_the_back_only(self):
        melee = self.shards[27097]
        self.assertEqual(frozenset(DOUBLED_ON), melee.doubles)
        self.assertEqual(66, wakfu_runes.value(melee, 11, True))
        self.assertEqual(33, wakfu_runes.value(melee, 11, False))
