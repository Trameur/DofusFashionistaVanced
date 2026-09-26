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
import math
import re

from fashionistapulp.dofus_constants import (NEUTRAL, calculate_damage,
                                             get_stat_maximum)

from chardata.pushback import pushback_damage
from chardata.spell_buffs import (_buff_value, _decide_spell_level,
                                  get_damage_spells_for_version)
from chardata.spell_variants import variant_of

MAX_CASTS = 8

# Retro spells that can only hit a summon, with the words of their description
ONLY_HITS_A_SUMMON = {
    'retro': {
        30: 'punir une invocation',        # Osamodas, Fouet
        46: 'aux invocations',             # Enutrof, Desinvocation
        198: 'punissant une invocation',   # Sadida, Sacrifice Poupesque
    },
}

# Starting AP, for builds saved without base stats
BASE_AP = 6


def combat_ap(total_ap, game_version, temporix=False):
    """AP of a turn, capped except in Retro and TemporiX."""
    total = total_ap or BASE_AP
    cap = get_stat_maximum(game_version, temporix=temporix).get('AP')
    return min(total, cap) if cap else total


def _run_that_hurts(runs, effects):
    """First run that hits, else the first (Tout ou Rien heals first)."""
    def frappe(run):
        return any(not getattr(effects[index], 'heals', False)
                   and (effects[index].min_dam or effects[index].max_dam)
                   for groupe in run for index in groupe)

    for run in runs:
        if frappe(run):
            return run
    return runs[0]


# Must match itemscraper/get_spells_retro.py
RANDOM_ELEMENT_LABEL = 'Hit in one random element'

# The generator heads the rows of a placed thing; must match PLACED_LABELS there
PLACED_LABEL = re.compile(
    r'^((?:Trap|Glyph|Bomb) (?:damage|heals))(?: - (.+))?$')


def _draw_is_random(aggregates):
    """True when the game draws the element, not the caster."""
    return any(label == RANDOM_ELEMENT_LABEL
               for label, _indices in (aggregates or []))


def element_runs(aggregates, effects):
    """Runs of (label, indices) groups, each the element faces of one hit."""
    aggregates = [(label, indices) for label, indices in (aggregates or [])
                  if not all(index < len(effects)
                             and effects[index].element.startswith('buff')
                             for index in indices)]
    if len(aggregates) < 2:
        return []
    runs = []
    run = []
    seen = set()
    for label, indices in aggregates:
        if len(indices) != 1 or indices[0] >= len(effects):
            return []
        element = effects[indices[0]].element
        # A placed thing's rows are a hit of their own, never a face of the last
        if element in seen or PLACED_LABEL.match(label or ''):
            if len(run) > 1:
                runs.append(run)
            run, seen = [], set()
        seen.add(element)
        run.append((label, list(indices)))
    if len(run) > 1:
        runs.append(run)
    return runs


def _element_alternatives(aggregates, effects):
    """Groups of a best-element spell, or None for a stacking spell."""
    runs = [[set(indices) for _label, indices in run]
            for run in element_runs(aggregates, effects)]
    if not runs:
        return None
    return _run_that_hurts(runs, effects)


def _first_group_that_hurts(aggregates, hits):
    """First aggregate group that hits; a heals-only group is the ally half."""
    def frappe(indices):
        return any(not getattr(effect, 'heals', False)
                   for index, effect in hits
                   if index in indices
                   and (effect.min_dam or effect.max_dam))

    for _label, indices in aggregates:
        groupe = set(indices)
        if frappe(groupe):
            return groupe
    return set(aggregates[0][1])


def scored_group_label(digest, effects, waiting_rows=()):
    """Label of the aggregate group the turn scored, or ''."""
    aggregates = getattr(digest, 'aggregates', None)
    if not aggregates or len(aggregates) < 2:
        return ''
    if _element_alternatives(aggregates, effects) is not None:
        return ''
    hits = [(index, effect) for index, effect in enumerate(effects)
            if not effect.element.startswith('buff')
            and index not in waiting_rows]
    retenu = _first_group_that_hurts(aggregates, hits)
    for label, indices in aggregates:
        if set(indices) == retenu:
            return label
    return ''


