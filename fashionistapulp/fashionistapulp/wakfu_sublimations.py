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

"""Wakfu sublimations, gear states and class passives: the one place their rules live.

The numbers come from the generated block wakfu_special_items (client tables 66, 67, 68
and 29, items.json type 812 and the client code); nothing here types one of them.
"""

import collections
import math
import re

from .wakfu_db import effect_value, level_value
from .wakfu_runes import WHITE

NONE, OPTIMISTIC = 'none', 'optimistic'
MODES = (NONE, OPTIMISTIC)
SOLVE = 'solve'
PASSIVE_MODES = (SOLVE, NONE)

KIND_NORMAL, KIND_RELIC, KIND_EPIC = 'normal', 'relic', 'epic'
SPECIAL_KINDS = (KIND_RELIC, KIND_EPIC)

# What a chosen source is: a sublimation item, a worn piece with state lines, a passive
SUBLIMATION, GEAR, PASSIVE = 'sublimation', 'gear', 'passive'

# The families a player may opt into
OPT_IN_FAMILIES = 'EFGH'

# summed: the levels added up, cap: the state's own (None for none), counted: the level the
# fight reads, condition: whether its lines are free of conditions or one of the guarded
# ones holds, lines: {key: value} it gives
StateReport = collections.namedtuple(
    'StateReport', 'summed cap counted family condition lines')

_STAT_COMPARE = re.compile(
    r'GetCharac\("(\w+)"[^)]*\)\s*(>=|<=|>|<|==|!=)\s*'
    r'(?:GetCharac\("(\w+)"[^)]*\)|(-?\d+))')

_OPERATORS = {
    '>=': lambda left, right: left >= right,
    '<=': lambda left, right: left <= right,
    '>': lambda left, right: left > right,
    '<': lambda left, right: left < right,
    '==': lambda left, right: left == right,
    '!=': lambda left, right: left != right,
}


def load():
    """The generated block module, or None where it has not been written."""
    try:
        from . import wakfu_special_items
    except ImportError:
        return None
    return wakfu_special_items


def read_options(structure, sublimations, passives):
    """(mode, passive mode) of the sublimations and passives arguments; ValueError on a bad one.

    None means NONE for both. The structure is not read: the modes name no count.
    """
    if sublimations is None:
        mode = NONE
    elif sublimations in MODES:
        mode = sublimations
    else:
        raise ValueError('sublimations are %s or None, got %r'
                         % (', '.join(map(repr, MODES)), sublimations))
    if passives is None:
        passive_mode = NONE
    elif passives in PASSIVE_MODES:
        passive_mode = passives
    else:
        raise ValueError('passives are %s or None, got %r'
                         % (', '.join(map(repr, PASSIVE_MODES)), passives))
    return mode, passive_mode


def read_opt_in(opt_in):
    """{family: rate} of an opt-in argument, whole families E to H and rates in [0, 1]."""
    out = {}
    for family, rate in dict(opt_in or {}).items():
        if family not in OPT_IN_FAMILIES or len(family) != 1:
            raise ValueError('opt-in families are %s, got %r' % (OPT_IN_FAMILIES, family))
        if (isinstance(rate, bool) or not isinstance(rate, (int, float))
                or not 0 <= rate <= 1):
            raise ValueError('an opt-in rate is a number from 0 to 1, got %r' % (rate,))
        out[family] = rate
    return out


def value_at(p0, p1, e):
    """The value of a line p0 + p1 * e, the way the client rounds it."""
    return level_value(p0, p1, e)


def counted_level(levels, cap):
    """The level a state counts at: the levels added up, held under its cap when it has one."""
    total = sum(levels)
    return total if cap is None else min(total, cap)


def pattern_fits(pattern, colours):
    """True when the sockets, in order, hold the pattern (the client's fpM.a).

    Some start i has a socket i + j for every j, none wrapping past the last one, whose
    colour is WHITE or equals the pattern's, a pattern colour of 0 matching any.
    """
    pattern = tuple(pattern or ())
    colours = tuple(colours or ())
    for start in range(len(colours) - len(pattern) + 1):
        if all(wanted == 0 or colours[start + at] in (wanted, WHITE)
               for at, wanted in enumerate(pattern)):
            return True
    return False


def colour_needs(pattern):
    """Counter {colour: sockets} the pattern asks for, a joker (0) asking for none."""
    return collections.Counter(colour for colour in (pattern or ()) if colour)


def slots_open(level):
    """How many passive slots a character of this level has."""
    block = load()
    return sum(1 for need in block.PASSIVE_SLOT_LEVELS if need <= level) if block else 0


def passive_of_class(entry, class_id, block=None):
    """True when a passive entry is one of the breed's own or one every class can take."""
    block = block or load()
    generic = getattr(block, 'GENERIC_BREED', None)
    return entry['breed'] == class_id or (generic is not None and entry['breed'] == generic)


