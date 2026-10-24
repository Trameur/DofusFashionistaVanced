import json
import struct
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'itemscraper'))

import wakfu_client_code  # noqa: E402

CLIENT_DIR = ROOT / 'itemscraper' / 'wakfu_client'

# Constant pool of the invented class, by index
POOL = [
    ('utf8', 'T'), ('class', 1), ('utf8', 'NAME_A'), ('string', 3), ('utf8', 'NAME_B'),
    ('string', 5), ('utf8', '<clinit>'), ('utf8', 'Code'), ('utf8', '<init>'),
    ('utf8', '()V'), ('nat', 9, 10), ('method', 2, 11), ('utf8', 'TABLE'), ('utf8', '[I'),
    ('nat', 13, 14), ('field', 2, 15), ('utf8', 'KEY'), ('string', 17),
]


def pool_bytes(rename):
    out = struct.pack('>H', len(POOL) + 1)
    for entry in POOL:
        kind = entry[0]
        if kind == 'utf8':
            blob = rename.get(entry[1], entry[1]).encode('utf-8')
            out += b'\x01' + struct.pack('>H', len(blob)) + blob
        elif kind == 'class':
            out += b'\x07' + struct.pack('>H', entry[1])
        elif kind == 'string':
            out += b'\x08' + struct.pack('>H', entry[1])
        elif kind == 'nat':
            out += b'\x0c' + struct.pack('>HH', entry[1], entry[2])
        elif kind == 'method':
            out += b'\x0a' + struct.pack('>HH', entry[1], entry[2])
        elif kind == 'field':
            out += b'\x09' + struct.pack('>HH', entry[1], entry[2])
    return out


def class_file(bytecode, **rename):
    """A class file whose only member is a static initializer running `bytecode`."""
    attribute = struct.pack('>HHI', 2, 2, len(bytecode)) + bytes(bytecode) + b'\x00\x00\x00\x00'
    method = struct.pack('>HHHH', 8, 7, 10, 1) + struct.pack('>HI', 8, len(attribute)) \
        + attribute
    return (b'\xca\xfe\xba\xbe' + struct.pack('>HH', 0, 52) + pool_bytes(rename)
            + struct.pack('>HHHHHH', 0x21, 2, 2, 0, 0, 1) + method)


NEW, DUP, LDC, BIPUSH, SPECIAL, PUTSTATIC, GETSTATIC = 0xbb, 0x59, 0x12, 0x10, 0xb7, 0xb3, 0xb2
ENUM = [NEW, 0, 2, DUP, LDC, 4, BIPUSH, 0, BIPUSH, 7, SPECIAL, 0, 12, PUTSTATIC, 0, 16,
        NEW, 0, 2, DUP, LDC, 6, BIPUSH, 1, BIPUSH, 9, SPECIAL, 0, 12, PUTSTATIC, 0, 16,
        0xb1]
ARRAY = [BIPUSH, 3, 0xbc, 10,
         DUP, 0x03, BIPUSH, 10, 0x4f, DUP, 0x04, BIPUSH, 30, 0x4f,
         DUP, 0x05, BIPUSH, 50, 0x4f, PUTSTATIC, 0, 16,
         LDC, 18, GETSTATIC, 0, 16, 0xb1]


def jar_of(path, **classes):
    with zipfile.ZipFile(path, 'w') as archive:
        for name, blob in classes.items():
            archive.writestr(name + '.class', blob)
    return path


