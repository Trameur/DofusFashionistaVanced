import json
import os
import struct
import subprocess
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

STORED_SEED = 12345


def signed(value):
    value &= 0xff
    return value - 256 if value > 127 else value


class Writer:
    """The inverse of wakfu_client.Reader: each primitive is stored plus a rolling byte."""

    def __init__(self, k, j, start=0):
        self.k, self.j = k, j
        self.out = bytearray()
        self.start = start
        self.b = signed(k ^ j)

    @property
    def pos(self):
        return self.start + len(self.out)

    def roll(self):
        self.b = signed(self.b + self.k * self.pos + self.j)

    def i8(self, value):
        self.roll()
        self.out += struct.pack('<B', (value + self.b) & 0xff)

    def boolean(self, value):
        self.roll()
        self.out += struct.pack('<B', (self.b + (1 if value else 0)) & 0xff)

    def i16(self, value):
        self.roll()
        self.out += struct.pack('<H', (value + self.b) & 0xffff)

    def i32(self, value):
        self.roll()
        self.out += struct.pack('<I', (value + self.b) & 0xffffffff)

    def i64(self, value):
        self.roll()
        self.out += struct.pack('<Q', (value + self.b) & 0xffffffffffffffff)

    def f32(self, value):
        self.roll()
        self.out += struct.pack('<f', value)

    def f64(self, value):
        self.roll()
        self.out += struct.pack('<d', value)

    def i16s(self, values):
        self.i32(len(values))
        for value in values:
            self.i16(value)

    def text(self, value):
        raw = value.encode('utf-8')
        self.i32(len(raw))
        self.out += raw

    def i32s(self, values):
        self.i32(len(values))
        for value in values:
            self.i32(value)

    def i8s(self, values):
        self.i32(len(values))
        for value in values:
            self.i8(value)

    def texts(self, values):
        self.i32(len(values))
        for value in values:
            self.text(value)


def item_record(writer, item):
    writer.i32(item['id'])
    writer.i16(0)
    for _ in range(3):
        writer.i32(0)
    writer.i16(item['level'])
    pairs = []
    for kind, text in item['criteria']:
        pairs += [kind, text]
    writer.texts(pairs)
    writer.i32(item['type'])
    writer.i16(0)
    for _ in range(3):
        writer.i8(0)
    for _ in range(2):
        writer.i32(0)
    for _ in range(4):
        writer.boolean(False)
    writer.i16(item['rarity'])
    writer.i8(0)
    writer.text('')
    writer.i32s(item['properties'])
    for _ in range(4):
        writer.i8(0)
    for _ in range(2):
        writer.f32(0.5)
    writer.i8(0)
    writer.i32s([])
    writer.i32(item['actions'])
    for _ in range(item['actions']):
        writer.i32(1)
        writer.i32(2)
        for _ in range(4):
            writer.boolean(True)
        writer.text('action')
        writer.texts(['a', 'b'])
        writer.texts([])
    first, second = item['sub_records']
    writer.i8(1 if first else 0)
    if first:
        writer.i8(3)
        writer.i8s([1, 2])
        writer.i32s([4])
        writer.i32s([5, 6])
        writer.boolean(True)
    writer.i8(1 if second else 0)
    if second:
        writer.i32(9)
        writer.i8s([7])
        writer.boolean(False)
        writer.boolean(True)
    writer.i32(0)


def breed_record(writer, breed):
    writer.i32(breed['id'])
    writer.text(breed['name'])
    fields = [0] + [breed['base'][key] for key in wakfu_client.BREED_FIELDS] + [0]
    for value in fields:
        writer.i32(value)
    writer.i8s([1])
    writer.i32(2)
    writer.f32(1.5)
    writer.f32(2.5)
    writer.i32(1)
    writer.i16(4)
    writer.i32s([8, 9])
    writer.i32(0)
    writer.i16(0)


def container(type_id, records, write, size_shift=0, id_shift=0):
    """The bytes of a table; size_shift and id_shift falsify the header of the first entry."""
    seed = STORED_SEED + wakfu_client.SEED_OFFSET
    body = bytearray()
    entries = []
    for number, record in enumerate(records):
        entry_seed = 17 + number
        writer = Writer(type_id, seed)
        writer.b = entry_seed
        writer.start = len(body)
        writer.out = bytearray()
        offset = len(body)
        write(writer, record)
        body += writer.out
        entries.append((record['id'], offset, len(writer.out), entry_seed))
    head = Writer(type_id, seed, start=0)
    head.out = bytearray(struct.pack('<i', STORED_SEED))
    head.i32(len(entries))
    for number, (ident, offset, size, entry_seed) in enumerate(entries):
        head.i64(ident + (id_shift if number == 0 else 0))
        head.i32(offset)
        head.i32(size + (size_shift if number == 0 else 0))
        head.i8(entry_seed)
    head.i8(0)
    return bytes(head.out) + bytes(body)


ITEMS = [
    {'id': 101, 'level': 55, 'type': 120, 'rarity': 4, 'properties': [1, 24],
     'criteria': [['EQUIP', 'IsBreed("ALPHA")'], ['CRAFT', 'GetCraftLevel(75) >= 80']],
     'actions': 0, 'sub_records': (False, False)},
    {'id': 102, 'level': 245, 'type': 103, 'rarity': 5, 'properties': [],
     'criteria': [], 'actions': 2, 'sub_records': (True, True)},
    {'id': 2000000001, 'level': -3, 'type': 134, 'rarity': 7, 'properties': [4, 9, 12],
     'criteria': [['EQUIP', 'GetCharac("FEROCITY") > -10']],
     'actions': 1, 'sub_records': (False, True)},
]

