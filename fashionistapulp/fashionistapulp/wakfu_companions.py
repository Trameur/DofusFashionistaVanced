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

"""The levels a Wakfu pet or mount is worn at, and the lines it gives there."""

import collections
from types import MappingProxyType

from .wakfu_db import level_value

# Levels.pet and Levels.mount are slot levels; Levels.items is {item id: level}
Levels = collections.namedtuple(
    'Levels', 'pet mount items', defaults=(None, None, MappingProxyType({})))

# The level_slot a slot level applies to
PET = 'PET'
MOUNT = 'MOUNT'


def is_level(level):
    return isinstance(level, int) and not isinstance(level, bool)


def highest_cap(structure, slot):
    """The highest level any item of this slot can reach, 0 when none levels."""
    return max((item.level_cap for item in structure.get_items_list()
                if getattr(item, 'level_cap', None) is not None
                and item.level_slot == slot), default=0)


def read_levels(structure, pet=None, mount=None, items=None):
    """The Levels of a request; ValueError when a level cannot be worn."""
    for name, slot, level in (('pet', PET, pet), ('mount', MOUNT, mount)):
        if level is None:
            continue
        top = highest_cap(structure, slot)
        if not is_level(level):
            raise ValueError('%s level %r is not a whole number' % (name, level))
        if not 0 <= level <= top:
            raise ValueError('%s level %r is outside 0 to %d' % (name, level, top))
    given = {}
    for ident, level in (items or {}).items():
        item = structure.get_item_by_id(ident)
        cap = getattr(item, 'level_cap', None)
        if item is None:
            raise ValueError('item %r is not in the catalogue, so it takes no level (%r)'
                             % (ident, level))
        if cap is None:
            raise ValueError('item %s (%s) does not level, so level %r is refused'
                             % (item.name, ident, level))
        if not is_level(level):
            raise ValueError('item %s (%s) level %r is not a whole number'
                             % (item.name, ident, level))
        if not 0 <= level <= cap:
            raise ValueError('item %s (%s) level %r is outside 0 to its cap of %d'
                             % (item.name, ident, level, cap))
        given[ident] = level
    return Levels(pet, mount, MappingProxyType(given))


def level_of(levels, item):
    """The level an item is worn at: None when it does not level."""
    cap = getattr(item, 'level_cap', None)
    if cap is None:
        return None
    if item.id in levels.items:
        return levels.items[item.id]
    slot_level = levels.pet if item.level_slot == PET else (
        levels.mount if item.level_slot == MOUNT else None)
    if slot_level is not None:
        return min(slot_level, cap)
    return cap


def lines_at(item, level):
    """[(stat id, value)] an item gives at a level, its stored lines for None."""
    if level is None:
        return list(item.stats)
    lines = ((stat_id, level_value(base, per_level, level))
             for stat_id, base, per_level in getattr(item, 'level_lines', ()))
    return [(stat_id, value) for stat_id, value in lines if value]