def rows_that_always_land(digest, effects, waiting_rows=()):
    """Hitting rows outside every group, when the kept group only heals."""
    if _element_alternatives(digest.aggregates, effects) is not None:
        return []
    if not digest.aggregates:
        return []
    attente = set(waiting_rows or ())
    hits = [(index, effect) for index, effect in enumerate(effects)
            if not effect.element.startswith('buff') and index not in attente]
    retenu = _first_group_that_hurts(digest.aggregates, hits)
    dedans = [effect for index, effect in hits
              if index in retenu and (effect.min_dam or effect.max_dam)]
    if not dedans:
        return []
    if any(not getattr(effect, 'heals', False) for effect in dedans):
        return []
    return _hitting_row_indexes_outside_every_group(digest.aggregates, hits)


def _hitting_row_indexes_outside_every_group(aggregates, hits):
    """Hitting rows no aggregate group covers."""
    couvertes = set()
    for _label, indices in aggregates or []:
        couvertes |= set(indices)
    return [index for index, effect in hits
            if index not in couvertes
            and not getattr(effect, 'heals', False)
            and (effect.min_dam or effect.max_dam)]


class WeaponCastable(object):
    """The equipped weapon, cast like a spell but scored as a weapon."""

    is_spell = False
    random_draw = False
    at_highest_rank = True
    stacks = 1
    spell_id = None

    def __init__(self, weapon, crit=False):
        self.weapon = weapon
        self.name = weapon.name
        self.cost = weapon.ap
        # Retro weapons have no uses per turn
        self.limit = getattr(weapon, 'uses_per_turn', None)
        element = getattr(weapon, 'element_maged', None) or NEUTRAL

        def swing(rows):
            hits = (rows or {}).get(element) or (rows or {}).get(NEUTRAL) or []
            kept = [hit for hit in hits if hit.min_dam or hit.max_dam]
            return [kept] if kept else []

        self.plain_alternatives = swing(weapon.non_crit_hits)
        self.crit_alternatives = swing(weapon.crit_hits)
        self.alternatives = (self.crit_alternatives if crit
                             else self.plain_alternatives)
        self.hits = self.alternatives[0] if self.alternatives else []
        self.crit_rate = getattr(weapon, 'crit_chance', None) or 0
        self.buffs = []

    def buff_deltas(self, count):
        return {}


