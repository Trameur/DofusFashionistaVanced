import collections
import glob
import json
import os
import sqlite3

from django.test import SimpleTestCase

from fashionistapulp import wakfu_criteria as criteria

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
CLASSES = (criteria.EVALUATED, criteria.HISTORY, criteria.STATE, criteria.IMPOSSIBLE)

# Every function and literal the client's EQUIP texts use, from the census of build 1.93.1.5312.334
CENSUS_NAMES = frozenset((
    'HasAnotherSameEquipment', 'GetCharac', 'GetCharacMax', 'GetCharacteristicMax',
    'IsBreed', 'HasEquipmentId', 'GetLevel', 'GetRealLevel', 'GetEquipment', 'True',
    'GetCraftLevel', 'GetInstanceId', 'IsDay', 'HasCraft', 'IsAchievementComplete',
    'GetWakfuGauge', 'GetStasisGauge', 'GetCrimeScore', 'GetCompanyRank',
    'GetNationId', 'HasPvpRank', 'GetGuildLevel', 'IsAdmin', 'False',
))
_cache = {}


def decoded_client():
    if 'decoded' not in _cache:
        found = sorted(glob.glob(os.path.join(ROOT, 'itemscraper', 'wakfu_client', '*',
                                              'decoded.json')))
        _cache['decoded'] = None
        if found:
            with open(found[-1], encoding='utf-8') as handle:
                _cache['decoded'] = json.load(handle)
    return _cache['decoded']


def database_path():
    from fashionistapulp.fashionista_config import get_items_db_path
    return get_items_db_path('wakfu')


class EveryWakfuCriteriaFunctionHasOneClassTests(SimpleTestCase):
    def test_every_grammar_function_is_in_exactly_one_class(self):
        self.assertEqual(CENSUS_NAMES, frozenset(criteria.FUNCTIONS))
        self.assertEqual(set(CLASSES), set(criteria.FUNCTIONS.values()))
        for name in criteria.FUNCTIONS:
            self.assertEqual(1, sum(criteria.FUNCTIONS[name] == one for one in CLASSES), name)
            self.assertEqual(criteria.FUNCTIONS[name], criteria.classify(name))

    def test_every_state_function_reads_one_option(self):
        states = {name for name, kind in criteria.FUNCTIONS.items() if kind == criteria.STATE}
        owners = collections.defaultdict(list)
        for option in criteria.STATE_OPTIONS:
            for name in option.functions:
                owners[name].append(option.name)
        self.assertEqual(states, set(owners))
        self.assertEqual([], [name for name, options in owners.items() if len(options) != 1])
        self.assertEqual(len(criteria.STATE_OPTIONS),
                         len({option.name for option in criteria.STATE_OPTIONS}))
        self.assertEqual(len(criteria.STATE_OPTIONS),
                         len({option.flag for option in criteria.STATE_OPTIONS}))

    def test_every_shown_function_has_a_label_key(self):
        shown = {name for name, kind in criteria.FUNCTIONS.items()
                 if kind in (criteria.HISTORY, criteria.IMPOSSIBLE)
                 and name not in ('IsAdmin',)}
        self.assertEqual(set(), shown - set(criteria.LABEL_KEYS))
        for name, (key, negated) in criteria.LABEL_KEYS.items():
            self.assertTrue(key.startswith('critere.'), name)
            self.assertTrue(negated is None or negated.startswith('critere.'), name)
        for option in criteria.STATE_OPTIONS:
            self.assertTrue(option.label_key.startswith('critere.'), option.name)


