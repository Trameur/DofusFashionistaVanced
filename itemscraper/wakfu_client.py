#!/usr/bin/env python3
"""Read the Wakfu client's item, breed, effect, set, state and ability tables, and its labels.

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
EFFECT_GROUP_TABLE = 29
ITEM_SET_TABLE = 36
STATE_TABLE = 67
STATIC_EFFECT_TABLE = 68
ABILITY_TABLE = 135
ABILITY_CATEGORY_TABLE = 136
SEED_OFFSET = 756423

ItemRecord = collections.namedtuple(
    'ItemRecord', 'id level type rarity properties criteria actions sub_records')
BreedRecord = collections.namedtuple('BreedRecord', 'id name base')

# Characteristic of each of the breed record's integer fields f1 to f12, in read order
BREED_FIELDS = ('HP', 'AP', 'MP', 'WP', 'INIT', 'FEROCITY', 'FUMBLE_RATE',
                'WISDOM', 'TACKLE', 'DODGE', 'PROSPECTION',
                'KO_TIME_BEFORE_DEATH')


# One row per read of a record class, in read order: (client field, kind). A
# kind ending in [] is an i32 count, then that many elements. A field is named
# for what it means only where the data proves it; the others keep the
# client's own field name.
# Every table has an unreferenced twin class that returns the same type id:
# the layouts below are the referenced one (aNy, not fGK, which breaks almost
# every record of 68).
STATIC_EFFECT_LAYOUT = (  # 68, aNy
    ('id', 'i32'), ('action_id', 'i32'), ('container_id', 'i32'),
    ('short_esK', 'i16'), ('area_size', 'i32[]'), ('area_shape', 'i16'),
    ('short_esN', 'i16'), ('ints_esO', 'i32[]'), ('short_esP', 'i16'),
    ('ints_esQ', 'i32[]'), ('ints_esR', 'i32[]'), ('ints_esS', 'i32[]'),
    ('ints_esT', 'i32[]'), ('ints_esU', 'i32[]'), ('ints_esV', 'i32[]'),
    ('ints_esW', 'i32[]'), ('normal_or_critical', 'text'), ('longs_esY', 'i64[]'),
    ('flag_beL', 'bool'), ('int_esZ', 'i32'), ('float_eta', 'f32'),
    ('flag_esu', 'bool'), ('flag_etb', 'bool'), ('short_etc', 'i16'),
    ('float_etd', 'f32'), ('params', 'f32[]'), ('float_ete', 'f32'),
    ('float_etf', 'f32'), ('byte_etg', 'i8'), ('byte_eth', 'i8'),
    ('byte_eti', 'i8'), ('int_beJ', 'i32'), ('flag_etj', 'bool'),
    ('short_etk', 'i16'), ('float_etl', 'f32'), ('byte_etm', 'i8'),
    ('flag_etn', 'bool'), ('text_eto', 'text'), ('short_etp', 'i16'),
    ('short_etq', 'i16'), ('text_etr', 'text'), ('container_type', 'text'),
    ('root_container_type', 'text'), ('flag_bex', 'bool'), ('flag_etu', 'bool'),
    ('flag_etv', 'bool'), ('flag_etw', 'bool'), ('flag_etx', 'bool'),
    ('flag_ety', 'bool'), ('int_dIM', 'i32'), ('flag_beM', 'bool'),
    ('ints_etz', 'i32[]'), ('flag_etA', 'bool'), ('flag_etB', 'bool'),
    ('flag_etC', 'bool'), ('flag_etD', 'bool'), ('flag_etE', 'bool'),
)
EFFECT_GROUP_LAYOUT = (('id', 'i32'), ('effect_ids', 'i32[]'))  # 29, aKX
# 67, aNx. efW lists the effects of the state: the STATE effects of table 68
# on all 6129 states. bcw is a text key (for example malus_portee).
STATE_LAYOUT = (
    ('id', 'i32'), ('aYh', 'i16'), ('ess', 'i32[]'), ('aOC', 'i32[]'),
    ('est', 'i32[]'), ('esu', 'bool'), ('esv', 'bool'), ('esw', 'bool'),
    ('esx', 'bool'), ('esy', 'text'), ('esz', 'text'), ('esA', 'bool'),
    ('beM', 'bool'), ('esB', 'bool'), ('efW', 'i32[]'), ('esC', 'i32[]'),
    ('esD', 'bool'), ('esE', 'bool'), ('esF', 'i8'), ('esG', 'i8'),
    ('esH', 'bool'), ('esI', 'bool'), ('bcw', 'text'), ('esJ', 'bool'),
    ('atM', 'i16'),
)
# 135, aJX. The ability's category is the one whose ability list holds it.
ABILITY_LAYOUT = (
    ('id', 'i32'), ('category', 'i32'), ('ddL', 'i32'), ('cgI', 'i32'),
    ('effect_ids', 'i32[]'),
)
ABILITY_CATEGORY_LAYOUT = (  # 136, aJY
    ('id', 'i32'), ('unlock_levels', 'i32[]'), ('ability_ids', 'i32[]'),
)
# The reader method of each kind
KIND_READERS = {'i8': 'i8', 'bool': 'boolean', 'i16': 'i16', 'i32': 'i32',
                'i64': 'i64', 'f32': 'f32', 'text': 'text', 'i32[]': 'i32s',
                'i64[]': 'i64s', 'f32[]': 'f32s'}

# What each reader hands back. The effect fields not named here are read to
# keep the record aligned and dropped: 178344 records of 57 fields would not
# fit in memory as dicts.
EffectRecord = collections.namedtuple(
    'EffectRecord', 'id action_id container_id container_type root_container_type'
                    ' normal_or_critical area_shape area_size params')
GroupRecord = collections.namedtuple('GroupRecord', 'id effect_ids')
StateRecord = collections.namedtuple('StateRecord', 'id bcw effect_ids')
AbilityRecord = collections.namedtuple(
    'AbilityRecord', 'id category ddL cgI effect_ids')
AbilityCategoryRecord = collections.namedtuple(
    'AbilityCategoryRecord', 'id unlock_levels ability_ids')
SetRecord = collections.namedtuple('SetRecord', 'id elG item_ids bonuses')


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

    def i64s(self):
        return [self.i64() for _ in range(self.count())]

    def f32s(self):
        return [self.f32() for _ in range(self.count())]

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


def _read_layout(reader, layout):
    """{field: value} of one record whose rows are `layout`."""
    return {name: getattr(reader, KIND_READERS[kind])() for name, kind in layout}


def _read_records(jar_path, table_id, read_one, label):
    """[record] in entry order; raises unless each ends at its declared size."""
    buf = _table(jar_path, '%d.bin' % table_id)
    entries, _indexes, reader = read_container(buf, table_id)
    out = []
    for ident, offset, size, seed in entries:
        reader.pos, reader.b = offset, seed
        record = read_one(reader)
        if record.id != ident:
            raise TableError('%s %d starts with id %d' % (label, ident, record.id))
        if reader.pos != offset + size:
            raise TableError('%s %d ends at %d, its header says %d'
                             % (label, ident, reader.pos, offset + size))
        out.append(record)
    return out


def _read_effect(reader):
    """The effect record of client class aNy."""
    row = _read_layout(reader, STATIC_EFFECT_LAYOUT)
    return EffectRecord(
        row['id'], row['action_id'], row['container_id'],
        row['container_type'].strip(), row['root_container_type'].strip(),
        row['normal_or_critical'].strip(), row['area_shape'], row['area_size'],
        row['params'])


def _read_group(reader):
    """The effect group record of client class aKX."""
    row = _read_layout(reader, EFFECT_GROUP_LAYOUT)
    return GroupRecord(row['id'], row['effect_ids'])


def _read_state(reader):
    """The state record of client class aNx."""
    row = _read_layout(reader, STATE_LAYOUT)
    return StateRecord(row['id'], row['bcw'], row['efW'])


def _read_ability(reader):
    """The ability record of client class aJX."""
    row = _read_layout(reader, ABILITY_LAYOUT)
    return AbilityRecord(row['id'], row['category'], row['ddL'], row['cgI'],
                         row['effect_ids'])


def _read_ability_category(reader):
    """The fixed ability category record of client class aJY."""
    row = _read_layout(reader, ABILITY_CATEGORY_LAYOUT)
    return AbilityCategoryRecord(row['id'], row['unlock_levels'], row['ability_ids'])


def _read_set(reader):
    """The item set record of client class aLT: a map of pieces needed to effect ids."""
    ident = reader.i16()
    elg = reader.i32()
    item_ids = reader.i32s()
    bonuses = {}
    for _ in range(reader.count()):
        pieces = reader.i32()
        if pieces in bonuses:
            raise TableError('set %d lists %d pieces twice' % (ident, pieces))
        bonuses[pieces] = reader.i32s()
    return SetRecord(ident, elg, item_ids, bonuses)


def read_effects(jar_path):
    """[EffectRecord] from the static effect table (68.jar)."""
    return _read_records(jar_path, STATIC_EFFECT_TABLE, _read_effect, 'effect')


def read_effect_groups(jar_path):
    """[GroupRecord] from the effect group table (29.jar)."""
    return _read_records(jar_path, EFFECT_GROUP_TABLE, _read_group, 'effect group')


def read_item_sets(jar_path):
    """[SetRecord] from the item set table (36.jar)."""
    return _read_records(jar_path, ITEM_SET_TABLE, _read_set, 'item set')


def read_states(jar_path):
    """[StateRecord] from the state table (67.jar)."""
    return _read_records(jar_path, STATE_TABLE, _read_state, 'state')


def read_abilities(jar_path):
    """[AbilityRecord] from the ability table (135.jar)."""
    return _read_records(jar_path, ABILITY_TABLE, _read_ability, 'ability')


def read_ability_categories(jar_path):
    """[AbilityCategoryRecord] from the fixed ability category table (136.jar)."""
    return _read_records(jar_path, ABILITY_CATEGORY_TABLE, _read_ability_category,
                         'ability category')


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
