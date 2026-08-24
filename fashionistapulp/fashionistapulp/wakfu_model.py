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

"""Pick the best legal set of Wakfu gear for a character.

Wakfu is not a Dofus version and this is not `model.py` with a flag. It shares
the solver underneath and nothing above it: the slots are different, the
exclusivity rules are different, the caps are different, and there is a floor
on critical hit that Dofus has no equivalent for.

WHAT MAKES A SET LEGAL. Every rule below was measured against Ankama's own
1.92.1.60 data or read from a source with a date, and every one is written down
where it came from in wakfu_slots.py and wakfu_stats.py:

- Twelve slots, one item each. A RING is the awkward one: its type declares
  both hands, so a build wears two rings, and the model has to place them
  rather than count them. That is why an item is bound to a POSITION here and
  not merely chosen.
- Three different types share ACCESSORY, the Emblem, the Tool and the Torch.
  Counting per type instead of per slot would let a build wear all three.
- A two-handed weapon empties the second hand. 508 weapons say so themselves,
  in `equipmentDisabledPositions`.
- At most one RELIC and at most one EPIC, and they are two independent groups
  rather than one rule about rarity: 97 items carry the first property and 115
  the second, and two items sit at those rarities WITHOUT the property.
- Out of combat a character may not pass 16 AP, 8 MP or 20 WP, counting the
  6, 3 and 6 they start with. Gear alone reaches +18, +15 and +16, so these
  bind on every build worth having.
- A character may not go below -9 % critical hit. 87 items sell stats in
  exchange for negative critical hit and one of them is -20 on its own, so
  wearing it means buying the difference back somewhere else.

THE SAME ITEM IS NEVER WORN TWICE. Nothing in Ankama's data says whether two
copies of one ring may be, and no source with a date says either; see
`game_versions.rings_can_double`, which answers no for Wakfu on purpose.
Refusing a legal double costs a slightly worse build. Allowing an illegal one
hands the player a set the game will not let them wear.

WHAT THIS DOES NOT DO YET, said plainly rather than left to be discovered: it
knows nothing of spells, of the elements a mastery line spreads over, or of
what a point of mastery is worth against a point of resistance. It takes the
weights it is given and finds the best set under the rules. Deciding those
weights is the next piece of work and it belongs to the game, not to the
solver.
"""

from __future__ import annotations

import collections

from .game_versions import get_game_version
from .lpproblem import LpProblem2
from .wakfu_slots import SLOTS
from .wakfu_stats import BASE_VALUES, CRITICAL_HIT_FLOOR_PERCENT, \
    OUT_OF_COMBAT_CAPS

# The categories of LP variable. `w` is "this item, worn in this slot".
WORN = 'w'


class WakfuBuild:
    """One question put to the solver: the best set at a level, under weights.

    `weights` maps a stat key, as `stats.key` spells it in the database, to
    what a point of it is worth. A stat nobody weighs is simply not part of
    the objective; it is not forbidden.
    """

    def __init__(self, structure, level, weights, forbidden=()):
        self.structure = structure
        self.level = level
        self.weights = dict(weights)
        self.forbidden = set(forbidden)
        self.problem = None
        self._placements = []
        self._by_item = {}

    # -- the pieces the solver is allowed to use -------------------------

    def _positions_of_type(self):
        """{type id: [position, ...]} from the database, not from a constant."""
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

    # -- the model -------------------------------------------------------

    def _stat_value(self, item, key):
        stat = self.structure.get_stat_by_key(key)
        if stat is None:
            return 0
        return sum(value for stat_id, value in item.stats
                   if stat_id == stat.id)

    def _worth(self, item):
        return sum(weight * self._stat_value(item, key)
                   for key, weight in self.weights.items() if weight)

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
        """One item in each of the twelve slots, and the two hands are two."""
        by_slot = collections.defaultdict(list)
        for item, position in self._placements:
            by_slot[position].append((item, position))
        for position in SLOTS:
            if by_slot[position]:
                self.problem.restriction_lt_eq(1, self._parcels(by_slot[position]))

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
            # Taking this weapon forbids everything in the second hand.
            self.problem.restriction_lt_eq(
                1, self._parcels([(item, position)]) + self._parcels(off_hand))

    def _one_relic_and_one_epic(self):
        for flag in ('relic', 'epic'):
            wearing = [(item, position) for item, position in self._placements
                       if flag in (item.flags or ())]
            if wearing:
                self.problem.restriction_lt_eq(1, self._parcels(wearing))

    def _caps(self):
        """AP, MP and WP, counting what the character already has."""
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
        """Never below -9 % in total, which is what makes those items usable.

        Written as a less-than by turning the sum around, because that is the
        only shape the solver wrapper offers.
        """
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

    # -- the answer -------------------------------------------------------

    def solve(self):
        """{position: item} for the best legal set, or None when there is none."""
        if self.problem is None:
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

    def totals(self, worn):
        """What a set adds up to, base values included."""
        out = collections.Counter()
        for item in worn.values():
            for stat_id, value in item.stats:
                stat = self.structure.get_stat_by_id(stat_id)
                if stat is not None:
                    out[stat.key] += value
        for name, value in BASE_VALUES.items():
            out[name.lower()] += value
        return out
