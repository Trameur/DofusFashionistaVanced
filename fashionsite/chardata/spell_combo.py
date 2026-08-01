# -*- coding: utf-8 -*-

# Copyright (C) 2020 The Dofus Fashionista
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

"""Best order of casts in one turn, for the build the page is showing.

Everything this needs already existed apart from the AP cost: what a spell hits
for, how often it may be cast, and what a self-buff grants per stack. It is a
search rather than a sort by damage per AP, because a buff cast first changes
what every later cast is worth, so the order IS the answer.

One turn, one target, no positioning: what it reports is the damage ceiling of
the stuff, not a fight plan.
"""

import copy

from fashionistapulp.dofus_constants import calculate_damage

from chardata.spell_buffs import (_buff_value, _decide_spell_level,
                                  get_damage_spells_for_version)

# A turn is a handful of casts, but a build with cheap spells and a big AP pool
# can still open a wide tree. Kept low enough to answer while the page loads.
MAX_CASTS = 8


class Castable(object):
    """A spell reduced to what a turn needs from it."""

    def __init__(self, spell, level_index, crit):
        self.spell = spell
        self.name = spell.name
        self.cost = spell.ap_cost(level_index)
        digest = spell.get_effects_digest()
        rows = digest.crit_dams if crit else digest.non_crit_dams
        self.effects = rows[level_index] if level_index < len(rows) else []
        self.buffs = [effect for effect in self.effects
                      if effect.element.startswith('buff')]
        hits = [(index, effect) for index, effect in enumerate(self.effects)
                if not effect.element.startswith('buff')]
        # With aggregates the rows are ALTERNATIVES, one line per stack or per
        # element, and a cast only ever lands one of them. The spells page
        # prints them as "Stack 0:", "Stack 1:"; adding them up multiplied Fit
        # of Rage by five. The first group is the one with nothing built up.
        if digest.aggregates:
            wanted = set(digest.aggregates[0][1])
            hits = [pair for pair in hits if pair[0] in wanted]
        self.hits = [effect for _index, effect in hits]
        self.stacked = bool(digest.aggregates)
        casting = spell.casting or {}
        limits = [casting.get(key, [None] * (level_index + 1))[level_index]
                  for key in ('per_turn', 'per_target')]
        limits = [limit for limit in limits if limit]
        self.limit = min(limits) if limits else None
        self.stacks = spell.stacks or 1

    def buff_deltas(self, count):
        """Stat bonus this spell grants after being cast that many times."""
        deltas = {}
        capped = min(count, self.stacks)
        for effect in self.buffs:
            parts = effect.element.split('_')
            if len(parts) > 2:
                # Category-restricted power (weapon only, glyphs only, ...).
                # Applying it to every hit would overstate the turn.
                continue
            stat = parts[1]
            value = _buff_value(self.spell.buff_scaling, stat, capped,
                                effect.max_dam)
            if stat == 'depow':
                stat, value = 'pow', -value
            if value:
                deltas[stat] = deltas.get(stat, 0) + value
        return deltas


def _average(damages):
    total = 0
    for damage in damages:
        if damage.heals:
            continue
        total += (damage.min_dam + damage.max_dam) / 2.0
    return total


def castable_spells(char_class, char_level, game_version, crit=False):
    """The class spells a character of that level can actually cast.

    The class bucket only. The shared one holds weapons, pies and Dofus
    effects, which a turn does not get to cast at will.
    """
    by_class = get_damage_spells_for_version(game_version)
    spells = by_class.get(char_class, [])
    out = []
    for spell in spells:
        if not spell.casting or char_level < spell.level_req[0]:
            continue
        level_index = _decide_spell_level(spell.level_req, char_level)
        castable = Castable(spell, level_index, crit)
        if not castable.cost or (not castable.hits and not castable.buffs):
            continue
        out.append(castable)
    return out


def best_turn(stats, spells, ap, crit=False):
    """Highest-damage cast order that fits the AP, and what it adds up to.

    Returns (total, [(spell name, damage of that cast), ...]).
    """
    stats = dict(stats)
    spells = [spell for spell in spells if spell.cost and spell.cost <= ap]
    if not spells:
        return 0.0, []

    def damage_of(spell, counts):
        if not spell.hits:
            return 0.0
        buffed = dict(stats)
        for index, other in enumerate(spells):
            if not counts[index]:
                continue
            for stat, value in other.buff_deltas(counts[index]).items():
                if stat in buffed:
                    buffed[stat] = buffed[stat] + value
        # Copied: calculate_damage resolves "best element" by writing it back
        # into the row, which would stick to the shared spell for good.
        rows = [copy.copy(effect) for effect in spell.hits]
        return _average(calculate_damage(rows, buffed, crit, True))

    best = {}

    def search(ap_left, counts, depth):
        key = (ap_left, counts)
        if key in best:
            return best[key]
        outcome = (0.0, ())
        if depth < MAX_CASTS:
            for index, spell in enumerate(spells):
                if spell.cost > ap_left:
                    continue
                if spell.limit and counts[index] >= spell.limit:
                    continue
                gained = damage_of(spell, counts)
                after = list(counts)
                after[index] += 1
                total, order = search(ap_left - spell.cost, tuple(after),
                                      depth + 1)
                total += gained
                if total > outcome[0]:
                    outcome = (total, ((index, gained),) + order)
        best[key] = outcome
        return outcome

    total, order = search(ap, (0,) * len(spells), 0)
    return total, [(spells[index].name, gained) for index, gained in order]