def passives_of(class_id, level):
    """[spell id] of the passives a breed has unlocked at this level, in unlock order.

    The breed's own and those every class can take share the same slots."""
    block = load()
    if block is None:
        return []
    found = [(entry['unlock'], ident) for ident, entry in block.PASSIVES.items()
             if passive_of_class(entry, class_id, block) and entry['unlock'] <= level]
    return [ident for _unlock, ident in sorted(found)]


def special_kind(item):
    """KIND_RELIC or KIND_EPIC for a piece that takes that special sublimation, else None.

    The client lets a relic sublimation on a piece of the relic rarity and an epic one on a
    piece of the epic rarity, whatever its flags say.
    """
    block = load()
    rarity = getattr(item, 'rarity', None)
    if block is None or rarity is None:
        return None
    if rarity == block.RARITY_RELIC:
        return KIND_RELIC
    if rarity == block.RARITY_EPIC:
        return KIND_EPIC
    return None


def _one_condition(condition, totals, level, class_id, weapon_types):
    function, key, operator, value = condition
    if function == 'text':
        return _text_holds(key, totals)
    compare = _OPERATORS.get(operator)
    if compare is None:
        return False
    if function in ('GetCharac', 'GetCharacMax', 'GetCharacteristicMax'):
        return compare(totals.get(key, 0), value)
    if function == 'GetLevel':
        return compare(level, value)
    if function == 'IsBreed':
        return compare(class_id, value)
    if function == 'HasWeaponType':
        return (value in weapon_types) == (operator != '!=')
    return False


def _text_holds(text, totals):
    """A condition kept as the client's text: stat compared with stat, joined by `and`.

    Anything else does not hold, so a line is never counted on a test that was not read.
    """
    for part in (part.strip() for part in text.split(' and ')):
        match = _STAT_COMPARE.fullmatch(part)
        if match is None:
            return False
        left, operator, other, number = match.groups()
        right = totals.get(other.lower(), 0) if other else int(number)
        if not _OPERATORS[operator](totals.get(left.lower(), 0), right):
            return False
    return True


def condition_holds(conditions, totals, level, class_id, weapon_types=()):
    """[bool] for each of a state's or passive's conditions, read on `totals`."""
    return [_one_condition(condition, totals, level, class_id, weapon_types)
            for condition in conditions]


# What a condition is to the model: a test on the character alone, a comparison of stat
# totals, or something the model does not read
STATIC, CLAUSES, UNSUPPORTED = 'static', 'clauses', 'unsupported'
_STAT_FUNCTIONS = ('GetCharac', 'GetCharacMax', 'GetCharacteristicMax')
_CHARACTER_FUNCTIONS = ('GetLevel', 'IsBreed')


def text_clauses(text):
    """[(left key, operator, other key or None, number or None)] of a text condition, or None."""
    found = []
    for part in (part.strip() for part in text.split(' and ')):
        match = _STAT_COMPARE.fullmatch(part)
        if match is None:
            return None
        left, operator, other, number = match.groups()
        found.append((left.lower(), operator, other.lower() if other else None,
                      None if other else int(number)))
    return found


def condition_kind(condition):
    """STATIC, CLAUSES or UNSUPPORTED for a condition of a state or a passive."""
    function, key, operator, _value = condition
    if function == 'text':
        return CLAUSES if text_clauses(key) is not None else UNSUPPORTED
    if function in _CHARACTER_FUNCTIONS:
        return STATIC if operator in _OPERATORS else UNSUPPORTED
    if function in _STAT_FUNCTIONS and operator in _OPERATORS and operator != '!=':
        return CLAUSES
    return UNSUPPORTED


def condition_clauses(condition):
    """[({stat key: coefficient}, operator, bound)] that hold together exactly when a
    CLAUSES condition holds; the operator is '>=' or '<=' and the sum is of whole totals."""
    function, key, operator, value = condition
    if function == 'text':
        pairs = [({left: 1, other: -1} if other else {left: 1}, op,
                  0 if other else number)
                 for left, op, other, number in text_clauses(key)]
    else:
        pairs = [({key: 1}, operator, value)]
    out = []
    for coefficients, op, bound in pairs:
        if op == '>':
            out.append((coefficients, '>=', bound + 1))
        elif op == '<':
            out.append((coefficients, '<=', bound - 1))
        elif op == '==':
            out.extend([(coefficients, '>=', bound), (coefficients, '<=', bound)])
        else:
            out.append((coefficients, op, bound))
    return out


def _guarded(guards, holds):
    return all(holds[at] for at in guards)


def share_at(p0, p1, e):
    """The share of a source a conversion moves, undoing the float32 storage of its params."""
    return round(float(effect_value((p0, p1), 0, e)), 6)