class EveryClientEquipTextIsReviewedTests(SimpleTestCase):
    def setUp(self):
        self.client = decoded_client()
        if self.client is None or not os.path.exists(database_path()):
            self.skipTest('no decoded Wakfu client or database; run get_wakfu_client.py')
        connection = sqlite3.connect('file:%s?mode=ro' % database_path(), uri=True)
        try:
            self.gear = {ident for (ident,) in connection.execute('SELECT id FROM items')}
        finally:
            connection.close()
        self.records = {int(key): value for key, value in self.client['items'].items()
                        if int(key) in self.gear}

    def test_every_equip_text_parses_and_names_known_functions(self):
        texts = [(ident, text) for ident, record in sorted(self.records.items())
                 for kind, text in record['criteria'] if kind == 'EQUIP']
        self.assertGreater(len(texts), 1000)
        for ident, text in texts:
            tree = criteria.parse(text)
            for name in criteria.functions(tree):
                self.assertIn(name, criteria.FUNCTIONS, 'item %s' % ident)

    def test_every_criteria_kind_and_property_on_gear_is_reviewed(self):
        kinds = {kind for record in self.records.values() for kind, _text in record['criteria']}
        self.assertEqual(set(), kinds - set(criteria.REVIEWED_KINDS))
        properties = {number for record in self.records.values() for number in record['properties']}
        self.assertEqual(set(), properties - set(criteria.REVIEWED_PROPERTIES))
        equip = {ident: text for ident, record in self.records.items()
                 for kind, text in record['criteria'] if kind == 'EQUIP'}
        for ident, record in self.records.items():
            for kind, text in record['criteria']:
                if kind != 'CRAFT' or 'HasEquipmentId' not in text:
                    continue
                targets = [call.args[0] for call in _calls(criteria.parse(text))
                           if call.name == 'HasEquipmentId']
                self.assertTrue(targets)
                for target in targets:
                    self.assertIn(target, equip, 'item %s CRAFT names %s' % (ident, target))
                    names = [call.args[0] for call in _calls(criteria.parse(equip[target]))
                             if call.name == 'HasEquipmentId']
                    self.assertIn(ident, names, 'item %s is not mirrored by %s' % (ident, target))

    def test_no_gear_record_carries_actions_or_sub_records_unless_it_is_unusable(self):
        carrying = {ident: record for ident, record in self.records.items()
                    if record['actions'] or record['sub_records']}
        for ident, record in carrying.items():
            self.assertEqual([['EQUIP', 'False']], record['criteria'], 'item %s' % ident)
        self.assertEqual(0, sum(record['sub_records'] for record in self.records.values()))


def _calls(tree):
    for node in criteria._walk(tree):
        if isinstance(node, criteria.Call):
            yield node


