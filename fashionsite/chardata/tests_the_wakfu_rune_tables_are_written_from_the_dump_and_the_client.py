import contextlib
import copy
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
from chardata.tests_wakfu_effect_groups_resolve_to_known_effects import (  # noqa: E402
    effect, tables)

RUNE = 900
HELMET, CLOAK, DAGGER = 10, 11, 12
LINES = ((5001, 0, 0, 1.0, 0.0), (5002, 1, 2, 0.0, 1.5), (5003, 3, 3, -3.0, 4.5))


def gear(ident, type_id, type_name, position, slots):
    return {'id': ident, 'name': {'en': 'Piece %d' % ident, 'fr': 'Piece %d fr' % ident},
            'level': 50, 'type_id': type_id, 'type_name': {'en': type_name, 'fr': type_name},
            'positions': [position], 'disables': [], 'rarity': 3, 'set_id': None,
            'gfx_id': 1000 + ident, 'two_handed': False, 'exclusive': None,
            'shard_slots': slots, 'lines': [{'stat': 'HP', 'value': 100, 'action': 20}]}


def rune(**shard):
    fields = {'color': 1, 'double_positions': [0, 13], 'curve': [1, 2, 4],
              'requirement': [0, 36, 51]}
    fields.update(shard)
    return {
        'id': RUNE, 'name': {'en': 'Melee Mastery', 'fr': 'Maitrise Melee'}, 'level': 0,
        'type_id': 811, 'type_name': {'en': 'Rune'}, 'positions': [], 'disables': [],
        'rarity': 1, 'set_id': None, 'gfx_id': 0, 'two_handed': False, 'exclusive': None,
        'shard_slots': [0, 0], 'shard': fields,
        'lines': [{'action': 1052, 'effect': ident, 'params': [base, slope],
                   'stat': 'MELEE_DMG', 'value': base} for ident, _low, _high, base, slope
                  in LINES]}


def client_effects():
    return [dict(effect(ident, 1052, 'ITEM_EQUIP', RUNE), min_level=low, max_level=high,
                 params=[base, slope]) for ident, low, high, base, slope in LINES]


