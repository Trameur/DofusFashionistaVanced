import os
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import wakfu_client  # noqa: E402
from chardata.tests_wakfu_client_decoder_reads_a_table_it_wrote import (  # noqa: E402
    container)


# What a field is written as when the invented record does not name it
DEFAULTS = {'i8': 0, 'bool': False, 'i16': 0, 'i32': 0, 'i64': 0, 'f32': 0.5,
            'text': '', 'i32[]': [], 'i64[]': [], 'f32[]': []}
WRITE = {'i8': 'i8', 'bool': 'boolean', 'i16': 'i16', 'i32': 'i32', 'i64': 'i64',
         'f32': 'f32', 'text': 'text', 'i32[]': 'i32s'}


def put(writer, kind, value):
    if kind in WRITE:
        getattr(writer, WRITE[kind])(value)
        return
    writer.i32(len(value))
    for one in value:
        getattr(writer, WRITE[kind[:-2]])(one)


def write_layout(layout, short=None):
    """A record writer for `layout`; `short` names a field written one byte short."""
    def write(writer, record):
        for name, kind in layout:
            if name == short:
                assert kind == 'i16', 'a one byte shift needs an i16 to narrow'
                writer.i8(0)
                continue
            value = record.get(name, DEFAULTS[kind])
            put(writer, kind, value)
    return write


def write_set(writer, record):
    writer.i16(record['id'])
    writer.i32(record['elG'])
    writer.i32s(record['item_ids'])
    writer.i32(len(record['bonuses']))
    for pieces, effect_ids in record['bonuses']:
        writer.i32(pieces)
        writer.i32s(effect_ids)


def jar(path, name, blob):
    with zipfile.ZipFile(path, 'w') as handle:
        handle.writestr(name, blob)
    return path


EFFECTS = [
    {'id': 1, 'action_id': 20, 'container_id': 28822, 'area_size': [3, 4],
     'area_shape': 2, 'normal_or_critical': 'NORMAL  ', 'container_type': 'ITEM_EQUIP ',
     'root_container_type': 'ITEM_EQUIP', 'params': [6.0, 0.5, 1.25, -2.0]},
    {'id': 2, 'action_id': 304, 'container_id': 77, 'normal_or_critical': 'CRITICAL',
     'container_type': 'GROUP', 'root_container_type': 'STATE', 'params': [0.4]},
    {'id': 2000000003, 'action_id': 330, 'container_id': -5, 'area_size': [],
     'normal_or_critical': 'NORMAL', 'container_type': 'SET', 'root_container_type': 'SET',
     'params': []},
]
GROUPS = [{'id': 10, 'effect_ids': [1, 2]}, {'id': 11, 'effect_ids': []},
          {'id': 12, 'effect_ids': [2000000003]}]
STATES = [{'id': 5, 'bcw': 'malus_portee', 'efW': [1, 2]}, {'id': 6, 'bcw': '', 'efW': []}]
ABILITIES = [{'id': 20, 'category': 4, 'ddL': 20, 'cgI': 2, 'effect_ids': [136469]},
             {'id': 31, 'category': 3, 'ddL': 0, 'cgI': 231, 'effect_ids': []}]
CATEGORIES = [{'id': 2, 'unlock_levels': [2, 6, 10, 243], 'ability_ids': [1, 16]},
              {'id': 6, 'unlock_levels': [], 'ability_ids': [2, 3, 4]}]
SETS = [{'id': 41, 'elG': 13013, 'item_ids': [2023, 2021], 'bonuses': []},
        {'id': 620, 'elG': -1, 'item_ids': [1, 2, 3, 4, 5, 6],
         'bonuses': [(3, [100, 101]), (6, [102])]},
        {'id': 643, 'elG': 5, 'item_ids': [], 'bonuses': [(10, [])]}]

TABLES = (
    (wakfu_client.STATIC_EFFECT_TABLE, 'effects', EFFECTS, wakfu_client.read_effects,
     write_layout(wakfu_client.STATIC_EFFECT_LAYOUT)),
    (wakfu_client.EFFECT_GROUP_TABLE, 'groups', GROUPS, wakfu_client.read_effect_groups,
     write_layout(wakfu_client.EFFECT_GROUP_LAYOUT)),
    (wakfu_client.STATE_TABLE, 'states', STATES, wakfu_client.read_states,
     write_layout(wakfu_client.STATE_LAYOUT)),
    (wakfu_client.ABILITY_TABLE, 'abilities', ABILITIES, wakfu_client.read_abilities,
     write_layout(wakfu_client.ABILITY_LAYOUT)),
    (wakfu_client.ABILITY_CATEGORY_TABLE, 'categories', CATEGORIES,
     wakfu_client.read_ability_categories,
     write_layout(wakfu_client.ABILITY_CATEGORY_LAYOUT)),
    (wakfu_client.ITEM_SET_TABLE, 'sets', SETS, wakfu_client.read_item_sets, write_set),
)


def f32(number):
    return struct.unpack('<f', struct.pack('<f', number))[0]


