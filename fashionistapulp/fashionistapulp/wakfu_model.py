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

"""Pick the best legal set of Wakfu gear for a character."""

from __future__ import annotations

import collections

from .game_versions import get_game_version
from .lpproblem import LpProblem2
from .wakfu_slots import SLOTS
from .wakfu_stats import BASE_VALUES, CRITICAL_HIT_FLOOR_PERCENT, \
    OUT_OF_COMBAT_CAPS

# LP variable: this item, worn in this slot
WORN = 'w'
# LP variable: the set's AP total is this number
AP_TOTAL = 'apt'

# Stats a line spread over N elements may land on
SPREAD_FAMILIES = {
    'dmg_in_percent': ('dmg_fire_percent', 'dmg_water_percent',
                       'dmg_earth_percent', 'dmg_air_percent'),
    'res_in_percent': ('res_fire_percent', 'res_water_percent',
                       'res_earth_percent', 'res_air_percent'),
}

# Element stat: the generic stat of its family
FAMILY_OF = {element: generic for generic, family in SPREAD_FAMILIES.items()
             for element in family}


def same_item(item):
    """Key shared by every rarity of one item: its type and French title."""
    # Each rarity is its own id; the English title can differ between them
    # (Kralaring, Kringlove)
    return item.type, (item.localized_names or {}).get('fr') or item.name


class WakfuSet(dict):
    """{position: item} of a solve."""

    def __init__(self, worn=(), full_set_status=None, no_candidate=()):
        super().__init__(worn)
        # Status of the every-slot model when it gave no set, else None
        self.full_set_status = full_set_status
        self.no_candidate = tuple(no_candidate)

    @property
    def full_set_dropped(self):
        """True when the solve had to allow empty slots."""
        return self.full_set_status is not None