class Castable(object):

    is_spell = True

    def __init__(self, spell, level_index, crit):
        self.spell = spell
        self.name = spell.name
        self.spell_id = spell.spell_id
        self.cost = spell.ap_cost(level_index)
        digest = spell.get_effects_digest()
        rows = digest.crit_dams if crit else digest.non_crit_dams
        self.effects = rows[level_index] if level_index < len(rows) else []
        self.buffs = [effect for effect in self.effects
                      if effect.element.startswith('buff')]

        # Rows waiting on something the cast does not do, like a push (Noa)
        waiting_rows = set(getattr(spell, 'conditional', None) or {})

        def landed(effects):
            """The damage a cast can land, one list per alternative."""
            hits = [(index, effect) for index, effect in enumerate(effects)
                    if not effect.element.startswith('buff')
                    and index not in waiting_rows]
            # Aggregate groups are alternatives, a cast lands one
            groups = _element_alternatives(digest.aggregates, effects)
            par_paliers = groups is None and bool(digest.aggregates)
            if groups is None:
                groups = ([_first_group_that_hurts(digest.aggregates, hits)]
                          if digest.aggregates else [None])
            # Missing rows are stored as 0 to 0 and would still get flat damage
            out = []
            for wanted in groups:
                kept = [effect for index, effect in hits
                        if (wanted is None or index in wanted)
                        and (effect.min_dam or effect.max_dam)]
                if par_paliers and kept and all(
                        getattr(effect, 'heals', False) for effect in kept):
                    dehors = rows_that_always_land(digest, effects,
                                                   waiting_rows)
                    if dehors:
                        kept = [effects[index] for index in dehors]
                if kept:
                    out.append(kept)
            return out

        def at_level(rows):
            return landed(rows[level_index] if level_index < len(rows) else [])

        def waiting_at(rows):
            """The rows the cast leaves for later, with what each waits for."""
            effects = rows[level_index] if level_index < len(rows) else []
            return [(effect, (spell.conditional or {})[index])
                    for index, effect in enumerate(effects)
                    if index in waiting_rows
                    and (effect.min_dam or effect.max_dam)]

        def late_at(rows, critical=False):
            """The rows that land, but not now, with when each does."""
            effects = rows[level_index] if level_index < len(rows) else []
            when_by_row = getattr(spell, 'delayed', None) or {}
            if critical:
                own = getattr(spell, 'delayed_crit', None)
                if own is not None:
                    when_by_row = own
            return [(effect, when_by_row[index])
                    for index, effect in enumerate(effects)
                    if index in when_by_row
                    and (effect.min_dam or effect.max_dam)]

        def late_by_effect(rows, critical=False):
            return {id(effect): when
                    for effect, when in late_at(rows, critical)}

        self.waiting_plain = waiting_at(digest.non_crit_dams)
        self.waiting_crit = waiting_at(digest.crit_dams)
        self.delayed_plain = late_at(digest.non_crit_dams)
        self.delayed_crit = late_at(digest.crit_dams, critical=True)
        # Late rows by identity: an aggregate spell is scored on one group only
        self.late_by_effect = {}
        self.late_by_effect.update(late_by_effect(digest.non_crit_dams))
        self.late_by_effect.update(late_by_effect(digest.crit_dams,
                                                  critical=True))
        # Filled in by castable_spells
        self.pushes = False
        self.push_cells = 0
        self.push_needs_state = None
        self.strips_pushback_resist = 0
        self.plain_alternatives = at_level(digest.non_crit_dams)
        self.crit_alternatives = at_level(digest.crit_dams)
        self.alternatives = (self.crit_alternatives if crit
                             else self.plain_alternatives)
        self.hits = self.alternatives[0] if self.alternatives else []
        self.stacked = bool(digest.aggregates)
        rows = digest.non_crit_dams
        self.scored_group = scored_group_label(
            digest, rows[level_index] if level_index < len(rows) else [],
            waiting_rows)
        casting = spell.casting or {}
        crit_rates = casting.get('crit') or []
        self.crit_rate = (crit_rates[level_index]
                          if level_index < len(crit_rates) else 0)
        limits = [casting.get(key, [None] * (level_index + 1))[level_index]
                  for key in ('per_turn', 'per_target')]
        # A spell on a cooldown cannot come back the same turn
        cooldown = casting.get('cooldown', [None] * (level_index + 1))[level_index]
        if cooldown:
            limits.append(1)
        limits = [limit for limit in limits if limit]
        self.limit = min(limits) if limits else None
        self.stacks = spell.stacks or 1
        # Drawn by the game: the turn averages the faces
        self.random_draw = _draw_is_random(digest.aggregates)

    def buff_deltas(self, count):
        deltas = {}
        capped = min(count, self.stacks)
        for effect in self.buffs:
            parts = effect.element.split('_')
            stat = parts[1]
            scaled_as = stat
            if len(parts) > 2:
                # Skip glyph/trap buffs; Weapon Skill's Power is weapon only
                if parts[2] != 'weapon' or stat != 'pow':
                    continue
                stat = 'powweap'
            value = _buff_value(self.spell.buff_scaling, scaled_as, capped,
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


def crit_chance(base_rate, stats, game_version):
    """Odds of a critical, 0 to 1."""
    if not base_rate:
        return 0.0
    bonus = stats.get('ch', 0) or 0
    if game_version == 'retro':
        return 1.0 / retro_critical_x(base_rate, bonus, stats.get('agi', 0) or 0)
    return min(100, max(1, base_rate + bonus)) / 100.0


def retro_critical_x(base_rate, bonus, agility):
    """The X of 1/X the Retro client shows as its current critical chance."""
    x = base_rate - max(0, bonus)
    agility = max(0, agility)
    if agility:
        x = min(x, x * math.e * 1.1 / math.log(agility + 12))
    return math.floor(max(x, 2))


def final_multiplier(stats):
    """Final damage %, applied after calculate_damage."""
    multiplier = (100.0 + stats.get('final', 0)) / 100.0
    negative = stats.get('negfinal', 0)
    if negative:
        multiplier = multiplier * (100.0 - negative) / 100.0
    return multiplier


def buffs_in_force(char_class, char_level, game_version, buff_state,
                   levels=None):
    """Stat deltas of the ticked buffs, stored as 'n2' or 'c1' (crit, stacks)."""
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
    """(spell, stacks, crit) per ticked entry, class or shared bucket."""
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
    """Rank to read a spell at: the picked one, else the highest reachable."""
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
    """Class spells only; `levels` is {spell name: rank index}."""
    from chardata.spell_reference import (push_info, pushing_spell_ids,
                                          strips_pushback_resist)
    by_class = get_damage_spells_for_version(game_version)
    pushing = pushing_spell_ids(game_version)
    spells = by_class.get(char_class, [])
    summon_only = ONLY_HITS_A_SUMMON.get(game_version) or {}
    out = []
    for spell in spells:
        if not spell.casting or char_level < spell.level_req[0]:
            continue
        if spell.spell_id in summon_only:
            continue
        level_index = _chosen_level(levels, spell, char_level)
        castable = Castable(spell, level_index, crit)
        castable.at_highest_rank = (
            level_index == _decide_spell_level(spell.level_req, char_level))
        if not castable.cost or (not castable.hits and not castable.buffs):
            continue
        castable.pushes = spell.spell_id in pushing
        info = push_info(game_version, spell.spell_id, level_index) or {}
        castable.push_cells = info.get('cells') or 0 if info.get('damaging') else 0
        castable.push_needs_state = (info.get('needs') or {}).get('state')
        castable.strips_pushback_resist = strips_pushback_resist(
            game_version, spell.spell_id, level_index)
        out.append(castable)
    return out


def _variant_partners(spells, game_version):
    """index -> indices of its variant pair; only one of a pair is armed."""
    if not game_version:
        return {}
    by_variant = {}
    for index, spell in enumerate(spells):
        variant = variant_of(game_version, getattr(spell, 'spell_id', None))
        if variant is not None:
            by_variant.setdefault(variant, []).append(index)
    partners = {}
    for indices in by_variant.values():
        if len(indices) < 2:
            continue
        for index in indices:
            partners[index] = frozenset(other for other in indices
                                        if other != index)
    return partners


def conditional_extras(stats, spells, order, crit=False, standing=None,
                       game_version=None, caster_level=0, pushback=False):
    """[(spell name, trigger, damage)] a push could add, outside the total."""
    if not order:
        return []
    by_name = {spell.name: spell for spell in spells}
    cast_names = [name for name, _damage in order]
    triggers = set()
    if any(getattr(by_name.get(name), 'pushes', False) for name in cast_names):
        triggers.add('pushback')
    if not triggers:
        return []

    counts = {}
    for name in cast_names:
        counts[name] = counts.get(name, 0) + 1
    buffed = dict(stats)
    standing = standing or {}
    for name, times in counts.items():
        other = by_name.get(name)
        if other is None or not other.buffs:
            continue
        already = min(standing.get(name, 0), other.stacks)
        reached = min(already + times, other.stacks)
        if reached <= already:
            continue
        was = other.buff_deltas(already) if already else {}
        for stat, value in other.buff_deltas(reached).items():
            buffed[stat] = buffed.get(stat, 0) + value - was.get(stat, 0)
    multiplier = final_multiplier(buffed)

    # Stripped pushback resistance adds to every push of the turn
    stripped = max([getattr(by_name.get(name), 'strips_pushback_resist', 0) or 0
                    for name in cast_names] or [0])

    out = []
    for name in sorted(set(cast_names)):
        castable = by_name.get(name)
        cells = getattr(castable, 'push_cells', 0)
        gated = getattr(castable, 'push_needs_state', None)
        # Skip pushes the turn counted; a state-gated push is never counted
        if cells and caster_level and (not pushback or gated):
            dealt = pushback_damage(caster_level,
                                    buffed.get('pshdam', 0) or 0,
                                    cells, target_resistance=-stripped,
                                    game_version=game_version)
            if dealt:
                trigger = ('pushback into an obstacle at a state'
                           if getattr(castable, 'push_needs_state', None)
                           else 'pushback into an obstacle')
                out.append((name, trigger, dealt * counts[name]))
        rows = getattr(castable, 'waiting_crit' if crit else 'waiting_plain',
                       None) or []
        for effect, trigger in rows:
            if trigger not in triggers:
                continue
            gained = (_average(calculate_damage([copy.copy(effect)], buffed,
                                                crit, castable.is_spell))
                      * multiplier)
            if gained:
                out.append((name, trigger, gained * counts[name]))
    return out


def delayed_damage(stats, spells, order, crit=False, standing=None,
                   game_version=None):
    """{spell name: damage} dealt at the start or end of a turn (poisons)."""
    if not order:
        return {}
    by_name = {spell.name: spell for spell in spells}
    standing = standing or {}

    # In cast order, with the buffs standing at each cast, like the search
    out = {}
    seen = {}
    for name, _damage in order:
        castable = by_name.get(name)
        rows = getattr(castable, 'delayed_crit' if crit else 'delayed_plain',
                       None) or []
        if rows:
            buffed = dict(stats)
            for other_name, times in seen.items():
                other = by_name.get(other_name)
                if other is None or not other.buffs:
                    continue
                already = min(standing.get(other_name, 0), other.stacks)
                reached = min(already + times, other.stacks)
                if reached <= already:
                    continue
                was = other.buff_deltas(already) if already else {}
                for stat, value in other.buff_deltas(reached).items():
                    buffed[stat] = (buffed.get(stat, 0) + value
                                    - was.get(stat, 0))
            multiplier = final_multiplier(buffed)
            late = getattr(castable, 'late_by_effect', None) or {}

            def worth(alternatives, critical):
                """(scored, late) of the alternative _damage_of would take."""
                best = (0.0, 0.0)
                for alternative in alternatives or []:
                    total = 0.0
                    delayed = 0.0
                    for effect in alternative:
                        value = (_average(calculate_damage([copy.copy(effect)],
                                                           buffed, critical,
                                                           castable.is_spell))
                                 * multiplier)
                        total += value
                        if id(effect) in late:
                            delayed += value
                    if total > best[0]:
                        best = (total, delayed)
                return best

            if crit:
                gained = worth(castable.alternatives, True)[1]
            else:
                odds = crit_chance(getattr(castable, 'crit_rate', 0), buffed,
                                   game_version)
                plain = worth(getattr(castable, 'plain_alternatives', None)
                              or castable.alternatives, False)[1]
                critical = (worth(getattr(castable, 'crit_alternatives', None),
                                  True)[1] if odds else 0.0)
                gained = (plain * (1 - odds) + critical * odds
                          if critical else plain)
            if gained:
                out[name] = out.get(name, 0.0) + gained
        seen[name] = seen.get(name, 0) + 1
    return out


def delayed_moments(spells, order, crit=False):
    """{spell name: [when, ...]} for the rows a cast leaves for later."""
    by_name = {spell.name: spell for spell in spells}
    out = {}
    for name, _damage in order or []:
        castable = by_name.get(name)
        rows = getattr(castable, 'delayed_crit' if crit else 'delayed_plain',
                       None) or []
        moments = []
        for _effect, when in rows:
            if when not in moments:
                moments.append(when)
        if moments:
            out[name] = moments
    return out


# No map: on average an obstacle stops half the push
PUSH_STOPPED_ON_AVERAGE = 0.5


def push_value(castable, stats, game_version, caster_level):
    """What one cast's push is worth on average, 0 when it cannot be told."""
    cells = getattr(castable, 'push_cells', 0)
    if not cells or not caster_level:
        return 0.0
    # State-gated push (Torrent pushes at High Tide, pulls at Low Tide)
    if getattr(castable, 'push_needs_state', None):
        return 0.0
    dealt = pushback_damage(caster_level, stats.get('pshdam', 0) or 0, cells,
                            game_version=game_version)
    return (dealt or 0.0) * PUSH_STOPPED_ON_AVERAGE


def best_turn(stats, spells, ap, crit=False, standing=None, game_version=None,
              pushback=False, caster_level=0):
    """(total, [(spell name, damage), ...]) for the best order fitting the AP."""
    stats = dict(stats)
    # Ticked buffs are already in stats: a recast adds only the difference
    standing = standing or {}
    spells = [spell for spell in spells if spell.cost and spell.cost <= ap]
    if not spells:
        return 0.0, []
    partners = _variant_partners(spells, game_version)
    # A cast's damage only depends on the buff stacks standing, cache on those
    buff_indexes = tuple(index for index, spell in enumerate(spells)
                         if spell.buffs)
    scores = {}

    def damage_of(spell, counts):
        if not spell.alternatives and not (pushback
                                           and getattr(spell, 'push_cells', 0)):
            return 0.0
        key = (spell.name,
               tuple(min(counts[index], spells[index].stacks)
                     for index in buff_indexes))
        if key in scores:
            return scores[key]
        value = _damage_of(spell, counts)
        scores[key] = value
        return value

    def _damage_of(spell, counts):
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
        # Weapon Skill only lifts the weapon's Power
        if not spell.is_spell and buffed.get('powweap'):
            buffed['pow'] = buffed.get('pow', 0) + buffed['powweap']
        multiplier = final_multiplier(buffed)

        def scored(alternatives, critical):
            # Caster picks the best element; a game draw averages the faces
            gains = []
            for alternative in alternatives:
                rows = [copy.copy(effect) for effect in alternative]
                gains.append(_average(calculate_damage(rows, buffed, critical,
                                                       spell.is_spell))
                             * multiplier)
            if not gains:
                return 0.0
            if getattr(spell, 'random_draw', False):
                return max(0.0, sum(gains) / len(gains))
            return max(0.0, max(gains))

        pushed = (push_value(spell, buffed, game_version, caster_level)
                  if pushback else 0.0)
        if crit:
            return scored(spell.alternatives, True) + pushed
        odds =crit_chance(getattr(spell, 'crit_rate', 0), buffed, game_version)
        plain = scored(getattr(spell, 'plain_alternatives', spell.alternatives),
                       False)
        if not odds:
            return plain + pushed
        critical = scored(getattr(spell, 'crit_alternatives', None) or [], True)
        if not critical:
            return plain + pushed
        return plain * (1 - odds) + critical * odds + pushed

    best = {}
    # Counts past a spell's stack cap and cast limit change nothing: fold them
    caps =tuple(max(spell.stacks or 1, spell.limit or 0, 1)
                 for spell in spells)

    def fold(counts):
        return tuple(min(count, cap) for count, cap in zip(counts, caps))

    def search(ap_left, counts, depth):
        key = (ap_left, fold(counts))
        if key in best:
            return best[key]
        outcome = (0.0, ())
        if depth < MAX_CASTS:
            for index, spell in enumerate(spells):
                if spell.cost > ap_left:
                    continue
                if spell.limit and counts[index] >= spell.limit:
                    continue
                if any(counts[other] for other in partners.get(index, ())):
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
