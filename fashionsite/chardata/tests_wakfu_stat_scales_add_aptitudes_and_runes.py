import collections
import os
from unittest import mock

from django.test import SimpleTestCase

from chardata.tests_wakfu_role_value_sums_share_times_log_of_its_components import (
    CAPE, HELMET, RING, STAT_ID, Catalogue, Stat)
from fashionistapulp import wakfu_aptitudes, wakfu_runes, wakfu_value

Socketed = collections.namedtuple('Socketed', 'id level type stats removed shard_slots')
HANDS = frozenset({'LEFT_HAND', 'RIGHT_HAND'})


class Structure(Catalogue):
    """The catalogue stub with the aptitude and rune tables the scales read."""

    aptitude_abilities = {1: (4, 5)}

    def __init__(self, shards, *pieces):
        super().__init__(*pieces)
        self.shards = shards

    def get_stat_by_id(self, ident):
        return Stat(ident, [key for key, number in STAT_ID.items() if number == ident][0])


def piece(item_id, type_id, sockets, level=50, **stats):
    return Socketed(item_id, level, type_id,
                    tuple((STAT_ID[key], value) for key, value in stats.items()), False,
                    (0, sockets))


def tackle_rune(per_level=10):
    return wakfu_runes.Rune(1, 3, STAT_ID['tackle'], HANDS, (1, 1, 1), (0, 36, 51),
                            [(1, 1, 3, 0, per_level)], {})


def abilities(*rows):
    return wakfu_aptitudes.Table(
        {ident: (category, cap, [(key, per_point)], []) for ident, category, cap, key, per_point
         in rows}, {}, {})


class TheScalesAddWhatAptitudesAndRunesCanGiveTests(SimpleTestCase):
    def structure(self, shards=None):
        shards = {1: tackle_rune()} if shards is None else shards
        return Structure(shards, piece(1, HELMET, 1, tackle=30), piece(2, RING, 2, tackle=20),
                         piece(3, CAPE, 0, dodge=10))

    def scale(self, structure, key='tackle', table=None, budget=None):
        table = table or abilities()
        with mock.patch.object(wakfu_aptitudes, 'table', return_value=table), \
                mock.patch.object(wakfu_aptitudes, 'budgets', return_value=budget or {}):
            return wakfu_value.stat_scale(structure, key, 50)

    def test_the_sockets_of_each_piece_hold_the_best_rune_doubled_where_the_rune_doubles(self):
        # head 30 and one socket at tier 2 (20), each hand 20 and two sockets (2 x 20 x 2)
        self.assertEqual((30 + 20) + 2 * (20 + 2 * 40), self.scale(self.structure()))

    def test_without_a_rune_for_the_stat_the_sockets_add_nothing(self):
        self.assertEqual(30 + 2 * 20, self.scale(self.structure({})))
        self.assertEqual(10, self.scale(self.structure(), 'dodge'))

    def test_a_rune_tier_the_piece_level_does_not_allow_is_not_counted(self):
        low = Structure({1: tackle_rune()}, piece(1, HELMET, 1, level=30, tackle=30))
        self.assertEqual(30 + 10, self.scale(low))

    def test_the_aptitude_points_of_a_category_go_to_the_ability_giving_the_most(self):
        table = abilities((1, 4, 5, 'tackle', 6), (2, 4, 5, 'tackle', 4), (3, 5, 5, 'tackle', 2))
        budget = {4: 5, 5: 3}
        base = self.scale(self.structure({}))
        self.assertEqual(base + 6 * 5 + 2 * 3, self.scale(self.structure({}), 'tackle', table,
                                                          budget))

    def test_points_left_in_a_category_pass_to_the_next_ability(self):
        table = abilities((1, 4, 2, 'tackle', 6), (2, 4, 5, 'tackle', 4))
        base = self.scale(self.structure({}))
        self.assertEqual(base + 6 * 2 + 4 * 3, self.scale(self.structure({}), 'tackle', table,
                                                          {4: 5}))

    def test_a_structure_without_aptitudes_or_runes_keeps_the_scale_of_its_items(self):
        bare = Catalogue(*self.structure().pieces)
        self.assertEqual(30 + 2 * 20, wakfu_value.stat_scale(bare, 'tackle', 50))


class TheScalesOfTheGameDataTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')

    def setUp(self):
        if not os.path.exists(self.path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        from fashionistapulp.structure import get_structure
        self.structure = get_structure('wakfu')

    def without(self, **hidden):
        structure = self.structure

        class Proxy:
            def __getattr__(self, name):
                return hidden[name] if name in hidden else getattr(structure, name)
        return Proxy()

    def test_the_aptitudes_of_the_client_add_their_points_to_the_scale(self):
        for top in (20, 110, 245):
            table = wakfu_aptitudes.table(self.structure, top, False)
            budget = wakfu_aptitudes.budgets(self.structure, top)
            for key in ('tackle', 'dodge', 'init'):
                with self.subTest(top=top, key=key):
                    best = max((dict(lines).get(key, 0) * cap, category)
                               for category, cap, lines, _ in table.abilities.values()
                               if key in dict(lines))
                    items = wakfu_value.stat_scale(
                        self.without(aptitude_abilities={}, shards={}), key, top)
                    held = wakfu_value.stat_scale(self.without(shards={}), key, top)
                    self.assertGreaterEqual(held - items, best[0])
                    self.assertLessEqual(held - items,
                                         max(dict(lines).get(key, 0)
                                             for _, _, lines, _ in table.abilities.values())
                                         * budget[best[1]])

    def test_the_runes_of_the_client_add_their_sockets_to_the_scale(self):
        for top in (20, 110, 245):
            for key in ('tackle', 'dodge', 'init'):
                with self.subTest(top=top, key=key):
                    items = wakfu_value.stat_scale(
                        self.without(aptitude_abilities={}, shards={}), key, top)
                    held = wakfu_value.stat_scale(self.without(aptitude_abilities={}), key, top)
                    self.assertGreater(held, items)

    def test_the_scales_never_shrink_with_the_bracket(self):
        for key in ('tackle', 'dodge', 'init'):
            found = [wakfu_value.stat_scale(self.structure, key, top) for top in (20, 110, 245)]
            self.assertEqual(sorted(found), found, key)

    def test_initiative_is_no_longer_the_sixty_of_the_one_pet_that_gives_it(self):
        for top in (35, 110, 245):
            self.assertGreater(wakfu_value.stat_scale(self.structure, 'init', top), 60)
