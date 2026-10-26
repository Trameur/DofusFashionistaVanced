import os
import sqlite3

from django.test import SimpleTestCase

from fashionistapulp import wakfu_presets, wakfu_slots

EPIC_LEVELS = (20, 35, 50, 65, 80, 95, 110, 125, 140, 155, 170, 185, 200, 215, 230, 245)


class TheBracketsFollowTheEpicItemLevelsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from fashionistapulp.fashionista_config import get_items_db_path
        cls.path = get_items_db_path('wakfu')
        cls.conn = None
        if os.path.exists(cls.path):
            cls.conn = sqlite3.connect('file:%s?mode=ro' % cls.path, uri=True)

    @classmethod
    def tearDownClass(cls):
        if cls.conn is not None:
            cls.conn.close()
        super().tearDownClass()

    def setUp(self):
        if self.conn is None:
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def test_the_epic_rarity_is_the_one_the_slot_rules_name(self):
        self.assertEqual('epic', wakfu_slots.RARITIES[wakfu_presets.EPIC])

    def test_there_are_sixteen_brackets_topped_by_the_levels_epic_items_exist_at(self):
        found = wakfu_presets.brackets(self.conn)
        self.assertEqual(16, len(found))
        self.assertEqual(EPIC_LEVELS, tuple(high for _, high in found))
        epic = {level for (level,) in self.conn.execute(
            'SELECT DISTINCT items.level FROM items JOIN item_rarity '
            'ON item_rarity.item = items.id WHERE item_rarity.rarity = 7')}
        self.assertEqual(set(EPIC_LEVELS), epic)

    def test_the_first_bracket_is_twenty_levels_wide_and_the_others_fifteen(self):
        found = wakfu_presets.brackets(self.conn)
        self.assertEqual((1, 20), found[0])
        self.assertEqual(20, found[0][1] - found[0][0] + 1)
        for low, high in found[1:]:
            self.assertEqual(15, high - low + 1, (low, high))

    def test_the_brackets_follow_each_other_without_a_gap_or_an_overlap(self):
        found = wakfu_presets.brackets(self.conn)
        for (_, high), (low, _) in zip(found, found[1:]):
            self.assertEqual(high + 1, low)

    def test_every_shard_item_level_threshold_is_a_bracket_top_plus_one(self):
        thresholds = {level for (level,) in self.conn.execute(
            'SELECT DISTINCT item_level FROM shard_levels WHERE item_level > 0')}
        tops = {high for _, high in wakfu_presets.brackets(self.conn)}
        self.assertEqual(10, len(thresholds))
        self.assertEqual(set(), {level - 1 for level in thresholds} - tops)

    def test_the_brackets_agree_with_the_credited_fan_brackets_of_fifteen_levels(self):
        self.assertIn('MethodWakfu', wakfu_presets.BRACKET_CREDIT)
        self.assertIn('16', wakfu_presets.BRACKET_CREDIT)
        self.assertIn('15', wakfu_presets.BRACKET_CREDIT)
        found = wakfu_presets.brackets(self.conn)
        self.assertEqual(16, len(found))
        self.assertTrue(all(high - low + 1 == 15 for low, high in found[1:]))

    def test_a_level_takes_the_bracket_it_falls_in(self):
        for level, expected in ((1, (1, 20)), (20, (1, 20)), (21, (21, 35)), (35, (21, 35)),
                                (36, (36, 50)), (110, (96, 110)), (245, (231, 245)),
                                (300, (231, 245))):
            with self.subTest(level=level):
                self.assertEqual(expected, wakfu_presets.bracket_of(level, self.path))
