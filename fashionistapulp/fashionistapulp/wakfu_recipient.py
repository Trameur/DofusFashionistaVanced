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

"""Who the effects of a Wakfu spell land on, read from the item database."""
import collections
import json

CASTER = 'caster'
OWN_SUMMON = 'own summon'
ALLY = 'ally'
TEAM = 'team'
ENEMY = 'enemy'
TARGETED = 'targeted'
AREA = 'area'
UNKNOWN = 'unknown'

REASON_PARTY = 'the other party of a trigger event'
REASON_BYTES = 'a listener without its trigger bytes'
REASON_CASTER = 'a caster change from an unknown unit'
REASON_FILTER = 'the database holds no target filter'

#: Hand list: the group actions of the client's class tree of effect groups.
GROUP_ACTIONS = frozenset({330, 844, 912, 913, 999, 1020, 1047, 1103})
STEAL_ACTION = 865

_LISTENER_LISTS = (0, 1, 3, 4, 5)
_BYTE_COLUMNS = ('trigger_side', 'trigger_target', 'trigger_caster')
_DEPTH = 60
_CAP = 40000

_PARTY = 'party'
_BYTES = 'bytes'
_UNNAMED = 'unnamed caster'
_UNKNOWN_UNITS = {_PARTY: REASON_PARTY, _BYTES: REASON_BYTES, _UNNAMED: REASON_CASTER}
_KNOWN_SIDE = {CASTER: 'own', OWN_SUMMON: 'own', ALLY: 'own', TEAM: 'own', ENEMY: 'other'}


class Recipient(collections.namedtuple('Recipient', 'unit outputs reason')):
    """The unit an effect lands on, the sides it reaches and, for an unknown unit, why."""


class Foot(collections.namedtuple('Foot', 'anchor cells exact picked')):
    """The cells a node can cover, relative to the targeted cell ('cell') or the caster's cell ('caster');
    anchor None for a unit that cannot be placed; exact False when a turn of the shape or an unmodelled
    shape makes the cells a superset; picked True when the node's unit is one an area collected, so an
    area drawn around it can sit anywhere in those cells."""


_AT_CELL = Foot('cell', frozenset({(0, 0)}), True, False)
_AT_CASTER = Foot('caster', frozenset({(0, 0)}), True, False)
_NOWHERE = Foot(None, frozenset(), False, False)


def _turned(cells):
    return frozenset((-y, x) for x, y in cells)


