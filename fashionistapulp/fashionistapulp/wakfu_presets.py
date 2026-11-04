# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""The Wakfu presets: what a build can be asked for, per class, and the role each one means.

    offered(8)                      # the presets Iop sees, the default first
    role(8, 'tank', ('fire',), 245)  # the wakfu_value.Role of that choice
    standard_weights(8, 245, 'tank', ('fire',))

A preset holds role fields and shares, never an element: the build's elements are always
asked. The classes' official roles are read from the client's breed texts, the level brackets
from the levels of the epic items.
"""

import collections
import functools
import os
import sqlite3

from . import wakfu_family, wakfu_slots, wakfu_value
from .wakfu_stats import OUT_OF_COMBAT_CAPS

MELEE_DAMAGE = ('damage_melee_single', 'damage_melee_area')
DISTANCE_DAMAGE = ('damage_distance_single', 'damage_distance_area')
MIXED_DAMAGE = ('damage_mixed_single', 'damage_mixed_area')
DAMAGE_PRESETS = MELEE_DAMAGE + DISTANCE_DAMAGE + MIXED_DAMAGE
ROLE_PRESETS = ('tank', 'heal', 'support', 'placement', 'hindrance', 'mule')

#: reach None is the class's own reach, see class_reach
PRESETS = collections.OrderedDict(
    [(key, {'reach': key.split('_')[1], 'target': key.split('_')[2], 'berserk': False})
     for key in DAMAGE_PRESETS]
    + [(key, {'reach': None, 'target': 'single', 'berserk': False}) for key in ROLE_PRESETS])

#: share of each component per preset; the damage presets take life from the defense_weight rule
STARTING_SHARES = {
    'tank': {'damage': 1, 'life': 1, 'lock': 0.1},
    'heal': {'damage': 0.25, 'heal': 1, 'life': 0.25},
    'support': {'damage': 0.25, 'armor': 0.75, 'heal': 0.25, 'life': 0.25, 'initiative': 0.05},
    'placement': {'damage': 0.5, 'placement': 1, 'dodge': 0.1, 'life': 0.25},
    'hindrance': {'damage': 0.5, 'hindrance': 1, 'lock': 0.1, 'life': 0.25},
    'mule': {'mule': 1, 'life': 0.5},
}
PVP_SHARES = {'dodge': 0.05, 'initiative': 0.05}

#: {class id: {preset: {component: share}}} that replace the starting shares of one class
SHARES = {
    6: {'heal': {'damage': 0.125}},
    7: {'heal': {'damage': 0.125}},
    10: {'support': {'armor': 0.625, 'life': 0.5}},
    16: {'support': {'armor': 0.625, 'life': 0.5}},
    19: {'heal': {'damage': 0.0625}},
}

#: the preset a family of a class's official role asks for; damage has the damage presets
ROLE_PRESET = {'tank': 'tank', 'heal': 'heal', 'support': 'support', 'placement': 'placement',
               'hindrance': 'hindrance', 'mule': 'mule'}

#: What each client role id means (breed.role.desc.<breed>.<id>); id 0 is the class's specialty
ROLE_OF_ID = {
    1: ('hindrance',),
    2: ('tank',),
    3: ('heal',),
    4: ('damage',),
    5: ('placement',),
    6: ('summons',),
    7: ('hindrance', 'placement'),
    8: ('support',),
}
NOT_MODELLED_ROLES = ('summons',)

#: the families a preset is about: it is offered when one of them reads, and refused when none
DEFINING = {'heal': ('heal',), 'support': ('armor', 'heal'), 'placement': ('placement',),
            'hindrance': ('hindrance',)}

#: The word each specialty text opens with, in English and French, and what it means
Specialty = collections.namedtuple('Specialty', 'english french roles reach')
SPECIALTY = {
    'Prospecting': Specialty('Prospecting', 'Prospection', ('mule',), None),
    'Murderer': Specialty('Murderer', 'Assassinat', ('damage',), None),
    'Medicine': Specialty('Medicine', 'Médecine', ('heal',), None),
    'Melee': Specialty('Melee', 'Mêlée', ('damage',), 'melee'),
    'Long Range': Specialty('Long Range', 'Distance', ('damage',), 'distance'),
    'Bombs': Specialty('Bombs', 'Bombes', ('damage',), None),
    'Versatility': Specialty('Versatility', 'Polyvalence', ('damage',), None),
}

#: MethodWakfu lists 16 brackets of 15 levels [Fan]: the epic item levels agree with it
BRACKET_CREDIT = 'MethodWakfu, General information: 16 level brackets of 15 levels'
EPIC = next(number for number, name in wakfu_slots.RARITIES.items() if name == 'epic')
FIRST_BRACKET_LOW = 1

ClientRole = collections.namedtuple('ClientRole', 'id key')


def _path(path=None):
    if path is None:
        from .fashionista_config import get_items_db_path
        path = get_items_db_path('wakfu')
    return path


def _connect(path):
    return sqlite3.connect('file:%s?mode=ro' % path, uri=True)


def _stamp(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def brackets(conn):
    """[(low, high)] of the level brackets: each top is a level epic items exist at."""
    tops = [level for (level,) in conn.execute(
        'SELECT DISTINCT items.level FROM items JOIN item_rarity ON item_rarity.item = items.id '
        'WHERE item_rarity.rarity = ? AND COALESCE(items.removed, 0) = 0 ORDER BY items.level',
        (EPIC,))]
    lows = [FIRST_BRACKET_LOW] + [top + 1 for top in tops[:-1]]
    return list(zip(lows, tops))



def class_roles(conn):
    """{breed id: (ClientRole, ...)} of the roles the client's breed texts give each class."""
    found = collections.defaultdict(list)
    for key, in conn.execute(
            "SELECT key FROM client_breed_texts WHERE language = 'en' "
            "AND key LIKE 'breed.role.desc.%'"):
        _, _, _, breed, role = key.split('.')
        found[int(breed)].append(ClientRole(int(role), key))
    return {breed: tuple(sorted(roles)) for breed, roles in sorted(found.items())}


