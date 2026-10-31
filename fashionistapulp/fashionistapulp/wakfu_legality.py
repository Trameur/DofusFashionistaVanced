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
from . import (wakfu_aptitudes, wakfu_companions, wakfu_criteria, wakfu_runes,
               wakfu_sublimations)
from .wakfu_slots import (BLOCKED_BY_TWO_HANDED, EXCLUSIVE_PROPERTIES,
                          SOLVED_SLOTS, TWO_HANDED_FLAG)
from .wakfu_stats import OUT_OF_COMBAT_CAPS, SPREAD_FAMILIES

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
RUNE_UNKNOWN = 'unknown rune'
RUNE_SOCKET = 'rune socket'
RUNE_COLOUR = 'rune colour'
RUNE_TIER = 'rune tier'
SUBLIMATION_UNKNOWN = 'unknown sublimation'
SUBLIMATION_SOCKETS = 'sublimation without sockets'
SUBLIMATION_PATTERN = 'sublimation pattern'
SUBLIMATION_PER_ITEM = 'two sublimations on one item'
SUBLIMATION_RARITY = 'special sublimation rarity'
RELIC_SUBLIMATION = 'one relic sublimation'
EPIC_SUBLIMATION = 'one epic sublimation'
STACK = 'stack over its cap'
STATE_CONDITION = 'state condition'
PASSIVE_UNKNOWN = 'unknown passive'
PASSIVE_CLASS = 'passive of another class'
PASSIVE_LEVEL = 'passive level'
PASSIVE_SLOTS = 'passive slots'
PASSIVE_TWICE = 'passive twice'
ORDER = 'state order'

WEAPON_POSITIONS = ('FIRST_WEAPON', 'SECOND_WEAPON')

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


def rune_violations(structure, held, runes, rune_tier=None):
    """[(rule, text)] of the runes of a set; held: {position: [worn items]}.

    Every field is read from the catalogue: the rune table, the piece's socket count and
    its level.
    """
    found = []
    for position, sockets in sorted((runes or {}).items()):
        filled = wakfu_runes.entries(sockets)
        if not filled:
            continue
        items = held.get(position)
        if not items:
            found.append((RUNE_SOCKET, '%d runes sit in %s, where nothing is worn'
                          % (len(filled), position)))
            continue
        piece = items[0]
        if len(filled) > wakfu_runes.sockets_of(piece):
            found.append((RUNE_SOCKET, '%s in %s holds %d runes, it has %d sockets at most'
                          % (piece.name, position, len(filled),
                             wakfu_runes.sockets_of(piece))))
        for colour, ident, tier in filled:
            known_colour = colour in wakfu_runes.SOCKET_COLOURS
            if not known_colour:
                found.append((RUNE_SOCKET, 'a socket of %s in %s has the colour %r'
                              % (piece.name, position, colour)))
            rune = structure.shards.get(ident)
            if rune is None:
                found.append((RUNE_UNKNOWN, 'rune %r is not in the rune table' % (ident,)))
                continue
            if known_colour and colour != rune.colour and colour != wakfu_runes.WHITE:
                found.append((RUNE_COLOUR, 'rune %d (colour %d) sits in a socket of colour '
                                           '%r of %s in %s'
                              % (ident, rune.colour, colour, piece.name, position)))
            if not isinstance(tier, int) or isinstance(tier, bool) \
                    or not 1 <= tier <= len(rune.costs):
                found.append((RUNE_TIER, 'rune %d has no tier %r' % (ident, tier)))
                continue
            allowed = wakfu_runes.allowed_tier(rune, piece.level)
            if tier > allowed:
                found.append((RUNE_TIER, 'rune %d is tier %d in %s of level %d, which '
                                         'allows tier %d' % (ident, tier, piece.name,
                                                             piece.level, allowed)))
            elif rune_tier and tier > rune_tier:
                found.append((RUNE_TIER, 'rune %d is tier %d, over the tier cap of %d'
                              % (ident, tier, rune_tier)))
    return found


def _by_position(given):
    """{position: [ids]} of a mapping whose values may be one id or several."""
    out = collections.defaultdict(list)
    for position, held in (given.items() if hasattr(given, 'items') else (given or ())):
        if isinstance(held, (list, tuple, set, frozenset)):
            out[position].extend(held)
        else:
            out[position].append(held)
    return out


