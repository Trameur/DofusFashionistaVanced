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
from .structure import fits_the_class
from .wakfu_criteria import base_values, start_state, state_holds, unlocking
from .wakfu_slots import (BLOCKED_BY_TWO_HANDED, EXCLUSIVE_PROPERTIES, SLOTS,
                          TWO_HANDED_FLAG)
from .wakfu_stats import OUT_OF_COMBAT_CAPS

# LP variable: this item, worn in this slot
WORN = 'w'
# LP variable: the set's AP total is this number
AP_TOTAL = 'apt'

# WakfuSet.status and WakfuBuild.reason
PROVEN = 'proven'
TIME_LIMIT = 'time limit'
INFEASIBLE = 'infeasible'

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


# One source of stat points, and the lowest and highest sum any set can take from it
Part = collections.namedtuple('Part', 'terms lowest highest')

# A stat's total: the base low and high, then the terms of every part
StatTotal = collections.namedtuple('StatTotal',
                                   'key low high terms lowest highest')


class WakfuSet(dict):
    """{position: item} of a solve."""

    def __init__(self, worn=(), full_set_status=None, no_candidate=(),
                 status=None):
        super().__init__(worn)
        # Status of the every-slot model when it gave no set, else None
        self.full_set_status = full_set_status
        self.no_candidate = tuple(no_candidate)
        # PROVEN when the search closed its gap, TIME_LIMIT when CBC stopped
        # on its clock holding this set
        self.status = status

    @property
    def full_set_dropped(self):
        """True when the solve had to allow empty slots."""
        return self.full_set_status is not None


