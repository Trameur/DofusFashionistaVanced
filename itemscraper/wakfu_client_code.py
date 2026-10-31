#!/usr/bin/env python3
"""Read constants out of the Wakfu client's own code (lib/wakfu-client.jar).

    python itemscraper/wakfu_client_code.py <wakfu-client.jar>

The class files are read as data and nothing is loaded into a JVM. A table holds
characteristic ids, rarity ids, spell kinds and slot levels as numbers; the names
and the level thresholds live only in the code. Each constant is found by a text
the class loads, never by its obfuscated name, and an anchor that matches more or
fewer than one class stops the update: a silent misread would feed wrong
conditions to every solve.
"""

from __future__ import annotations

import json
import struct
import sys
import zipfile

CHARACTERISTIC_ANCHOR = ('INDIRECT_DMG', 'DMG_FIRE_PERCENT')
RARITY_ANCHOR = ('LEGENDARY', 'RELIC2')
SPELL_KIND_ANCHOR = ('ACTIVE', 'PASSIVE_FROM_1', 'PASSIVE_FROM_0')
PASSIVE_SLOTS_KEY = 'level.up.toast.passive.spell.slots'

INT_ARRAY = '[I'


class ClientCodeError(ValueError):
    pass


# Bytes of operand after each opcode that has a fixed number of them
_OPERAND_BYTES = {}
for _op in (0x10, 0x12, 0xa9, 0xbc) + tuple(range(0x15, 0x1a)) + tuple(range(0x36, 0x3b)):
    _OPERAND_BYTES[_op] = 1
for _op in (0x11, 0x13, 0x14, 0x84, 0xbb, 0xbd, 0xc0, 0xc1, 0xc6, 0xc7) \
        + tuple(range(0x99, 0xa9)) + tuple(range(0xb2, 0xb9)):
    _OPERAND_BYTES[_op] = 2
for _op in (0xb9, 0xba, 0xc8, 0xc9):
    _OPERAND_BYTES[_op] = 4
_OPERAND_BYTES[0xc5] = 3

_ICONST = {0x02 + step: step - 1 for step in range(7)}  # iconst_m1 .. iconst_5
_ALOAD_FIRST, _ALOAD_LAST = 0x2a, 0x2d
_DUP, _IASTORE, _NEW, _NEWARRAY, _PUTSTATIC, _GETSTATIC = 0x59, 0x4f, 0xbb, 0xbc, 0xb3, 0xb2
_BIPUSH, _SIPUSH, _LDC, _LDC_W = 0x10, 0x11, 0x12, 0x13
_INVOKESPECIAL = 0xb7


class ClassInfo:
    """One parsed class file: constant pool, fields and methods with their Code bytes."""

    def __init__(self, name, pool, fields, methods):
        self.name = name
        self.pool = pool
        self.fields = fields
        self.methods = methods

    def utf8(self, index):
        return self.pool[index][1]

    def string_constants(self):
        return {self.utf8(entry[1]) for entry in self.pool if entry and entry[0] == 'string'}

    def member_ref(self, index):
        """(owner class, member name, descriptor) of a field or method reference."""
        _kind, owner, name_and_type = self.pool[index]
        _tag, name_index, descriptor_index = self.pool[name_and_type]
        return (self.utf8(self.pool[owner][1]), self.utf8(name_index),
                self.utf8(descriptor_index))

    def method(self, name):
        for found, _descriptor, code in self.methods:
            if found == name:
                return code
        return None


def parse_class(blob):
    """The ClassInfo of one class file."""
    if blob[:4] != b'\xca\xfe\xba\xbe':
        raise ClientCodeError('not a class file')
    position = 8
    count = struct.unpack_from('>H', blob, position)[0]
    position += 2
    pool = [None] * count
    index = 1
    while index < count:
        tag = blob[position]
        position += 1
        if tag == 1:
            length = struct.unpack_from('>H', blob, position)[0]
            pool[index] = ('utf8', blob[position + 2:position + 2 + length].decode(
                'utf-8', 'replace'))
            position += 2 + length
        elif tag == 3:
            pool[index] = ('int', struct.unpack_from('>i', blob, position)[0])
            position += 4
        elif tag == 4:
            pool[index] = ('float', struct.unpack_from('>f', blob, position)[0])
            position += 4
        elif tag in (5, 6):
            pool[index] = ('long' if tag == 5 else 'double', blob[position:position + 8])
            position += 8
            index += 1
        elif tag in (7, 8, 16, 19, 20):
            kind = {7: 'class', 8: 'string', 16: 'mtype', 19: 'module', 20: 'package'}[tag]
            pool[index] = (kind, struct.unpack_from('>H', blob, position)[0])
            position += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            kind = {9: 'field', 10: 'method', 11: 'imethod', 12: 'nat', 17: 'dynamic',
                    18: 'indy'}[tag]
            first, second = struct.unpack_from('>HH', blob, position)
            pool[index] = (kind, first, second)
            position += 4
        elif tag == 15:
            pool[index] = ('handle', blob[position])
            position += 3
        else:
            raise ClientCodeError('constant pool tag %d at %d' % (tag, position))
        index += 1
    _access, this, _super = struct.unpack_from('>HHH', blob, position)
    position += 6
    interfaces = struct.unpack_from('>H', blob, position)[0]
    position += 2 + 2 * interfaces
    members = []
    for _ in range(2):
        found = []
        total = struct.unpack_from('>H', blob, position)[0]
        position += 2
        for _ in range(total):
            _flags, name, descriptor, attributes = struct.unpack_from('>HHHH', blob, position)
            position += 8
            code = None
            for _ in range(attributes):
                attribute, length = struct.unpack_from('>HI', blob, position)
                position += 6
                if pool[attribute][1] == 'Code':
                    code = blob[position:position + length]
                position += length
            found.append((pool[name][1], pool[descriptor][1], code))
        members.append(found)
    return ClassInfo(pool[pool[this][1]][1], pool, members[0], members[1])


