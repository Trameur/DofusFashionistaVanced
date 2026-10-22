import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

SCRAPER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper')
if SCRAPER not in sys.path:
    sys.path.insert(0, SCRAPER)

import wakfu_client  # noqa: E402
from chardata.tests_wakfu_client_decoder_reads_a_table_it_wrote import (  # noqa: E402
    container)
from chardata.tests_wakfu_client_tables_read_back_every_record import (  # noqa: E402
    jar)

DEFAULTS = {'i8': 3, 'bool': True, 'i16': 4, 'i32': 5, 'i64': 6, 'f32': 0.5, 'f64': 0.25,
            'text': 'x', 'i32[]': [1, 2], 'i16[]': [7], 'text[]': ['a', 'b']}
WRITE = {'i8': 'i8', 'bool': 'boolean', 'i16': 'i16', 'i32': 'i32', 'i64': 'i64',
         'f32': 'f32', 'f64': 'f64', 'text': 'text', 'i32[]': 'i32s', 'i16[]': 'i16s',
         'text[]': 'texts'}


def write_nested(writer, cls, record):
    """One record of a class of NESTED_LAYOUTS; a field the record does not name is defaulted."""
    for row in wakfu_client.NESTED_LAYOUTS[cls]:
        name, kind = row[0], row[1]
        if kind == 'array':
            items = record.get(name, [])
            writer.i32(len(items))
            for item in items:
                write_nested(writer, row[2], item)
        elif kind == 'map':
            entries = record.get(name, {})
            writer.i32(len(entries))
            for key, item in entries.items():
                getattr(writer, WRITE[row[2]])(key)
                write_nested(writer, row[3], item)
        else:
            getattr(writer, WRITE[kind])(record.get(name, DEFAULTS[kind]))


def table(number, cls, records, **shifts):
    def write(writer, record):
        write_nested(writer, cls, record)
    return container(number, records, write, **shifts)


SPELLS = [
    {'id': 5043, 'breed': 11, 'ap': 4.0, 'mp': 0.0, 'wp': 1.0, 'range_min': 2.0,
     'range_max': 6.0, 'element': 3, 'unlock_level': 45, 'max_level': 245,
     'effect_ids': [100, 101, 102], 'icon': 604,
     'erY': {2: {'eso': 8, 'esp': 1.5}},
     'erZ': {9: {'esq': 2, 'esr': [4, 5]}},
     'esa': {'HasState(7030, 2)': {'ema': 1008, 'esb': {3: {'eso': 1, 'esp': 2.5}}}}},
    {'id': 5044, 'breed': 0, 'ap': 0.0, 'mp': 0.0, 'wp': 0.0, 'range_min': 0.0,
     'range_max': 0.0, 'element': 9, 'unlock_level': 1, 'max_level': 1, 'effect_ids': []},
    {'id': 2000000001, 'breed': -2, 'ap': 2.0, 'mp': 1.0, 'wp': 0.0, 'range_min': 1.0,
     'range_max': 1.0, 'element': 1, 'unlock_level': 200, 'max_level': 200,
     'effect_ids': [7]},
]
PETS = [
    {'id': 11, 'item': 14335, 'eoq': 50, 'eop': 50, 'emm': 25,
     'eoL': [{'eox': 1, 'ayu': 2}], 'eoM': [{'atl': 9, 'aSg': 8}, {'atl': 10, 'aSg': 1}],
     'eoO': [{'atl': 5, 'ctQ': 90000000000}], 'eoP': [3, 4],
     'eoQ': [{'atl': 1, 'eoR': -16777216, 'eoS': 12}]},
    {'id': 128, 'item': 20274, 'eoq': 0, 'eop': 1, 'emm': 0},
]
MOUNTS = [
    {'id': 149, 'item': 20812, 'eop': 50, 'emm': 50, 'eoq': 50,
     'eou': [{'eox': 1, 'ayu': 1}], 'eov': [{'atl': 12284, 'aSg': 1}],
     'eow': [{'atl': 27578, 'bkQ': False}, {'atl': 18378, 'bkQ': True}]},
    {'id': 135, 'item': 20624, 'eop': 50, 'emm': 50, 'eoq': 50},
]
MONSTERS = [
    {'id': 735, 'family': 147, 'ens': [1], 'egG': [4, 5], 'atk': 143604168,
     'enu': [{'spell': 99, 'eoi': 3}],
     'enA': [{'id': 1, 'ehu': 'IsDead("target")'}],
     'enB': [{'id': 2, 'condition': 'not IsDead("target")', 'loot_list': 809, 'bKb': 3000,
              'eof': 17075, 'eog': [1, 2]},
             {'id': 3, 'condition': '', 'loot_list': 2318, 'bKb': 3000, 'eof': 6257}],
     'enD': [{'id': 4}], 'enK': [8],
     'enH': [{'item': 5407, 'rate': 0.25, 'quantity_min': 1, 'quantity_max': 3,
              'enW': [1]},
             {'item': 18787, 'rate': 0.01, 'quantity_min': 1, 'quantity_max': 1}],
     'enL': [{'enT': 'k', 'bdE': ['u', 'v']}], 'enM': [{'enS': 1, 'aYY': 2}],
     'enN': [{'enR': 1, 'bcG': 'tag'}]},
    {'id': 1918, 'family': 3000, 'enH': [], 'enB': [], 'atk': 100200002},
]
LOOT_LISTS = [
    {'id': 2789, 'emf': 1,
     'emg': [{'id': 24706, 'target': 4899, 'is_list': False, 'rate': -1.0,
              'quantity_min': 25, 'quantity_max': 100},
             {'id': 24707, 'target': 2793, 'is_list': True, 'rate': 5.0,
              'quantity_min': 1, 'quantity_max': 1}]},
    {'id': 2793, 'emf': 3, 'emg': []},
]

