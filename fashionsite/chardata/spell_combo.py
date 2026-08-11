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

"""Best order of casts in one turn: one target, no positioning."""

import copy

from fashionistapulp.dofus_constants import calculate_damage, get_stat_maximum

from chardata.spell_buffs import (_buff_value, _decide_spell_level,
                                  get_damage_spells_for_version)

MAX_CASTS = 8

# What a character starts a fight with, before any gear. The stats the site
# carries are gear bonuses only, so a build with no AP item reads as 0 and had
# nothing to spend.
BASE_AP = 6


def combat_ap(gear_ap, game_version):
    """The AP a turn actually has. Retro never got the PA/PM/PO limitation, so
    only the other versions take the cap."""
    total = BASE_AP + (gear_ap or 0)
    cap = get_stat_maximum(game_version).get('AP')
    return min(total, cap) if cap else total


def _element_alternatives(aggregates, effects):
    """The groups of a best-element spell, or None when they are not that.

    The generator writes a best-element hit as one single-row group per
    element, and a stacking spell as one group per stack. They look identical
    apart from the elements: four groups of earth/fire/water/air are one hit
    the caster picks, five groups all of water are the same hit growing. Only
    the first shape may be scored on its best row; keeping group 0 there meant
    always scoring Earth, on 84 Dofus 3 spells.

    A spell can carry several such runs, one per glyph grade or per state.
    Those are alternatives too, but which one applies is not something the
    panel knows, so it keeps the first, the way it already assumes nothing is
    stacked yet.
    """
    if not aggregates or len(aggregates) < 2:
        return None
    run = []
    seen = set()
    for _label, indices in aggregates:
        if len(indices) != 1 or indices[0] >= len(effects):
            return None
        element = effects[indices[0]].element
        if element in seen:
            break
        seen.add(element)
        run.append(set(indices))
    return run if len(run) > 1 else None


class Castable(object):

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
        # Aggregate rows are alternatives, one per stack or element; a cast
        # lands one. First group = nothing built up.
        groups = _element_alternatives(digest.aggregates, self.effects)
        if groups is None:
            groups = [set(digest.aggregates[0][1])] if digest.aggregates else [None]
        # A row the spell does not have at this level is stored as 0 to 0, and
        # the damage formula hands it the flat bonus anyway: max(0 + dam, 0).
        # Friendship Word carried twelve of them, 40% of what it claimed.
        self.alternatives = []
        for wanted in groups:
            kept = [effect for index, effect in hits
                    if (wanted is None or index in wanted)
                    and (effect.min_dam or effect.max_dam)]
            if kept:
                self.alternatives.append(kept)
        self.hits = self.alternatives[0] if self.alternatives else []
        self.stacked = bool(digest.aggregates)
        casting = spell.casting or {}
        limits = [casting.get(key, [None] * (level_index + 1))[level_index]
                  for key in ('per_turn', 'per_target')]
        # A spell on a cooldown cannot come back the same turn, and 67 of the
        # 536 Dofus 3 class spells are gated by nothing else. No spell carries
        # a cooldown together with a per-turn cap, so this cannot tighten one.
        cooldown = casting.get('cooldown', [None] * (level_index + 1))[level_index]
        if cooldown:
            limits.append(1)
        limits = [limit for limit in limits if limit]
        self.limit = min(limits) if limits else None
        self.stacks = spell.stacks or 1

    def buff_deltas(self, count):
        deltas = {}
        capped = min(count, self.stacks)
        for effect in self.buffs:
            parts = effect.element.split('_')
            if len(parts) > 2:  # weapon-only, glyph-only... not every hit
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
    """Class bucket only: the shared one is weapons, pies and Dofus effects."""
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
    """(total, [(spell name, damage), ...]) for the best order fitting the AP."""
    stats = dict(stats)
    spells = [spell for spell in spells if spell.cost and spell.cost <= ap]
    if not spells:
        return 0.0, []

    def damage_of(spell, counts):
        if not spell.alternatives:
            return 0.0
        buffed = dict(stats)
        for index, other in enumerate(spells):
            if not counts[index]:
                continue
            for stat, value in other.buff_deltas(counts[index]).items():
                if stat in buffed:
                    buffed[stat] = buffed[stat] + value
        # A best-element spell offers one hit per element and the caster takes
        # the one their gear favours, so it has to be scored after the buffs.
        best_seen = 0.0
        for alternative in spell.alternatives:
            rows = [copy.copy(effect) for effect in alternative]
            gained = _average(calculate_damage(rows, buffed, crit, True))
            if gained > best_seen:
                best_seen = gained
        return best_seen

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
