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

"""Objective terms for weapon hits: what a weapon's swings add to the best turn, in played characteristic points."""

import logging
import pickle

from fashionistapulp.item_effects import played_characteristics

logger = logging.getLogger(__name__)

VERSIONS = ('dofus3',)
CHARACTERISTIC_STEP = 20
SEARCHED = 3


def weapon_swing(item, stats):
    """The weapon as a castable of the turn, potion element picked on these stats; None without hits."""
    from chardata.spell_combo import WeaponCastable
    from fashionistapulp.modelresult import ModelResultItem
    piece = ModelResultItem(item)
    if not getattr(piece, 'ap', 0) or not hasattr(piece, 'non_crit_hits'):
        return None
    piece.mage_weapon_smartly(stats)
    castable = WeaponCastable(piece)
    return castable if castable.alternatives else None


def candidate_weapons(structure, level, forbidden):
    return [item for item in structure.get_available_items_list()
            if structure.get_type_name_by_id(item.type) == 'Weapon'
            and item.level <= level and item.id not in forbidden]


class TurnReader(object):
    """best_turn on one set of stats and spells; spell-only turns kept by AP."""

    def __init__(self, stats, spells, ap, game_version, level):
        from chardata.spell_combo import best_turn
        self.best_turn = best_turn
        self.stats = stats
        self.spells = spells
        self.ap = ap
        self.game_version = game_version
        self.level = level
        self._spells_only = {}
        self._swings = {}

    def _cast(self, castables, ap, stats=None, deltas=None):
        used = dict(self.stats if stats is None else stats)
        for key, value in (deltas or {}).items():
            used[key] = used.get(key, 0) + value
        return self.best_turn(used, castables, ap, standing={}, game_version=self.game_version,
                              pushback=False, caster_level=self.level)

    def full(self, weapon=None, deltas=None):
        castables = self.spells + ([weapon] if weapon is not None else [])
        return self._cast(castables, self.ap, deltas=deltas)[0]

    def spells_only(self, ap):
        """(best spell-only turn within ap, the stats once its buffs are cast)."""
        if ap <= 0:
            return 0.0, self.stats
        if ap not in self._spells_only:
            total, order = self._cast(self.spells, ap)
            self._spells_only[ap] = (total, self._buffed(order))
        return self._spells_only[ap]

    def _buffed(self, order):
        counts = {}
        for name, _damage in order:
            counts[name] = counts.get(name, 0) + 1
        stats = dict(self.stats)
        for spell in self.spells:
            if spell.buffs and counts.get(spell.name):
                for stat, value in spell.buff_deltas(counts[spell.name]).items():
                    stats[stat] = stats.get(stat, 0) + value
        return stats

    def one_swing(self, weapon, ap):
        """One swing after the buffs of the spell-only turn within ap."""
        key = (id(weapon), ap)
        if key not in self._swings:
            self._swings[key] = self._cast([weapon], weapon.cost,
                                           stats=self.spells_only(ap)[1])[0]
        return self._swings[key]

    def swing_counts(self, weapon):
        cost = weapon.cost
        if not cost or cost > self.ap:
            return 0
        most = self.ap // cost
        return min(most, weapon.limit) if weapon.limit else most

    def lower_gain(self, weapon):
        """The spell-only turn on the AP left, then the swings after its buffs."""
        without = self.spells_only(self.ap)[0]
        best = without
        for swings in range(1, self.swing_counts(weapon) + 1):
            left = self.ap - swings * weapon.cost
            best = max(best, self.spells_only(left)[0] + swings * self.one_swing(weapon, left))
        return best - without

    def gain(self, weapon):
        """The turn with the weapon less the turn without it, from best_turn itself."""
        if not self.swing_counts(weapon):
            return 0.0
        return self.full(weapon) - self.spells_only(self.ap)[0]


def stat_lines_value(item, weights, structure):
    return sum(weights.get(structure.get_stat_by_id(stat_id).key, 0) * value
               for stat_id, value in item.stats)


def terms_on_stats(reader, weights, worn, weapons_by_id, line_values=None, searched=SEARCHED):
    """{item id: term} on one set of stats; the shortlist and the worn weapon get best_turn's gain."""
    played = played_characteristics(weights)
    if not played:
        return {}
    with_worn = reader.full(worn)
    raised = reader.full(worn, {key: CHARACTERISTIC_STEP for key in played})
    per_point = (raised - with_worn) / float(CHARACTERISTIC_STEP * len(played))
    if per_point <= 0:
        return {}
    paid = sum(weights.get(key, 0) for key in played) / float(len(played))
    gains = {item_id: reader.lower_gain(weapon) for item_id, weapon in weapons_by_id.items()}
    line_values = line_values or {}

    def estimate(item_id):
        return gains[item_id] / per_point * paid + line_values.get(item_id, 0)
    shortlist = sorted(gains, key=estimate, reverse=True)[:searched]
    worn_id = getattr(getattr(worn, 'weapon', None), 'id', None)
    if worn_id in weapons_by_id:
        shortlist.append(worn_id)
    for item_id in set(shortlist):
        gains[item_id] = max(gains[item_id], reader.gain(weapons_by_id[item_id]))
    return {item_id: gain / per_point * paid for item_id, gain in gains.items() if gain > 0}


def weapon_hit_terms(char, result, model_input):
    """{weapon item id: objective term}, read on the set `result` wears; {} when weapon hits do not apply."""
    game_version = getattr(char, 'game_version', None)
    if result is None or game_version not in VERSIONS:
        return {}
    if 'weapon' in (model_input.empty_slot_types or []) or (model_input.locked_equips or {}).get('weapon'):
        return {}
    weights = model_input.objective_values
    if not played_characteristics(weights):
        return {}
    from chardata.solution import get_solution_from_minimal
    from chardata.spell_combo import castable_spells, combat_ap
    from chardata.spell_modifiers import worn_spell_modifiers
    from chardata.spells_view import _weapon_castable
    from chardata.temporix_mode import solution_uses_temporix
    from fashionistapulp.structure import get_structure
    try:
        solution = get_solution_from_minimal(char, pickle.loads(pickle.dumps(result)),
                                             refresh_base_stats=False)
        stats = dict(solution.get_stats_total())
    except Exception:
        logger.exception('could not read the first set of char %s for weapon hit terms',
                         getattr(char, 'id', '?'))
        return {}
    ap = combat_ap(stats.get('ap'), game_version,
                   temporix=solution_uses_temporix(solution, game_version))
    spells = castable_spells(char.char_class, char.level, game_version,
                             modifiers=worn_spell_modifiers(solution, game_version))
    if not ap or not spells:
        return {}
    structure = get_structure(game_version)
    weapons = {}
    for item in candidate_weapons(structure, char.level, model_input.forbidden_equips or ()):
        swing = weapon_swing(item, stats)
        # Without a uses-per-turn value the swings would fill the whole turn
        if swing is not None and swing.limit:
            weapons[item.id] = swing
    reader = TurnReader(stats, spells, ap, game_version, char.level)
    line_values = {item_id: stat_lines_value(structure.get_item_by_id(item_id), weights, structure)
                   for item_id in weapons}
    return terms_on_stats(reader, weights, _weapon_castable(solution), weapons, line_values)
