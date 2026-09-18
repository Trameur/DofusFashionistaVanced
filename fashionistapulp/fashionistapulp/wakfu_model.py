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

# Stats a line spread over N elements may land on
SPREAD_FAMILIES = {
    'dmg_in_percent': ('dmg_fire_percent', 'dmg_water_percent',
                       'dmg_earth_percent', 'dmg_air_percent'),
    'res_in_percent': ('res_fire_percent', 'res_water_percent',
                       'res_earth_percent', 'res_air_percent'),
}


class WakfuBuild:
    """Best set at a level; `weights` is keyed by stats.key."""

    def __init__(self, structure, level, weights, forbidden=(),
                 full_set=True):
        self.structure = structure
        self.level = level
        self.weights = dict(weights)
        self.forbidden = set(forbidden)
        # Fill every slot, or slots worth 0 in the objective stay empty
        self.full_set = full_set
        self.problem = None
        self._placements = []
        self._by_item = {}

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
        for item in self.structure.get_items_list():
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

    def _spread_worth(self, stat_id, elements):
        """Spread lines land on the build's best elements: top N weights."""
        key = self._key_of(stat_id)
        family = SPREAD_FAMILIES.get(key)
        if family is None:
            return self.weights.get(key, 0)
        wanted = sorted((self.weights.get(name, 0) for name in family),
                        reverse=True)
        return sum(wanted[:max(0, elements)])

    def _worth(self, item):
        spread = list(item.element_spread or ())
        # Spread lines are also rows of item.stats, skip them in the plain sum
        separately = collections.Counter((stat_id, value)
                                         for stat_id, value, _e in spread)
        total = 0
        for stat_id, value in item.stats:
            if separately[(stat_id, value)]:
                separately[(stat_id, value)] -= 1
                continue
            total += self.weights.get(self._key_of(stat_id), 0) * value
        for stat_id, value, elements in spread:
            total += value * self._spread_worth(stat_id, elements)
        return total

    def build(self):
        self.problem = LpProblem2()
        self._placements = self._candidates()
        self._by_item = collections.defaultdict(list)
        for item, position in self._placements:
            self.problem.setup_variable(WORN, self._name(item, position), 0, 1)
            self._by_item[item.id].append((item, position))

        self._one_item_per_slot()
        self._one_copy_of_an_item()
        self._two_handed_empties_the_off_hand()
        self._one_relic_and_one_epic()
        self._caps()
        self._critical_hit_floor()
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
        """A ring may go in either hand, but only one of them at a time."""
        doubles = get_game_version('wakfu').rings_can_double
        for placements in self._by_item.values():
            if len(placements) > 1:
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
        """Critical hit floor, as a <= on the negated sum."""
        parcels = []
        for item, position in self._placements:
            value = self._stat_value(item, 'ferocity')
            if value:
                parcels.append((-value, WORN, self._name(item, position)))
        if parcels:
            self.problem.restriction_lt_eq(-CRITICAL_HIT_FLOOR_PERCENT, parcels)

    def _objective(self):
        self.problem.init_objective_function()
        for item, position in self._placements:
            worth = self._worth(item)
            if worth:
                self.problem.add_to_of(WORN, self._name(item, position), worth)
        self.problem.finish_objective_function()

    def solve(self):
        """{position: item}, or None; retries without full_set if infeasible."""
        if self.problem is None:
            self.build()
        self.problem.run()
        if self.problem.get_status() != 'Optimal' and self.full_set:
            self.full_set = False
            self.problem = None
            self.build()
            self.problem.run()
        if self.problem.get_status() != 'Optimal':
            return None
        chosen = self.problem.get_result()
        worn = {}
        for item, position in self._placements:
            name = '%s_%s' % (WORN, self._name(item, position))
            if (chosen.get(name) or 0) > 0.5:
                worn[position] = item
        return worn

    def where_the_spread_lands(self, worn):
        """{stat key: total} for the elements a build's spread lines feed."""
        landing = collections.Counter()
        for item in worn.values():
            for stat_id, value, elements in item.element_spread or ():
                family = SPREAD_FAMILIES.get(self._key_of(stat_id))
                if family is None:
                    continue
                wanted = sorted(family, key=lambda name: -self.weights.get(name, 0))
                for name in wanted[:max(0, elements)]:
                    landing[name] += value
        return landing

    def totals(self, worn):
        """Stat totals of a set, base values included."""
        out = collections.Counter()
        for item in worn.values():
            for stat_id, value in item.stats:
                stat = self.structure.get_stat_by_id(stat_id)
                if stat is not None:
                    out[stat.key] += value
        for name, value in BASE_VALUES.items():
            out[name.lower()] += value
        return out
