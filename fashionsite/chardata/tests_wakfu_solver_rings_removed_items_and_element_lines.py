import collections
import os
import sqlite3

from django.test import SimpleTestCase

MASTERY = ('dmg_in_percent', 'dmg_fire_percent', 'dmg_water_percent',
           'dmg_earth_percent', 'dmg_air_percent')
RESISTANCE = ('res_in_percent', 'res_fire_percent', 'res_water_percent',
              'res_earth_percent', 'res_air_percent')
RING = 103


class WakfuDatabaseCase(SimpleTestCase):
    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        from fashionistapulp.structure import get_structure
        self.path = get_items_db_path('wakfu')
        if not os.path.exists(self.path):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.structure = get_structure('wakfu')

    def rows(self, query, parameters=()):
        connection = sqlite3.connect('file:%s?mode=ro' % self.path, uri=True)
        try:
            return connection.execute(query, parameters).fetchall()
        finally:
            connection.close()

    def item(self, item_id):
        item = self.structure.get_item_by_id(item_id)
        self.assertIsNotNone(item, 'item %d is gone from the Wakfu data' % item_id)
        return item

    def key(self, stat_id):
        return self.structure.get_stat_by_id(stat_id).key

    def lines(self, item, family):
        return [(self.key(stat_id), value) for stat_id, value in item.stats
                if self.key(stat_id) in family]

    def solve(self, level, weights, allowed):
        from fashionistapulp.wakfu_model import WakfuBuild
        forbidden = {item.id for item in self.structure.get_items_list()} - set(allowed)
        build = WakfuBuild(self.structure, level, weights, forbidden)
        return build, build.build().solve()


class AWakfuRingIsWornOnceWhateverItsRarityTests(WakfuDatabaseCase):
    def test_the_rarities_of_one_ring_share_a_key(self):
        from fashionistapulp.wakfu_model import same_item
        for ids in ((31847, 31848, 31849), (13574, 24117), (10787, 27805), (21139, 21388)):
            with self.subTest(ids=ids):
                self.assertEqual(1, len({same_item(self.item(item_id)) for item_id in ids}))

    def test_a_legacy_ring_is_keyed_with_its_same_title_remake(self):
        from fashionistapulp.wakfu_model import same_item
        for ids in ((14042, 26795, 26796, 26797), (23613, 25766, 25767, 25768)):
            with self.subTest(ids=ids):
                self.assertEqual(0, self.item(ids[0]).rarity)
                self.assertEqual(1, len({same_item(self.item(item_id)) for item_id in ids}))

    def test_two_rings_sharing_only_an_english_title_are_two_rings(self):
        from fashionistapulp.wakfu_model import same_item
        chouillarde, ratachouille = self.item(15403), self.item(15414)
        self.assertEqual(chouillarde.name, ratachouille.name)
        self.assertNotEqual(same_item(chouillarde), same_item(ratachouille))

    def test_a_ring_crafted_from_a_ring_with_the_same_picture_shares_its_key(self):
        from fashionistapulp.wakfu_model import same_item
        crafts = self.rows(
            'SELECT r.item, r.ingredient_ankama_id FROM item_recipes r'
            ' JOIN items made ON made.id = r.item'
            ' JOIN items used ON used.id = r.ingredient_ankama_id'
            ' JOIN item_picture a ON a.item = made.id'
            ' JOIN item_picture b ON b.item = used.id'
            " WHERE r.ingredient_subtype = 'equipment' AND made.type = ?"
            ' AND used.type = ? AND a.gfx = b.gfx', (RING, RING))
        self.assertGreater(len(crafts), 100)
        split = [(made, used) for made, used in crafts
                 if same_item(self.item(made)) != same_item(self.item(used))]
        self.assertEqual([], split)

    def test_a_build_never_wears_two_rarities_of_one_ring(self):
        from fashionistapulp.wakfu_model import same_item

        def hp(item):
            return sum(value for key, value in self.lines(item, ('hp',)))

        for level, ids in ((245, (31847, 31848, 31849)), (200, (13574, 24117)), (215, (10787, 27805))):
            with self.subTest(ids=ids):
                group = [self.item(item_id) for item_id in ids]
                filler = min((item for item in self.structure.get_available_items_list()
                              if item.type == RING and item.level <= level
                              and same_item(item) != same_item(group[0])), key=hp)
                self.assertLess(hp(filler), min(hp(item) for item in group))
                build, worn = self.solve(level, {'hp': 1}, [item.id for item in group] + [filler.id])
                self.assertIsNotNone(worn)
                self.assertTrue(build.full_set, 'fell back to the loose form')
                self.assertEqual({'LEFT_HAND', 'RIGHT_HAND'}, set(worn))
                self.assertEqual({max(group, key=hp).id, filler.id}, {item.id for item in worn.values()})