def area_cells(shape, size):
    """(cells, turns): the cells of an area around its centre, +x pointing away from the caster, and
    whether the client turns the shape with the cast direction; cells is None for an unmodelled shape."""
    s = list(size)
    cells = set()
    turns = True
    if shape == 1:
        cells.add((0, 0))
        turns = False
    elif shape == 2:
        r = s[0]
        cells |= {(x, y) for x in range(-r, r + 1) for y in range(-r, r + 1) if abs(x) + abs(y) <= r}
        turns = False
    elif shape == 3:
        ahead = s[0]
        if len(s) == 2:
            behind, left, right = ahead, s[1], s[1]
        elif len(s) == 4:
            behind, left, right = s[1], s[2], s[3]
        else:
            behind = left = right = ahead
        cells.add((0, 0))
        cells |= {(n, 0) for n in range(1, ahead + 1)} | {(-n, 0) for n in range(1, behind + 1)}
        cells |= {(0, -n) for n in range(1, left + 1)} | {(0, n) for n in range(1, right + 1)}
        turns = False
    elif shape == 4:
        width, height = abs(s[0]), abs(s[1])
        cells.add((0, 0))
        cells |= {(n, 0) for n in range(1, height + 1)}
        cells |= {(height, n) for n in range(1, width + 1)} | {(height, -n) for n in range(1, width + 1)}
    elif shape == 5:
        low, high = min(s), max(s)
        cells |= {(x, y) for x in range(-high, high + 1) for y in range(-high, high + 1)
                  if low <= abs(x) + abs(y) <= high}
        turns = False
    elif shape == 6:
        width = s[0]
        height = s[1] if len(s) > 1 else width
        width += 1 if width and width % 2 == 0 else 0
        height += 1 if height and height % 2 == 0 else 0
        cells |= {(i - (width - 1) // 2, j - (height - 1) // 2)
                  for i in range(width) for j in range(height)}
        turns = width != height
    elif shape == 7:
        if len(s) == 2:
            inner_x = inner_y = min(s)
            outer_x = outer_y = max(s)
        else:
            inner_x, inner_y, outer_x, outer_y = s[0], s[1], s[2], s[3]
        for i in range(outer_x + 1):
            for j in range(outer_y + 1):
                if i < inner_x and j < inner_y:
                    continue
                cells |= {(i, j), (-i, j), (i, -j), (-i, -j)}
    elif shape == 8:
        cells |= set(zip(s[0::2], s[1::2]))
    elif shape == 9:
        width, height = abs(s[0]), abs(s[1])
        cells.add((0, 0))
        cells |= {(0, n) for n in range(1, width + 1)} | {(0, -n) for n in range(1, width + 1)}
        cells |= {(n, 0) for n in range(1, height + 1)}
    elif shape == 11:
        cells.add((0, 0))
        cells |= {(sx * n, sy * n) for n in range(1, max(s) + 1) for sx in (1, -1) for sy in (1, -1)}
        turns = False
    elif shape == 12:
        for n in range(min(s), max(s) + 1):
            cells |= {(0, -n), (0, n), (n, 0), (-n, 0)}
        turns = False
    elif shape == 13:
        height = s[0]
        cells |= {(i, j) for i in range(height) for j in range(-i, i + 1)}
    elif shape == 32767:
        return frozenset(), False
    else:
        return None, True
    cells = frozenset(cells)
    if turns:
        quarter = _turned(cells)
        turns = not (quarter == cells and _turned(quarter) == cells)
    return cells, turns


def _spread(base, shape, size):
    """The footprint widened by a node's own area."""
    if base.anchor is None:
        return base
    cells, turns = area_cells(shape, size)
    if cells is None or not cells:
        return Foot(base.anchor, base.cells, False, False)
    if cells == {(0, 0)}:
        return Foot(base.anchor, base.cells, base.exact, False)
    if len(base.cells) * len(cells) > _CAP:
        radius = (max(abs(a) + abs(b) for a, b in base.cells)
                  + max(abs(a) + abs(b) for a, b in cells))
        wide = frozenset((p, q) for p in range(-radius, radius + 1)
                         for q in range(-radius, radius + 1) if abs(p) + abs(q) <= radius)
        return Foot(base.anchor, wide, False, False)
    out = frozenset((a + p, b + q) for a, b in base.cells for p, q in cells)
    return Foot(base.anchor, out, base.exact and not turns and not base.picked, False)


def reaches_caster(foot, range_min, range_max):
    """'yes', 'possibly' or 'no': can the footprint cover the caster at a legal cast?"""
    if foot.anchor == 'caster':
        if (0, 0) in foot.cells:
            return 'yes' if foot.exact else 'possibly'
        return 'no'
    if foot.anchor is None:
        return 'possibly'
    hit = [c for c in foot.cells if range_min <= abs(c[0]) + abs(c[1]) <= range_max]
    if not hit:
        return 'no'
    if (0, 0) in hit or foot.exact:
        return 'yes'
    if any(c[0] < 0 and abs(c[1]) <= -c[0] for c in hit):
        return 'possibly'
    return 'no'


def _outputs(unit, foot, range_min, range_max):
    if unit == CASTER:
        return frozenset({'caster'})
    if unit in (OWN_SUMMON, ALLY):
        return frozenset({'allies'})
    if unit == ENEMY:
        return frozenset({'enemies'})
    if unit in (TEAM, TARGETED, AREA):
        sides = {'allies'} if unit == TEAM else {'allies', 'enemies'}
        found = reaches_caster(foot, range_min, range_max)
        if found == 'yes':
            sides.add('caster')
        elif found == 'possibly':
            sides.add('possibly_caster')
        return frozenset(sides)
    return frozenset({'unknown'})


def _decisive(mask, caster):
    """The unit a filter names relative to the caster, None when it decides nothing."""
    if mask & 2:
        return caster
    if mask & 4096:
        return OWN_SUMMON if caster == CASTER else _UNNAMED
    side = _KNOWN_SIDE.get(caster)
    if mask & 128 or mask & 4:
        if side == 'own':
            return ALLY if mask & 128 else TEAM
        return ENEMY if side == 'other' else _UNNAMED
    if mask & 8:
        if side == 'own':
            return ENEMY
        return TEAM if side == 'other' else _UNNAMED
    return None


def _multi_cell(shape, size):
    return not (shape == 1 and not size)


def _value(params, index):
    if len(params) >= 2 * index + 2:
        return params[2 * index] + params[2 * index + 1]
    return None


class _Effect(collections.namedtuple('_Effect', 'action shape size params mask listener side target caster')):
    __slots__ = ()


class _Walk:
    def __init__(self, conn, spell):
        self.conn = conn
        self.spell = spell
        columns = {row[1] for row in conn.execute('pragma table_info(effects)')}
        self.has_mask = 'target_mask' in columns
        self.has_bytes = all(name in columns for name in _BYTE_COLUMNS)
        select = ['action', 'area_shape', 'area_size', 'params',
                  'target_mask' if self.has_mask else 'NULL',
                  'triggers' if 'triggers' in columns else 'NULL']
        select += list(_BYTE_COLUMNS) if self.has_bytes else ['NULL'] * 3
        self.query = 'select %s from effects where id = ?' % ', '.join(select)
        self.effects = {}
        self.children = {}
        self.out = {}
        self.range_min = self.range_max = 0

    def effect(self, effect_id):
        if effect_id not in self.effects:
            row = self.conn.execute(self.query, (effect_id,)).fetchone()
            if row is None:
                self.effects[effect_id] = None
            else:
                action, shape, size, params, mask, triggers, side, target, caster = row
                lists = json.loads(triggers) if triggers else []
                listener = any(i < len(lists) and lists[i] for i in _LISTENER_LISTS)
                self.effects[effect_id] = _Effect(
                    action, shape, json.loads(size or '[]'), json.loads(params or '[]'), mask or 0,
                    listener, side or 0, target or 0, caster or 0)
        return self.effects[effect_id]

    def kids(self, effect_id):
        if effect_id not in self.children:
            self.children[effect_id] = [row[0] for row in self.conn.execute(
                'select effect from effect_groups where group_id = ? order by position', (effect_id,))]
        return self.children[effect_id]

    def run(self):
        spell = self.conn.execute(
            'select ap, mp, wp, range_min, range_max from client_spells where id = ?',
            (self.spell,)).fetchone()
        if spell is None:
            return {}
        ap, mp, wp, low, high = spell
        self.range_min, self.range_max = int(low or 0), int(high or 0)
        passive = not (ap or mp or wp)
        if passive or not self.range_max:
            center, foot = CASTER, _AT_CASTER
        else:
            center, foot = TARGETED, _AT_CELL
        roots = [row[0] for row in self.conn.execute(
            'select effect from client_spell_effects where spell = ? order by position', (self.spell,))]
        blind = None if self.has_mask else REASON_FILTER
        for root in roots:
            self.node(root, CASTER, CASTER if passive else None, _AT_CASTER if passive else None,
                      center, foot, blind, 0)
        return self.out

    def emit(self, effect_id, unit, foot):
        if effect_id in self.out:
            return
        if unit in _UNKNOWN_UNITS:
            self.out[effect_id] = Recipient(UNKNOWN, frozenset({'unknown'}), _UNKNOWN_UNITS[unit])
        else:
            self.out[effect_id] = Recipient(
                unit, _outputs(unit, foot, self.range_min, self.range_max), None)

    def emit_blind(self, effect_id, reason):
        if effect_id not in self.out:
            self.out[effect_id] = Recipient(UNKNOWN, frozenset({'unknown'}), reason)

    def blind_below(self, effect_id, reason, depth):
        if depth > _DEPTH:
            return
        self.emit_blind(effect_id, reason)
        for kid in self.kids(effect_id):
            self.blind_below(kid, reason, depth + 1)

    def choose(self, x, caster, handed, hfoot, center, cfoot):
        """The unit of a node and the cells it covers."""
        if handed in (TEAM, ALLY) and x.mask & 2:
            return handed, hfoot
        decided = _decisive(x.mask, caster)
        if decided is not None:
            return decided, (_AT_CASTER if decided == CASTER else _spread(cfoot, x.shape, x.size))
        if _multi_cell(x.shape, x.size):
            return AREA, _spread(cfoot, x.shape, x.size)
        return (handed, hfoot) if handed is not None else (center, cfoot)

    def fire(self, x, holder, hfoot, caster):
        """(caster, target, target footprint) of a fired copy."""
        side = x.side
        by_caster = holder if side == 1 else _PARTY
        by_target = holder if side == 2 else _PARTY
        target = {1: holder, 2: holder, 3: caster, 4: by_caster, 5: by_target}.get(x.target, _BYTES)
        new_caster = {1: caster, 2: holder, 3: holder, 4: by_caster, 5: by_target}.get(x.caster, _BYTES)
        if target == holder:
            foot = hfoot
        else:
            foot = _AT_CASTER if target == CASTER else _NOWHERE
        return new_caster, target, foot

    def node(self, effect_id, caster, handed, hfoot, center, cfoot, blind, depth, fired=False):
        x = self.effect(effect_id)
        if x is None or depth > _DEPTH:
            return
        if blind:
            self.blind_below(effect_id, blind, depth)
            return
        if fired:
            unit, foot = handed, hfoot
        else:
            unit, foot = self.choose(x, caster, handed, hfoot, center, cfoot)
        if x.listener and not fired:
            if not (self.has_bytes and x.target and x.caster):
                self.blind_below(effect_id, REASON_BYTES, depth)
                return
            new_caster, target, target_foot = self.fire(x, unit, foot, caster)
            self.node(effect_id, new_caster, target, target_foot, target, target_foot, None,
                      depth + 1, True)
            return
        foot = _AT_CASTER if unit == CASTER else foot
        self.emit(effect_id, unit, foot)
        kids = self.kids(effect_id)
        picked = unit in (ALLY, TEAM, ENEMY, OWN_SUMMON, AREA) and len(foot.cells) > 1
        child = foot._replace(picked=picked)
        if x.action == STEAL_ACTION:
            on_target = len(x.params) // 2 >= 3 and _value(x.params, 2) != 0
            for i, kid in enumerate(kids):
                if i == 0 or on_target:
                    given, given_foot = unit, child
                else:
                    given, given_foot = caster, (_AT_CASTER if caster == CASTER else _NOWHERE)
                self.node(kid, caster, given, given_foot, unit, child, None, depth + 1)
            return
        if x.action in GROUP_ACTIONS:
            count = len(x.params) // 2
            on_target = _value(x.params, 2) == 1 if count >= 3 else True
            hand = _value(x.params, 4) == 1 if count >= 5 else True
            swap = int(_value(x.params, 5)) if count >= 6 else 0
            new_caster, new_unit, new_foot = caster, unit, child
            if swap == 1:
                new_caster = unit
                if handed is not None:
                    new_unit, new_foot = handed, hfoot
                else:
                    new_unit, new_foot = center, cfoot
            elif swap == 2:
                new_caster, new_unit = unit, caster
                new_foot = _AT_CASTER if caster == CASTER else _NOWHERE
            if on_target and hand:
                given, given_foot, middle, middle_foot = new_unit, new_foot, new_unit, new_foot
            elif on_target:
                given, given_foot, middle, middle_foot = None, None, new_unit, new_foot
            else:
                given = given_foot = None
                if _multi_cell(x.shape, x.size):
                    middle, middle_foot = AREA, _spread(cfoot, x.shape, x.size)
                else:
                    middle, middle_foot = center, cfoot
            for kid in kids:
                self.node(kid, new_caster, given, given_foot, middle, middle_foot, None, depth + 1)
            return
        for kid in kids:
            self.node(kid, caster, None, None, unit, child, None, depth + 1)


def recipients_of(conn, spell_id):
    """The recipient of every effect reached from a spell's root effects, by effect id."""
    return _Walk(conn, spell_id).run()