class TheWakfuDatabaseHoldsWhatTheTextsSayTests(SimpleTestCase):
    def setUp(self):
        if not os.path.exists(database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.db = sqlite3.connect('file:%s?mode=ro' % database_path(), uri=True)
        self.addCleanup(self.db.close)
        if not self.db.execute('SELECT 1 FROM sqlite_master WHERE name = ?',
                               ('item_criteria',)).fetchone():
            self.skipTest('the database holds no equip conditions')

    def rows(self, sql, *args):
        return self.db.execute(sql, args).fetchall()

    def test_derived_rows_equal_the_derivation_of_each_raw_text(self):
        ids = {key.lower(): number for number, key in self.rows('SELECT id, key FROM stats')}
        names = {name for (name,) in self.rows('SELECT name FROM breeds')}
        gear = {ident for (ident,) in self.rows('SELECT id FROM items')}
        self.assertTrue(ids)
        expected = collections.defaultdict(set)
        texts = self.rows('SELECT item, criteria FROM item_criteria')
        self.assertGreater(len(texts), 1000)
        for ident, text in texts:
            derived = criteria.derive(criteria.parse(text), stat_keys=set(ids),
                                      breed_names=names, item_ids=gear)
            if derived.unusable:
                expected['unusable_items'].add((ident,))
            for name in derived.classes:
                expected['item_class_conditions'].add((ident, name))
            for key, value in derived.min_stats.items():
                expected['min_stat_to_equip'].add((ident, ids[key], value))
            for key, value in derived.max_stats.items():
                expected['max_stat_to_equip'].add((ident, ids[key], value))
            for other in derived.worn_with:
                expected['items_worn_with'].add((ident, other))
            for other in derived.not_worn_with:
                expected['items_not_worn_together'].add((ident, other))
            if derived.min_level is not None:
                expected['min_level_to_equip'].add((ident, derived.min_level))
            if derived.max_level is not None:
                expected['max_level_to_equip'].add((ident, derived.max_level))
            for condition in derived.state:
                expected['item_state_conditions'].add(
                    (ident, condition.option, condition.nation, condition.operator,
                     condition.value))
        tables = {
            'unusable_items': 'SELECT item FROM unusable_items',
            'item_class_conditions': 'SELECT item, class FROM item_class_conditions',
            'min_stat_to_equip': 'SELECT item, stat, value FROM min_stat_to_equip',
            'max_stat_to_equip': 'SELECT item, stat, value FROM max_stat_to_equip',
            'items_worn_with': 'SELECT item, other FROM items_worn_with',
            'items_not_worn_together': 'SELECT item, other FROM items_not_worn_together',
            'min_level_to_equip': 'SELECT item, value FROM min_level_to_equip',
            'max_level_to_equip': 'SELECT item, value FROM max_level_to_equip',
            'item_state_conditions': 'SELECT item, option, nation, operator, value'
                                     ' FROM item_state_conditions',
        }
        mirrored = {ident for ident, _text in texts}
        for table, sql in tables.items():
            held = {row for row in self.rows(sql) if row[0] in mirrored}
            self.assertEqual(expected[table], held, table)

    def test_no_derived_row_without_a_raw_text(self):
        raw = {ident for (ident,) in self.rows('SELECT item FROM item_criteria')}
        for table in ('item_class_conditions', 'items_worn_with', 'min_level_to_equip',
                      'max_level_to_equip', 'unusable_items', 'item_state_conditions'):
            owners = {ident for (ident,) in self.rows('SELECT item FROM %s' % table)}
            self.assertEqual(set(), owners - raw, table)
        for table in ('min_stat_to_equip', 'max_stat_to_equip', 'items_not_worn_together'):
            owners = {ident for (ident,) in self.rows('SELECT item FROM %s' % table)}
            self.assertEqual(set(), owners - raw, table)

    def test_labels_and_nations_are_in_five_languages_german_being_english(self):
        held = collections.defaultdict(set)
        for key, language in self.rows('SELECT key, language FROM criteria_labels'):
            held[key].add(language)
        wanted = {key for key, negated in criteria.LABEL_KEYS.values() for key in (key, negated)
                  if key} | {option.label_key for option in criteria.STATE_OPTIONS}
        for key in sorted(wanted):
            self.assertEqual(set(LANGUAGES), held.get(key, set()), key)
        nations = collections.defaultdict(set)
        for ident, language in self.rows('SELECT id, language FROM nations'):
            nations[ident].add(language)
        self.assertGreaterEqual(len(nations), 6)
        for ident, languages in nations.items():
            self.assertEqual(set(LANGUAGES), languages, 'nation %s' % ident)

    def test_no_pool_item_needs_get_equipment(self):
        carrying = [ident for ident, text in self.rows('SELECT item, criteria FROM item_criteria')
                    if 'GetEquipment' in criteria.functions(criteria.parse(text))]
        self.assertEqual([], carrying)

    def test_the_lock_forbid_wakfu_list_holds_only_legacy_items(self):
        from chardata import lock_forbid
        listed = lock_forbid.DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION.get('wakfu', [])
        legacy = {ident for (ident,) in self.rows(
            'SELECT item FROM item_rarity WHERE rarity = 0')}
        self.assertEqual([], [ident for ident in listed if ident not in legacy])

    def test_every_unique_piece_is_held_to_one_copy(self):
        from fashionistapulp.game_versions import get_game_version
        unique = [ident for ident, text in self.rows('SELECT item, criteria FROM item_criteria')
                  if 'HasAnotherSameEquipment' in criteria.functions(criteria.parse(text))]
        self.assertGreater(len(unique), 100)
        self.assertFalse(get_game_version('wakfu').rings_can_double)