def _rendered_colours(sockets):
    """The colours of the sockets of a piece, in order, filled or not."""
    return [socket.colour if isinstance(socket, wakfu_runes.Socket) else tuple(socket)[0]
            for socket in sockets or ()]


def _placed(block, ident, normal, found):
    """The block row of a chosen sublimation, or None after reporting why it cannot be."""
    row = block.SUBLIMATIONS.get(ident) if block else None
    if row is None:
        found.append((SUBLIMATION_UNKNOWN,
                      'sublimation %r is not in the client tables' % (ident,)))
        return None
    if (row[2] == wakfu_sublimations.KIND_NORMAL) != normal:
        found.append((SUBLIMATION_UNKNOWN, 'sublimation %r is a %s one, given as a %s one'
                      % (ident, row[2], 'normal' if normal else 'special')))
        return None
    return row


def sublimation_violations(held, sublimations, specials, runes):
    """[(rule, text)] of the sublimations of a set; held: {position: [worn items]}.

    sublimations and specials: {position: sublimation item id, or several}. A normal
    sublimation needs sockets in the pattern's colours, one per piece; a relic or epic one
    needs a piece of the matching rarity, one per piece and one of each kind in the set.
    """
    found = []
    block = wakfu_sublimations.load()
    normals = _by_position(sublimations)
    special = _by_position(specials)
    kinds = collections.Counter()
    for position in sorted(set(normals) | set(special)):
        items = held.get(position)
        piece = items[0] if items else None
        for normal, ids in ((True, normals.get(position, [])),
                            (False, special.get(position, []))):
            if len(ids) > 1:
                found.append((SUBLIMATION_PER_ITEM, '%d %s sublimations sit in %s, one at '
                              'most' % (len(ids), 'normal' if normal else 'special',
                                        position)))
            for ident in ids:
                row = _placed(block, ident, normal, found)
                if row is None:
                    continue
                if piece is None:
                    found.append((SUBLIMATION_SOCKETS, 'sublimation %d sits in %s, where '
                                  'nothing is worn' % (ident, position)))
                    continue
                _state, _level, kind, pattern = row
                if normal:
                    found.extend(_pattern_violations(
                        ident, pattern, piece, position, (runes or {}).get(position)))
                    continue
                kinds[kind] += 1
                if wakfu_sublimations.special_kind(piece) != kind:
                    found.append((SUBLIMATION_RARITY, '%s sublimation %d sits on %s in %s, '
                                  'of rarity %r' % (kind, ident, piece.name, position,
                                                    getattr(piece, 'rarity', None))))
    if kinds[wakfu_sublimations.KIND_RELIC] > 1:
        found.append((RELIC_SUBLIMATION, '%d relic sublimations are worn'
                      % kinds[wakfu_sublimations.KIND_RELIC]))
    if kinds[wakfu_sublimations.KIND_EPIC] > 1:
        found.append((EPIC_SUBLIMATION, '%d epic sublimations are worn'
                      % kinds[wakfu_sublimations.KIND_EPIC]))
    return found


def _pattern_violations(ident, pattern, piece, position, sockets):
    sockets_held = wakfu_runes.sockets_of(piece)
    if sockets_held < len(pattern):
        return [(SUBLIMATION_SOCKETS, 'sublimation %d needs %d sockets, %s in %s has %d '
                 'at most' % (ident, len(pattern), piece.name, position, sockets_held))]
    if not wakfu_sublimations.pattern_fits(pattern, _rendered_colours(sockets)):
        return [(SUBLIMATION_PATTERN, 'sublimation %d (pattern %s) does not fit the sockets '
                 'of %s in %s' % (ident, '-'.join(map(str, pattern)), piece.name, position))]
    return []


def passive_violations(level, class_id, passives):
    """[(rule, text)] of the passives chosen: known, of the class, unlocked, in the slots."""
    found = []
    block = wakfu_sublimations.load()
    chosen = collections.Counter(passives or ())
    for ident, times in sorted(chosen.items()):
        if times > 1:
            found.append((PASSIVE_TWICE, 'passive %r is chosen %d times' % (ident, times)))
        entry = block.PASSIVES.get(ident) if block else None
        if entry is None:
            found.append((PASSIVE_UNKNOWN,
                          'passive %r is not in the client tables' % (ident,)))
        elif class_id is None or not wakfu_sublimations.passive_of_class(
                entry, class_id, block):
            found.append((PASSIVE_CLASS, 'passive %d (%s) belongs to breed %d, not to %s'
                          % (ident, entry['name'], entry['breed'],
                             'a build with no class' if class_id is None
                             else 'breed %d' % class_id)))
        elif entry['unlock'] > level:
            found.append((PASSIVE_LEVEL, 'passive %d (%s) unlocks at level %d, above the '
                          'build level %d' % (ident, entry['name'], entry['unlock'], level)))
    if len(chosen) > wakfu_sublimations.slots_open(level):
        found.append((PASSIVE_SLOTS, '%d passives are chosen, level %d opens %d slots'
                      % (len(chosen), level, wakfu_sublimations.slots_open(level))))
    return found


