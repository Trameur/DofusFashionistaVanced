#!/usr/bin/env python3
"""Read the Wakfu client's item table, breed table and label files.

    python itemscraper/wakfu_client.py <35.jar>

Each reader follows the layout of one client class. A table that does not end
where its own header says stops the update: a silent misread would feed wrong
conditions to every solve.
"""

from __future__ import annotations

import collections
import struct
import sys
import zipfile

ITEM_TABLE = 35
BREED_TABLE = 86
SEED_OFFSET = 756423

ItemRecord = collections.namedtuple(
    'ItemRecord', 'id level type rarity properties criteria actions sub_records')
BreedRecord = collections.namedtuple('BreedRecord', 'id name base')

# Characteristic of each of the breed record's integer fields f1 to f12, in read order
BREED_FIELDS = ('HP', 'AP', 'MP', 'WP', 'INIT', 'FEROCITY', 'FUMBLE_RATE',
                'WISDOM', 'TACKLE', 'DODGE', 'PROSPECTION',
                'KO_TIME_BEFORE_DEATH')


class TableError(ValueError):
    pass


def _signed_byte(value):
    value &= 0xff
    return value - 256 if value > 127 else value


class Reader:
    """Every primitive but float and string bytes is offset by a rolling byte."""

    def __init__(self, buf, base, k, j):
        self.buf, self.base, self.k, self.j = buf, base, k, j
        self.pos = 0
        self.b = _signed_byte(k ^ j)

    def _roll(self):
        self.b = _signed_byte(self.b + self.k * self.pos + self.j)

    def _raw(self, fmt, size):
        try:
            value = struct.unpack_from('<' + fmt, self.buf, self.base + self.pos)[0]
        except struct.error as error:
            raise TableError('the table ends early: %s' % error) from error
        self.pos += size
        return value

    def i8(self):
        self._roll()
        return _signed_byte(self._raw('b', 1) - self.b)

    def boolean(self):
        self._roll()
        return self._raw('b', 1) != self.b

    def i16(self):
        self._roll()
        value = (self._raw('h', 2) - self.b) & 0xffff
        return value - 0x10000 if value & 0x8000 else value

    def i32(self):
        self._roll()
        value = (self._raw('i', 4) - self.b) & 0xffffffff
        return value - (1 << 32) if value & 0x80000000 else value

    def i64(self):
        self._roll()
        value = (self._raw('q', 8) - self.b) & 0xffffffffffffffff
        return value - (1 << 64) if value & (1 << 63) else value

    def f32(self):
        self._roll()
        return self._raw('f', 4)

    def text(self):
        size = self.i32()
        if size < 0 or self.base + self.pos + size > len(self.buf):
            raise TableError('a text runs past the end of the table')
        raw = bytes(self.buf[self.base + self.pos:self.base + self.pos + size])
        self.pos += size
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError as error:
            raise TableError('a text is not utf-8: %s' % error) from error

    def count(self):
        number = self.i32()
        if number < 0 or number > len(self.buf):
            raise TableError('a count of %d cannot be right' % number)
        return number

    def i32s(self):
        return [self.i32() for _ in range(self.count())]

    def i8s(self):
        return [self.i8() for _ in range(self.count())]

    def texts(self):
        return [self.text() for _ in range(self.count())]


def read_container(buf, type_id):
    """(entries [(id, offset, size, seed)], indexes, Reader on the records)."""
    if len(buf) < 4:
        raise TableError('the table is shorter than its header')
    seed = struct.unpack_from('<i', buf, 0)[0] + SEED_OFFSET
    seed = ((seed + (1 << 31)) % (1 << 32)) - (1 << 31)
    head = Reader(buf, 0, type_id, seed)
    head.pos = 4
    entries = [(head.i64(), head.i32(), head.i32(), head.i8())
               for _ in range(head.count())]
    indexes = {}
    for _ in range(head.i8() & 0xff):
        unique = head.i8() != 0
        name = head.text()
        indexes[name] = {head.i64(): (head.i32() if unique else head.i32s())
                         for _ in range(head.count())}
    return entries, indexes, Reader(buf, head.pos, type_id, seed)


def _table(jar_path, entry_name):
    try:
        with zipfile.ZipFile(jar_path) as jar:
            return jar.read(entry_name)
    except KeyError as error:
        raise TableError('%s has no entry %s' % (jar_path, entry_name)) from error
    except zipfile.BadZipFile as error:
        raise TableError('%s is not a jar: %s' % (jar_path, error)) from error


