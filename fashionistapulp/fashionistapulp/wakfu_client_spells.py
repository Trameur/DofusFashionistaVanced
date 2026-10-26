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

"""The Wakfu classes' spells as the client holds them, with a check against the encyclopedia.

    book = ClientSpellBook()
    spell = book.spell(4775)
    for row in spell.damage_rows():
        row.value(245), spell.critical_of(row).value(245)

A row is one effect found by walking the spell's effect tree (client_spell_effects, then
effect_groups, groups inside groups). It carries the branch it belongs to (NORMAL or
CRITICAL), every criterion on the way down, its area and the signature that pairs it with
the other branch. Its value at a displayed level L is read at L - 1.
"""

import collections
import json
import re
import sqlite3

from . import wakfu_db
from .wakfu_value_rules import RULES

NORMAL = 'NORMAL'
CRITICAL = 'CRITICAL'

LEVELS = range(1, 246)

#: The damage actions and their element. 917 is the element the caster picks, 1083 is light
DAMAGE_ACTIONS = {1: 'physical', 2: 'fire', 3: 'earth', 4: 'water', 5: 'air',
                  917: 'variable', 1083: 'light'}
#: The heal actions. 24 steals life; the others name the element that scales them
HEAL_ACTIONS = {24: 'steal', 25: 'physical', 251: 'air', 253: 'earth', 258: 'water',
                259: 'fire', 1084: 'light'}
FAMILIES = {
    'damage': tuple(DAMAGE_ACTIONS),
    'heal': tuple(HEAL_ACTIONS),
    'armor': (1013, 1010),
    'push': (300, 301),
    'teleport': (302, 422),
    'removal': (55, 56, 48, 57, 161, 194, 192),
}
FAMILY_OF = {action: family for family, actions in FAMILIES.items() for action in actions}
VARIABLE = 'variable'
#: The harvest's element names for a client action that does not carry its own
HARVEST_ELEMENTS = frozenset(('fire', 'water', 'earth', 'air'))

# Harvest kinds and the family each one is checked against
KINDS = {'damage': 'damage', 'healing': 'heal'}

AGREE = 'agree'
ELEMENT_DIFFERS = 'element differs'
PARTIAL = 'partial'
MISSING = 'missing'
#: Rows whose spell tree holds no row of the family at all
NO_ROW = 'no row in the client tree'
#: Some harvest rows have no equal curve in the client tree (states, multiplier groups)
VALUES_MISSING = 'values missing in the client tree'


def _clean(criterion):
    return re.sub(r'\s+', ' ', criterion or '').strip()


Row = collections.namedtuple(
    'Row', 'effect action family element branch criteria area_shape area_size params'
           ' signature depth')


class ClientRow(Row):
    __slots__ = ()

    @property
    def is_area(self):
        """More than one cell: a single cell is shape 1 with no size."""
        return not (self.area_shape == 1 and not self.area_size)

    @property
    def conditional(self):
        return bool(self.criteria)

    def value(self, level, index=0):
        """The floored value of parameter pair `index` at the displayed level."""
        if len(self.params) < 2 * index + 2:
            return 0
        return wakfu_db.level_value(self.params[2 * index], self.params[2 * index + 1],
                                    max(0, level - RULES['client_spell_level_offset'].value))

    def curve(self, index=0):
        return tuple(self.value(level, index) for level in LEVELS)


class ClientSpell:
    """One client spell: costs, range, element, unlock level and its effect rows."""

    def __init__(self, spell_id, breed, ap, mp, wp, range_min, range_max, element,
                 unlock_level, max_level, rows):
        self.id = spell_id
        self.breed = breed
        self.ap = ap
        self.mp = mp
        self.wp = wp
        self.range = (range_min, range_max)
        self.element = element
        self.unlock_level = unlock_level
        self.max_level = max_level
        self.rows = tuple(rows)
        self._paired = {}

    def castable_at(self, level):
        return level >= self.unlock_level

    def rows_of(self, family, branch=NORMAL):
        return tuple(row for row in self.rows if row.family == family and row.branch == branch)

    def damage_rows(self, branch=NORMAL):
        return self.rows_of('damage', branch)

    def critical_of(self, row):
        """The CRITICAL row that pairs with a NORMAL row, or None.

        The pair is the row at the same place in the tree: the same actions, criteria
        and index among siblings. Failing that, the CRITICAL row with the same action
        and criteria that comes in the same order.
        """
        if row.branch != NORMAL:
            raise ValueError('only a NORMAL row has a critical')
        if not self._paired:
            self._pair()
        return self._paired.get(row.effect)

    def _pair(self):
        by_signature = {}
        by_kind = collections.defaultdict(list)
        for row in self.rows:
            if row.branch == CRITICAL:
                by_signature.setdefault(row.signature, row)
                by_kind[row.action, row.criteria].append(row)
        seen = collections.Counter()
        for row in self.rows:
            if row.branch != NORMAL:
                continue
            kind = (row.action, row.criteria)
            order = seen[kind]
            seen[kind] += 1
            found = by_signature.get(row.signature)
            if found is None and order < len(by_kind[kind]):
                found = by_kind[kind][order]
            self._paired[row.effect] = found


