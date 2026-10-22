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
from . import wakfu_criteria
from .wakfu_slots import (BLOCKED_BY_TWO_HANDED, EXCLUSIVE_PROPERTIES, SLOTS,
                          TWO_HANDED_FLAG)
from .wakfu_stats import OUT_OF_COMBAT_CAPS

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
MINIMUM = 'minimum'
CLASS = 'class'
CONDITION = 'condition'
NOT_WORN_WITH = 'not worn with'
WORN_WITH = 'worn with'
UNUSABLE = 'unusable'
STATE = 'player state'

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


def violations(structure, level, worn, forbidden=(), locked=(), minimums=None,
               class_id=None, state=None):
    """[(rule, text)] of every rule a set breaks; an empty list is a legal set.

    worn: {position: item}, or an iterable of (position, item); a position
    may hold a list, which is how a set with two items in one slot is written.
    locked: (item id, position or None) pairs. minimums: {stat key: lowest
    total, base values included}. class_id: the breed, none for a build with
    no class. state: the PlayerState the player-state conditions are read
    against, the game's start values by default.
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

    if any(TWO_HANDED_FLAG in (item.flags or ()) for item in wearing) \
            and held.get(BLOCKED_BY_TWO_HANDED):
        found.append((TWO_HANDED, 'a two-handed weapon is worn with the %s '
                                  'slot filled' % BLOCKED_BY_TWO_HANDED))

    for flag in EXCLUSIVE_FLAGS:
        group = [item for item in wearing if flag in (item.flags or ())]
        if len(group) > 1:
            found.append(('one %s' % flag, '%d %s items are worn: %s' % (
                len(group), flag, ', '.join(item.name for item in group))))

    base = wakfu_criteria.base_values(structure, class_id)
    for name, cap in OUT_OF_COMBAT_CAPS.items():
        total = (base.get(name.lower(), (0, 0))[1]
                 + rules.stat_total(wearing, name.lower()))
        if total > cap:
            found.append((CAP, '%s is %d, over the cap of %d' % (name, total, cap)))

    for key, lowest in sorted((minimums or {}).items()):
        total = base.get(key, (0, 0))[0] + rules.stat_total(wearing, key)
        if total < lowest:
            found.append((MINIMUM, '%s is %d, under the minimum of %d'
                          % (key, total, lowest)))

    found.extend(_conditions(structure, pairs, level, class_id,
                             state or wakfu_criteria.start_state()))
    return found


def _show(node):
    """A failing atom in the text it was written in, close enough to read."""
    if isinstance(node, wakfu_criteria.Compare):
        return '%s %s %s' % (_show(node.call), node.op, node.value)
    if isinstance(node, wakfu_criteria.Call):
        return '%s(%s)' % (node.name, ', '.join(str(one) for one in node.args))
    if isinstance(node, wakfu_criteria.Not):
        return 'not ' + _show(node.child)
    if isinstance(node, wakfu_criteria.Const):
        return str(node.value)
    return '(' + ' ... '.join(sorted(wakfu_criteria.functions(node))) + ')'


def _rule_of(node):
    """The rule a failing conjunct of an EQUIP text breaks."""
    while isinstance(node, wakfu_criteria.Hidden):
        node = node.child
    names = wakfu_criteria.functions(node)
    negated = isinstance(node, wakfu_criteria.Not)
    if 'HasEquipmentId' in names:
        return NOT_WORN_WITH if negated else WORN_WITH
    if 'HasAnotherSameEquipment' in names:
        return SAME_ITEM
    if 'IsBreed' in names:
        return CLASS
    if 'IsAdmin' in names or 'False' in names:
        return UNUSABLE
    if names & set(wakfu_criteria.LEVEL_FUNCTIONS):
        return LEVEL
    if any(wakfu_criteria.classify(name) == wakfu_criteria.STATE
           for name in names if name in wakfu_criteria.FUNCTIONS):
        return STATE
    return CONDITION


def _conditions(structure, pairs, level, class_id, state):
    """Each worn piece's own EQUIP text, judged with and without the piece."""
    bases = structure.get_breed_base_values()
    names = structure.get_breed_names()
    breeds = [class_id] if class_id is not None else sorted(bases)
    wearing = [item for _position, item in pairs]
    sums = collections.Counter()
    owns = {}
    for item in wearing:
        own = collections.Counter()
        for stat_id, value in item.stats:
            stat = structure.get_stat_by_id(stat_id)
            if stat is not None:
                own[stat.key] += value
        owns[item.id] = own
        sums.update(own)
    found = []
    for index, (position, item) in enumerate(pairs):
        text = getattr(item, 'criteria', None)
        if not text:
            continue
        tree = wakfu_criteria.parse(text)
        others = {one.id for place, one in enumerate(wearing) if place != index}
        seen = set()
        for breed in breeds:
            for without in (False, True):
                totals = collections.Counter(bases.get(breed, {}))
                totals.update(sums)
                if without:
                    totals.subtract(owns[item.id])
                env = wakfu_criteria.Env(level, names.get(breed), state, totals,
                                         item.id, others)
                for node in wakfu_criteria.failing_atoms(tree, env):
                    key = (_rule_of(node), _show(node))
                    if key in seen:
                        continue
                    seen.add(key)
                    found.append((key[0], '%s in %s fails %s' % (
                        item.name, position, key[1])))
    return found
