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

"""Wakfu's damage and resistance formulas, and the solver weights they give a role.

value = log(turn damage) + defense x log(effective life); a weight is 100 times
its derivative, so one point of a stat is worth weight percent of the value.
"""

import collections
import math

from .wakfu_stats import BASE_VALUES, ELEMENTS as ELEMENT_NAMES
from .wakfu_value_rules import RULES

ELEMENTS = tuple(name.lower() for name in ELEMENT_NAMES)
MASTERY_OF = {element: 'dmg_%s_percent' % element for element in ELEMENTS}
RESISTANCE_OF = {element: 'res_%s_percent' % element for element in ELEMENTS}
ELEMENTAL_MASTERY = 'dmg_in_percent'
ELEMENTAL_RESISTANCE = 'res_in_percent'
REACH_MASTERY = {'distance': 'ranged_dmg', 'melee': 'melee_dmg'}


def rule(name):
    return RULES[name].value


class DamageDealer(collections.namedtuple(
        'DamageDealer', 'elements reach defense damage_inflicted')):
    """A damage role: the elements it casts, its reach and its defence weight."""

    def __new__(cls, elements=('fire',), reach='distance', defense=None,
                damage_inflicted=0):
        elements = tuple(dict.fromkeys(name.strip().lower() for name in elements))
        unknown = set(elements) - set(ELEMENTS)
        if not elements or unknown:
            raise ValueError('elements are %s, got %r' % (', '.join(ELEMENTS), elements))
        if reach not in REACH_MASTERY:
            raise ValueError('reach is %s, got %r' % (' or '.join(REACH_MASTERY), reach))
        if defense is None:
            defense = rule('defense_weight')
        if defense < 0:
            raise ValueError('defense cannot be negative')
        return super().__new__(cls, elements, reach, float(defense),
                               damage_inflicted)

    def minimums(self):
        """{stat key: lowest total, base included} every set of the role keeps."""
        floors = {name.lower(): BASE_VALUES[name]
                  for name in rule('resources_kept_at_base')}
        if self.reach == 'distance':
            floors['range'] = rule('range_floor_at_distance')
        return floors


def resistance_percent(raw):
    """Resistance percent the game applies: whole percent, toward zero, capped."""
    percent = 100 * (1 - rule('resistance_base') ** (raw / 100))
    # 1 - 0.8 is 0.19999999999999996 in floats
    return min(math.trunc(round(percent, 9)), rule('resistance_cap_percent'))


def share_taken(raw):
    """Share of a hit that goes through a raw resistance, whole percents ignored."""
    floor = 1 - rule('resistance_cap_percent') / 100
    return max(rule('resistance_base') ** (raw / 100), floor)


def critical_chance(ferocity):
    """Crit chance a hit sees, 0 to 1, base value included."""
    raw = ferocity + rule('base_critical_hit_percent')
    return min(max(raw, 0), rule('critical_hit_cap_percent')) / 100


def hit_damage(base, masteries, critical=False, critical_mastery=0,
               damage_inflicted=0, orientation=1.0, resistance=0,
               base_multiplier=1.0):
    """One hit before barrier and block; resistance in percent."""
    if critical:
        base = math.floor(base * base_multiplier * rule('critical_multiplier'))
        masteries += critical_mastery
    else:
        base = math.floor(base * base_multiplier)
    inflicted = max(damage_inflicted, rule('damage_inflicted_floor_percent'))
    return (base * (1 + masteries * rule('mastery_percent_per_point') / 100)
            * orientation * (1 + inflicted / 100) * (1 - resistance / 100))


def expected_factor(mastery, critical_mastery, chance):
    """Expected mastery multiplier of one hit, crits weighed by their chance."""
    per_point = rule('mastery_percent_per_point') / 100
    normal = 1 + mastery * per_point
    critical = rule('critical_multiplier') * (
        1 + (mastery + critical_mastery) * per_point)
    return (1 - chance) * normal + chance * critical


def bare_totals():
    """Stat totals of a character wearing nothing."""
    return collections.Counter({name.lower(): value
                                for name, value in BASE_VALUES.items()})


def applicable_mastery(role, totals, element):
    return (totals.get(MASTERY_OF[element], 0)
            + totals.get(ELEMENTAL_MASTERY, 0)
            + totals.get(REACH_MASTERY[role.reach], 0))


def damage_factor(role, totals):
    """Mean expected mastery multiplier over the role's elements."""
    chance = critical_chance(totals.get('ferocity', 0))
    critical_mastery = totals.get('critical_bonus', 0)
    return sum(expected_factor(applicable_mastery(role, totals, element),
                               critical_mastery, chance)
               for element in role.elements) / len(role.elements)


def turn_damage(role, totals):
    """Damage of a turn, per point of base damage per AP."""
    inflicted = max(role.damage_inflicted,
                    rule('damage_inflicted_floor_percent'))
    return totals.get('ap', 0) * damage_factor(role, totals) * (1 + inflicted / 100)


def life(level, totals):
    return (rule('base_life') + rule('life_per_level') * level
            + totals.get('hp', 0))