def _state_entry(block, key):
    if isinstance(key, tuple):
        return block.PASSIVES.get(key[1])
    return block.STATES.get(key)


def state_violations(reported, computed):
    """[(rule, text)] where a reported state differs from the one the checker computed.

    reported, computed: {state: StateReport}. A reported level must equal the cap-held sum
    of the levels chosen, a state with guards must give the lines its conditions allow
    on the checker's sheet totals, in both directions, and a state the checker computes
    must be reported.
    """
    found = []
    block = wakfu_sublimations.load()
    for key, report in sorted((reported or {}).items(), key=lambda one: str(one[0])):
        mine = computed.get(key)
        entry = _state_entry(block, key) if block else None
        cap = entry.get('cap') if entry else report.cap
        held = wakfu_sublimations.counted_level([report.summed], cap)
        if mine is None or report.counted != held or report.counted != mine.counted:
            found.append((STACK, 'state %s is counted at level %r, its sources give %r '
                          'under the cap %r' % (key, report.counted,
                                                mine.counted if mine else 0, cap)))
        elif dict(report.lines) != dict(mine.lines) and entry is not None and any(
                guards for *_head, guards in list(entry['lines']) + list(entry.get('shares', ()))
                + [row[:6] for row in entry['conversions']]):
            found.append((STATE_CONDITION, 'state %s gives %r, its conditions give %r'
                          % (key, dict(report.lines), dict(mine.lines))))
    if reported:
        for key in sorted(set(computed) - set(reported), key=str):
            found.append((STACK, 'state %s is chosen and counted at level %r, but not '
                          'reported' % (key, computed[key].counted)))
    return found


def _gear_totals(structure, wearing, read, spread=None):
    """Counter {stat key: total} of the lines of the worn pieces.

    spread: {stat key: total} the lines spread over elements landed on, as the solver chose
    them; each such line then counts on those elements and not on its generic stat.
    """
    totals = collections.Counter()
    for item in wearing:
        for stat_id, value in wakfu_companions.lines_at(item, read.get(item.id)):
            stat = structure.get_stat_by_id(stat_id)
            if stat is not None:
                totals[stat.key] += value
        if spread is not None:
            for stat_id, value, _elements in getattr(item, 'element_spread', None) or ():
                stat = structure.get_stat_by_id(stat_id)
                if stat is not None and stat.key in SPREAD_FAMILIES:
                    totals[stat.key] -= value
    if spread is not None:
        totals.update(spread)
    return totals


def _sheet_lines(structure, level, wearing, held, aptitudes, battleground, runes):
    """(Counter of the aptitude, set tier and rune lines, tier reader, lines by position)."""
    lines = _aptitude_lines(structure, level, aptitudes, battleground)
    tiers = _tier_reader(structure, level, battleground)
    lines.update(tiers({item.id for item in wearing}) if tiers else {})
    rune_lines = wakfu_runes.position_lines(
        structure, {position: items[0] for position, items in held.items()}, runes)
    for one in rune_lines.values():
        lines.update(one)
    return lines, tiers, rune_lines


def _fights(structure, level, class_id, pairs, extra, sublimations, specials, passives,
            opt_in):
    """{breed: (Counter of the fight lines, {state: StateReport})} of the chosen sources.

    extra: Counter of the sheet totals the base values are added to. With no class every
    breed is read. Gear states count whenever a sublimation or passive argument is given.
    """
    block = wakfu_sublimations.load()
    if block is None:
        return {}
    choices = [(wakfu_sublimations.SUBLIMATION, ident)
               for given in (sublimations, specials)
               for ids in _by_position(given).values() for ident in ids]
    choices += [(wakfu_sublimations.GEAR, item.id) for _position, item in pairs
                if item.id in block.GEAR_STATES]
    choices += [(wakfu_sublimations.PASSIVE, ident) for ident in sorted(set(passives or ()))]
    bases = structure.get_breed_base_values()
    weapon_types = {item.type for position, item in pairs if position in WEAPON_POSITIONS}
    out = {}
    for breed in ([class_id] if class_id is not None else sorted(bases)):
        totals = collections.Counter(bases.get(breed, {}))
        totals.update(extra)
        lines, reports = wakfu_sublimations.fight_lines(
            choices, totals, level, breed, opt_in, weapon_types)
        out[breed] = (collections.Counter(lines), reports)
    return out


