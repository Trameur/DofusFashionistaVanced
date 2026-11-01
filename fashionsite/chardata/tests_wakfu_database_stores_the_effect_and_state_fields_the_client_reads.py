import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import build_wakfu_db as builder  # noqa: E402
import get_wakfu_client  # noqa: E402

CLIENT_DIR = Path(SCRAPER) / 'wakfu_client'
NO_TRIGGERS = [[], [], [], [], [], [], []]
_REAL = {}


def real_tables():
    """The newest decoded tables.json, read once, or None."""
    if 'tables' not in _REAL:
        found = sorted(CLIENT_DIR.glob('*/tables.json'),
                       key=lambda path: get_wakfu_client.version_key(path.parent.name))
        _REAL['tables'] = None
        if found:
            with open(found[-1], encoding='utf-8') as handle:
                _REAL['tables'] = json.load(handle)
    return _REAL['tables']


def real_db():
    if not builder.WAKFU_DB.exists():
        return None
    conn = sqlite3.connect('file:%s?mode=ro' % builder.WAKFU_DB, uri=True)
    columns = [row[1] for row in conn.execute('PRAGMA table_info(effects)')]
    if not {'target_mask', 'trigger_side', 'trigger_target', 'trigger_caster'} <= set(columns):
        conn.close()
        return None
    return conn


def an_effect(ident, **fields):
    row = {'id': ident, 'action_id': 20, 'container_id': 10, 'container_type': 'ITEM_EQUIP',
           'root_container_type': 'ITEM_EQUIP', 'normal_or_critical': 'NORMAL',
           'area_shape': 1, 'area_size': [], 'params': [1.0, 0.0], 'criterion': '',
           'min_level': None, 'max_level': None, 'triggers': NO_TRIGGERS,
           'target_mask': 0, 'display': True, 'trigger_side': 0, 'trigger_target': 0,
           'trigger_caster': 0}
    row.update(fields)
    return row


def a_state(ident, **fields):
    row = {'id': ident, 'bcw': 'key%d' % ident, 'effect_ids': [], 'max_level': 1,
           'cumulable': False}
    row.update(fields)
    return row


def an_item(ident, lines=(), **fields):
    row = {'id': ident, 'name': {'en': 'Item %d' % ident, 'fr': 'Objet %d' % ident},
           'level': 50, 'type_id': 134, 'type_name': {'en': 'Helmet', 'fr': 'Casque'},
           'positions': ['HEAD'], 'disables': [], 'rarity': 3, 'set_id': None,
           'gfx_id': 1010, 'two_handed': False, 'exclusive': None,
           'lines': list(lines)}
    row.update(fields)
    return row


def small_build(directory, items, tables=None, texts=None, code=None, descriptions=None,
                version='1.93.1.62', client_version='6.0_1.93.1.1.1'):
    """Build a database in `directory` from invented items and client files; its path."""
    directory = Path(directory)
    dump = directory / 'transformed_wakfu.json'
    dump.write_text(json.dumps({'version': version, 'client_version': client_version,
                                'equipment': items}), encoding='utf-8')
    raw = directory / 'raw' / version
    raw.mkdir(parents=True)
    if descriptions is not None:
        (raw / 'items.json').write_text(json.dumps(descriptions), encoding='utf-8')
    game_version = '.'.join(version.split('.')[:3])
    client = directory / 'client'
    folder = client / 'one'
    folder.mkdir(parents=True)
    if tables is not None:
        tables = dict(tables, game_version=game_version)
        for key in ('groups', 'sets', 'abilities', 'ability_categories', 'spells', 'pets',
                    'mounts', 'monsters', 'loot_lists'):
            tables.setdefault(key, [])
        tables.setdefault('states', [])
        tables.setdefault('item_ids', [item['id'] for item in items])
        (folder / 'tables.json').write_text(json.dumps(tables), encoding='utf-8')
    if texts is not None:
        (folder / 'texts.json').write_text(
            json.dumps({'game_version': game_version, 'texts': texts}), encoding='utf-8')
    if code is not None:
        (folder / 'client_code.json').write_text(
            json.dumps(dict(code, game_version=game_version)), encoding='utf-8')
    db = directory / 'items_wakfu.db'
    with contextlib.redirect_stdout(io.StringIO()):
        builder.build(dump, db, str(directory / 'raw'), str(client))
    return db