class ClientSpellBook:
    """The class spells of the client table, read from items_wakfu.db."""

    def __init__(self, db_path=None):
        if db_path is None:
            from .fashionista_config import get_items_db_path
            db_path = get_items_db_path('wakfu')
        self.conn = sqlite3.connect('file:%s?mode=ro' % db_path, uri=True)
        self._effects = None
        self._kids = None
        self._spells = {}

    def close(self):
        self.conn.close()

    def _load(self):
        if self._effects is not None:
            return
        self._effects = {row[0]: row for row in self.conn.execute(
            'SELECT id, action, normal_or_critical, area_shape, area_size, params,'
            ' criterion FROM effects WHERE root_container_type = ?', ('SPELL',))}
        self._kids = collections.defaultdict(list)
        for group, effect in self.conn.execute(
                'SELECT group_id, effect FROM effect_groups ORDER BY group_id, position'):
            self._kids[group].append(effect)

    def _walk(self, effect_ids, branch, criteria, path, depth, out):
        counted = collections.Counter()
        for effect_id in effect_ids:
            row = self._effects.get(effect_id)
            if row is None:
                continue
            _, action, own_branch, shape, size, params, criterion = row
            here = own_branch or branch
            criterion = _clean(criterion)
            below = criteria + ((criterion,) if criterion else ())
            index = counted[here]
            counted[here] += 1
            signature = path + ((action, criterion, index),)
            family = FAMILY_OF.get(action)
            element = DAMAGE_ACTIONS.get(action) or HEAL_ACTIONS.get(action)
            out.append(ClientRow(effect_id, action, family, element, here, below, shape,
                                 tuple(json.loads(size or '[]')), tuple(json.loads(params)),
                                 signature, depth))
            self._walk(self._kids.get(effect_id, ()), here, below, signature, depth + 1, out)

    def spell(self, spell_id):
        if spell_id not in self._spells:
            self._load()
            head = self.conn.execute(
                'SELECT id, breed, ap, mp, wp, range_min, range_max, element, unlock_level,'
                ' max_level FROM client_spells WHERE id = ?', (spell_id,)).fetchone()
            if head is None:
                raise KeyError(spell_id)
            roots = [effect for (effect,) in self.conn.execute(
                'SELECT effect FROM client_spell_effects WHERE spell = ? ORDER BY position',
                (spell_id,))]
            rows = []
            self._walk(roots, None, (), (), 0, rows)
            self._spells[spell_id] = ClientSpell(*head, rows)
        return self._spells[spell_id]

    def class_spells(self, breed):
        """Every client spell of the class, by id."""
        return tuple(self.spell(spell_id) for (spell_id,) in self.conn.execute(
            'SELECT id FROM client_spells WHERE breed = ? ORDER BY id', (breed,)))

    def breeds(self):
        return tuple(breed for (breed,) in self.conn.execute(
            'SELECT DISTINCT breed FROM client_spells WHERE breed > 0 ORDER BY breed'))


# The harvest check

Match = collections.namedtuple('Match', 'position status row levels element')


def element_fits(action_element, harvest_element):
    """Whether a client action can carry the harvest's element label."""
    harvest_element = (harvest_element or '').lower()
    if action_element == VARIABLE:
        return harvest_element in HARVEST_ELEMENTS
    return action_element == harvest_element


def _harvest_curves(conn, spell_id, kind):
    """{position: (element, values by level)} of the non-percent harvest rows."""
    out = {}
    for position, element, value in conn.execute(
            'SELECT position, element, value FROM spell_effects WHERE spell = ? AND kind = ?'
            ' AND is_percent = 0 ORDER BY position, level', (spell_id, kind)):
        entry = out.setdefault(position, [element, []])
        entry[1].append(value)
    return {position: (element, tuple(values)) for position, (element, values) in out.items()}


