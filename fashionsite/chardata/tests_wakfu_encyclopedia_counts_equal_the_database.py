import os
import unicodedata

from django.test import SimpleTestCase

from chardata import wakfu_encyclopedia_data as data

LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')


class WakfuEncyclopediaCountsEqualTheDatabaseTests(SimpleTestCase):
    """The index, the filters, the sets and the labels agree with counts read from SQL."""

    def setUp(self):
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)
        self.idx = data.index('fr')

    def scalar(self, sql, *args):
        return self.conn.execute(sql, args).fetchone()[0]

    def test_the_index_lists_every_live_item_once(self):
        self.assertEqual(len(self.idx.items), self.scalar(
            'SELECT COUNT(*) FROM items WHERE removed = 0'))
        self.assertEqual(len({one.id for one in self.idx.items}), len(self.idx.items))
        for language in LANGUAGES:
            self.assertEqual(len(data.index(language).items), len(self.idx.items))

    def test_the_index_names_every_live_item_in_every_language(self):
        for language in LANGUAGES:
            nameless = [one.id for one in data.index(language).items if not one.name]
            self.assertEqual(nameless, [], language)

    def test_the_index_is_ordered_by_level_descending(self):
        levels = [one.level for one in self.idx.items]
        self.assertEqual(levels, sorted(levels, reverse=True))

    def test_the_index_types_are_the_live_item_types(self):
        self.assertEqual(len(self.idx.types), self.scalar(
            'SELECT COUNT(DISTINCT type) FROM items WHERE removed = 0'))
        for language in LANGUAGES:
            for _item_type, name in data.index(language).types:
                self.assertTrue(name, language)
                self.assertFalse(set('[]{}') & set(name), name)

    def test_the_index_rarities_are_the_rarities_of_live_items(self):
        self.assertEqual(len(self.idx.rarities), self.scalar(
            'SELECT COUNT(DISTINCT r.rarity) FROM item_rarity r JOIN items i ON i.id = r.item'
            ' WHERE i.removed = 0'))

    def test_every_stat_key_a_live_item_holds_has_a_label_in_every_language(self):
        used = {row[0] for row in self.conn.execute(
            'SELECT DISTINCT s.key FROM stats_of_item o JOIN stats s ON s.id = o.stat'
            ' JOIN items i ON i.id = o.item WHERE i.removed = 0')}
        for language in LANGUAGES:
            shown = dict(data.index(language).stats)
            self.assertEqual(set(shown) ^ used, set(), language)
            self.assertTrue(all(shown.values()), language)

    def test_an_item_stat_is_the_sum_of_its_rows_for_that_stat(self):
        rows = self.conn.execute(
            'SELECT o.item, s.key, SUM(o.value) FROM stats_of_item o JOIN stats s'
            ' ON s.id = o.stat GROUP BY o.item, s.key').fetchall()
        for item_id, key, total in rows:
            one = self.idx.by_id.get(item_id)
            if one is not None:
                self.assertEqual(one.stats[key], total, (item_id, key))

    def test_filtering_by_type_returns_the_live_items_of_that_type(self):
        for item_type, _name in self.idx.types:
            expected = self.scalar('SELECT COUNT(*) FROM items WHERE removed = 0 AND type = ?',
                                   item_type)
            self.assertEqual(len(data.filter_items(self.idx, {'type': item_type})), expected)

    def test_filtering_by_rarity_returns_the_live_items_of_that_rarity(self):
        for rarity, _name in self.idx.rarities:
            expected = self.scalar(
                'SELECT COUNT(*) FROM item_rarity r JOIN items i ON i.id = r.item'
                ' WHERE i.removed = 0 AND r.rarity = ?', rarity)
            self.assertEqual(len(data.filter_items(self.idx, {'rarity': rarity})), expected)

    def test_filtering_by_level_returns_the_live_items_in_the_range(self):
        expected = self.scalar(
            'SELECT COUNT(*) FROM items WHERE removed = 0 AND level >= 100 AND level <= 150')
        found = data.filter_items(self.idx, {'min_level': 100, 'max_level': 150})
        self.assertEqual(len(found), expected)

    def test_filtering_by_a_stat_minimum_returns_the_items_with_that_much(self):
        expected = self.scalar(
            'SELECT COUNT(*) FROM (SELECT o.item FROM stats_of_item o JOIN stats s'
            ' ON s.id = o.stat JOIN items i ON i.id = o.item WHERE i.removed = 0'
            " AND s.key = 'hp' GROUP BY o.item HAVING SUM(o.value) >= 500)")
        found = data.filter_items(self.idx, {'stats': [('hp', 500)]})
        self.assertEqual(len(found), expected)
        self.assertTrue(data.is_stat_key(self.idx, 'hp'))
        self.assertFalse(data.is_stat_key(self.idx, 'not_a_stat'))

    def test_ordering_by_a_stat_puts_the_highest_first(self):
        found = data.filter_items(self.idx, {'orders': [('hp', 'desc')]})
        values = [one.stats.get('hp', 0) for one in found]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_searching_a_name_finds_the_item_with_and_without_accents(self):
        name = next(one.name for one in self.idx.items
                    if unicodedata.normalize('NFD', one.name) != one.name)
        plain = ''.join(c for c in unicodedata.normalize('NFD', name)
                        if not unicodedata.combining(c))
        for text in (name, plain.upper()):
            found = data.filter_items(self.idx, {'q': text})
            self.assertIn(name, [one.name for one in found])

    def test_the_sets_are_the_client_sets_with_a_live_member(self):
        expected = self.scalar(
            'SELECT COUNT(DISTINCT m.item_set) FROM client_set_members m JOIN items i'
            ' ON i.id = m.item WHERE i.removed = 0')
        self.assertEqual(len(self.idx.sets), expected)

    def test_a_set_page_holds_the_pieces_plus_the_members_without_an_item_record(self):
        for entry in self.idx.sets:
            members = self.scalar(
                'SELECT COUNT(*) FROM client_set_members WHERE item_set = ?', entry.id)
            detail = data.set_detail(entry.id, 'fr')
            with self.subTest(item_set=entry.id):
                self.assertEqual(len(detail.pieces) + detail.other_count, members)
                self.assertEqual(entry.size, members)
                self.assertEqual(entry.live_count, len(detail.pieces))

    def test_a_set_page_shows_a_bonus_tier_for_each_piece_count_the_database_holds(self):
        counts = {row[0]: row[1] for row in self.conn.execute(
            'SELECT item_set, COUNT(DISTINCT pieces) FROM set_bonuses GROUP BY item_set')}
        live_sets = [row[0] for row in self.conn.execute(
            'SELECT DISTINCT m.item_set FROM client_set_members m JOIN items i'
            ' ON i.id = m.item WHERE i.removed = 0')]
        expected = [one for one in live_sets if one in counts]
        self.assertTrue(expected)
        for set_id in expected:
            self.assertEqual(len(data.set_detail(set_id, 'fr').bonuses), counts[set_id], set_id)

    def test_an_unknown_item_or_set_has_no_page(self):
        self.assertIsNone(data.item_detail(-1, 'fr'))
        self.assertIsNone(data.set_detail(-1, 'fr'))

    def test_an_item_recipe_holds_the_ingredient_rows_in_order(self):
        item_id = self.scalar(
            'SELECT r.item FROM item_recipes r JOIN items i ON i.id = r.item'
            ' WHERE i.removed = 0 GROUP BY r.item ORDER BY COUNT(*) DESC, r.item LIMIT 1')
        rows = self.scalar('SELECT COUNT(*) FROM item_recipes WHERE item = ?', item_id)
        recipe = data.item_detail(item_id, 'fr').recipe
        self.assertEqual(len(recipe.ingredients), rows)
        self.assertTrue(all(one.name for one in recipe.ingredients))
        self.assertTrue(all(one.quantity > 0 for one in recipe.ingredients))

    def test_an_item_without_a_recipe_has_none(self):
        item_id = self.scalar(
            'SELECT i.id FROM items i WHERE i.removed = 0 AND NOT EXISTS'
            ' (SELECT 1 FROM item_recipes r WHERE r.item = i.id) ORDER BY i.id LIMIT 1')
        self.assertIsNone(data.item_detail(item_id, 'fr').recipe)