class WakfuBuild:
    """Best set at a level; `weights` is keyed by stats.key.

    ap_values: optional {AP total: worth}, base included; the set is then worth
    the entry of its AP total instead of weights['ap'] per AP.

    locked: (item id, position or None) pairs; each item is worn, in that
    position when one is given. A lock the rules cannot honour raises
    ValueError here, before any solve. After solve(), reason says why a solve
    gave no set: INFEASIBLE or TIME_LIMIT.

    class_id: the breed; its base values count and its class pieces are
    candidates. With none, a piece that asks for a class is left out and the
    base values are the range over every breed. state: the PlayerState the
    pieces' player-state conditions are read against, the game's start values
    by default.
    """

    def __init__(self, structure, level, weights, forbidden=(),
                 full_set=True, minimums=None, ap_values=None, locked=(),
                 class_id=None, state=None):
        self.structure = structure
        self.level = level
        self.class_id = class_id
        self.state = state or start_state()
        self._base = base_values(structure, class_id)
        self._class_name = (None if class_id is None
                            else structure.get_breed_names()[class_id])
        self._totals = {}
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
        self.reason = None
        self.problem = None
        self._placements = []
        self._locks = self._read_locks(locked)

    def _positions_of_type(self):
        """{type id: [position, ...]}"""
        places = collections.defaultdict(list)
        for type_id, position in self.structure.get_type_positions():
            places[type_id].append(position)
        return places

    def _read_locks(self, locked):
        """[(item, position or None)] of the locks, refused when no set can honour them."""
        locked = list(locked)
        if not locked:
            return []
        locks = []
        places = self._positions_of_type()
        for ident, position in locked:
            item = self.structure.get_item_by_id(ident)
            if item is None:
                raise ValueError('locked item %r is not in the catalogue' % (ident,))
            if item.removed:
                raise ValueError('locked item %s is removed from the game' % item.name)
            if item.level > self.level:
                raise ValueError('locked item %s is level %d, above the build '
                                 'level %d' % (item.name, item.level, self.level))
            if item.id in self.forbidden:
                raise ValueError('locked item %s is forbidden' % item.name)
            why = self._why_not_wearable(item)
            if why:
                raise ValueError('locked item %s %s' % (item.name, why))
            for target_id in getattr(item, 'worn_with', ()):
                self._check_worn_with_target(item, target_id)
            allowed = places.get(item.type, ())
            if not allowed:
                raise ValueError('locked item %s fits no slot' % item.name)
            if position is not None and position not in allowed:
                raise ValueError('locked item %s cannot sit in %s, only in %s'
                                 % (item.name, position, ', '.join(allowed)))
            locks.append((item, position))
        self._check_locks_agree(locks, places)
        return locks

    def _check_locks_agree(self, locks, places):
        keys = {}
        for item, _position in locks:
            other = keys.setdefault(same_item(item), item)
            if other is not item:
                raise ValueError('locked items %s and %s are one item in two '
                                 'rarities' % (other.name, item.name))
        if len({item.id for item, _position in locks}) < len(locks):
            raise ValueError('an item is locked twice')
        held = {item.id: item for item, _position in locks}
        for item, _position in locks:
            for other_id in getattr(item, 'not_worn_with', ()):
                if other_id in held:
                    raise ValueError('locked items %s and %s cannot be worn '
                                     'together' % (item.name, held[other_id].name))
        for flag in EXCLUSIVE_PROPERTIES.values():
            held = [item for item, _p in locks if flag in (item.flags or ())]
            if len(held) > 1:
                raise ValueError('locked items %s are all %s items, a character '
                                 'wears one' % (', '.join(i.name for i in held), flag))
        if not self._slots_for_locks(locks, places):
            raise ValueError('locked items %s need the same slot'
                             % ', '.join(item.name for item, _p in locks))
        two_handed = [item for item, _p in locks
                      if TWO_HANDED_FLAG in (item.flags or ())]
        if two_handed:
            for item, position in locks:
                only_place = position or (places[item.type][0]
                                          if len(places[item.type]) == 1 else None)
                if only_place == BLOCKED_BY_TWO_HANDED:
                    raise ValueError('locked item %s is two-handed and a lock fills '
                                     'the second weapon slot' % two_handed[0].name)

    @staticmethod
    def _slots_for_locks(locks, places):
        """True when every lock can have a slot of its own."""
        taken = {}

        def place(index, seen):
            item, position = locks[index]
            for slot in ([position] if position else places[item.type]):
                if slot in seen:
                    continue
                seen.add(slot)
                if slot not in taken or place(taken[slot], seen):
                    taken[slot] = index
                    return True
            return False

        return all(place(index, set()) for index in range(len(locks)))

    def _why_not_wearable(self, item):
        """Why this character cannot wear a piece whatever else is worn, or ''."""
        if getattr(item, 'unusable', False):
            return 'cannot be worn by anyone'
        if not fits_the_class(item, self._class_name):
            return 'is for the %s, not for this character' % '/'.join(
                getattr(item, 'classes', ()))
        lowest = getattr(item, 'min_level', None)
        highest = getattr(item, 'max_level', None)
        if lowest is not None and self.level < lowest:
            return 'needs level %d, the build is level %d' % (lowest, self.level)
        if highest is not None and self.level > highest:
            return 'is for level %d at most, the build is level %d' % (
                highest, self.level)
        conditions = getattr(item, 'state_conditions', ())
        if not state_holds(conditions, self.state):
            return 'needs ' + ', '.join(self._state_needs(conditions))
        return ''

    def _state_needs(self, conditions):
        """['wakfu_gauge >= 41', ...] for each condition the build state fails."""
        failing = unlocking(conditions, self.state) or {}
        out = []
        for condition in conditions:
            key = ((condition.option, condition.nation)
                   if condition.option == 'citizenship' else condition.option)
            if key not in failing:
                continue
            name = condition.option
            if condition.option == 'citizenship':
                name = 'citizenship of nation %s' % condition.nation
            out.append('%s %s %s' % (name, condition.operator, condition.value))
        return sorted(out)

    def _check_worn_with_target(self, item, target_id):
        target = self.structure.get_item_by_id(target_id)
        if target is None or target.removed:
            raise ValueError('locked item %s needs item %s, which is not in the '
                             'catalogue' % (item.name, target_id))
        if target.level > self.level or target.id in self.forbidden \
                or self._why_not_wearable(target):
            raise ValueError('locked item %s needs %s, which this build cannot '
                             'wear' % (item.name, target.name))

    @staticmethod
    def _statless(item):
        return not item.stats and not item.element_spread

    def _candidates(self):
        """Every (item, position) a character of this level could wear."""
        places = self._positions_of_type()
        wearable = []
        for item in self.structure.get_available_items_list():
            if item.level > self.level or item.id in self.forbidden:
                continue
            if self._why_not_wearable(item):
                continue
            for position in places.get(item.type, ()):
                wearable.append((item, position))
        # A piece with no stat line only stands where no piece with one does
        locked = {item.id for item, _position in self._locks}
        with_stats = {position for item, position in wearable
                      if not self._statless(item)}
        kept = {(item.id, position) for item, position in wearable
                if not self._statless(item) or item.id in locked
                or position not in with_stats}
        # A kept piece brings in the piece it must be worn with, and goes when
        # that piece cannot be worn at all
        by_id = collections.defaultdict(list)
        for item, position in wearable:
            by_id[item.id].append((item, position))
        items = {item.id: item for item, _position in wearable}
        changed = True
        while changed:
            changed = False
            for ident, position in sorted(kept):
                targets = getattr(items[ident], 'worn_with', ())
                if any(target not in by_id for target in targets):
                    kept.discard((ident, position))
                    changed = True
                    continue
                for target in targets:
                    for other, place in by_id[target]:
                        if (other.id, place) not in kept:
                            kept.add((other.id, place))
                            changed = True
        return [(item, position) for item, position in wearable
                if (item.id, position) in kept]

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
        self._totals = {}
        self._placements = self._candidates()
        for item, position in self._placements:
            self.problem.setup_variable(WORN, self._name(item, position), 0, 1)

        self._one_item_per_slot()
        self._one_copy_of_an_item()
        self._two_handed_empties_the_off_hand()
        self._one_relic_and_one_epic()
        self._caps()
        self._minimums()
        self._locked()
        self._ap_total()
        self._stat_gates()
        self._item_relations()
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
            if self.full_set and position != BLOCKED_BY_TWO_HANDED:
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
                    if position == BLOCKED_BY_TWO_HANDED]
        if not off_hand:
            return
        for item, position in self._placements:
            if TWO_HANDED_FLAG not in (item.flags or ()):
                continue
            self.problem.restriction_lt_eq(
                1, self._parcels([(item, position)]) + self._parcels(off_hand))

    def _one_relic_and_one_epic(self):
        for flag in EXCLUSIVE_PROPERTIES.values():
            wearing = [(item, position) for item, position in self._placements
                       if flag in (item.flags or ())]
            if wearing:
                self.problem.restriction_lt_eq(1, self._parcels(wearing))

    def _gear_part(self, key):
        """The worn pieces' lines of one stat."""
        terms = []
        lowest = collections.defaultdict(int)
        highest = collections.defaultdict(int)
        for item, position in self._placements:
            value = self._stat_value(item, key)
            if value:
                terms.append((value, WORN, self._name(item, position)))
                lowest[position] = min(lowest[position], value)
                highest[position] = max(highest[position], value)
        return Part(terms, sum(lowest.values()), sum(highest.values()))

    def _total_parts(self):
        """Every source of stat points; a later source is appended here."""
        return [self._gear_part]

    def stat_total_expr(self, key):
        """A stat's total as base plus terms, the one every rule reads."""
        if key not in self._totals:
            low, high = self._base.get(key, (0, 0))
            terms, lowest, highest = [], 0, 0
            for part in self._total_parts():
                one = part(key)
                terms += one.terms
                lowest += one.lowest
                highest += one.highest
            self._totals[key] = StatTotal(key, low, high, terms, lowest, highest)
        return self._totals[key]

    def _caps(self):
        """AP, MP and WP caps, base values included."""
        for name, cap in OUT_OF_COMBAT_CAPS.items():
            total = self.stat_total_expr(name.lower())
            if total.terms:
                self.problem.restriction_lt_eq(cap - total.high, total.terms)

    def _minimums(self):
        """Lowest totals, base values included, as a <= on the negated sums."""
        for key, required in sorted(self.minimums.items()):
            total = self.stat_total_expr(key)
            if total.terms:
                self.problem.restriction_lt_eq(
                    total.low - required,
                    [(-value, category, name)
                     for value, category, name in total.terms])

    def _locked(self):
        """Each locked item is worn, in its position when the lock names one."""
        for item, position in self._locks:
            placements = [(one, place) for one, place in self._placements
                          if one.id == item.id
                          and (position is None or place == position)]
            self.problem.restriction_eq(1, self._parcels(placements))

    def _ap_totals(self):
        """Every AP total a set can reach, base included, up to the cap."""
        total = self.stat_total_expr('ap')
        return range(total.low + total.lowest, OUT_OF_COMBAT_CAPS['AP'] + 1)

    def _ap_total(self):
        """One AP_TOTAL variable at 1, the one the worn AP adds up to."""
        if self.ap_values is None:
            return
        totals = self._ap_totals()
        for total in totals:
            self.problem.setup_variable(AP_TOTAL, total, 0, 1)
        self.problem.restriction_eq(1, [(1, AP_TOTAL, total) for total in totals])
        base = self.stat_total_expr('ap')
        parcels = [(base.low - total, AP_TOTAL, total) for total in totals]
        parcels.extend(base.terms)
        self.problem.restriction_eq(0, parcels)

    def _variables_of(self, item):
        return [self._name(one, position) for one, position in self._placements
                if one.id == item.id]

    def _gate_row(self, item, key, bound, upper):
        """One condition of a piece on a stat total, read with and without the piece."""
        total = self.stat_total_expr(key)
        value = self._stat_value(item, key)
        if upper:
            slack = total.high + total.highest - min(value, 0) - bound
            sign, rhs = 1, bound - total.high + min(value, 0) + slack
        else:
            slack = bound + max(value, 0) - (total.low + total.lowest)
            sign, rhs = -1, total.low - max(value, 0) - bound + slack
        if slack <= 0:
            return
        coefficients = collections.OrderedDict(
            (name, sign * coefficient) for coefficient, _category, name in total.terms)
        for name in self._variables_of(item):
            coefficients[name] = coefficients.get(name, 0) + slack
        parcels = [(coefficient, WORN, name)
                   for name, coefficient in coefficients.items()]
        self.problem.add_row(LpProblem2._parcel_terms(parcels), '<=', rhs,
                             'gate_%d_%s_%s' % (item.id, key,
                                                'max' if upper else 'min'))

    def _stat_gates(self):
        """Each piece's own conditions on the stat totals of the set it is worn in."""
        seen = set()
        for item, _position in self._placements:
            if item.id in seen:
                continue
            seen.add(item.id)
            for stat_id, bound in getattr(item, 'min_stats_to_equip', ()):
                key = self._key_of(stat_id)
                if key is not None:
                    self._gate_row(item, key, bound, upper=False)
            for stat_id, bound in getattr(item, 'max_stats_to_equip', ()):
                key = self._key_of(stat_id)
                if key is not None:
                    self._gate_row(item, key, bound, upper=True)

    def _item_relations(self):
        """Pieces worn only with, or never with, another piece."""
        wanted = {item.id: item for item, _position in self._placements}
        for ident, item in sorted(wanted.items()):
            for other_id in sorted(getattr(item, 'not_worn_with', ())):
                other = wanted.get(other_id)
                if other is None or other_id < ident:
                    continue
                if same_item(item) == same_item(other):
                    continue
                parcels = [(1, WORN, name) for name in self._variables_of(item)]
                parcels += [(1, WORN, name) for name in self._variables_of(other)]
                self.problem.add_row(LpProblem2._parcel_terms(parcels), '<=', 1,
                                     'apart_%d_%d' % (ident, other_id))
            for other_id in sorted(getattr(item, 'worn_with', ())):
                if other_id not in wanted:
                    continue
                parcels = [(1, WORN, name) for name in self._variables_of(item)]
                parcels += [(-1, WORN, name)
                            for name in self._variables_of(wanted[other_id])]
                self.problem.add_row(LpProblem2._parcel_terms(parcels), '<=', 0,
                                     'needs_%d_%d' % (ident, other_id))

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

    def _run(self, deadline):
        from .wakfu_value import solver_time_limit

        with solver_time_limit(deadline):
            self.problem.run()

    def solve(self, deadline=None):
        """WakfuSet or None; drops full_set only when that model is infeasible.

        deadline: a time.monotonic() value; each CBC run, the fallback run
        included, is cut to what is left when it starts.

        With no set, reason says why: INFEASIBLE, TIME_LIMIT, or the solver's
        own word for any other status.
        """
        if self.problem is None:
            self.build()
        self.reason = None
        self._run(deadline)
        if self.problem.get_status() == 'Infeasible' and self.full_set:
            self.full_set_status = self.problem.get_status()
            self.full_set = False
            self.problem = None
            self.build()
            self._run(deadline)
        status = self.problem.get_status()
        if status != 'Optimal':
            # PuLP calls a search that ran out of time without a set Not Solved
            self.reason = {'Not Solved': TIME_LIMIT,
                           'Infeasible': INFEASIBLE}.get(status, status.lower())
            return None
        chosen = self.problem.get_result()
        placed = {position for _item, position in self._placements}
        # Optimal is also what PuLP says when CBC stopped on its time limit
        worn = WakfuSet(full_set_status=self.full_set_status,
                        no_candidate=[slot for slot in SLOTS
                                      if slot not in placed],
                        status=(PROVEN if self.problem.solution_is_proven()
                                else TIME_LIMIT))
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
        for name in OUT_OF_COMBAT_CAPS:
            out[name.lower()] += self._base[name.lower()][0]
        return out