class TheWakfuRuneTablesAreWrittenFromTheDumpAndTheClientTests(SimpleTestCase):
    def setUp(self):
        if not builder.DOFUS_DB.exists():
            self.skipTest('items.db absent, the Wakfu schema is copied from it')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.db = self.directory / 'items_wakfu.db'
        self.pieces = [gear(HELMET, 134, 'Helmet', 'HEAD', [1, 4]),
                       gear(CLOAK, 132, 'Cloak', 'BACK', [1, 4]),
                       gear(DAGGER, 112, 'Dagger', 'SECOND_WEAPON', [0, 0])]

    def build(self, runes=None, effects=None, pieces=None):
        runes = [rune()] if runes is None else runes
        payload = tables(client_effects() if effects is None else effects, [])
        payload['game_version'] = '1.0'
        folder = self.directory / 'client' / '1.0'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'tables.json').write_text(json.dumps(payload), encoding='utf-8')
        dump = self.directory / 'transformed_wakfu.json'
        dump.write_text(json.dumps({
            'version': '1.0',
            'equipment': list(self.pieces if pieces is None else pieces) + runes}),
            encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            builder.main(['--dump', str(dump), '--db', str(self.db),
                          '--out', str(self.directory / 'raw'),
                          '--client', str(self.directory / 'client')])

    def rows(self, query):
        connection = sqlite3.connect(self.db)
        try:
            return connection.execute(query).fetchall()
        finally:
            connection.close()

    def test_a_rune_is_written_with_its_colour_action_stat_names_levels_and_lines(self):
        self.build()
        melee = self.rows("SELECT id FROM stats WHERE key = 'melee_dmg'")[0][0]
        self.assertEqual([(RUNE, 1, 1052, melee)], self.rows('SELECT * FROM shards'))
        self.assertEqual({('en', 'Melee Mastery'), ('fr', 'Maitrise Melee')},
                         set(self.rows('SELECT language, name FROM shard_names')))
        self.assertEqual([(RUNE, 'BACK'), (RUNE, 'HEAD')],
                         self.rows('SELECT * FROM shard_double_positions ORDER BY position'))
        self.assertEqual([(RUNE, 1, 1, 0), (RUNE, 2, 2, 36), (RUNE, 3, 4, 51)],
                         self.rows('SELECT * FROM shard_levels ORDER BY level'))
        self.assertEqual([(RUNE,) + line for line in LINES],
                         self.rows('SELECT * FROM shard_lines ORDER BY effect'))

    def test_a_rune_whose_action_gives_no_stat_is_written_with_a_null_stat(self):
        empty = rune()
        for line in empty['lines']:
            line.pop('stat')
            line['action'] = 400
        self.build(runes=[empty])
        self.assertEqual([(RUNE, 1, 400, None)], self.rows('SELECT * FROM shards'))

    def test_every_gear_item_gets_its_socket_range_and_a_rune_gets_none(self):
        self.build()
        self.assertEqual([(HELMET, 1, 4), (CLOAK, 1, 4), (DAGGER, 0, 0)],
                         self.rows('SELECT * FROM item_shard_slots ORDER BY item'))

    def test_a_removed_item_keeps_its_socket_range(self):
        self.build(runes=[rune(double_positions=[])])
        self.build(runes=[rune(double_positions=[])], pieces=self.pieces[1:])
        self.assertEqual([(HELMET, 1, 4), (CLOAK, 1, 4), (DAGGER, 0, 0)],
                         self.rows('SELECT * FROM item_shard_slots ORDER BY item'))
        self.assertEqual([(HELMET, 1)], self.rows('SELECT id, removed FROM items'
                                                  ' WHERE removed = 1'))

    def test_a_previous_database_without_the_socket_table_is_read(self):
        self.build(runes=[rune(double_positions=[])])
        connection = sqlite3.connect(self.db)
        connection.execute('DROP TABLE item_shard_slots')
        connection.commit()
        connection.close()
        self.build(runes=[rune(double_positions=[])], pieces=self.pieces[1:])
        self.assertEqual([(CLOAK, 1, 4), (DAGGER, 0, 0)],
                         self.rows('SELECT * FROM item_shard_slots ORDER BY item'))

    def test_a_double_position_id_the_client_enum_lacks_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, 'map lacks'):
            self.build(runes=[rune(double_positions=[0, 99])])

    def test_a_double_position_no_item_with_sockets_fills_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, 'no item with sockets fills'):
            self.build(runes=[rune(double_positions=[0, 16])])
        with self.assertRaisesRegex(ValueError, 'no item with sockets fills'):
            self.build(runes=[rune(double_positions=[1])])

    def test_an_effect_the_client_table_lacks_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, 'not in the client effect table'):
            self.build(effects=client_effects()[:2])

    def test_an_effect_without_a_level_range_stops_the_build(self):
        broken = client_effects()
        broken[1]['min_level'] = None
        with self.assertRaisesRegex(ValueError, 'no level range'):
            self.build(effects=broken)

    def test_a_tier_covered_twice_or_never_stops_the_build(self):
        twice = client_effects()
        twice[2]['min_level'] = 2
        with self.assertRaisesRegex(ValueError, 'tier 2 is covered by 2 lines'):
            self.build(effects=twice)
        never = client_effects()
        never[1]['max_level'] = 1
        with self.assertRaisesRegex(ValueError, 'tier 2 is covered by 0 lines'):
            self.build(effects=never)

    def test_a_rune_mixing_actions_stops_the_build(self):
        mixed = rune()
        mixed['lines'][1]['action'] = 1053
        with self.assertRaisesRegex(ValueError, 'mixes actions'):
            self.build(runes=[mixed])

    def test_a_curve_and_a_requirement_of_different_lengths_stop_the_build(self):
        with self.assertRaisesRegex(ValueError, '3 costs for 2 item levels'):
            self.build(runes=[rune(requirement=[0, 36])])

    def test_the_client_table_decoded_before_the_level_range_cannot_pass_as_a_range(self):
        old = [{key: value for key, value in one.items() if key not in ('min_level', 'max_level')}
               for one in copy.deepcopy(client_effects())]
        with self.assertRaisesRegex(ValueError, 'no level range'):
            self.build(effects=old)