def _read_item(reader):
    """The item record of client class aLO."""
    ident = reader.i32()
    reader.i16()
    reader.i32()
    reader.i32()
    reader.i32()
    level = reader.i16()
    pairs = reader.texts()
    kind = reader.i32()
    reader.i16()
    for _ in range(3):
        reader.i8()
    for _ in range(2):
        reader.i32()
    for _ in range(4):
        reader.boolean()
    rarity = reader.i16()
    reader.i8()
    reader.text()
    properties = reader.i32s()
    for _ in range(4):
        reader.i8()
    for _ in range(2):
        reader.f32()
    reader.i8()
    reader.i32s()
    actions = reader.count()
    for _ in range(actions):
        reader.i32()
        reader.i32()
        for _ in range(4):
            reader.boolean()
        reader.text()
        reader.texts()
        reader.texts()
    sub_records = 0
    if reader.i8() != 0:
        sub_records += 1
        reader.i8()
        reader.i8s()
        reader.i32s()
        reader.i32s()
        reader.boolean()
    if reader.i8() != 0:
        sub_records += 1
        reader.i32()
        reader.i8s()
        reader.boolean()
        reader.boolean()
    reader.i32()
    if len(pairs) % 2:
        raise TableError('item %d has an odd criteria list' % ident)
    criteria = [[pairs[index], pairs[index + 1]] for index in range(0, len(pairs), 2)]
    return ItemRecord(ident, level, kind, rarity, properties, criteria, actions,
                      sub_records)


def read_items(jar_path):
    """{item id: ItemRecord} from the item table of a client jar (35.jar)."""
    buf = _table(jar_path, '%d.bin' % ITEM_TABLE)
    entries, _indexes, reader = read_container(buf, ITEM_TABLE)
    out = {}
    for ident, offset, size, seed in entries:
        reader.pos, reader.b = offset, seed
        record = _read_item(reader)
        if record.id != ident:
            raise TableError('record %d starts with id %d' % (ident, record.id))
        if reader.pos != offset + size:
            raise TableError('record %d ends at %d, its header says %d'
                             % (ident, reader.pos, offset + size))
        out[ident] = record
    return out


def _read_breed(reader):
    """The breed record of client class aKe."""
    ident = reader.i32()
    name = reader.text()
    fields = [reader.i32() for _ in range(14)]
    reader.i8s()
    for _ in range(reader.count()):
        reader.f32()
    for _ in range(reader.count()):
        reader.i16()
    reader.i32s()
    for _ in range(reader.count()):
        reader.i16()
    reader.i16()
    base = dict(zip(BREED_FIELDS, fields[1:13]))
    return BreedRecord(ident, name, base)


def read_breeds(jar_path):
    """[BreedRecord] from the breed table of a client jar (86.jar)."""
    buf = _table(jar_path, '%d.bin' % BREED_TABLE)
    entries, _indexes, reader = read_container(buf, BREED_TABLE)
    if not entries:
        raise TableError('the breed table has no record')
    out = []
    for ident, offset, size, seed in entries:
        reader.pos, reader.b = offset, seed
        record = _read_breed(reader)
        if record.id != ident:
            raise TableError('breed %d starts with id %d' % (ident, record.id))
        if reader.pos != offset + size:
            raise TableError('breed %d ends at %d, its header says %d'
                             % (ident, reader.pos, offset + size))
        out.append(record)
    return out


def read_labels(jar_path, language):
    """({critere.* key: text}, {nation id: name}) of one language jar, texts verbatim."""
    name = 'texts_%s.properties' % language
    try:
        with zipfile.ZipFile(jar_path) as jar:
            body = jar.read(name).decode('utf-8')
    except KeyError as error:
        raise TableError('%s has no entry %s' % (jar_path, name)) from error
    except zipfile.BadZipFile as error:
        raise TableError('%s is not a jar: %s' % (jar_path, error)) from error
    labels, nations = {}, {}
    for line in body.splitlines():
        key, separator, text = line.partition('=')
        if not separator:
            continue
        key = key.strip()
        if key.startswith('critere.'):
            labels[key] = text
        elif key.startswith('nation.short.'):
            tail = key[len('nation.short.'):]
            if tail.isdigit():
                nations[int(tail)] = text
    return labels, nations


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print('usage: wakfu_client.py <35.jar>')
        return 2
    try:
        items = read_items(argv[0])
    except TableError as error:
        print('the item table cannot be read: %s' % error)
        return 1
    print('entries %d size or id mismatches 0' % len(items))
    return 0


if __name__ == '__main__':
    sys.exit(main())