TABLES = (
    (66, 'aNt', SPELLS, wakfu_client.read_spells),
    (117, 'aMy', PETS, wakfu_client.read_pets),
    (144, 'aMq', MOUNTS, wakfu_client.read_mounts),
    (42, 'aMd', MONSTERS, wakfu_client.read_monsters),
    (39, 'aMa', LOOT_LISTS, wakfu_client.read_loot_lists),
)


class TheWakfuSpellPetMonsterTablesReadBackEveryRecordTests(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def jar_of(self, number, cls, records, **shifts):
        blob = table(number, cls, records, **shifts)
        return jar(self.folder / ('%d.jar' % number), '%d.bin' % number, blob)

    def test_the_spell_reader_returns_the_fields_of_every_invented_spell(self):
        read = wakfu_client.read_spells(self.jar_of(66, 'aNt', SPELLS))
        self.assertEqual([5043, 5044, 2000000001], [record.id for record in read])
        self.assertEqual(
            (11, 4.0, 0.0, 1.0, 2.0, 6.0, 3, 45, 245, [100, 101, 102], 604),
            tuple(read[0])[1:])
        self.assertEqual([604, 5, 5], [record.icon for record in read])
        self.assertEqual((-2, 2.0, 1.0, 1.0, 1.0, 1, 200, [7]),
                         (read[2].breed, read[2].ap, read[2].mp, read[2].range_min,
                          read[2].range_max, read[2].element, read[2].unlock_level,
                          read[2].effect_ids))

    def test_the_pet_and_mount_readers_return_their_items_and_level_fields(self):
        pets = wakfu_client.read_pets(self.jar_of(117, 'aMy', PETS))
        self.assertEqual([(11, 14335, 50, 50, 25), (128, 20274, 0, 1, 0)],
                         [tuple(record) for record in pets])
        mounts = wakfu_client.read_mounts(self.jar_of(144, 'aMq', MOUNTS))
        self.assertEqual([(149, 20812, 50, 50, 50), (135, 20624, 50, 50, 50)],
                         [tuple(record) for record in mounts])

    def test_the_monster_reader_returns_the_family_the_drops_and_the_harvest_entries(self):
        read = wakfu_client.read_monsters(self.jar_of(42, 'aMd', MONSTERS))
        self.assertEqual([(735, 147), (1918, 3000)],
                         [(record.id, record.family) for record in read])
        self.assertEqual([(5407, 0.25, 1, 3), (18787, 0.01, 1, 1)],
                         [tuple(drop) for drop in read[0].drops])
        self.assertEqual([(809, 'not IsDead("target")'), (2318, '')],
                         [tuple(harvest) for harvest in read[0].harvests])
        self.assertEqual(([], []), (read[1].drops, read[1].harvests))
        self.assertEqual([143604168, 100200002], [record.picture for record in read])

    def test_the_loot_list_reader_keeps_a_nested_list_as_a_reference_and_minus_one_as_given(self):
        read = wakfu_client.read_loot_lists(self.jar_of(39, 'aMa', LOOT_LISTS))
        self.assertEqual([2789, 2793], [record.id for record in read])
        self.assertEqual([(24706, 4899, False, -1.0, 25, 100),
                          (24707, 2793, True, 5.0, 1, 1)],
                         [tuple(row) for row in read[0].rows])
        self.assertEqual([], read[1].rows)

    def test_every_reader_raises_on_a_wrong_record_size_or_id(self):
        for number, cls, records, read in TABLES:
            with self.assertRaisesRegex(wakfu_client.TableError, 'header says', msg=number):
                read(self.jar_of(number, cls, records, size_shift=3))
            with self.assertRaisesRegex(wakfu_client.TableError, 'starts with id', msg=number):
                read(self.jar_of(number, cls, records, id_shift=1))

    def test_every_reader_raises_on_a_header_size_one_byte_off(self):
        for number, cls, records, read in TABLES:
            for shift in (1, -1):
                with self.assertRaises(wakfu_client.TableError, msg=(number, shift)):
                    read(self.jar_of(number, cls, records, size_shift=shift))

    def test_every_reader_raises_on_a_truncated_or_foreign_file(self):
        for number, cls, records, read in TABLES:
            good = table(number, cls, records)
            with self.assertRaises(wakfu_client.TableError, msg=number):
                read(jar(self.folder / 'cut.jar', '%d.bin' % number, good[:-5]))
            with self.assertRaises(wakfu_client.TableError, msg=number):
                read(jar(self.folder / 'other.jar', 'other.bin', good))

    def test_a_record_one_byte_short_in_a_nested_record_raises(self):
        layouts = dict(wakfu_client.NESTED_LAYOUTS)
        layouts['aNt'] = tuple(('max_level', 'i8') if row[0] == 'max_level' else row
                               for row in layouts['aNt'])
        layouts['aMh'] = tuple(('quantity_min', 'i8') if row[0] == 'quantity_min' else row
                               for row in layouts['aMh'])
        with mock.patch.dict(wakfu_client.NESTED_LAYOUTS, layouts):
            narrow_spells = table(66, 'aNt', SPELLS)
            narrow_drops = table(42, 'aMd', MONSTERS)
        with self.assertRaises(wakfu_client.TableError):
            wakfu_client.read_spells(jar(self.folder / 'narrow66.jar', '66.bin', narrow_spells))
        with self.assertRaises(wakfu_client.TableError):
            wakfu_client.read_monsters(jar(self.folder / 'narrow42.jar', '42.bin', narrow_drops))
