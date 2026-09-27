import collections
import io
import json
import os
import sqlite3

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
STATE_ACTION = 304
CdnItem = collections.namedtuple('CdnItem', 'id type rarity properties equip use')
_cache = {}


def _read(path):
    with io.open(path, encoding='utf-8') as handle:
        return json.load(handle)


class WakfuCountsDifferFromTheCdnOnlyByScopeTests(SimpleTestCase):
    """Every item, line or spell the CDN counts and the database lacks falls in a named group."""

    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        self.db = get_items_db_path('wakfu')
        if not os.path.exists(self.db):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        dump = os.path.join(SCRAPER, 'transformed_wakfu.json')
        if not os.path.exists(dump):
            self.skipTest('no decoded Wakfu dump; run itemscraper/get_items_wakfu.py')
        if 'dump' not in _cache:
            _cache['dump'] = _read(dump)
        self.dump = _cache['dump']
        self.build_dir = os.path.join(SCRAPER, 'wakfu_raw', self.dump['version'])
        if not os.path.exists(os.path.join(self.build_dir, 'items.json')):
            self.skipTest('no CDN mirror of Wakfu %s' % self.dump['version'])

    def cdn(self, name):
        path = os.path.join(self.build_dir, name)
        if path not in _cache:
            _cache[path] = _read(path)
        return _cache[path]

    def cdn_items(self):
        out = []
        for row in self.cdn('items.json'):
            definition = row['definition']
            base = definition['item']
            parameters = base['baseParameters']
            out.append(CdnItem(base['id'], parameters['itemTypeId'], parameters.get('rarity'),
                               set(base.get('properties') or ()), definition.get('equipEffects') or [],
                               definition.get('useEffects') or []))
        return out

    def positions(self):
        """{equipment type id: {position, ...}}"""
        return {row['definition']['id']: set(row['definition'].get('equipmentPositions') or ())
                for row in self.cdn('equipmentItemTypes.json')}

    def property_id(self, name):
        found = [row['id'] for row in self.cdn('itemProperties.json') if row['name'] == name]
        self.assertEqual(1, len(found), 'itemProperties.json names %s %d times' % (name, len(found)))
        return found[0]

    def ids(self, query, parameters=()):
        connection = sqlite3.connect('file:%s?mode=ro' % self.db, uri=True)
        try:
            return {row[0] for row in connection.execute(query, parameters)}
        finally:
            connection.close()

    def live(self):
        return self.ids('SELECT id FROM items WHERE removed = 0')

    def legacy_in_db(self):
        from fashionistapulp.wakfu_slots import LEGACY_RARITY
        return self.ids('SELECT r.item FROM item_rarity r JOIN items i ON i.id = r.item'
                        ' WHERE r.rarity = ? AND i.removed = 0', (LEGACY_RARITY,))

    def test_every_rarity_zero_item_is_out_of_the_game_encyclopedia(self):
        from fashionistapulp.wakfu_slots import LEGACY_RARITY, RARITIES
        hidden = self.property_id('EXCLUDE_FROM_ENCYCLOPEDIA')
        legacy = [item for item in self.cdn_items() if item.rarity == LEGACY_RARITY]
        self.assertGreater(len(legacy), 100)
        self.assertEqual([], [item.id for item in legacy if hidden not in item.properties])
        self.assertEqual('legacy', RARITIES[LEGACY_RARITY])

    def test_the_cdn_epics_are_the_database_epics_plus_those_with_no_stat_line(self):
        from fashionistapulp.wakfu_slots import EXCLUSIVE_PROPERTIES
        epic = {group: number for number, group in EXCLUSIVE_PROPERTIES.items()}['epic']
        cdn = {item.id: item for item in self.cdn_items() if epic in item.properties}
        database = self.ids("SELECT item FROM item_flags WHERE flag = 'epic'")
        self.assertGreater(len(database), 50)
        self.assertEqual(set(), database - set(cdn))
        no_stat_line = {item_id for item_id, item in cdn.items() if not item.equip}
        self.assertEqual(no_stat_line, set(cdn) - database)

    def test_the_cdn_rarity_zero_equipment_is_the_database_legacy_tier_plus_what_it_leaves_out(self):
        from fashionistapulp.wakfu_slots import LEGACY_RARITY, NOT_GEAR, SLOTS
        positions = self.positions()
        cdn = [item for item in self.cdn_items() if item.rarity == LEGACY_RARITY and item.type in positions]
        not_gear = {item.id for item in cdn if not positions[item.type] & set(SLOTS)}
        worn_there = set().union(*(positions[item.type] for item in cdn if item.id in not_gear))
        self.assertEqual(set(), worn_there - set(NOT_GEAR))
        no_stat_line = {item.id for item in cdn if item.id not in not_gear and not item.equip}
        legacy = self.legacy_in_db()
        self.assertGreater(len(legacy), 100)
        self.assertEqual(legacy, {item.id for item in cdn} - not_gear - no_stat_line)

    def test_database_items_out_of_the_encyclopedia_are_the_legacy_tier_and_a_few_others(self):
        hidden = self.property_id('EXCLUDE_FROM_ENCYCLOPEDIA')
        live = self.live()
        hidden_in_db = {item.id for item in self.cdn_items() if hidden in item.properties and item.id in live}
        legacy = self.legacy_in_db()
        self.assertGreater(len(legacy), 100)
        self.assertEqual(set(), legacy - hidden_in_db)
        self.assertLess(len(hidden_in_db - legacy), len(legacy) // 10)

    def test_the_cdn_state_lines_are_the_decoded_ones_plus_weapon_use_effects(self):
        from fashionistapulp.wakfu_slots import SLOTS

        def states(effects):
            return [effect for effect in effects
                    if ((effect.get('effect') or {}).get('definition') or {}).get('actionId') == STATE_ACTION]

        items = self.cdn_items()
        equip = [item for item in items for _line in states(item.equip)]
        use = [item for item in items for _line in states(item.use)]
        decoded = sum(1 for entry in self.dump['equipment'] for line in entry['lines']
                      if line.get('action') == STATE_ACTION)
        self.assertEqual(len(equip), decoded)

        positions, live = self.positions(), self.live()
        hosts = collections.Counter()
        stray = []
        for item in equip:
            if item.id in live:
                hosts['gear in the database'] += 1
            elif item.type not in positions:
                hosts['not equipment'] += 1
            elif not positions[item.type] & set(SLOTS):
                hosts['not gear'] += 1
            else:
                stray.append(item.id)
        self.assertEqual([], stray)
        self.assertGreater(hosts['gear in the database'], 20)
        self.assertGreater(hosts['not equipment'], 100)

        weapons = {type_id for type_id, places in positions.items() if 'FIRST_WEAPON' in places}
        self.assertEqual([], [item.id for item in use if item.id not in live or item.type not in weapons])

    def test_the_spell_table_is_the_french_harvest_and_each_language_names_what_it_lists(self):
        def harvest(language):
            path = os.path.join(self.build_dir, 'spells_%s.json' % language)
            if not os.path.exists(path):
                self.skipTest('no %s spell harvest for Wakfu %s' % (language, self.dump['version']))
            if path not in _cache:
                _cache[path] = {int(spell_id) for spell_id in _read(path)}
            return _cache[path]

        def named(language):
            return self.ids('SELECT spell FROM spell_names WHERE language = ?', (language,))

        french = harvest('fr')
        self.assertEqual(french, self.ids('SELECT id FROM spells'))
        for language in ('en', 'es', 'pt'):
            with self.subTest(language=language):
                listed = harvest(language)
                self.assertGreater(len(listed & french), 600)
                self.assertEqual(listed & french, named(language))
        self.assertEqual(named('en'), named('de'))