class TheBuilderStoresWhatTheClientRecordHoldsTests(SimpleTestCase):
    def setUp(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = temp.name

    def build(self, effects, states=()):
        db = small_build(self.directory, [an_item(10)],
                         tables={'effects': effects, 'states': list(states)})
        conn = sqlite3.connect(str(db))
        self.addCleanup(conn.close)
        return conn

    def test_an_effects_record_order_is_its_place_in_the_client_table_not_its_id(self):
        effects = [an_effect(300), an_effect(100), an_effect(200)]
        conn = self.build(effects)
        stored = dict(conn.execute('SELECT id, record_order FROM effects'))
        self.assertEqual({300: 0, 100: 1, 200: 2}, stored)

    def test_the_display_flag_and_the_target_mask_are_stored_as_the_client_read_them(self):
        big = 2 ** 50 + 5
        effects = [an_effect(1, display=False, target_mask=big),
                   an_effect(2, display=True, target_mask=0),
                   an_effect(3, target_mask=2)]
        conn = self.build(effects)
        rows = {row[0]: row[1:] for row in conn.execute(
            'SELECT id, display, target_mask FROM effects')}
        self.assertEqual({1: (0, big), 2: (1, 0), 3: (1, 2)}, rows)

    def test_the_trigger_lists_are_stored_as_a_json_array_of_the_seven_lists(self):
        triggers = [[2], [], [], [], [], [1028, 1001], []]
        conn = self.build([an_effect(1, triggers=triggers), an_effect(2)])
        stored = {ident: json.loads(text) for ident, text in conn.execute(
            'SELECT id, triggers FROM effects')}
        self.assertEqual({1: triggers, 2: NO_TRIGGERS}, stored)

    def test_the_three_trigger_bytes_are_stored_as_the_decoded_record_held_them(self):
        effects = [an_effect(1, trigger_side=3, trigger_target=5, trigger_caster=4),
                   an_effect(2, trigger_side=1, trigger_target=2, trigger_caster=2),
                   an_effect(3)]
        conn = self.build(effects)
        rows = {row[0]: row[1:] for row in conn.execute(
            'SELECT id, trigger_side, trigger_target, trigger_caster FROM effects')}
        self.assertEqual({1: (3, 5, 4), 2: (1, 2, 2), 3: (0, 0, 0)}, rows)

    def test_a_decoded_folder_without_the_trigger_bytes_is_refused(self):
        effect = an_effect(1)
        del effect['trigger_side']
        with self.assertRaisesMessage(ValueError, 'decode the client again'):
            self.build([effect])

    def test_a_states_stack_cap_and_cumulable_flag_are_stored(self):
        states = [a_state(5, max_level=6, cumulable=True), a_state(6, max_level=1)]
        conn = self.build([an_effect(1)], states)
        self.assertEqual({5: (6, 1), 6: (1, 0)}, {row[0]: row[1:] for row in conn.execute(
            'SELECT id, max_level, cumulable FROM states')})

    def test_a_decoded_folder_without_a_target_mask_is_refused(self):
        effect = an_effect(1)
        del effect['target_mask']
        with self.assertRaisesMessage(ValueError, 'decode the client again'):
            self.build([effect])


class TheStoredEffectAndStateFieldsAreTheDecodedClientsTests(SimpleTestCase):
    def setUp(self):
        self.tables = real_tables()
        self.db = real_db()
        if self.db is not None:
            self.addCleanup(self.db.close)
        if (self.tables is None or self.db is None
                or 'trigger_side' not in self.tables['effects'][0]):
            self.skipTest('no decoded Wakfu client or database with the new columns')

    def test_every_stored_effect_holds_the_flag_mask_triggers_and_place_of_its_client_record(self):
        client = {effect['id']: (number, effect)
                  for number, effect in enumerate(self.tables['effects'])}
        stored = self.db.execute(
            'SELECT id, display, record_order, target_mask, triggers FROM effects').fetchall()
        self.assertGreater(len(stored), 100000)
        wrong = []
        for ident, display, order, mask, triggers in stored:
            number, effect = client[ident]
            if (int(effect['display']), number, effect['target_mask'],
                    effect['triggers']) != (display, order, mask, json.loads(triggers)):
                wrong.append(ident)
        self.assertEqual([], wrong[:5])

    def test_the_hidden_effect_count_equals_the_client_records_with_the_flag_off(self):
        stored_ids = {row[0] for row in self.db.execute('SELECT id FROM effects')}
        hidden = sum(1 for effect in self.tables['effects']
                     if effect['id'] in stored_ids and not effect['display'])
        self.assertEqual(hidden, self.db.execute(
            'SELECT COUNT(*) FROM effects WHERE display = 0').fetchone()[0])
        self.assertGreater(hidden, 0)

    def test_record_order_is_distinct_for_every_stored_effect(self):
        total, distinct = self.db.execute(
            'SELECT COUNT(*), COUNT(DISTINCT record_order) FROM effects').fetchone()
        self.assertEqual(total, distinct)

    def test_the_non_zero_mask_count_equals_the_client_masks_of_the_stored_effects(self):
        stored_ids = {row[0] for row in self.db.execute('SELECT id FROM effects')}
        masked = sum(1 for effect in self.tables['effects']
                     if effect['id'] in stored_ids and effect['target_mask'])
        self.assertEqual(masked, self.db.execute(
            'SELECT COUNT(*) FROM effects WHERE target_mask != 0').fetchone()[0])
        self.assertGreater(masked, 0)

    def test_every_stored_effect_holds_the_three_trigger_bytes_of_its_client_record(self):
        client = {effect['id']: (effect['trigger_side'], effect['trigger_target'],
                                 effect['trigger_caster']) for effect in self.tables['effects']}
        stored = self.db.execute(
            'SELECT id, trigger_side, trigger_target, trigger_caster FROM effects').fetchall()
        self.assertGreater(len(stored), 100000)
        wrong = [row[0] for row in stored if client[row[0]] != row[1:]]
        self.assertEqual([], wrong[:5])

    def test_each_trigger_byte_value_has_as_many_stored_effects_as_client_records(self):
        stored_ids = {row[0] for row in self.db.execute('SELECT id FROM effects')}
        for column in ('trigger_side', 'trigger_target', 'trigger_caster'):
            with self.subTest(column=column):
                client = {}
                for effect in self.tables['effects']:
                    if effect['id'] in stored_ids:
                        client[effect[column]] = client.get(effect[column], 0) + 1
                stored = dict(self.db.execute(
                    'SELECT %s, COUNT(*) FROM effects GROUP BY 1' % column))
                self.assertEqual(client, stored)
                self.assertGreater(len(stored), 2)

    def test_no_effect_holds_a_trigger_target_or_caster_without_listening_to_an_event(self):
        listening = (0, 1, 3, 4, 5)
        fired = unlistened = unpaired = 0
        for triggers, target, caster in self.db.execute(
                'SELECT triggers, trigger_target, trigger_caster FROM effects'):
            lists = json.loads(triggers)
            listens = any(lists[index] for index in listening)
            if target or caster:
                fired += 1
                unlistened += not listens
                unpaired += not (target and caster)
        self.assertGreater(fired, 0)
        self.assertEqual((0, 0), (unlistened, unpaired))

    def test_the_six_roses_armor_effect_is_filtered_on_the_caster_and_animal_link_on_an_ally(self):
        rows = dict(self.db.execute(
            'SELECT id, target_mask FROM effects WHERE id IN (145873, 326491)'))
        self.assertEqual({145873: 2, 326491: 5}, rows)

    def test_every_stored_state_holds_the_stack_cap_and_cumulable_flag_of_its_record(self):
        client = {state['id']: (state['max_level'], int(state['cumulable']))
                  for state in self.tables['states']}
        stored = {row[0]: row[1:] for row in self.db.execute(
            'SELECT id, max_level, cumulable FROM states')}
        self.assertEqual(client, stored)
        self.assertGreater(sum(flag for _cap, flag in stored.values()), 0)
