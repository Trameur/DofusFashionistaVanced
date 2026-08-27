#!/usr/bin/env python3
"""Reader for D2O, the table format of the Dofus 2 (Flash/AIR) client.

Why this exists: our Dofus 2 raw dump comes from the dofusdude mirror, and that
mirror publishes 52 files for 2.73.3.14 without `spell_levels.json`. The
comment in `dofus_constants_dofus2.py` used to say the 2.73 archive "ships no
spell level at all", which was a statement about the mirror and not about the
game. Ankama's own CDN carries `data/common/SpellLevels.d2o` for that exact
version, so the numbers were always there.

A D2O file is:

    "D2O" then an int32 pointing at the index
    the records, back to back, each one an int32 class id then its fields
    at the index offset: int32 byte length, then (int32 id, int32 offset) pairs
    then int32 class count, then the class definitions

A class definition is an int32 id, the AS3 class and package names, an int32
field count, and the fields. A field is its name then a type chain: a vector
writes its own AS3 name and then the type it holds, which may itself be a
vector.
"""

import struct

INT = -1
BOOLEAN = -2
STRING = -3
NUMBER = -4
I18N = -5
UINT = -6
VECTOR = -99

# Ankama's serialiser writes the four-letter word "null" rather than an empty
# string when a String field holds nothing. The dofusdude mirror normalises it
# to the empty string, and matching that is what makes a table decoded here
# interchangeable with the ones already in the dump: decoded this way, our
# Spells.d2o reproduces the mirror's spells.json on all 15655 records, field
# for field. Keeping the marker instead would disagree on 24388 fields and
# prove nothing.
NULL_STRING = 'null'
NULL_STRING_AS = ''


class _Reader:

    def __init__(self, buf, pos=0):
        self.buf = buf
        self.pos = pos

    def seek(self, pos):
        self.pos = pos

    def int32(self):
        value = struct.unpack_from('>i', self.buf, self.pos)[0]
        self.pos += 4
        return value

    def uint32(self):
        value = struct.unpack_from('>I', self.buf, self.pos)[0]
        self.pos += 4
        return value

    def double(self):
        value = struct.unpack_from('>d', self.buf, self.pos)[0]
        self.pos += 8
        return value

    def boolean(self):
        value = self.buf[self.pos] != 0
        self.pos += 1
        return value

    def utf(self):
        length = struct.unpack_from('>H', self.buf, self.pos)[0]
        self.pos += 2
        raw = self.buf[self.pos:self.pos + length]
        self.pos += length
        return raw.decode('utf-8', 'replace')


def _read_type(reader):
    """One link of a field's type chain: (kind, inner kind or None)."""
    kind = reader.int32()
    if kind == VECTOR:
        reader.utf()  # the AS3 name of the vector, which nothing here needs
        return (VECTOR, _read_type(reader))
    return (kind, None)


class _GameClass:

    def __init__(self, reader):
        self.name = reader.utf()
        self.package = reader.utf()
        self.fields = []
        for _ in range(reader.int32()):
            field_name = reader.utf()
            self.fields.append((field_name, _read_type(reader)))

    def read(self, reader, classes):
        return {name: _read_value(kind, reader, classes)
                for name, kind in self.fields}


def _read_value(kind, reader, classes):
    which, inner = kind
    if which == INT or which == I18N:
        return reader.int32()
    if which == UINT:
        return reader.uint32()
    if which == BOOLEAN:
        return reader.boolean()
    if which == STRING:
        text = reader.utf()
        return NULL_STRING_AS if text == NULL_STRING else text
    if which == NUMBER:
        return reader.double()
    if which == VECTOR:
        return [_read_value(inner, reader, classes)
                for _ in range(reader.int32())]
    # Anything else is a class id, but the record names its own class again,
    # so the declared one is only a hint and the stream decides.
    return _read_record(reader, classes)


def _read_record(reader, classes):
    class_id = reader.int32()
    if class_id == -1:
        return None
    return classes[class_id].read(reader, classes)


def load(path):
    """Read a .d2o file. Returns ({record id: record}, {class id: class})."""
    with open(path, 'rb') as handle:
        buf = handle.read()
    if buf[:3] != b'D2O':
        raise ValueError('%s does not start with the D2O marker' % path)

    reader = _Reader(buf, 3)
    reader.seek(reader.int32())
    index_bytes = reader.int32()
    index = [(reader.int32(), reader.int32())
             for _ in range(index_bytes // 8)]

    classes = {}
    for _ in range(reader.int32()):
        class_id = reader.int32()
        classes[class_id] = _GameClass(reader)

    records = {}
    for record_id, offset in index:
        reader.seek(offset)
        records[record_id] = _read_record(reader, classes)
    return records, classes


def load_rows(path):
    """The records as a plain list, which is how the Dofus 2 dump stores them."""
    records, _ = load(path)
    return [records[key] for key in sorted(records)]


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path')
    parser.add_argument('--json', metavar='FILE', help='write the rows there')
    args = parser.parse_args()

    records, classes = load(args.path)
    print('%d record(s), class(es): %s'
          % (len(records), ', '.join(sorted(c.name for c in classes.values()))))
    if args.json:
        rows = [records[key] for key in sorted(records)]
        with open(args.json, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(rows, handle, ensure_ascii=False)
        print('%s -> %s' % (args.path, args.json))


if __name__ == '__main__':
    main()