def specialty_word(conn, breed, language='en'):
    """The word the class's specialty text (role id 0) opens with, None when it has none."""
    row = conn.execute('SELECT text FROM client_breed_texts WHERE key = ? AND language = ?',
                       ('breed.role.desc.%d.0' % breed, language)).fetchone()
    if row is None:
        return None
    return row[0].split(':')[0].strip()


@functools.lru_cache(maxsize=None)
def _tables(path, stamp):
    conn = _connect(path)
    try:
        roles = class_roles(conn)
        words = {breed: specialty_word(conn, breed) for breed in roles}
        return brackets(conn), roles, words
    finally:
        conn.close()


def _read(path=None):
    path = _path(path)
    return _tables(path, _stamp(path))


def bracket_of(level, path=None):
    """(low, high) of the bracket a level falls in; a level above the last one takes the last."""
    found = _read(path)[0]
    for low, high in found:
        if level <= high:
            return low, high
    return found[-1]


def _spec(class_id, path=None):
    _, roles, words = _read(path)
    if class_id not in roles:
        raise ValueError('class %r has no role text in the client tables' % (class_id,))
    word = words.get(class_id)
    specialty = SPECIALTY.get(word) if word is not None else None
    if word is not None and specialty is None:
        raise ValueError('class %d has an unknown specialty %r' % (class_id, word))
    return roles[class_id], specialty


def official_roles(class_id, path=None):
    """The site roles of the class, in the order of its client role ids, each once."""
    entries, specialty = _spec(class_id, path)
    found = []
    for entry in entries:
        names = specialty.roles if entry.id == 0 else ROLE_OF_ID[entry.id]
        for name in names:
            if name not in found:
                found.append(name)
    return tuple(found)


def class_reach(class_id, path=None):
    """melee or distance when the class's specialty says so, mixed otherwise."""
    specialty = _spec(class_id, path)[1]
    return (specialty.reach if specialty is not None else None) or 'mixed'


def default_preset(class_id, path=None):
    """The preset chosen for a class: its single target damage preset."""
    return 'damage_%s_single' % class_reach(class_id, path)


def _ceiling():
    return {name.lower(): cap for name, cap in OUT_OF_COMBAT_CAPS.items()}


@functools.lru_cache(maxsize=None)
def _readable(path, stamp, class_id, family, level):
    from . import wakfu_turn

    book = wakfu_turn.SpellBook(path)
    try:
        spells = book.family_spells(class_id, level, family)
    finally:
        book.close()
    role = wakfu_value.Role(wakfu_value.ELEMENTS, 'distance')
    options = {'recipient': 'allies'} if family == 'armor' else {}
    return wakfu_turn.TurnModel(spells, role, family, **options).damage(_ceiling()) > 0


def reads(class_id, family, bracket, path=None):
    """Whether the class has a turn of the family (heal, armor, placement or hindrance) that
    the reader counts at the first level of the bracket whose top is `bracket`, with AP, MP
    and WP at their caps; an armor turn counts the rows that reach allies. The family turns
    read no element filter, so no element is asked."""
    if family not in wakfu_family.FAMILIES:
        raise ValueError('family is one of %s, got %r' % (wakfu_family.FAMILIES, family))
    path = _path(path)
    return _readable(path, _stamp(path), class_id, family, bracket_of(bracket, path)[0])