def _bytecode(code):
    """The instruction bytes of a Code attribute."""
    length = struct.unpack_from('>I', code, 4)[0]
    return code[8:8 + length]


def _instructions(code):
    """(offset, opcode, operand bytes) over a Code attribute's bytecode."""
    bytecode = _bytecode(code)
    position = 0
    while position < len(bytecode):
        opcode = bytecode[position]
        start = position
        position += 1
        if opcode == 0xc4:
            width = 5 if bytecode[position] == 0x84 else 3
            operand = bytecode[position:position + width]
            position += width
        elif opcode in (0xaa, 0xab):
            position = (position + 3) & ~3
            if opcode == 0xaa:
                low, high = struct.unpack_from('>ii', bytecode, position + 4)
                width = 12 + 4 * (high - low + 1)
            else:
                pairs = struct.unpack_from('>i', bytecode, position + 4)[0]
                width = 8 + 8 * pairs
            operand = bytecode[position:position + width]
            position += width
        else:
            width = _OPERAND_BYTES.get(opcode, 0)
            operand = bytecode[position:position + width]
            position += width
        yield start, opcode, operand


def _pushed_int(info, opcode, operand):
    """The int an instruction pushes, else None."""
    if opcode in _ICONST:
        return _ICONST[opcode]
    if opcode == _BIPUSH:
        return struct.unpack('>b', operand)[0]
    if opcode == _SIPUSH:
        return struct.unpack('>h', operand)[0]
    if opcode in (_LDC, _LDC_W):
        index = operand[0] if opcode == _LDC else struct.unpack('>H', operand)[0]
        entry = info.pool[index]
        return entry[1] if entry[0] == 'int' else None
    return None


def _pushed_string(info, opcode, operand):
    if opcode in (_LDC, _LDC_W):
        index = operand[0] if opcode == _LDC else struct.unpack('>H', operand)[0]
        entry = info.pool[index]
        if entry[0] == 'string':
            return info.utf8(entry[1])
    return None


def classes_with_strings(jar, strings):
    """[ClassInfo] of the jar's classes that load every one of `strings`.

    `jar` is a path or an open ZipFile. The raw bytes are searched first, so only the
    few candidates are parsed.
    """
    wanted = tuple(text.encode('utf-8') for text in strings)
    archive = jar if isinstance(jar, zipfile.ZipFile) else zipfile.ZipFile(jar)
    found = []
    for name in archive.namelist():
        if not name.endswith('.class'):
            continue
        blob = archive.read(name)
        if all(text in blob for text in wanted):
            info = parse_class(blob)
            if set(strings) <= info.string_constants():
                found.append(info)
    return found


def enum_arguments(info):
    """[(name, [ints])] of an enum's constants, in <clinit> order.

    Each constant is `new, dup, ldc name, ordinal, arguments, invokespecial`. The ints are
    the ordinal, then every int pushed as an argument.
    """
    code = info.method('<clinit>')
    if code is None:
        raise ClientCodeError('%s has no static initializer' % info.name)
    constants = []
    name = None
    pushed = []
    previous = None
    for _start, opcode, operand in _instructions(code):
        text = _pushed_string(info, opcode, operand)
        if text is not None and previous == _DUP:
            name = text
            pushed = []
        elif name is not None:
            number = _pushed_int(info, opcode, operand)
            if number is not None:
                pushed.append(number)
            elif opcode == _INVOKESPECIAL:
                constants.append((name, pushed))
                name = None
        previous = opcode
    return constants


