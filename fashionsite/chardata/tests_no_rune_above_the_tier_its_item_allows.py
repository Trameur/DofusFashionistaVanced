import types

from django.test import SimpleTestCase

from chardata.tests_wakfu_runes_enter_every_total_and_gate import (
    EXTRA, HIGH_CHEST, LOW_AMULET, MELEE, NARROW_BOOTS, RED, ARuneCase, socketed)
from fashionistapulp import wakfu_legality, wakfu_runes

# (piece level, highest tier it allows), from the requirement list of the game's runes
LEVELS = ((0, 1), (35, 1), (36, 2), (50, 2), (51, 3), (65, 3), (66, 4), (215, 10),
          (216, 11), (245, 11))


class NoRuneAboveTheTierItsItemAllowsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.structure import get_structure
        from fashionistapulp.fashionista_config import get_items_db_path
        import os
        cls.shards = {}
        if os.path.exists(get_items_db_path('wakfu')):
            cls.shards = get_structure('wakfu').shards

    def setUp(self):
        if not self.shards:
            self.skipTest('no Wakfu database with the rune tables')

    def test_the_allowed_tier_follows_the_level_requirements_for_every_rune(self):
        for ident, rune in self.shards.items():
            self.assertEqual([tier for _level, tier in LEVELS],
                             [wakfu_runes.allowed_tier(rune, level) for level, _tier in LEVELS],
                             ident)

    def test_a_level_50_piece_holds_neither_a_tier_3_nor_a_tier_4_rune(self):
        piece = types.SimpleNamespace(level=50)
        for ident, rune in self.shards.items():
            self.assertEqual(2, wakfu_runes.socket_tier(rune, piece), ident)

    def test_a_cap_lowers_the_tier_of_a_socket_and_never_raises_it(self):
        rune = self.shards[27097]
        piece = types.SimpleNamespace(level=216)
        self.assertEqual(11, wakfu_runes.socket_tier(rune, piece))
        self.assertEqual(5, wakfu_runes.socket_tier(rune, piece, cap=5))
        self.assertEqual(2, wakfu_runes.socket_tier(rune, types.SimpleNamespace(level=50),
                                                    cap=9))

    def test_the_shards_of_a_tier_are_the_costs_added_up_and_the_inverse_reads_them_back(self):
        rune = self.shards[27097]
        self.assertEqual([1, 3, 7, 15, 31, 63, 127, 319, 895, 3199, 12415],
                         [wakfu_runes.shards_at(rune, tier) for tier in range(1, 12)])
        for tier in range(1, 12):
            shards = wakfu_runes.shards_at(rune, tier)
            self.assertEqual(tier, wakfu_runes.tier_for_shards(rune, shards))
            self.assertEqual(tier - 1, wakfu_runes.tier_for_shards(rune, shards - 1))


class NoRuneAboveTheTierItsItemAllowsInASolveTests(ARuneCase):
    """Invented runes with four tiers, asked for at 36, 51 and 66, on pieces of level 30, 50
    and 70."""

    WEIGHTS = {'melee_dmg': 1, 'hp': 1}

    @classmethod
    def catalogue(cls):
        return super().catalogue() + [socketed(one) for one in EXTRA]

    def solve_locked(self, **options):
        return self.solve_runes(self.WEIGHTS, locked=[(LOW_AMULET, None), (HIGH_CHEST, None)],
                                **options)

    def test_every_socket_holds_the_tier_its_piece_allows(self):
        _build, worn = self.solve_locked()
        self.assertEqual((30, 70), (worn['NECK'].level, worn['CHEST'].level))
        rune = self.structure.shards[MELEE]
        tiers = {}
        for position, sockets in worn.runes.items():
            for socket in sockets:
                self.assertEqual(wakfu_runes.allowed_tier(rune, worn[position].level),
                                 socket.tier, position)
            tiers[position] = sockets[0].tier
        self.assertEqual((1, 4), (tiers['NECK'], tiers['CHEST']))
        self.assertEqual(2, tiers['HEAD'])

    def test_a_level_30_piece_holds_tier_1_and_a_level_70_piece_the_top_tier(self):
        _build, worn = self.solve_locked()
        self.assertEqual({1}, {socket.tier for socket in worn.runes['NECK']})
        self.assertEqual({4}, {socket.tier for socket in worn.runes['CHEST']})
        self.assertEqual({1}, {socket.value for socket in worn.runes['NECK']})
        self.assertEqual({15}, {socket.value for socket in worn.runes['CHEST']})

    def test_a_tier_cap_lowers_every_socket_and_raises_none(self):
        for cap in (1, 2, 3):
            with self.subTest(cap=cap):
                build, worn = self.solve_locked(rune_tier=cap)
                self.assertEqual(cap, worn.rune_tier)
                rune = self.structure.shards[MELEE]
                for position, sockets in worn.runes.items():
                    for socket in sockets:
                        self.assertEqual(min(cap, wakfu_runes.allowed_tier(
                            rune, worn[position].level)), socket.tier, (cap, position))
                self.assertEqual([], self.violations(worn))

    def test_the_checker_flags_a_tier_above_the_one_the_piece_allows(self):
        _build, worn = self.solve_locked()
        for position, tier in (('NECK', 2), ('HEAD', 3), ('CHEST', 5), ('HEAD', 0)):
            with self.subTest(position=position, tier=tier):
                found = wakfu_legality.violations(self.structure, 100, worn,
                                                  runes={position: [(RED, MELEE, tier)]})
                self.assertEqual([wakfu_legality.RUNE_TIER], [rule for rule, _t in found])
        found = wakfu_legality.violations(self.structure, 100, worn,
                                          runes={'CHEST': [(RED, MELEE, 4)]})
        self.assertEqual([], found)

    def test_the_checker_flags_a_tier_above_the_cap(self):
        _build, worn = self.solve_locked()
        runes = {'CHEST': [(RED, MELEE, 3)]}
        self.assertEqual([], wakfu_legality.violations(self.structure, 100, worn, runes=runes))
        found = wakfu_legality.violations(self.structure, 100, worn, runes=runes, rune_tier=2)
        self.assertEqual([wakfu_legality.RUNE_TIER], [rule for rule, _t in found])

    def test_a_piece_with_two_sockets_holds_two_runes_and_no_more(self):
        _build, worn = self.solve_runes(self.WEIGHTS, locked=[(NARROW_BOOTS, None)])
        self.assertEqual(NARROW_BOOTS, worn['LEGS'].id)
        self.assertEqual(2, len([socket for socket in worn.runes['LEGS']
                                 if socket.rune is not None]))
        self.assertEqual({4}, {len(sockets) for position, sockets in worn.runes.items()
                               if position != 'LEGS'})
        found = wakfu_legality.violations(self.structure, 100, worn,
                                          runes={'LEGS': [(RED, MELEE, 4)] * 3})
        self.assertEqual([wakfu_legality.RUNE_SOCKET], [rule for rule, _t in found])
        found = wakfu_legality.violations(self.structure, 100, worn,
                                          runes={'LEGS': [(RED, MELEE, 4)] * 2})
        self.assertEqual([], found)