class TheWakfuClientTablesReadBackEveryRecordTests(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def table(self, number, records, write, **shifts):
        blob = container(number, records, write, **shifts)
        return jar(self.folder / ('%d.jar' % number), '%d.bin' % number, blob)

    def test_the_effect_reader_returns_every_invented_effect_field_for_field(self):
        read = wakfu_client.read_effects(
            self.table(68, EFFECTS, write_layout(wakfu_client.STATIC_EFFECT_LAYOUT)))
        self.assertEqual([1, 2, 2000000003], [record.id for record in read])
        first, second, third = read
        self.assertEqual(
            (20, 28822, 'ITEM_EQUIP', 'ITEM_EQUIP', 'NORMAL', 2, [3, 4]),
            (first.action_id, first.container_id, first.container_type,
             first.root_container_type, first.normal_or_critical, first.area_shape,
             first.area_size))
        self.assertEqual([6.0, 0.5, 1.25, -2.0], first.params)
        self.assertEqual([f32(0.4)], second.params)
        self.assertEqual(('CRITICAL', 'GROUP', 'STATE', 77), (
            second.normal_or_critical, second.container_type,
            second.root_container_type, second.container_id))
        self.assertEqual((330, -5, []), (third.action_id, third.container_id, third.params))

    def test_the_group_state_ability_and_category_readers_return_their_fields(self):
        groups = wakfu_client.read_effect_groups(
            self.table(29, GROUPS, write_layout(wakfu_client.EFFECT_GROUP_LAYOUT)))
        self.assertEqual([(10, [1, 2]), (11, []), (12, [2000000003])],
                         [(record.id, record.effect_ids) for record in groups])
        states = wakfu_client.read_states(
            self.table(67, STATES, write_layout(wakfu_client.STATE_LAYOUT)))
        self.assertEqual([(5, 'malus_portee', [1, 2]), (6, '', [])],
                         [(record.id, record.bcw, record.effect_ids) for record in states])
        abilities = wakfu_client.read_abilities(
            self.table(135, ABILITIES, write_layout(wakfu_client.ABILITY_LAYOUT)))
        self.assertEqual([(20, 4, 20, 2, [136469]), (31, 3, 0, 231, [])],
                         [tuple(record) for record in abilities])
        categories = wakfu_client.read_ability_categories(
            self.table(136, CATEGORIES, write_layout(wakfu_client.ABILITY_CATEGORY_LAYOUT)))
        self.assertEqual([(2, [2, 6, 10, 243], [1, 16]), (6, [], [2, 3, 4])],
                         [tuple(record) for record in categories])

    def test_the_set_reader_returns_the_bonus_map_of_each_set(self):
        read = wakfu_client.read_item_sets(self.table(36, SETS, write_set))
        self.assertEqual([41, 620, 643], [record.id for record in read])
        self.assertEqual({}, read[0].bonuses)
        self.assertEqual({3: [100, 101], 6: [102]}, read[1].bonuses)
        self.assertEqual([1, 2, 3, 4, 5, 6], read[1].item_ids)
        self.assertEqual(-1, read[1].elG)
        self.assertEqual({10: []}, read[2].bonuses)

    def test_a_set_that_lists_the_same_piece_count_twice_raises(self):
        twice = [{'id': 7, 'elG': 0, 'item_ids': [], 'bonuses': [(3, [1]), (3, [2])]}]
        with self.assertRaisesRegex(wakfu_client.TableError, 'twice'):
            wakfu_client.read_item_sets(self.table(36, twice, write_set))

    def test_every_reader_raises_on_a_wrong_record_size_or_id(self):
        for number, _name, records, read, write in TABLES:
            with self.assertRaisesRegex(wakfu_client.TableError, 'header says', msg=number):
                read(self.table(number, records, write, size_shift=3))
            with self.assertRaisesRegex(wakfu_client.TableError, 'starts with id', msg=number):
                read(self.table(number, records, write, id_shift=1))

    def test_every_reader_raises_on_a_truncated_or_foreign_file(self):
        for number, _name, records, read, write in TABLES:
            good = container(number, records, write)
            with self.assertRaises(wakfu_client.TableError, msg=number):
                read(jar(self.folder / 'cut.jar', '%d.bin' % number, good[:-5]))
            with self.assertRaises(wakfu_client.TableError, msg=number):
                read(jar(self.folder / 'other.jar', 'other.bin', good))

    def test_a_record_one_byte_short_in_the_middle_raises(self):
        for number, field, layout, read, records in (
                (68, 'short_esK', wakfu_client.STATIC_EFFECT_LAYOUT,
                 wakfu_client.read_effects, EFFECTS),
                (67, 'aYh', wakfu_client.STATE_LAYOUT, wakfu_client.read_states, STATES)):
            honest = self.table(number, records, write_layout(layout))
            self.assertEqual(len(records), len(read(honest)))
            # The header sizes follow the narrow records, the reader still takes an i16
            narrow = container(number, records, write_layout(layout, short=field))
            with self.assertRaises(wakfu_client.TableError, msg=number):
                read(jar(self.folder / 'narrow.jar', '%d.bin' % number, narrow))

    def test_every_reader_raises_on_a_header_size_one_byte_off(self):
        for number, _name, records, read, write in TABLES:
            for shift in (1, -1):
                with self.assertRaises(wakfu_client.TableError, msg=(number, shift)):
                    read(self.table(number, records, write, size_shift=shift))