class WakfuBuild:
    """Best set at a level; `weights` is keyed by stats.key.

    ap_values: optional {AP total: worth}, base included; the set is then worth
    the entry of its AP total instead of weights['ap'] per AP.
    """

    def __init__(self, structure, level, weights, forbidden=(),
                 full_set=True, minimums=None, ap_values=None):
        self.structure = structure
        self.level = level
        self.weights = dict(weights)
        self.ap_values = None if ap_values is None else dict(ap_values)
        if self.ap_values is not None:
            self.weights.pop('ap', None)
        self.forbidden = set(forbidden)
        # Fill every slot, or slots worth 0 in the objective stay empty
        self.full_set = full_set
        # {stat key: lowest total, base values included}
        self.minimums = dict(minimums or {})
        self.full_set_status = None
        self.problem = None
        self._placements = []

    def _positions_of_type(self):
        """{type id: [position, ...]}"""
        places = collections.defaultdict(list)
        for type_id, position in self.structure.get_type_positions():
            places[type_id].append(position)
        return places

    def _candidates(self):
        """Every (item, position) a character of this level could wear."""
        places = self._positions_of_type()
        out = []
        for item in self.structure.get_available_items_list():
            if item.level > self.level or item.id in self.forbidden:
                continue
            for position in places.get(item.type, ()):
                out.append((item, position))
        return out

    def _stat_value(self, item, key):
        stat = self.structure.get_stat_by_key(key)
        if stat is None:
            return 0
        return sum(value for stat_id, value in item.stats
                   if stat_id == stat.id)

    def _key_of(self, stat_id):
        stat = self.structure.get_stat_by_id(stat_id)
        return stat.key if stat is not None else None

    def _element_weights(self, generic):
        """{element stat: weight}, dmg_in_percent's or res_in_percent's added."""
        extra = self.weights.get(generic, 0)
        return {name: self.weights.get(name, 0) + extra
                for name in SPREAD_FAMILIES[generic]}

    def _lands_on(self, generic, value, elements):
        """Elements a spread line feeds: the best N, the worst N for a loss."""
        weights = self._element_weights(generic)
        sign = -1 if value >= 0 else 1
        ranked = sorted(weights, key=lambda name: sign * weights[name])
        return ranked[:max(0, elements)]

    def _plain_lines(self, item):
        """(stat id, value) rows of an item, its spread lines left out."""
        # Spread lines are also rows of item.stats
        spread = collections.Counter((stat_id, value) for stat_id, value, _e
                                     in item.element_spread or ())
        for stat_id, value in item.stats:
            if spread[(stat_id, value)]:
                spread[(stat_id, value)] -= 1
                continue
            yield stat_id, value

    def _plain_weight(self, key):
        """Worth of one point of a line that is not spread."""
        if key in SPREAD_FAMILIES:
            # Elemental mastery and resistance apply to every element
            return sum(self._element_weights(key).values())
        if key in FAMILY_OF:
            return self._element_weights(FAMILY_OF[key])[key]
        return self.weights.get(key, 0)

    def _spread_weight(self, key, value, elements):
        if key not in SPREAD_FAMILIES:
            return self.weights.get(key, 0)
        weights = self._element_weights(key)
        return sum(weights[name]
                   for name in self._lands_on(key, value, elements))

    def _worth(self, item):
        total = 0
        for stat_id, value in self._plain_lines(item):
            total += value * self._plain_weight(self._key_of(stat_id))
        for stat_id, value, elements in item.element_spread or ():
            total += value * self._spread_weight(self._key_of(stat_id), value,
                                                 elements)
        return total

    def build(self):
        self.problem = LpProblem2()
        self._placements = self._candidates()
        for item, position in self._placements:
            self.problem.setup_variable(WORN, self._name(item, position), 0, 1)

        self._one_item_per_slot()
        self._one_copy_of_an_item()
        self._two_handed_empties_the_off_hand()
        self._one_relic_and_one_epic()
        self._caps()
        self._critical_hit_floor()
        self._minimums()
        self._ap_total()
        self._objective()
        return self

    def _name(self, item, position):
        return '%d_%s' % (item.id, position)

    def _parcels(self, placements, coefficient=1):
        return [(coefficient, WORN, self._name(item, position))
                for item, position in placements]

    def _one_item_per_slot(self):
        """One item per slot, exactly one when full_set."""
        by_slot = collections.defaultdict(list)
        for item, position in self._placements:
            by_slot[position].append((item, position))
        for position in SLOTS:
            if not by_slot[position]:
                continue
            parcels = self._parcels(by_slot[position])
            if self.full_set and position != 'SECOND_WEAPON':
                # Off hand can stay empty for two-handed weapons
                self.problem.restriction_eq(1, parcels)
            else:
                self.problem.restriction_lt_eq(1, parcels)

    def _one_copy_of_an_item(self):
        """One copy of a ring, in either hand, its other rarities included."""
        doubles = get_game_version('wakfu').rings_can_double
        by_item = collections.defaultdict(list)
        for item, position in self._placements:
            by_item[same_item(item)].append((item, position))
        for placements in by_item.values():
            if len({position for _item, position in placements}) > 1:
                self.problem.restriction_lt_eq(
                    2 if doubles else 1, self._parcels(placements))

    def _two_handed_empties_the_off_hand(self):
        off_hand = [(item, position) for item, position in self._placements
                    if position == 'SECOND_WEAPON']
        if not off_hand:
            return
        for item, position in self._placements:
            if position != 'FIRST_WEAPON':
                continue
            if 'two_handed' not in (item.flags or ()):
                continue
            self.problem.restriction_lt_eq(
                1, self._parcels([(item, position)]) + self._parcels(off_hand))

    def _one_relic_and_one_epic(self):
        for flag in ('relic', 'epic'):
            wearing = [(item, position) for item, position in self._placements
                       if flag in (item.flags or ())]
            if wearing:
                self.problem.restriction_lt_eq(1, self._parcels(wearing))

    def _caps(self):
        """AP, MP and WP caps, base values included."""
        for name, cap in OUT_OF_COMBAT_CAPS.items():
            key = name.lower()
            parcels = []
            for item, position in self._placements:
                value = self._stat_value(item, key)
                if value:
                    parcels.append((value, WORN, self._name(item, position)))
            if parcels:
                self.problem.restriction_lt_eq(cap - BASE_VALUES[name], parcels)

    def _critical_hit_floor(self):
        """Critical hit floor on the gear sum, as a <= on the negated sum."""
        parcels = []
        for item, position in self._placements:
            value = self._stat_value(item, 'ferocity')
            if value:
                parcels.append((-value, WORN, self._name(item, position)))
        if parcels:
            self.problem.restriction_lt_eq(-CRITICAL_HIT_FLOOR_PERCENT, parcels)

    def _minimums(self):
        """Lowest totals, base values included, as a <= on the negated sums."""
        for key, lowest in sorted(self.minimums.items()):
            parcels = []
            for item, position in self._placements:
                value = self._stat_value(item, key)
                if value:
                    parcels.append((-value, WORN, self._name(item, position)))
            if parcels:
                self.problem.restriction_lt_eq(
                    BASE_VALUES.get(key.upper(), 0) - lowest, parcels)

    def _ap_totals(self):
        """Every AP total a set can reach, base included, up to the cap."""
        lowest = collections.defaultdict(int)
        for item, position in self._placements:
            lowest[position] = min(lowest[position], self._stat_value(item, 'ap'))
        return range(BASE_VALUES['AP'] + sum(lowest.values()),
                     OUT_OF_COMBAT_CAPS['AP'] + 1)

    def _ap_total(self):
        """One AP_TOTAL variable at 1, the one the worn AP adds up to."""
        if self.ap_values is None:
            return
        totals = self._ap_totals()
        for total in totals:
            self.problem.setup_variable(AP_TOTAL, total, 0, 1)
        self.problem.restriction_eq(1, [(1, AP_TOTAL, total) for total in totals])
        parcels = [(BASE_VALUES['AP'] - total, AP_TOTAL, total) for total in totals]
        for item, position in self._placements:
            value = self._stat_value(item, 'ap')
            if value:
                parcels.append((value, WORN, self._name(item, position)))
        self.problem.restriction_eq(0, parcels)

    def _objective(self):
        self.problem.init_objective_function()
        for item, position in self._placements:
            worth = self._worth(item)
            if worth:
                self.problem.add_to_of(WORN, self._name(item, position), worth)
        if self.ap_values is not None:
            floor = min(self.ap_values.values())
            for total in self._ap_totals():
                self.problem.add_to_of(AP_TOTAL, total, self.ap_values.get(total, floor))
        self.problem.finish_objective_function()

    def solve(self):
        """WakfuSet or None; drops full_set when that model gives no set."""
        if self.problem is None:
            self.build()
        self.problem.run()
        if self.problem.get_status() != 'Optimal' and self.full_set:
            self.full_set_status = self.problem.get_status()
            self.full_set = False
            self.problem = None
            self.build()
            self.problem.run()
        if self.problem.get_status() != 'Optimal':
            return None
        chosen = self.problem.get_result()
        placed = {position for _item, position in self._placements}
        worn = WakfuSet(full_set_status=self.full_set_status,
                        no_candidate=[slot for slot in SLOTS
                                      if slot not in placed])
        for item, position in self._placements:
            name = '%s_%s' % (WORN, self._name(item, position))
            if (chosen.get(name) or 0) > 0.5:
                worn[position] = item
        return worn

    def spread_lines(self, worn):
        """[(position, item, key, value, elements it landed on)] of a set."""
        out = []
        for position in sorted(worn):
            item = worn[position]
            for stat_id, value, elements in item.element_spread or ():
                key = self._key_of(stat_id)
                if key in SPREAD_FAMILIES:
                    out.append((position, item, key, value,
                                self._lands_on(key, value, elements)))
        return out

    def where_the_spread_lands(self, worn):
        """{stat key: total} for the elements a build's spread lines feed."""
        landing = collections.Counter()
        for _position, _item, _key, value, landed in self.spread_lines(worn):
            for name in landed:
                landing[name] += value
        return landing

    def totals(self, worn):
        """Stat totals of a set, base values included, spread lines landed."""
        out = collections.Counter()
        for item in worn.values():
            for stat_id, value in self._plain_lines(item):
                key = self._key_of(stat_id)
                if key is not None:
                    out[key] += value
            for stat_id, value, _elements in item.element_spread or ():
                key = self._key_of(stat_id)
                if key is not None and key not in SPREAD_FAMILIES:
                    out[key] += value
        out.update(self.where_the_spread_lands(worn))
        for name, value in BASE_VALUES.items():
            out[name.lower()] += value
        return out