BREEDS = [
    {'id': 1, 'name': 'ALPHA', 'base': dict(zip(wakfu_client.BREED_FIELDS,
                                                 (50, 6, 3, 6, 100, 3, 0, 0, 0, 0, 0, 4)))},
    {'id': 2, 'name': 'BETA', 'base': dict(zip(wakfu_client.BREED_FIELDS,
                                                (60, 6, 4, 12, 90, 5, 1, 2, 3, 4, 5, 6)))},
]


def jar(path, name, blob):
    with zipfile.ZipFile(path, 'w') as handle:
        handle.writestr(name, blob)
    return path


class TheWakfuClientDecoderReadsATableItWroteTests(SimpleTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def items_jar(self, **shifts):
        blob = container(wakfu_client.ITEM_TABLE, ITEMS, item_record, **shifts)
        return jar(self.folder / '35.jar', '35.bin', blob)

    def breeds_jar(self):
        blob = container(wakfu_client.BREED_TABLE, BREEDS, breed_record)
        return jar(self.folder / '86.jar', '86.bin', blob)

    def test_the_decoder_returns_every_invented_item_field_for_field(self):
        read = wakfu_client.read_items(self.items_jar())
        self.assertEqual({101, 102, 2000000001}, set(read))
        for item in ITEMS:
            record = read[item['id']]
            self.assertEqual(
                (item['level'], item['type'], item['rarity'], item['properties'],
                 [list(pair) for pair in item['criteria']], item['actions'],
                 sum(bool(one) for one in item['sub_records'])),
                (record.level, record.type, record.rarity, record.properties,
                 record.criteria, record.actions, record.sub_records), item['id'])

    def test_the_decoder_returns_every_invented_breed_and_its_base_values(self):
        read = wakfu_client.read_breeds(self.breeds_jar())
        self.assertEqual([(breed['id'], breed['name'], breed['base']) for breed in BREEDS],
                         [(record.id, record.name, record.base) for record in read])
        self.assertEqual(12, len(read[0].base))
        self.assertEqual(12, read[1].base['WP'])

    def test_a_wrong_record_size_a_wrong_id_or_a_truncated_file_raises(self):
        with self.assertRaisesRegex(wakfu_client.TableError, 'header says'):
            wakfu_client.read_items(self.items_jar(size_shift=3))
        with self.assertRaisesRegex(wakfu_client.TableError, 'starts with id'):
            wakfu_client.read_items(self.items_jar(id_shift=1))
        good = container(wakfu_client.ITEM_TABLE, ITEMS, item_record)
        cut = jar(self.folder / 'cut.jar', '35.bin', good[:-100])
        with self.assertRaises(wakfu_client.TableError):
            wakfu_client.read_items(cut)
        with self.assertRaises(wakfu_client.TableError):
            wakfu_client.read_items(jar(self.folder / 'tiny.jar', '35.bin', b'\x00'))
        with self.assertRaises(wakfu_client.TableError):
            wakfu_client.read_items(jar(self.folder / 'other.jar', 'other.bin', good))

    def test_the_command_line_exits_one_on_a_record_size_mismatch(self):
        script = os.path.join(SCRAPER, 'wakfu_client.py')
        good = self.items_jar()
        ok = subprocess.run([sys.executable, script, str(good)], capture_output=True, text=True)
        self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
        self.assertIn('size or id mismatches 0', ok.stdout)
        bad = jar(self.folder / 'bad.jar', '35.bin',
                  container(wakfu_client.ITEM_TABLE, ITEMS, item_record, size_shift=3))
        failed = subprocess.run([sys.executable, script, str(bad)], capture_output=True, text=True)
        self.assertEqual(1, failed.returncode, failed.stdout + failed.stderr)
        self.assertIn('cannot be read', failed.stdout)

    def test_a_file_whose_sha1_differs_from_the_manifest_is_refused(self):
        import argparse
        import get_wakfu_client
        install = self.folder / 'install'
        for path in get_wakfu_client.FILES:
            target = install / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'content of ' + path.encode())
        manifest = self.folder / 'main.manifest'
        manifest.write_bytes(b'unused')
        blobs = {path: (install / path).read_bytes() for path in get_wakfu_client.FILES}
        own = {path: {'size': len(blob), 'hash': get_wakfu_client.sha1_of(blob)}
               for path, blob in blobs.items()}
        (install / 'manifest.json').write_text(json.dumps(own), encoding='utf-8')
        args = argparse.Namespace(from_install=str(install), manifest=str(manifest))
        real = get_wakfu_client.cytrus_cdn.find_file

        def find(_manifest, path, hashes={}):
            blob = blobs[path]
            return {'size': len(blob), 'hash': hashes.get(path, get_wakfu_client.sha1_of(blob))}

        get_wakfu_client.cytrus_cdn.find_file = find
        try:
            self.assertEqual(set(get_wakfu_client.FILES), set(get_wakfu_client.from_install(args)))
            wrong = get_wakfu_client.ITEMS_JAR
            get_wakfu_client.cytrus_cdn.find_file = \
                lambda m, path: find(m, path, {wrong: '0' * 40})
            with self.assertRaisesRegex(get_wakfu_client.ClientError, 'cytrus manifest'):
                get_wakfu_client.from_install(args)
            get_wakfu_client.cytrus_cdn.find_file = find
            own[wrong]['hash'] = '1' * 40
            (install / 'manifest.json').write_text(json.dumps(own), encoding='utf-8')
            with self.assertRaisesRegex(get_wakfu_client.ClientError, 'manifest.json'):
                get_wakfu_client.from_install(args)
        finally:
            get_wakfu_client.cytrus_cdn.find_file = real