class TheWakfuClientCodeReaderReadsTheConstantsTests(TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def test_the_enum_reader_returns_each_name_ordinal_and_first_id_in_order(self):
        info = wakfu_client_code.parse_class(class_file(ENUM))
        self.assertEqual([('NAME_A', 0, 7), ('NAME_B', 1, 9)],
                         wakfu_client_code.enum_constants(info))

    def test_the_array_reader_returns_the_ints_the_initializer_stores(self):
        info = wakfu_client_code.parse_class(class_file(ARRAY))
        self.assertEqual((10, 30, 50), wakfu_client_code.static_int_array(info, 'TABLE'))
        with self.assertRaises(wakfu_client_code.ClientCodeError):
            wakfu_client_code.static_int_array(info, 'OTHER')

    def test_the_field_reader_returns_what_the_method_loading_a_text_reads(self):
        info = wakfu_client_code.parse_class(class_file(ARRAY))
        self.assertEqual([('T', 'TABLE', '[I')],
                         wakfu_client_code.getstatic_fields(info, 'KEY'))
        self.assertEqual([], wakfu_client_code.getstatic_fields(info, 'NAME_A'))

    def test_a_class_is_found_by_the_texts_it_loads_and_not_by_its_name(self):
        path = jar_of(self.folder / 'a.jar', first=class_file(ENUM),
                      second=class_file(ENUM, NAME_A='OTHER_A'))
        found = wakfu_client_code.classes_with_strings(path, ('NAME_A', 'NAME_B'))
        self.assertEqual(1, len(found))
        other = wakfu_client_code.classes_with_strings(path, ('OTHER_A',))
        self.assertEqual(1, len(other))
        self.assertEqual([], wakfu_client_code.classes_with_strings(path, ('MISSING',)))

    def test_an_anchor_that_matches_two_classes_raises(self):
        path = jar_of(self.folder / 'two.jar', first=class_file(ENUM), second=class_file(ENUM))
        with self.assertRaises(wakfu_client_code.ClientCodeError):
            wakfu_client_code._only(path, ('NAME_A',), 'invented')

    def test_an_anchor_that_matches_no_class_raises(self):
        path = jar_of(self.folder / 'none.jar', first=class_file(ARRAY))
        with self.assertRaises(wakfu_client_code.ClientCodeError):
            wakfu_client_code._only(path, ('MISSING',), 'invented')
        with self.assertRaises(wakfu_client_code.ClientCodeError):
            wakfu_client_code.read_constants(path)

    def test_a_file_that_is_not_a_class_raises(self):
        with self.assertRaises(wakfu_client_code.ClientCodeError):
            wakfu_client_code.parse_class(b'not a class file')


class TheLiveWakfuClientCodeHoldsTheConstantsTheGameHasTests(TestCase):
    """Guards on the real client jar, skipped where it is not mirrored."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.constants = None
        jars = sorted(CLIENT_DIR.glob('*/wakfu-client.jar'))
        if jars:
            cls.constants = wakfu_client_code.read_constants(jars[-1])
            cls.folder = jars[-1].parent

    def setUp(self):
        if self.constants is None:
            self.skipTest('no wakfu-client.jar; run itemscraper/get_wakfu_client.py')

    def test_the_slot_levels_rise_and_end_at_the_level_cap(self):
        levels = self.constants['passive_slot_levels']
        self.assertEqual(sorted(set(levels)), levels)
        self.assertEqual(200, levels[-1])

    def test_the_rarities_name_the_relic_and_the_epic_by_their_ids(self):
        rarities = self.constants['rarities']
        self.assertEqual((5, 7), (rarities['RELIC'], rarities['RELIC2']))

    def test_the_spell_kinds_name_the_active_kind_first(self):
        kinds = self.constants['spell_kinds']
        self.assertEqual(0, kinds['ACTIVE'])
        self.assertEqual({0, 1, 2}, set(kinds.values()))

    def test_the_characteristics_hold_each_id_once_and_the_ones_the_stats_use(self):
        found = self.constants['characteristics']
        self.assertEqual((1, 2, 3, 4), (found['HP'], found['AP'], found['MP'], found['WP']))
        self.assertEqual(len(found), len(set(found.values())))

    def test_the_decoded_file_holds_what_the_jar_reads(self):
        path = self.folder / 'client_code.json'
        if not path.exists():
            self.skipTest('no client_code.json beside the jar')
        saved = json.loads(path.read_text(encoding='utf-8'))
        for name in ('characteristics', 'rarities', 'spell_kinds', 'passive_slot_levels'):
            self.assertEqual(self.constants[name], saved[name], name)