def enum_constants(info):
    """[(name, ordinal, first int argument)] of an enum's constants, in <clinit> order.

    The first int argument is the first int pushed after the ordinal (the id, for the enums
    read here).
    """
    constants = []
    for name, pushed in enum_arguments(info):
        if len(pushed) >= 2:
            constants.append((name, pushed[0], pushed[1]))
        elif len(pushed) == 1:
            constants.append((name, pushed[0], None))
    return constants


# Position of the default value among the ints a characteristic constant pushes: ordinal,
# id, minimum, maximum, lowest start, highest start, default
CHARACTERISTIC_DEFAULT_AT = 6


def characteristic_defaults(info):
    """{characteristic name: default value} of the characteristic enum's constants."""
    return {name: pushed[CHARACTERISTIC_DEFAULT_AT]
            for name, pushed in enum_arguments(info)
            if len(pushed) > CHARACTERISTIC_DEFAULT_AT}


def static_int_array(info, field):
    """The values of the `int[]` static field `field`, built in <clinit>."""
    code = info.method('<clinit>')
    if code is None:
        raise ClientCodeError('%s has no static initializer' % info.name)
    stack = []
    for _start, opcode, operand in _instructions(code):
        number = _pushed_int(info, opcode, operand)
        if number is not None:
            stack.append(number)
        elif opcode == _NEWARRAY and operand == b'\x0a' and stack \
                and isinstance(stack[-1], int):
            stack.append([0] * stack.pop())
        elif opcode == _DUP and stack:
            stack.append(stack[-1])
        elif opcode == _IASTORE and len(stack) >= 3 and isinstance(stack[-3], list):
            value, at = stack.pop(), stack.pop()
            stack.pop()[at] = value
        elif opcode == _PUTSTATIC:
            _owner, name, _descriptor = info.member_ref(struct.unpack('>H', operand)[0])
            held = stack.pop() if stack else None
            if name == field and isinstance(held, list):
                return tuple(held)
            stack = []
        else:
            stack = []
    raise ClientCodeError('%s holds no int array %s' % (info.name, field))


def getstatic_fields(info, text):
    """[(owner, field, descriptor)] read by getstatic in each method that loads `text`."""
    found = []
    for _name, _descriptor, code in info.methods:
        if code is None:
            continue
        instructions = list(_instructions(code))
        if not any(_pushed_string(info, opcode, operand) == text
                   for _start, opcode, operand in instructions):
            continue
        for _start, opcode, operand in instructions:
            if opcode == _GETSTATIC:
                reference = info.member_ref(struct.unpack('>H', operand)[0])
                if reference not in found:
                    found.append(reference)
    return found


def _only(jar, strings, what):
    found = classes_with_strings(jar, strings)
    if len(found) != 1:
        raise ClientCodeError('%s: %d classes load %s, expected 1'
                              % (what, len(found), ', '.join(strings)))
    return found[0]


def read_constants(jar_path):
    """The constants of the client code, and the class each was read from."""
    with zipfile.ZipFile(jar_path) as jar:
        characteristics = _only(jar, CHARACTERISTIC_ANCHOR, 'characteristics')
        rarities = _only(jar, RARITY_ANCHOR, 'rarities')
        kinds = _only(jar, SPELL_KIND_ANCHOR, 'spell kinds')
        # Another class loads the key without reading a slot table: only the class whose
        # method reads an int array beside the key is the anchor
        readers = [(info, reference) for info in classes_with_strings(jar, (PASSIVE_SLOTS_KEY,))
                   for reference in getstatic_fields(info, PASSIVE_SLOTS_KEY)
                   if reference[2] == INT_ARRAY]
        if len(readers) != 1:
            raise ClientCodeError('passive slots: %d int arrays are read beside %s, expected 1'
                                  % (len(readers), PASSIVE_SLOTS_KEY))
        toast, (owner, field, _descriptor) = readers[0]
        owner_info = parse_class(jar.read(owner + '.class'))
        return {
            'characteristics': {name: first for name, _ordinal, first
                                in enum_constants(characteristics)},
            'characteristic_defaults': characteristic_defaults(characteristics),
            'rarities': {name: first for name, _ordinal, first in enum_constants(rarities)},
            'spell_kinds': {name: ordinal for name, ordinal, _first
                            in enum_constants(kinds)},
            'passive_slot_levels': list(static_int_array(owner_info, field)),
            'anchors': {'characteristics': characteristics.name, 'rarities': rarities.name,
                        'spell_kinds': kinds.name, 'passive_slots': toast.name,
                        'passive_slot_levels': '%s.%s' % (owner, field)},
        }


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print(__doc__)
        return 2
    try:
        print(json.dumps(read_constants(arguments[0]), indent=1, sort_keys=True))
    except (ClientCodeError, OSError, zipfile.BadZipFile, struct.error) as error:
        print('the client code could not be read: %s' % error)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