class ARemovedWakfuItemIsNeverACandidateTests(WakfuDatabaseCase):
    def test_no_removed_item_is_a_candidate(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        removed = {item.id for item in self.structure.get_items_list() if item.removed}
        self.assertIn(32178, removed)
        candidates = WakfuBuild(self.structure, 245, {'hp': 1})._candidates()
        self.assertGreater(len(candidates), 1000)
        self.assertEqual(set(), removed & {item.id for item, _position in candidates})


class APlainElementalLineCountsOnEveryElementTests(WakfuDatabaseCase):
    def only(self, family, key):
        return [item for item in self.structure.get_available_items_list()
                if not item.element_spread and self.lines(item, family)
                and all(name == key for name, _value in self.lines(item, family))]

    def pair(self, family):
        """(item with only the plain line, same one-slot type item with only a smaller fire line)."""
        slots = collections.Counter(type_id for type_id, _position in self.structure.get_type_positions())
        for plain in self.only(family, family[0]):
            if slots[plain.type] != 1:
                continue
            plain_value = sum(value for _key, value in self.lines(plain, family))
            for fire in self.only(family, family[1]):
                fire_value = sum(value for _key, value in self.lines(fire, family))
                if fire.type == plain.type and 0 < fire_value < plain_value:
                    return plain, fire
        self.fail('no item pair to compare in %s' % family[0])

    def test_a_fire_build_values_plain_elemental_mastery(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        plain, fire = self.pair(MASTERY)
        value = sum(value for _key, value in self.lines(plain, MASTERY))
        self.assertEqual(value, WakfuBuild(self.structure, 245, {'dmg_fire_percent': 1})._worth(plain))
        every = {key: 1 for key in MASTERY[1:]}
        self.assertEqual(4 * value, WakfuBuild(self.structure, 245, every)._worth(plain))
        level = max(plain.level, fire.level)
        _build, worn = self.solve(level, {'dmg_fire_percent': 1}, (plain.id, fire.id))
        self.assertEqual([plain.id], [item.id for item in worn.values()])

    def test_a_fire_build_values_plain_elemental_resistance(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        plain, fire = self.pair(RESISTANCE)
        value = sum(value for _key, value in self.lines(plain, RESISTANCE))
        self.assertEqual(value, WakfuBuild(self.structure, 245, {'res_fire_percent': 1})._worth(plain))
        level = max(plain.level, fire.level)
        _build, worn = self.solve(level, {'res_fire_percent': 1}, (plain.id, fire.id))
        self.assertEqual([plain.id], [item.id for item in worn.values()])

    def test_a_weight_on_elemental_mastery_counts_on_each_element(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        plain, _fire = self.pair(MASTERY)
        value = sum(value for _key, value in self.lines(plain, MASTERY))
        self.assertEqual(4 * value, WakfuBuild(self.structure, 245, {'dmg_in_percent': 1})._worth(plain))


class WakfuTotalsPutSpreadLinesWhereTheyLandTests(WakfuDatabaseCase):
    def sums(self, ids, stat_ids):
        marks = ','.join('?' * len(ids))
        named = self.rows('SELECT stat, SUM(value) FROM stats_of_item WHERE item IN (%s)'
                          ' GROUP BY stat' % marks, ids)
        spread = self.rows('SELECT stat, SUM(value), SUM(MAX(value, 0)), SUM(value * elements)'
                           ' FROM stat_element_count WHERE item IN (%s) GROUP BY stat' % marks, ids)
        return ({stat: total for stat, total in named if stat in stat_ids},
                {stat: (total, gains, mass) for stat, total, gains, mass in spread})

    def test_a_fire_build_reports_its_spread_mastery_on_its_elements(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        build = WakfuBuild(self.structure, 110, {'dmg_fire_percent': 1})
        worn = build.build().solve()
        self.assertIsNotNone(worn)
        ids = sorted(item.id for item in worn.values())
        by_key = {stat.key: stat.id for stat in (self.structure.get_stat_by_key(key) for key in MASTERY)}
        named, spread = self.sums(ids, set(by_key.values()))
        spread_total, spread_gains, spread_mass = spread.get(by_key['dmg_in_percent'], (0, 0, 0))
        self.assertGreater(spread_mass, 0, 'the set carries no spread line, so nothing was checked')
        totals = build.totals(worn)
        self.assertEqual(named.get(by_key['dmg_in_percent'], 0) - spread_total, totals['dmg_in_percent'])
        self.assertEqual(named.get(by_key['dmg_fire_percent'], 0) + spread_gains, totals['dmg_fire_percent'])
        self.assertEqual(sum(named.get(by_key[key], 0) for key in MASTERY[1:]) + spread_mass,
                         sum(totals[key] for key in MASTERY[1:]))

    def test_a_resistance_loss_lands_on_the_element_the_build_wants_least(self):
        from fashionistapulp.wakfu_model import WakfuBuild
        kel_dwa = self.item(21697)
        loss = [(self.key(stat_id), value, elements) for stat_id, value, elements in kel_dwa.element_spread]
        self.assertEqual([('res_in_percent', -250, 1)], loss)
        build = WakfuBuild(self.structure, 245, {'res_fire_percent': 1})
        landing = build.where_the_spread_lands({'LEFT_HAND': kel_dwa})
        self.assertEqual(0, landing['res_fire_percent'])
        self.assertEqual(-250, sum(landing[key] for key in RESISTANCE[1:]))
        self.assertEqual(landing['res_water_percent'], build.totals({'LEFT_HAND': kel_dwa})['res_water_percent'])
        self.assertEqual(0, build._spread_weight('res_in_percent', -250, 1))
