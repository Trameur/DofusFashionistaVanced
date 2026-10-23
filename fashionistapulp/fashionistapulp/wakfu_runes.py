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

"""Wakfu runes: what a rune gives in a socket, at the tier the piece's level allows."""

import collections

from .wakfu_db import level_value

# The client's colour codes (enum QE); a socket is never NONE (0) once it is slotted
RED, GREEN, BLUE, WHITE = 1, 2, 3, 4
RUNE_COLOURS = (RED, GREEN, BLUE)
SOCKET_COLOURS = RUNE_COLOURS + (WHITE,)

NONE, OPTIMISTIC = 'none', 'optimistic'
MODES = (NONE, OPTIMISTIC)

# colour and stat are codes, doubles the positions the rune counts twice on, costs and
# requirements the shards and the item level of each tier (index 0 is tier 1), lines the
# (effect, min_level, max_level, base, per_level) rows, names {language: name}
Rune = collections.namedtuple(
    'Rune', 'id colour stat doubles costs requirements lines names')
# value is the characteristic the socket gives, shards what the tier holds
Socket = collections.namedtuple(
    'Socket', 'index colour rune tier value doubled shards')


def allowed_tier(rune, item_level):
    """The highest tier a piece of this level allows (the client's fpI.WB)."""
    return sum(1 for needed in rune.requirements if needed <= (item_level or 0))


def shards_at(rune, tier):
    """The shards a socket holds at this tier (the client's fpI.Wz)."""
    return sum(rune.costs[:tier])


def tier_for_shards(rune, shards):
    """The highest tier that `shards` pay for (the client's fpI.WA), 0 for none."""
    tier = 0
    while tier < len(rune.costs) and shards_at(rune, tier + 1) <= shards:
        tier += 1
    return tier


def value(rune, tier, doubled):
    """What the rune gives at this tier: the integer of its one line, twice when doubled."""
    if rune.stat is None:
        return 0
    if not 1 <= tier <= len(rune.costs):
        raise ValueError('rune %d has no tier %d' % (rune.id, tier))
    holding = [line for line in rune.lines if line[1] <= tier <= line[2]]
    if len(holding) != 1:
        raise ValueError('rune %d has %d lines at tier %d' % (rune.id, len(holding), tier))
    _effect, _low, _high, base, per_level = holding[0]
    number = level_value(base, per_level, tier)
    return number * 2 if doubled else number


def socket_tier(rune, item, cap=None):
    """The tier a socket of this piece holds: the one its level allows, or the cap."""
    return min(allowed_tier(rune, item.level), cap or len(rune.costs))


def valued(structure):
    """{id: Rune} of the runes that give a characteristic."""
    return {ident: rune for ident, rune in structure.shards.items() if rune.stat is not None}


def read_options(structure, runes, rune_tier):
    """(mode, tier cap) of the runes and rune_tier arguments; ValueError on a bad one.

    A mode is None, NONE or OPTIMISTIC; a tier is None or a whole number from 0 up to the
    highest tier the rune table has, and 0 is the same as NONE.
    """
    if runes is None:
        mode = NONE
    elif runes in MODES:
        mode = runes
    else:
        raise ValueError('runes are %s or None, got %r' % (', '.join(map(repr, MODES)), runes))
    if rune_tier is None:
        return mode, None
    if not isinstance(rune_tier, int) or isinstance(rune_tier, bool) or rune_tier < 0:
        raise ValueError('rune_tier is a whole number from 0, got %r' % (rune_tier,))
    shards = getattr(structure, 'shards', None) or {}
    top = max((len(rune.costs) for rune in shards.values()), default=None)
    if top is not None and rune_tier > top:
        raise ValueError('rune_tier is 0 to %d, got %r' % (top, rune_tier))
    return (NONE if rune_tier == 0 else mode), rune_tier or None


def sockets_of(item):
    """How many sockets a piece can hold: the most its catalogue row gives."""
    return getattr(item, 'shard_slots', (0, 0))[1]


def entries(sockets):
    """[(colour, rune id, tier)] of the filled sockets of a Socket tuple or of such triples."""
    out = []
    for socket in sockets or ():
        if isinstance(socket, Socket):
            if socket.rune is not None:
                out.append((socket.colour, socket.rune, socket.tier))
        else:
            out.append(tuple(socket))
    return out


def position_lines(structure, worn, sockets):
    """{position: Counter {stat key: total}} of the sockets of the worn pieces.

    worn: {position: item}; sockets: {position: Sockets or (colour, rune id, tier)}. The
    value is read from the catalogue by rune, tier and position, never from Socket.value.
    A rune the table does not know, a tier it does not have and a position with no worn
    piece give nothing; wakfu_legality reports them.
    """
    out = {}
    for position, held in (sockets or {}).items():
        if position not in worn:
            continue
        lines = collections.Counter()
        for _colour, ident, tier in entries(held):
            rune = structure.shards.get(ident)
            if (rune is None or rune.stat is None or not isinstance(tier, int)
                    or not 1 <= tier <= len(rune.costs)):
                continue
            stat = structure.get_stat_by_id(rune.stat)
            if stat is not None:
                lines[stat.key] += value(rune, tier, position in rune.doubles)
        out[position] = lines
    return out


def lines(structure, worn, sockets):
    """Counter {stat key: total} of the sockets of a set."""
    total = collections.Counter()
    for one in position_lines(structure, worn, sockets).values():
        total.update(one)
    return total


def colours(sockets):
    """Counter {(position, colour): sockets} of the filled sockets, for the colour rows."""
    count = collections.Counter()
    for position, held in (sockets or {}).items():
        for colour, _ident, _tier in entries(held):
            count[(position, colour)] += 1
    return count
