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

# The stats the site carries are gear bonuses only; this is what a character
# starts a fight with.
BASE_AP = 6


def combat_ap(gear_ap, game_version):
    """The AP a turn has. Retro never got the PA/PM/PO limitation, so it takes
    no cap."""
    total = BASE_AP + (gear_ap or 0)
    cap = get_stat_maximum(game_version).get('AP')
    return min(total, cap) if cap else total


def _element_alternatives(aggregates, effects):
    """The groups of a best-element spell, or None when they are not that.

    The generator writes a best-element hit as one single-row group per element
    and a stacking spell as one group per stack; only a repeated element tells
    the two shapes apart. A spell can carry several such runs, one per glyph
    grade or per state; the first one is kept.
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
        # A spell on a cooldown cannot come back the same turn.
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


def final_multiplier(stats):
    """The percentage applied after everything else; calculate_damage stops at
    per-spell damage. Heals are not scored here, so finalheals is ignored."""
    multiplier = (100.0 + stats.get('final', 0)) / 100.0
    negative = stats.get('negfinal', 0)
    if negative:
        multiplier = multiplier * (100.0 - negative) / 100.0
    return multiplier


def buffs_in_force(char_class, char_level, game_version, buff_state,
                   levels=None):
    """Stat deltas from the buffs the reader ticked on the spells page.

    The page stores one entry per spell, 'n2' or 'c1': the letter says whether
    the buff was read on its critical line, the digits how many stacks.
    """
    deltas = {}
    for spell, stacks, crit in _ticked_buffs(char_class, char_level,
                                             game_version, buff_state):
        level_index = _chosen_level(levels, spell, char_level)
        castable = Castable(spell, level_index, crit)
        for stat, delta in castable.buff_deltas(stacks).items():
            deltas[stat] = deltas.get(stat, 0) + delta
    return deltas


def stacks_in_force(char_class, char_level, game_version, buff_state):
    """{spell name: stacks} for the buffs the reader ticked."""
    return {spell.name: stacks
            for spell, stacks, _crit
            in _ticked_buffs(char_class, char_level, game_version, buff_state)}


def _ticked_buffs(char_class, char_level, game_version, buff_state):
    """(spell, stacks, crit) per entry the page posted, in its own vocabulary.

    A ticked name can come from the class bucket or the shared one.
    """
    if not buff_state:
        return
    by_class = get_damage_spells_for_version(game_version)
    by_name = {spell.name: spell
               for bucket in (by_class.get('default', []),
                              by_class.get(char_class, []))
               for spell in bucket}
    for name, value in buff_state.items():
        spell = by_name.get(name)
        if spell is None or not value:
            continue
        crit = str(value)[0] == 'c'
        try:
            stacks = int(str(value)[1:])
        except ValueError:
            continue
        if not stacks or char_level < spell.level_req[0]:
            continue
        yield spell, stacks, crit


def _chosen_level(levels, spell, char_level):
    """The rank to read a spell at: the reader's pick, else the highest one the
    character level reaches."""
    highest = _decide_spell_level(spell.level_req, char_level)
    wanted = (levels or {}).get(spell.name)
    try:
        wanted = int(wanted)
    except (TypeError, ValueError):
        return highest
    if 0 <= wanted <= highest:
        return wanted
    return highest


def castable_spells(char_class, char_level, game_version, crit=False,
                    levels=None):
    """Class bucket only: the shared one is weapons, pies and Dofus effects.

    `levels` is {spell name: rank index}; without it every spell is read at the
    highest rank the character level allows.
    """
    by_class = get_damage_spells_for_version(game_version)
    spells = by_class.get(char_class, [])
    out = []
    for spell in spells:
        if not spell.casting or char_level < spell.level_req[0]:
            continue
        level_index = _chosen_level(levels, spell, char_level)
        castable = Castable(spell, level_index, crit)
        if not castable.cost or (not castable.hits and not castable.buffs):
            continue
        out.append(castable)
    return out


def best_turn(stats, spells, ap, crit=False, standing=None):
    """(total, [(spell name, damage), ...]) for the best order fitting the AP.

    `standing` is {spell name: stacks} for the buffs the reader already ticked,
    whose value is part of `stats`: recasting one adds only the difference.
    """
    stats = dict(stats)
    standing = standing or {}
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
            already = min(standing.get(other.name, 0), other.stacks)
            reached = min(already + counts[index], other.stacks)
            if reached <= already:
                continue
            was = other.buff_deltas(already) if already else {}
            for stat, value in other.buff_deltas(reached).items():
                gained = value - was.get(stat, 0)
                buffed[stat] = buffed.get(stat, 0) + gained
        # A best-element spell is scored after the buffs: the caster picks the
        # element their gear favours.
        best_seen = 0.0
        multiplier = final_multiplier(buffed)
        for alternative in spell.alternatives:
            rows = [copy.copy(effect) for effect in alternative]
            gained = _average(calculate_damage(rows, buffed, crit, True)) * multiplier
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