def _lines_of(entry, at, holds, sheet_totals):
    """Counter {key: value} of the lines and the conversions of an entry read at `at`.

    A conversion moves floor(source total x share) from the sheet total; one that takes
    from its own key never takes more than that total holds, and one with a cap never moves
    more than floor(cap x level). Each child is floored alone.
    """
    out = collections.Counter()
    if at <= 0:
        return out
    for _family, key, p0, p1, guards in entry['lines']:
        if _guarded(guards, holds):
            out[key] += value_at(p0, p1, at)
    for source, target, p0, p1, sign, guards, *cap in entry['conversions']:
        if not _guarded(guards, holds):
            continue
        have = max(sheet_totals.get(source, 0), 0)
        moved = math.floor(have * share_at(p0, p1, at))
        if cap:
            moved = min(moved, math.floor(cap[0] * at))
        if source == target and sign < 0:
            moved = min(moved, have)
        out[target] += sign * moved
    return out


def _report(entry, summed, counted, at, holds, sheet_totals):
    lines = _lines_of(entry, at, holds, sheet_totals)
    guards = [one for _f, _k, _a, _b, one in entry['lines'] if one]
    guards += [one[5] for one in entry['conversions'] if one[5]]
    return StateReport(
        summed, entry.get('cap'), counted, entry['family'],
        not guards or any(_guarded(one, holds) for one in guards),
        {key: value for key, value in lines.items() if value})


def sources_of(choices, block=None):
    """({state: [levels]}, [passive id]) of the chosen sublimations, gear and passives."""
    block = block or load()
    levels = collections.defaultdict(list)
    spells = []
    for kind, ident in choices:
        if kind == SUBLIMATION and ident in block.SUBLIMATIONS:
            state, level, _kind, _pattern = block.SUBLIMATIONS[ident]
            levels[state].append(level)
        elif kind == GEAR:
            for state, level in block.GEAR_STATES.get(ident, ()):
                levels[state].append(level)
        elif kind == PASSIVE and ident in block.PASSIVES:
            spells.append(ident)
    return levels, spells


def fight_lines(choices, sheet_totals, level, class_id, opt_in=None, weapon_types=()):
    """({key: value}, {state: StateReport}) the chosen sources give at the start of a fight.

    choices: (kind, id) pairs, kind SUBLIMATION (an item id), GEAR (a worn piece's id) or
    PASSIVE (a spell id). The conditions and the conversions read `sheet_totals`, the sheet
    totals of the set; level is the character's. A state is keyed by its id and a passive by
    (PASSIVE, spell id), its lines read at the character's level. The block gives no value
    for the lines of the families E to H, so an opt-in rate (read_opt_in) changes nothing yet.
    """
    block = load()
    read_opt_in(opt_in)
    total = collections.Counter()
    reports = {}
    if block is None:
        return {}, reports
    levels, spells = sources_of(choices, block)
    for state in sorted(levels):
        entry = block.STATES[state]
        counted = counted_level(levels[state], entry['cap'])
        holds = condition_holds(entry['conditions'], sheet_totals, level, class_id,
                                weapon_types)
        reports[state] = _report(entry, sum(levels[state]), counted, counted, holds,
                                 sheet_totals)
        total.update(reports[state].lines)
    for spell in sorted(spells):
        entry = block.PASSIVES[spell]
        holds = condition_holds(entry['conditions'], sheet_totals, level, class_id,
                                weapon_types)
        reports[(PASSIVE, spell)] = _report(entry, 1, 1, level, holds, sheet_totals)
        total.update(reports[(PASSIVE, spell)].lines)
    return {key: value for key, value in total.items() if value}, reports


def most_added(key, level=None):
    """The most a set can add to `key` through the fixed lines of its states and passives.

    The sum over the states of the most each adds (a state at the level its cap allows, or
    at the highest level it is given) and, with a `level`, of the best passives its open
    slots hold. Conversions are left out, as their size depends on the sheet totals.
    """
    block = load()
    if block is None:
        return 0
    top = {}
    for state, at, _kind, _pattern in block.SUBLIMATIONS.values():
        top[state] = max(top.get(state, 0), at)
    for pairs in block.GEAR_STATES.values():
        for state, at in pairs:
            top[state] = max(top.get(state, 0), at)
    total = 0
    for state, at in top.items():
        entry = block.STATES[state]
        counted = entry['cap'] or at
        total += max(0, sum(value_at(p0, p1, counted)
                            for _family, line, p0, p1, _guards in entry['lines']
                            if line == key))
    if level is not None:
        passives = sorted((sum(value_at(p0, p1, level)
                               for _family, line, p0, p1, _guards in entry['lines']
                               if line == key) for entry in block.PASSIVES.values()),
                          reverse=True)
        total += sum(value for value in passives[:slots_open(level)] if value > 0)
    return total