def warnings(structure, level, worn, class_id=None, aptitudes=None, battleground=False,
             levels=None, runes=None, sublimations=None, specials=None, passives=None,
             opt_in=None, spread=None):
    """[(ORDER, text)] where another counted line on a key could flip a state condition.

    The client runs a condition when the start-of-combat trigger fires, and which other
    start-of-combat effects ran first is not known; the checker reads the sheet totals. A
    warning is never a violation. The arguments are those of violations.
    """
    if runes is None:
        runes = getattr(worn, 'runes', None)
    if sublimations is None:
        sublimations = getattr(worn, 'sublimation_ids', None)
    if specials is None:
        specials = getattr(worn, 'special_ids', None)
    if passives is None:
        passives = getattr(worn, 'passives', None)
    if opt_in is None:
        opt_in = getattr(worn, 'opt_in', None)
    if spread is None:
        spread = getattr(worn, 'spread_landing', None)
    block = wakfu_sublimations.load()
    if block is None or (sublimations is None and specials is None and passives is None):
        return []
    pairs = []
    for position, given in _pairs(worn):
        item = structure.get_item_by_id(given.id)
        if item is not None:
            pairs.append((position, item))
    held = collections.defaultdict(list)
    for position, item in pairs:
        held[position].append(item)
    wearing = [item for _position, item in pairs]
    read, _bad = companion_levels(pairs, levels)
    lines, _tiers, _rune_lines = _sheet_lines(
        structure, level, wearing, held, aptitudes, battleground, runes)
    extra = _gear_totals(structure, wearing, read, spread)
    extra.update(lines)
    fights = _fights(structure, level, class_id, pairs, extra, sublimations, specials,
                     passives, opt_in)
    weapon_types = {item.type for position, item in pairs if position in WEAPON_POSITIONS}
    bases = structure.get_breed_base_values()
    found = []
    for breed, (fight, reports) in sorted(fights.items()):
        totals = collections.Counter(bases.get(breed, {}))
        totals.update(extra)
        for key, report in sorted(reports.items(), key=lambda one: str(one[0])):
            entry = _state_entry(block, key)
            others = collections.Counter(fight)
            others.subtract(report.lines)
            others = {name: value for name, value in others.items() if value}
            if not entry or not entry['conditions'] or not others:
                continue
            after = collections.Counter(totals)
            after.update(others)
            before = wakfu_sublimations.condition_holds(
                entry['conditions'], totals, level, breed, weapon_types)
            then = wakfu_sublimations.condition_holds(
                entry['conditions'], after, level, breed, weapon_types)
            for index, (now, later) in enumerate(zip(before, then)):
                text = 'state %s: condition %d reads %s on the sheet, and another counted ' \
                       'line on %s would make it %s' % (
                           key, index, 'true' if now else 'false', ', '.join(sorted(others)),
                           'true' if later else 'false')
                if now != later and (ORDER, text) not in found:
                    found.append((ORDER, text))
    return found