def mean_share_taken(totals):
    """Share of a hit that goes through, averaged over the four elements."""
    plain = totals.get(ELEMENTAL_RESISTANCE, 0)
    return sum(share_taken(totals.get(RESISTANCE_OF[element], 0) + plain)
               for element in ELEMENTS) / len(ELEMENTS)


def block_factor(totals):
    block = min(max(totals.get('block', 0), 0), 100)
    return 1 - (1 - rule('block_multiplier')) * block / 100


def effective_life(level, totals):
    return life(level, totals) / (mean_share_taken(totals) * block_factor(totals))


def value(role, level, totals):
    """log(turn damage) + role.defense x log(effective life)."""
    return (math.log(turn_damage(role, totals))
            + role.defense * math.log(effective_life(level, totals)))


def linear_weights(role, level, totals):
    """{stat key: percent of value per point}, the slope of value just above totals.

    Elemental mastery and resistance carry no weight of their own: the solver
    adds the four element weights for them.
    """
    per_point = rule('mastery_percent_per_point') / 100
    critical = rule('critical_multiplier')
    chance = critical_chance(totals.get('ferocity', 0))
    critical_mastery = totals.get('critical_bonus', 0)
    share = 1 / len(role.elements)
    factor = damage_factor(role, totals)

    slope = (1 - chance + critical * chance) * per_point
    weights = collections.Counter()
    for element in role.elements:
        weights[MASTERY_OF[element]] = 100 * share * slope / factor
    weights[REACH_MASTERY[role.reach]] = 100 * slope / factor
    weights['critical_bonus'] = 100 * critical * chance * per_point / factor

    raw_chance = totals.get('ferocity', 0) + rule('base_critical_hit_percent')
    if 0 <= raw_chance < rule('critical_hit_cap_percent'):
        gain = sum(
            (critical - 1) * (1 + applicable_mastery(role, totals, element) * per_point)
            + critical * critical_mastery * per_point
            for element in role.elements) * share
        weights['ferocity'] = gain / factor

    weights['ap'] = 100 / totals['ap']

    if role.defense:
        weights['hp'] = 100 * role.defense / life(level, totals)
        through = mean_share_taken(totals)
        slope = math.log(1 / rule('resistance_base')) / 100
        plain = totals.get(ELEMENTAL_RESISTANCE, 0)
        floor = 1 - rule('resistance_cap_percent') / 100
        for element in ELEMENTS:
            taken = rule('resistance_base') ** (
                (totals.get(RESISTANCE_OF[element], 0) + plain) / 100)
            if taken > floor:
                weights[RESISTANCE_OF[element]] = (
                    100 * role.defense * slope * taken / len(ELEMENTS) / through)
        if 0 <= totals.get('block', 0) < 100:
            weights['block'] = (100 * role.defense
                                * (1 - rule('block_multiplier')) / 100
                                / block_factor(totals))
    return dict(weights)


class ModelRound(collections.namedtuple('ModelRound',
                                        'weights build worn totals value')):
    """weights: what the round solved on; build: the landing totals and value use."""

    @property
    def ids(self):
        return frozenset(item.id for item in self.worn.values())


class ModelSolve(collections.namedtuple('ModelSolve', 'rounds best converged')):
    """Every round of a model solve, the best by value, and whether it settled."""


LANDING_PASSES = 4


def blend(point, totals, step):
    return collections.Counter({key: point[key] + step * (totals[key] - point[key])
                                for key in set(point) | set(totals)})


def land(structure, level, role, build, worn):
    """(value, build, totals) of the best landing tried for a set's spread lines.

    Each pass lands them on the weights at the totals the pass before gave.
    """
    from .wakfu_model import WakfuBuild

    totals = build.totals(worn)
    tried = [(value(role, level, totals), build, totals)]
    for _ in range(LANDING_PASSES):
        build = WakfuBuild(structure, level, linear_weights(role, level, totals))
        totals = build.totals(worn)
        if totals == tried[-1][2]:
            break
        tried.append((value(role, level, totals), build, totals))
    return max(tried, key=lambda one: one[0])


def solve(structure, level, role, forbidden=(), rounds=5, full_set=True):
    """Best set by value; each round solves on the tangent at a blend of the sets found.

    The blend moves toward each new set by 2/(k+2) of the way, a Frank-Wolfe
    step, and the rounds stop once a set comes back twice in a row.
    """
    from .wakfu_model import WakfuBuild

    point = bare_totals()
    minimums = role.minimums()
    done = []
    converged = False
    for number in range(max(1, rounds)):
        weights = linear_weights(role, level, point)
        build = WakfuBuild(structure, level, weights, forbidden, full_set,
                           minimums=minimums)
        worn = build.build().solve()
        if worn is None:
            break
        worth, landed, totals = land(structure, level, role, build, worn)
        done.append(ModelRound(weights, landed, worn, totals, worth))
        if len(done) > 1 and done[-2].ids == done[-1].ids:
            converged = True
            break
        point = blend(point, totals, 2 / (number + 2))
    if not done:
        return ModelSolve((), None, False)
    return ModelSolve(tuple(done), max(done, key=lambda one: one.value), converged)
