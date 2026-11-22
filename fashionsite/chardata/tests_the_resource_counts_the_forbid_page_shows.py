# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The forbid page counts what each banned resource forbids at the build's level: a locked piece spared, an OR family once, a total of distinct pieces."""
import pickle

from django.contrib.auth.models import User
from django.test import TestCase

from chardata import resource_ban
from chardata.models import Char
from fashionistapulp.structure import fits_the_level, get_structure, set_current_game_version

CRIMSON_PEBBLE = '12737:resources'
GELANO_RESOURCE = '757:resources'
LOCKER = 12623


class _ACountedBuild(TestCase):

    level = 200

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        self.structure = get_structure('dofus3')
        self.owner = User.objects.create_user('countban', 'ct@test.local', 'pw-count-ban-1')
        self.char = self.build()

    def build(self, keys=(CRIMSON_PEBBLE,), inclusions=None, level=None):
        return Char.objects.create(
            name='Counted', char_name='counted', char_class='Feca', char_build='build',
            level=level or self.level, minimum_stats=b'', minimum_crits=b'',
            stats_weight=b'', options=pickle.dumps({resource_ban.OPTION_KEY: list(keys)}),
            inclusions=pickle.dumps(inclusions or {}), exclusions=pickle.dumps([]),
            owner=self.owner, link_shared=False, game_version='dofus3')

    def state(self, char):
        return resource_ban.ban_state(char, self.structure, 'en')


class TheCountsMatchTheLevelTests(_ACountedBuild):

    def test_the_count_is_the_items_the_ban_forbids_that_the_level_can_wear(self):
        forbidden = resource_ban.items_the_ban_forbids(self.char, self.structure)
        wearable = {item_id for item_id in forbidden
                    if fits_the_level(self.structure.get_item_by_id(item_id), self.char.level)}

        rows, total = self.state(self.char)

        self.assertEqual(1, len(rows))
        self.assertGreater(len(wearable), 0)
        self.assertLessEqual(rows[0]['count'], len(wearable))
        self.assertEqual(rows[0]['count'], total)

    def test_a_low_level_sees_fewer_items_than_a_high_one(self):
        high = self.state(self.build(level=200))[1]
        low = self.state(self.build(level=20))[1]

        self.assertLess(low, high)

    def test_a_row_carries_the_key_a_name_and_an_icon_url_or_none(self):
        rows, _ = self.state(self.char)

        self.assertEqual(CRIMSON_PEBBLE, rows[0]['key'])
        self.assertEqual('Crimson Pebble', rows[0]['name'])
        self.assertIn('image_url', rows[0])

    def test_no_ban_has_no_rows_and_no_total(self):
        self.assertEqual(([], 0), self.state(self.build(keys=())))


class TwoResourcesForbiddingTheSamePieceCountItOnceTests(_ACountedBuild):

    def test_the_total_is_the_distinct_pieces_not_the_sum(self):
        both = self.state(self.build(keys=(CRIMSON_PEBBLE, GELANO_RESOURCE)))
        alone = self.state(self.build(keys=(CRIMSON_PEBBLE,)))
        other = self.state(self.build(keys=(GELANO_RESOURCE,)))

        counts = {row['key']: row['count'] for row in both[0]}
        self.assertEqual({CRIMSON_PEBBLE, GELANO_RESOURCE}, set(counts))
        self.assertEqual(alone[0][0]['count'], counts[CRIMSON_PEBBLE])
        self.assertGreaterEqual(both[1], max(alone[1], other[1]))
        self.assertLessEqual(both[1], alone[1] + other[1])

    def test_the_rows_come_in_the_order_of_their_names(self):
        rows, _ = self.state(self.build(keys=(CRIMSON_PEBBLE, GELANO_RESOURCE)))
        names = [row['name'] for row in rows]
        self.assertEqual(sorted(names, key=str.casefold), names)
        self.assertEqual(2, len(names))


class AnOrFamilyIsCountedOnceTests(_ACountedBuild):

    def test_every_row_of_the_gelano_is_one_piece(self):
        gelano = self.structure.get_item_by_name('Gelano (#1)')
        family = self.structure.get_available_or_items()[gelano.or_name]

        pieces = resource_ban._pieces_at_the_level(
            self.structure, [item.id for item in family], 200)

        self.assertGreater(len(family), 1)
        self.assertEqual(1, len(pieces))

    def test_the_count_of_the_gelano_resource_includes_the_family_once(self):
        char = self.build(keys=(GELANO_RESOURCE,))
        gelano = self.structure.get_item_by_name('Gelano (#1)')
        family = {item.id for item in self.structure.get_available_or_items()[gelano.or_name]}
        forbidden = resource_ban.items_the_ban_forbids(char, self.structure)
        rows_forbidden = {item_id for item_id in forbidden if item_id in family}

        rows, _ = self.state(char)

        self.assertTrue(rows_forbidden)
        without_the_family = resource_ban._pieces_at_the_level(
            self.structure, forbidden - family, 200)
        self.assertEqual(len(without_the_family) + 1, rows[0]['count'])


class ALockedPieceIsNotCountedTests(_ACountedBuild):

    def test_a_locked_piece_is_spared_and_not_counted(self):
        free = self.state(self.build())
        locked = self.state(self.build(inclusions={'belt': LOCKER}))

        self.assertEqual(free[1] - 1, locked[1])
        self.assertEqual(free[0][0]['count'] - 1, locked[0][0]['count'])

    def test_a_locked_gelano_spares_its_whole_family(self):
        gelano = self.structure.get_item_by_name('Gelano (#1)')
        plain = self.state(self.build(keys=(GELANO_RESOURCE,)))
        locked = self.state(self.build(keys=(GELANO_RESOURCE,),
                                       inclusions={'ring1': gelano.id}))

        self.assertEqual(plain[1] - 1, locked[1])