def violations(structure, level, worn, forbidden=(), locked=(), minimums=None,
               class_id=None, state=None, aptitudes=None, battleground=False,
               levels=None, runes=None, rune_tier=None, sublimations=None,
               specials=None, passives=None, opt_in=None, states=None, spread=None):
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
    gives it; a leveled item missing from it is read at its cap. runes:
    {position: iterable of (colour, rune id, tier)}, WakfuSet.runes when it is None;
    their lines count in every total checked. rune_tier: the highest tier a socket
    may hold. sublimations, specials: {position: sublimation item id} of the normal and of
    the relic or epic sublimations, passives: [spell id], opt_in: {family: rate}, states:
    {state: StateReport} as the solver reports it; each is read from the WakfuSet when it
    is None. With none of the first three the set has no sublimation part, and the fight
    totals are the sheet totals. The caps read the sheet totals, the minimums the fight
    totals, the item conditions both. spread: {stat key: total} the lines spread over
    elements landed on, WakfuSet.spread_landing when it is None; the states then read them
    on the elements, as the solver does, and None reads them on their generic stat.
    """
    rules = _Rules(structure)
    found = []
    pairs = []
    if runes is None:
        runes = getattr(worn, 'runes', None)
    if sublimations is None:
        sublimations = getattr(worn, 'sublimation_ids', None)
    if specials is None:
        specials = getattr(worn, 'special_ids', None)
    if passives is None:
        passives = getattr(worn, 'passives', None)
    if opt_in is None:
        opt_in = getattr(worn, 'opt_in', None)
    if states is None:
        states = getattr(worn, 'states', None)
    if spread is None:
        spread = getattr(worn, 'spread_landing', None)
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
    found.extend(rune_violations(structure, held, runes, rune_tier))
    if sublimations is not None or specials is not None:
        found.extend(sublimation_violations(held, sublimations, specials, runes))
    if passives is not None:
        found.extend(passive_violations(level, class_id, passives))
    lines, tiers, rune_lines = _sheet_lines(
        structure, level, wearing, held, aptitudes, battleground, runes)

    fights = {}
    if sublimations is not None or specials is not None or passives is not None:
        extra = _gear_totals(structure, wearing, read, spread)
        extra.update(lines)
        fights = _fights(structure, level, class_id, pairs, extra, sublimations, specials,
                         passives, opt_in)
    if states:
        verdicts = [state_violations(states, reports) for _fight, reports in fights.values()]
        if not verdicts:
            verdicts = [state_violations(states, {})]
        if all(verdicts):
            found.extend(verdicts[0])

    base = wakfu_criteria.base_values(structure, class_id)
    for name, cap in OUT_OF_COMBAT_CAPS.items():
        total = (base.get(name.lower(), (0, 0))[1]
                 + rules.stat_total(wearing, name.lower(), read) + lines[name.lower()])
        if total > cap:
            found.append((CAP, '%s is %d, over the cap of %d' % (name, total, cap)))

    for key, lowest in sorted((minimums or {}).items()):
        total = (base.get(key, (0, 0))[0] + rules.stat_total(wearing, key, read)
                 + lines[key])
        if fights:
            bases = structure.get_breed_base_values()
            total = min(bases.get(breed, {}).get(key, 0) + rules.stat_total(wearing, key, read)
                        + lines[key] + fight[key] for breed, (fight, _r) in fights.items())
        if total < lowest:
            found.append((MINIMUM, '%s is %d, under the minimum of %d'
                          % (key, total, lowest)))

    found.extend(_conditions(
        structure, pairs, level, class_id, state or wakfu_criteria.start_state(),
        _aptitude_lines(structure, level, aptitudes, battleground), tiers, read,
        rune_lines))
    if any(fight for fight, _reports in fights.values()):
        seen = set(found)
        found.extend(one for one in _conditions(
            structure, pairs, level, class_id, state or wakfu_criteria.start_state(),
            _aptitude_lines(structure, level, aptitudes, battleground), tiers, read,
            rune_lines, {breed: fight for breed, (fight, _r) in fights.items()})
            if one not in seen)
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
                levels=None, runes=None, fights=None):
    """Each worn piece's own EQUIP text, judged with and without the piece.

    lines: Counter of the aptitude lines. tiers: item ids worn -> Counter of
    the set bonus lines, so the reading without a piece drops its tiers too.
    levels: {item id: level} each piece is read at, as companion_levels gives it.
    runes: {position: Counter of the lines its runes give}, which belong to the piece
    worn there, so the reading without a piece leaves them out too.
    fights: {breed: Counter} of the fight lines, which the second reading adds to the sheet.
    """
    bases = structure.get_breed_base_values()
    names = structure.get_breed_names()
    breeds = [class_id] if class_id is not None else sorted(bases)
    wearing = [item for _position, item in pairs]
    held = {item.id for item in wearing}
    sums = collections.Counter()
    owns = {}
    for index, (position, item) in enumerate(pairs):
        own = collections.Counter()
        for stat_id, value in wakfu_companions.lines_at(item, (levels or {}).get(item.id)):
            stat = structure.get_stat_by_id(stat_id)
            if stat is not None:
                own[stat.key] += value
        if (runes or {}).get(position) and not any(
                place == position for place, _one in pairs[:index]):
            own.update(runes[position])
        owns[index] = own
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
                totals.update((fights or {}).get(breed, {}))
                if without:
                    totals.subtract(owns[index])
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