def _agreement(row_curve, harvest_curve):
    return sum(1 for mine, theirs in zip(row_curve, harvest_curve) if mine == theirs)


def match_harvest(book, spell_id, kind='damage'):
    """Match each harvest row of the spell to a NORMAL client row of the same curve.

    Returns [Match] in harvest position order. A row is matched when the client curve
    equals the harvest values at all 245 levels with a fitting element (AGREE) or with
    another element (ELEMENT_DIFFERS); otherwise the client row that agrees on most
    levels is kept (PARTIAL), or none (MISSING). A client row serves one harvest row.
    """
    family = KINDS[kind]
    spell = book.spell(spell_id)
    candidates = [row for row in spell.rows_of(family, NORMAL)]
    curves = {row.effect: row.curve() for row in candidates}
    used = set()
    out = []
    for position, (element, values) in _harvest_curves(book.conn, spell_id, kind).items():
        best = None
        for rank, row in enumerate(candidates):
            if row.effect in used:
                continue
            levels = _agreement(curves[row.effect], values)
            if levels == 0:
                continue
            fits = element_fits(row.element, element) if family == 'damage' else True
            exact = levels == len(values)
            # An exact curve with its element beats an exact curve without, which beats
            # a partial one; a client row that is not variable beats a variable one
            key = (exact and fits, exact, levels, row.action != 917, -rank)
            if best is None or key > best[0]:
                best = (key, row, levels, fits)
        if best is None:
            out.append(Match(position, MISSING, None, 0, element))
            continue
        _, row, levels, fits = best
        used.add(row.effect)
        if levels == len(values):
            status = AGREE if fits else ELEMENT_DIFFERS
        else:
            status = PARTIAL
        out.append(Match(position, status, row, levels, element))
    return out


def harvest_spells(conn, kind='damage'):
    """The ids of the harvest spells that hold non-percent rows of the kind."""
    return tuple(spell_id for (spell_id,) in conn.execute(
        'SELECT DISTINCT spell FROM spell_effects WHERE kind = ? AND is_percent = 0'
        ' ORDER BY spell', (kind,)))


def spell_status(book, spell_id, kind='damage'):
    """(status, [Match]) of one harvest spell the client holds."""
    spell = book.spell(spell_id)
    matches = match_harvest(book, spell_id, kind)
    if not spell.rows_of(KINDS[kind]):
        status = NO_ROW
    elif all(match.status in (AGREE, ELEMENT_DIFFERS) for match in matches):
        status = AGREE
    else:
        status = VALUES_MISSING
    return status, matches


def harvest_check(book, kind='damage'):
    """{spell id: (status, [Match])} over every harvest spell of the kind that the client holds.

    A harvest spell the client table lacks is listed with status 'not in the client'.
    """
    out = {}
    known = {spell_id for (spell_id,) in book.conn.execute('SELECT id FROM client_spells')}
    for spell_id in harvest_spells(book.conn, kind):
        if spell_id not in known:
            out[spell_id] = ('not in the client', [])
            continue
        out[spell_id] = spell_status(book, spell_id, kind)
    return out


def gap_list(book, kind='damage'):
    """{spell id: reason} for the harvest spells the client tree does not fully explain."""
    return {spell_id: status for spell_id, (status, _) in harvest_check(book, kind).items()
            if status != AGREE}


def costs_differ(book):
    """{spell id: [field, harvest, client]} where the harvest and client spells disagree."""
    out = collections.defaultdict(list)
    for spell_id, ap, mp, wp, reach in book.conn.execute(
            'SELECT s.id, s.ap, s.mp, s.wp, s.range FROM spells s'
            ' JOIN client_spells c ON c.id = s.id'):
        client = book.spell(spell_id)
        for field, mine, theirs in (('ap', ap or 0, client.ap), ('mp', mp or 0, client.mp),
                                    ('wp', wp or 0, client.wp)):
            if mine != theirs:
                out[spell_id].append((field, mine, theirs))
        numbers = [int(part) for part in re.findall(r'\d+', reach or '')]
        if numbers and (numbers[0], numbers[-1]) != client.range:
            out[spell_id].append(('range', (numbers[0], numbers[-1]), client.range))
    return dict(out)
