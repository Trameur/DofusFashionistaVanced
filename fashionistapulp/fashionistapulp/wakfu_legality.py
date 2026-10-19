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

"""Check a Wakfu set against every rule, from the database and not from the solver's constraints."""

import collections

from .game_versions import get_game_version
from .wakfu_slots import BLOCKED_BY_TWO_HANDED, EXCLUSIVE_PROPERTIES, SLOTS
from .wakfu_stats import BASE_VALUES, CRITICAL_HIT_FLOOR_PERCENT, \
    OUT_OF_COMBAT_CAPS

UNKNOWN = 'unknown item'
SLOT = 'slot'
SLOT_COUNT = 'slot count'
LEVEL = 'level'
REMOVED = 'removed'
FORBIDDEN = 'forbidden'
LOCK = 'lock'
SAME_ITEM = 'same item'
TWO_HANDED = 'two-handed'
# Rule names; the flags they police come from EXCLUSIVE_PROPERTIES
RELIC = 'one relic'
EPIC = 'one epic'
CAP = 'cap'
CRITICAL_FLOOR = 'critical floor'
MINIMUM = 'minimum'

EXCLUSIVE_FLAGS = tuple(EXCLUSIVE_PROPERTIES.values())


class _Rules:
    def __init__(self, structure):
        self.structure = structure
        self.positions = collections.defaultdict(set)
        for type_id, position in structure.get_type_positions():
            self.positions[type_id].add(position)

    def stat_total(self, items, key):
        stat = self.structure.get_stat_by_key(key)
        if stat is None:
            return 0
        return sum(value for item in items for stat_id, value in item.stats
                   if stat_id == stat.id)

    def title(self, item):
        names = item.localized_names or {}
        return item.type, names.get('fr') or item.name


def _pairs(worn):
    """[(position, item)] of a mapping, whose values may be lists, or of an iterable of pairs."""
    entries = worn.items() if hasattr(worn, 'items') else worn
    out = []
    for position, held in entries:
        if isinstance(held, (list, tuple, set, frozenset)):
            out.extend((position, item) for item in held)
        else:
            out.append((position, held))
    return out


def violations(structure, level, worn, forbidden=(), locked=(), minimums=None):
    """[(rule, text)] of every rule a set breaks; an empty list is a legal set.

    worn: {position: item}, or an iterable of (position, item); a position
    may hold a list, which is how a set with two items in one slot is written.
    locked: (item id, position or None) pairs. minimums: {stat key: lowest
    total, base values included}.
    """
    rules = _Rules(structure)
    found = []
    pairs = []
    # Every field is read from the catalogue, never from the object passed in
    for position, given in _pairs(worn):
        item = structure.get_item_by_id(given.id)
        if item is None:
            found.append((UNKNOWN, 'item %s is not in the catalogue' % (given.id,)))
        else:
            pairs.append((position, item))
    forbidden = set(forbidden)

    held = collections.defaultdict(list)
    for position, item in pairs:
        held[position].append(item)
    for position, items in held.items():
        if position not in SLOTS:
            found.append((SLOT, '%s is not a Wakfu slot' % position))
        if len(items) > 1:
            found.append((SLOT_COUNT, '%s holds %d items: %s' % (
                position, len(items), ', '.join(item.name for item in items))))

    for position, item in pairs:
        allowed = rules.positions.get(item.type, set())
        if position not in allowed:
            found.append((SLOT, '%s cannot be worn in %s (its type fits %s)' % (
                item.name, position, ', '.join(sorted(allowed)) or 'no slot')))
        if item.level > level:
            found.append((LEVEL, '%s is level %d, above the build level %d'
                          % (item.name, item.level, level)))
        if item.removed:
            found.append((REMOVED, '%s is removed from the game' % item.name))
        if item.id in forbidden:
            found.append((FORBIDDEN, '%s is forbidden' % item.name))

    wearing = [item for _position, item in pairs]
    for ident, position in locked:
        places = [place for place, item in pairs if item.id == ident]
        if not places:
            found.append((LOCK, 'locked item %s is not worn' % ident))
        elif position is not None and position not in places:
            found.append((LOCK, 'locked item %s is worn in %s, not in %s' % (
                ident, ', '.join(places), position)))

    copies = collections.defaultdict(list)
    for item in wearing:
        copies[rules.title(item)].append(item)
    allowed_copies = 2 if get_game_version('wakfu').rings_can_double else 1
    for items in copies.values():
        if len(items) > allowed_copies:
            found.append((SAME_ITEM, '%s is worn %d times, across rarities or ids %s'
                          % (items[0].name, len(items),
                             ', '.join(str(item.id) for item in items))))

    if any('two_handed' in (item.flags or ()) for item in wearing) \
            and held.get(BLOCKED_BY_TWO_HANDED):
        found.append((TWO_HANDED, 'a two-handed weapon is worn with the %s '
                                  'slot filled' % BLOCKED_BY_TWO_HANDED))

    for flag in EXCLUSIVE_FLAGS:
        group = [item for item in wearing if flag in (item.flags or ())]
        if len(group) > 1:
            found.append(('one %s' % flag, '%d %s items are worn: %s' % (
                len(group), flag, ', '.join(item.name for item in group))))

    for name, cap in OUT_OF_COMBAT_CAPS.items():
        total = BASE_VALUES[name] + rules.stat_total(wearing, name.lower())
        if total > cap:
            found.append((CAP, '%s is %d, over the cap of %d' % (name, total, cap)))

    ferocity = rules.stat_total(wearing, 'ferocity')
    if ferocity < CRITICAL_HIT_FLOOR_PERCENT:
        found.append((CRITICAL_FLOOR, 'the gear critical hit sum is %d, under the '
                                      'floor of %d' % (ferocity, CRITICAL_HIT_FLOOR_PERCENT)))

    for key, lowest in sorted((minimums or {}).items()):
        total = BASE_VALUES.get(key.upper(), 0) + rules.stat_total(wearing, key)
        if total < lowest:
            found.append((MINIMUM, '%s is %d, under the minimum of %d'
                          % (key, total, lowest)))
    return found
