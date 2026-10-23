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
from . import wakfu_aptitudes, wakfu_companions, wakfu_criteria
from .wakfu_slots import (BLOCKED_BY_TWO_HANDED, EXCLUSIVE_PROPERTIES,
                          SOLVED_SLOTS, TWO_HANDED_FLAG)
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
APTITUDE_UNKNOWN = 'unknown aptitude'
APTITUDE_CAP = 'aptitude cap'
APTITUDE_BUDGET = 'aptitude budget'
COMPANION_LEVEL = 'companion level'

EXCLUSIVE_FLAGS = tuple(EXCLUSIVE_PROPERTIES.values())


class _Rules:
    def __init__(self, structure):
        self.structure = structure
        self.positions = collections.defaultdict(set)
        for type_id, position in structure.get_type_positions():
            self.positions[type_id].add(position)

    def stat_total(self, items, key, read=None):
        stat = self.structure.get_stat_by_key(key)
        if stat is None:
            return 0
        read = read or {}
        return sum(value for item in items
                   for stat_id, value in wakfu_companions.lines_at(item, read.get(item.id))
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


def aptitude_violations(structure, level, aptitudes):
    """[(rule, text)] of a {ability id: points} that breaks a cap or a budget.

    Read from the raw rows of the abilities and their categories: an ability's
    cap is its own, or its category's budget when it has none, and a
    category's budget is the number of its unlock levels the level reached.
    """
    found = []
    spent = collections.Counter()
    for ident, points in sorted((aptitudes or {}).items(), key=lambda one: str(one[0])):
        row = structure.aptitude_abilities.get(ident)
        if row is None:
            found.append((APTITUDE_UNKNOWN,
                          'aptitude %r is not in the client tables' % (ident,)))
            continue
        if not isinstance(points, int) or isinstance(points, bool) or points < 0:
            found.append((APTITUDE_CAP, 'aptitude %d has %r points, not a whole '
                                        'number from 0' % (ident, points)))
            continue
        category, own_cap = row
        budget = _budget(structure, category, level)
        cap = own_cap or budget
        if points > cap:
            found.append((APTITUDE_CAP, 'aptitude %d has %d points, over its cap '
                                        'of %d' % (ident, points, cap)))
        spent[category] += points
    for category, total in sorted(spent.items()):
        budget = _budget(structure, category, level)
        if total > budget:
            found.append((APTITUDE_BUDGET, 'category %d holds %d points, over its '
                                           'budget of %d at level %d'
                          % (category, total, budget, level)))
    return found


def _budget(structure, category, level):
    return sum(1 for unlock in structure.aptitude_categories.get(category, ())
               if unlock <= level)


def _aptitude_lines(structure, level, aptitudes, battleground):
    """Counter of the stat lines the aptitude points give."""
    lines = collections.Counter()
    if not aptitudes:
        return lines
    table = wakfu_aptitudes.table(structure, level, battleground)
    for ident, points in aptitudes.items():
        if (ident in table.abilities and isinstance(points, int)
                and not isinstance(points, bool) and points > 0):
            for key, per_point in table.abilities[ident][2]:
                lines[key] += per_point * points
    return lines


def _tier_reader(structure, level, battleground):
    """A function: item ids worn -> Counter of the set bonus lines they reach."""
    if not battleground:
        return None
    table = wakfu_aptitudes.table(structure, level, True)

    def read(ids):
        lines = collections.Counter()
        for tier in wakfu_aptitudes.tiers_reached(table, ids):
            for key, number in table.tiers[tier]:
                lines[key] += number
        return lines

    return read


def companion_levels(pairs, levels):
    """({item id: level to read it at}, [(rule, text)]) for the worn items.

    An item that does not level is read at None. A level that cannot be worn is
    reported and read at the item's cap.
    """
    given = levels or {}
    read = {}
    found = []
    for _position, item in pairs:
        if item.id in read:
            continue
        cap = getattr(item, 'level_cap', None)
        if cap is None:
            read[item.id] = None
            if item.id in given:
                found.append((COMPANION_LEVEL, '%s has no level, yet level %r is given'
                                               % (item.name, given[item.id])))
            continue
        level = given.get(item.id, cap)
        if not wakfu_companions.is_level(level) or not 0 <= level <= cap:
            found.append((COMPANION_LEVEL, '%s is at level %r, outside 0 to its cap of '
                                           '%d' % (item.name, level, cap)))
            level = cap
        read[item.id] = level
    return read, found


def violations(structure, level, worn, forbidden=(), locked=(), minimums=None,
               class_id=None, state=None, aptitudes=None, battleground=False,
               levels=None):
    """[(rule, text)] of every rule a set breaks; an empty list is a legal set.

    worn: {position: item}, or an iterable of (position, item); a position
    may hold a list, which is how a set with two items in one slot is written.
    locked: (item id, position or None) pairs. minimums: {stat key: lowest
    total, base values included}. class_id: the breed, none for a build with
    no class. state: the PlayerState the player-state conditions are read
    against, the game's start values by default. aptitudes: {ability id:
    points} the set is worn with, None for none; their lines and those of the
    set bonus tiers of a battleground count in every total checked. levels:
    {item id: level} the worn pets and mounts are read at, as WakfuSet.levels
    gives it; a leveled item missing from it is read at its cap.
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
        if position not in SOLVED_SLOTS:
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
    read, bad_levels = companion_levels(pairs, levels)
    found.extend(bad_levels)
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

    found.extend(aptitude_violations(structure, level, aptitudes))
    lines = _aptitude_lines(structure, level, aptitudes, battleground)
    tiers = _tier_reader(structure, level, battleground)
    lines.update(tiers({item.id for item in wearing}) if tiers else {})

    base = wakfu_criteria.base_values(structure, class_id)
    for name, cap in OUT_OF_COMBAT_CAPS.items():
        total = (base.get(name.lower(), (0, 0))[1]
                 + rules.stat_total(wearing, name.lower(), read) + lines[name.lower()])
        if total > cap:
            found.append((CAP, '%s is %d, over the cap of %d' % (name, total, cap)))

    for key, lowest in sorted((minimums or {}).items()):
        total = (base.get(key, (0, 0))[0] + rules.stat_total(wearing, key, read)
                 + lines[key])
        if total < lowest:
            found.append((MINIMUM, '%s is %d, under the minimum of %d'
                          % (key, total, lowest)))

    found.extend(_conditions(
        structure, pairs, level, class_id, state or wakfu_criteria.start_state(),
        _aptitude_lines(structure, level, aptitudes, battleground), tiers, read))
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


def _conditions(structure, pairs, level, class_id, state, lines=None, tiers=None,
                levels=None):
    """Each worn piece's own EQUIP text, judged with and without the piece.

    lines: Counter of the aptitude lines. tiers: item ids worn -> Counter of
    the set bonus lines, so the reading without a piece drops its tiers too.
    levels: {item id: level} each piece is read at, as companion_levels gives it.
    """
    bases = structure.get_breed_base_values()
    names = structure.get_breed_names()
    breeds = [class_id] if class_id is not None else sorted(bases)
    wearing = [item for _position, item in pairs]
    held = {item.id for item in wearing}
    sums = collections.Counter()
    owns = {}
    for item in wearing:
        own = collections.Counter()
        for stat_id, value in wakfu_companions.lines_at(item, (levels or {}).get(item.id)):
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
                totals.update(lines or {})
                if without:
                    totals.subtract(owns[item.id])
                    totals.update(tiers(others) if tiers else {})
                else:
                    totals.update(tiers(held) if tiers else {})
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