def _unreadable(class_id, preset, table, bracket, path):
    """The family shares of a preset's table that the class cannot read in the bracket;
    ValueError when the preset's defining families are all among them."""
    found = [family for family in wakfu_family.FAMILIES
             if family in table and not reads(class_id, family, bracket, path)]
    if set(DEFINING.get(preset, ())) and set(DEFINING[preset]) <= set(found):
        raise ValueError('class %d reads no %s turn in the bracket up to level %d'
                         % (class_id, ' or '.join(DEFINING[preset]), bracket))
    return found


def offered(class_id, bracket, path=None):
    """The presets a class sees in a bracket (its top level): its default first, then those
    of its official roles whose defining families its turns can read, then the other damage
    presets. Any class may still ask for any preset."""
    default = default_preset(class_id, path)
    official = []
    for name in official_roles(class_id, path):
        preset = ROLE_PRESET.get(name)
        if preset is None or preset in official:
            continue
        defining = DEFINING.get(preset, ())
        if defining and not any(reads(class_id, family, bracket, path) for family in defining):
            continue
        official.append(preset)
    others = [key for key in DAMAGE_PRESETS if key != default]
    return (default,) + tuple(official) + tuple(others)


def _check_preset(preset, content):
    if preset not in PRESETS:
        raise ValueError('preset is one of %s, got %r' % (', '.join(PRESETS), preset))
    if content not in wakfu_value.CONTENTS:
        raise ValueError('content is %s, got %r' % (' or '.join(wakfu_value.CONTENTS), content))


def shares(class_id, preset, elements, content, bracket, path=None):
    """{component: share} of a preset for a class: its table, plus the pvp shares in pvp.

    bracket is the top level of the bracket. A family share the class cannot read in the
    bracket is dropped; a preset whose defining families are all unreadable (heal, armor,
    placement, hindrance, and support when neither armor nor heal reads) raises ValueError.
    """
    _check_preset(preset, content)
    _spec(class_id, path)
    if preset != 'mule' and not tuple(elements):
        raise ValueError('elements are required: choose from %s'
                         % ', '.join(wakfu_value.ELEMENTS))
    if preset in DAMAGE_PRESETS:
        table = {'damage': 1.0, 'life': wakfu_value.rule('defense_weight')}
    else:
        table = {}
    table.update(STARTING_SHARES.get(preset, {}))
    table.update(SHARES.get(class_id, {}).get(preset, {}))
    table = {name: float(share) for name, share in table.items()}
    if content == 'pvp':
        for name, share in PVP_SHARES.items():
            table[name] = table.get(name, 0.0) + share
    for family in _unreadable(class_id, preset, table, bracket, path):
        del table[family]
    return table


def role(class_id, preset, elements, level, content='pvm', path=None):
    """The wakfu_value.Role of a preset: ValueError without an element, except for the mule."""
    _check_preset(preset, content)
    spec = PRESETS[preset]
    top = bracket_of(level, path)[1]
    reach = spec['reach'] or class_reach(class_id, path)
    if isinstance(elements, str):
        elements = [name for name in elements.split(',') if name.strip()]
    elements = () if preset == 'mule' else tuple(elements)
    return wakfu_value.Role(
        elements, reach, spec['target'], content, spec['berserk'],
        shares=shares(class_id, preset, elements, content, top, path))


def _structure():
    from .structure import get_structure
    return get_structure('wakfu')


@functools.lru_cache(maxsize=None)
def _scales(path, stamp, top):
    return wakfu_value.stat_scales(_structure(), top)


def scales(level, path=None):
    """{stat key: scale} of the lock, dodge and initiative components in the level's bracket."""
    path = _path(path)
    return dict(_scales(path, _stamp(path), bracket_of(level, path)[1]))


def build_turns(book, class_id, level, built, path=None):
    """The wakfu_turn.RoleTurns a role is valued on, for a class at a level."""
    from . import wakfu_turn

    return wakfu_turn.role_turns(book, class_id, level, built, scales(level, path))


def standard_weights(class_id, level, preset, elements, content='pvm', path=None):
    """{stat key: percent of value per point} of a preset for a class, at the totals of a
    character wearing nothing."""
    from . import wakfu_criteria, wakfu_turn

    path = _path(path)
    built = role(class_id, preset, elements, level, content, path)
    base = wakfu_criteria.base_values(_structure(), class_id)
    totals = wakfu_value.bare_totals(base)
    book = wakfu_turn.SpellBook(path)
    try:
        turns = build_turns(book, class_id, level, built, path)
    finally:
        book.close()
    return wakfu_value.linear_weights(built, level, totals, turns)


def site_entry():
    """What chardata.presets needs for Wakfu: no style, box, mode or recipe of the Dofus
    presets, and the preset keys in display order. The labels belong to the setup page."""
    return {'styles': (), 'option_boxes': (), 'modes': ('general',), 'box_modes': {},
            'recipes': (), 'wakfu_presets': tuple(PRESETS)}
