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

value = the sum over a role's components of share x log(component): the damage of its best
turn, its effective life, its heals, armor, placement and hindrance, its lock, dodge and
initiative, its wisdom and prospection. A weight is 100 times the derivative, so one point
of a stat is worth weight percent of the value.
"""

import collections
import contextlib
import itertools
import math
import time

import pulp

from . import lpproblem, wakfu_aptitudes, wakfu_runes, wakfu_sublimations
from .wakfu_criteria import base_values
from .wakfu_defense import (  # noqa: F401  re-exported
    ARMOR_GIVEN, CONTENTS, ELEMENTAL_RESISTANCE, ELEMENTS, LIFE_PERCENT, RESISTANCE_OF,
    block_factor, class_armor_turn, defense_weights, effective_life, life,
    mean_share_taken, raw_life, resistance_percent, share_taken)
from .wakfu_stats import OUT_OF_COMBAT_CAPS
from .wakfu_value_rules import RULES

MASTERY_OF = {element: 'dmg_%s_percent' % element for element in ELEMENTS}
ELEMENTAL_MASTERY = 'dmg_in_percent'
FINAL_DAMAGE = 'final_dmg_in_percent'
REACH_MASTERY = {'distance': 'ranged_dmg', 'melee': 'melee_dmg'}
REACHES = ('melee', 'distance', 'mixed')
TARGETS = ('single', 'area')
FAMILY_COMPONENTS = ('heal', 'armor', 'placement', 'hindrance')
#: Components valued as 1 + total / scale, and the stat each one adds up
SCALED = {'lock': 'tackle', 'dodge': 'dodge', 'initiative': 'init'}
MULE_STATS = ('wisdom', 'prospection')
#: The components of a role, in the order value() adds them
COMPONENTS = ('damage', 'life') + FAMILY_COMPONENTS + tuple(SCALED) + ('mule',)


#: Rounds stop when less than this many seconds are left before a deadline
MIN_ROUND_SECONDS = 10
#: Seconds kept back from each CBC run for building the model and reading the answer
SOLVE_MARGIN_SECONDS = 3
#: A round whose set is no better stops the loop when the objective it gains over the
#: incumbent's set is at most this (objective units are percent of the value)
GAP_TOL = 0.1
#: Share of the remaining time the first step of a stepwise round may take
FIRST_STEP_SHARE = 0.6
#: Share of the remaining time a joint round may take when sublimations or passives are
#: solved, so that a round which ends on its clock leaves time for the stepwise rounds
JOINT_SHARE = 0.6
#: Share of the time left that the plain stage of a solve which picks sublimations or
#: passives may take, before they are solved on the plain set it found
PLAIN_SHARE = 0.5
#: A solve which picks sublimations or passives needs this many seconds left to run the
#: plain stage and the floor; with less it runs the round loop alone
FLOOR_SECONDS = 3 * MIN_ROUND_SECONDS
#: Seconds kept back from the caller's budget for landing the set and reading it
FINISH_SECONDS = 5


def out_of_time(deadline):
    """True when a monotonic deadline leaves too little for another round."""
    return deadline is not None and deadline - time.monotonic() < MIN_ROUND_SECONDS


def joint_deadline(deadline, picking):
    """The monotonic deadline of a joint round: a share of what is left when sublimations or
    passives are picked, the whole deadline otherwise; the whole deadline too when the share
    would leave less than a stepwise round needs."""
    if deadline is None or not picking:
        return deadline
    now = time.monotonic()
    left = max(0, deadline - now)
    if (1 - JOINT_SHARE) * left < 2 * MIN_ROUND_SECONDS:
        return now + left
    return now + JOINT_SHARE * left


def _start_of(round_):
    """The solution values of a round's set, None where it has none."""
    return None if round_ is None else getattr(round_.worn, 'solution_values', None) or None


def plain_deadline(deadline):
    """The monotonic deadline of the plain stage: a share of what is left."""
    if deadline is None:
        return None
    now = time.monotonic()
    return now + PLAIN_SHARE * max(0, deadline - now)


def plain_modes(sublimations, passives):
    """The sublimation and passive arguments of the plain stage: the ones that are picked
    become none, the others are kept."""
    return (wakfu_sublimations.NONE if sublimations == wakfu_sublimations.OPTIMISTIC
            else sublimations,
            wakfu_sublimations.NONE if passives == wakfu_sublimations.SOLVE else passives)


def picks_sublimations_or_passives(sublimations, passives):
    """True when the solver chooses sublimations or passives. Otherwise the solve keeps the
    plain round loop and the whole time budget."""
    return (sublimations == wakfu_sublimations.OPTIMISTIC
            or passives == wakfu_sublimations.SOLVE)


@contextlib.contextmanager
def solver_time_limit(deadline):
    """CBC's limit cut to what is left before a monotonic deadline, yielded; None keeps the usual one."""
    if deadline is None:
        yield None
        return
    left = int(deadline - time.monotonic()) - SOLVE_MARGIN_SECONDS
    limit = max(1, min(lpproblem.TIME_LIMIT_SECONDS, left))
    # One solver object per process, and one solve at a time
    previous = lpproblem.SOLVER.timeLimit
    lpproblem.SOLVER.timeLimit = limit
    try:
        yield limit
    finally:
        lpproblem.SOLVER.timeLimit = previous


def rule(name):
    return RULES[name].value


class DamageDealer(collections.namedtuple(
        'DamageDealer', 'elements reach defense damage_inflicted movement')):
    """A damage role: the elements it casts, its reach and its defence weight.

    movement: share of the turn's MP spent moving, 0 to 1; None spends none
    and leaves the caster_does_not_move rule to say whether the caster stood still.
    """

    def __new__(cls, elements, reach, defense=None,
                damage_inflicted=0, movement=None):
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
        if movement is not None:
            movement = float(movement)
            if not 0 <= movement <= 1:
                raise ValueError('movement is a share of MP, 0 to 1, got %r' % movement)
        return super().__new__(cls, elements, reach, float(defense),
                               damage_inflicted, movement)

    def minimums(self, base):
        """{stat key: lowest total, base included} every set of the role keeps.

        base: {stat key: (low, high)}, wakfu_criteria.base_values.
        """
        floors = {name.lower(): base[name.lower()][0]
                  for name in rule('resources_kept_at_base')}
        if self.reach == 'distance':
            floors['range'] = rule('range_floor_at_distance')
        return floors

    def role(self, content='pvm'):
        """The Role with the same damage and a life share of the defense weight."""
        return Role(self.elements, self.reach, content=content, movement=self.movement,
                    damage_inflicted=self.damage_inflicted,
                    shares={'damage': 1, 'life': self.defense})


class Role(collections.namedtuple(
        'Role', 'elements reach target content berserk movement damage_inflicted shares')):
    """What a build is for: the damage it casts and the components it is valued on.

    elements: the damage elements, empty only when the role has no damage share. reach:
    melee, distance or mixed (half of each). target: single, or area, where area damage rows
    count area_targets times. content: pvm or pvp, for the hits the life takes. berserk:
    the berserk conditions hold. movement and damage_inflicted: as in DamageDealer. shares:
    {component: share >= 0}, see COMPONENTS; the value is the sum of share x log(component).
    """

    def __new__(cls, elements, reach, target='single', content='pvm', berserk=False,
                movement=None, damage_inflicted=0, shares=None):
        elements = tuple(dict.fromkeys(name.strip().lower() for name in elements))
        shares = {'damage': 1} if shares is None else dict(shares)
        unknown = set(shares) - set(COMPONENTS)
        if unknown:
            raise ValueError('components are %s, got %s'
                             % (', '.join(COMPONENTS), ', '.join(sorted(unknown))))
        if any(share < 0 for share in shares.values()):
            raise ValueError('a share cannot be negative')
        shares = {name: float(shares[name]) for name in COMPONENTS if shares.get(name)}
        if not shares:
            raise ValueError('a role needs a share in some component')
        if set(shares) == {'life'}:
            raise ValueError('a role is never valued on life alone: damage comes first')
        unknown = set(elements) - set(ELEMENTS)
        if unknown or (shares.get('damage') and not elements):
            raise ValueError('elements are %s, got %r' % (', '.join(ELEMENTS), elements))
        for field, kinds, given in (('reach', REACHES, reach), ('target', TARGETS, target),
                                    ('content', CONTENTS, content)):
            if given not in kinds:
                raise ValueError('%s is %s, got %r' % (field, ' or '.join(kinds), given))
        if movement is not None:
            movement = float(movement)
            if not 0 <= movement <= 1:
                raise ValueError('movement is a share of MP, 0 to 1, got %r' % movement)
        return super().__new__(cls, elements, reach, target, content, bool(berserk),
                               movement, damage_inflicted, shares)

    @property
    def defense(self):
        return self.shares.get('life', 0.0)

    def minimums(self, base):
        """{stat key: lowest total, base included} every set of the role keeps."""
        floors = {name.lower(): base[name.lower()][0]
                  for name in rule('resources_kept_at_base')}
        if self.reach == 'distance' and 'damage' in self.shares:
            floors['range'] = rule('range_floor_at_distance')
        return floors


def as_role(role, content=None):
    """role as a Role: a DamageDealer becomes its equivalent, content replacing the role's."""
    if isinstance(role, DamageDealer):
        return role.role(content or 'pvm')
    if content is not None and content != role.content:
        if content not in CONTENTS:
            raise ValueError('content is %s, got %r' % (' or '.join(CONTENTS), content))
        return role._replace(content=content)
    return role


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


def bare_totals(base):
    """Stat totals of a character wearing nothing: AP, MP and WP at their base low."""
    return collections.Counter({name.lower(): base[name.lower()][0]
                                for name in OUT_OF_COMBAT_CAPS})


def resource_ceiling(base):
    """A bare character's totals with AP, MP and WP at their caps.

    A class turn that deals nothing there deals nothing on any set.
    """
    totals = bare_totals(base)
    for name, cap in OUT_OF_COMBAT_CAPS.items():
        totals[name.lower()] = cap
    return totals


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
    inflicted = max(role.damage_inflicted + totals.get(FINAL_DAMAGE, 0),
                    rule('damage_inflicted_floor_percent'))
    return totals.get('ap', 0) * damage_factor(role, totals) * (1 + inflicted / 100)


def value(role, level, totals, turn=None, content=None, armor_turn=0):
    """sum over the role's components of share x log(component), see components().

    role: a Role, or a DamageDealer (damage 1, life its defense). turn: a
    wakfu_turn.TurnModel (the damage turn, whose best turn replaces AP x damage_factor) or
    a wakfu_turn.RoleTurns; without one the damage is the closed form and the components that
    need spells or scales are left out. content: the role's, unless given; armor_turn: the
    class's self armor in one turn, taken from the turns' armor model when 0.
    """
    role, models, scales, armor_turn = _frame(role, level, totals, turn, content, armor_turn)
    total = 0.0
    for name in COMPONENTS:
        share = role.shares.get(name)
        if not share:
            continue
        worth = _worth(name, role, level, totals, models, scales, armor_turn)
        if worth is None:
            continue
        total += share * (math.log(worth) if worth > 0 else float('-inf'))
    return total


def components(role, level, totals, turn=None, content=None, armor_turn=0):
    """{component: C} of the role's components, the quantities value() takes the log of."""
    role, models, scales, armor_turn = _frame(role, level, totals, turn, content, armor_turn)
    worths = {name: _worth(name, role, level, totals, models, scales, armor_turn)
              for name in COMPONENTS if role.shares.get(name)}
    return {name: worth for name, worth in worths.items() if worth is not None}


def linear_weights(role, level, totals, turn=None, content=None, armor_turn=0):
    """{stat key: percent of value per point}, the slope of value just above totals.

    Elemental mastery and resistance carry no weight of their own: the solver
    adds the four element weights for them. The other arguments are those of value().
    """
    role, models, scales, armor_turn = _frame(role, level, totals, turn, content, armor_turn)
    weights = collections.Counter()
    for name in COMPONENTS:
        share = role.shares.get(name)
        if not share:
            continue
        for key, weight in _weights(name, share, role, level, totals, models, scales,
                                    armor_turn).items():
            weights[key] += weight
    return dict(weights)


def _frame(role, level, totals, turn, content, armor_turn):
    """(role, turn models or None, scales, armor turn) a value or a weight call works on."""
    role = as_role(role, content)
    models = scales = None
    if turn is not None:
        models = getattr(turn, 'models', None)
        scales = getattr(turn, 'scales', None)
        if models is None:
            if role.reach == 'mixed':
                raise ValueError('a mixed reach needs the turns of both reaches (RoleTurns)')
            models = {'damage': turn}
    if not armor_turn and models and 'self_armor' in models and role.shares.get('life'):
        armor_turn = class_armor_turn(models['self_armor'].best(totals))[0]
    return role, models, scales, armor_turn


def _need(models, name):
    if name not in models:
        raise ValueError('the turns hold no %s turn' % name)
    return models[name]


def _reaches(role, models):
    """[(share of the damage, the role at that reach, its turn model or None)]; a reach
    with no model is priced by the closed form."""
    models = models or {}
    if role.reach == 'mixed':
        return [(0.5, role._replace(reach=reach), models.get(reach))
                for reach in ('melee', 'distance')]
    return [(1, role, models.get('damage'))]


def damage_worth(role, totals, models=None):
    """The damage component: the best damage turn, a mixed reach half melee and half distance."""
    return sum(share * (model.damage(totals) if model is not None
                        else turn_damage(part, totals))
               for share, part, model in _reaches(role, models))


def damage_role(role):
    """The role valued on its damage alone."""
    return as_role(role)._replace(shares={'damage': 1.0})


def damage_turn(turn, role):
    """The turns of damage_role(role); a TurnModel already prices damage alone."""
    if getattr(turn, 'models', None) is None:
        return turn
    return type(turn)(damage_role(role), turn.level, turn.models, turn.scales)


def weighted_role(role, t):
    """The role with every share but the damage's multiplied by t: the role itself at 1 and,
    with a damage share of 1, its damage alone at 0. The linear weights of the objective
    ln(damage) + t x (value - ln(damage)) are those of this role."""
    role = as_role(role)
    return role._replace(shares={name: share if name == 'damage' else share * t
                                 for name, share in role.shares.items()
                                 if name == 'damage' or share * t})


def weighted_turn(turn, role, t):
    """The turns of weighted_role(role, t), which price AP the way that role weighs it; a
    TurnModel already prices damage alone."""
    if getattr(turn, 'models', None) is None:
        return turn
    return type(turn)(weighted_role(role, t), turn.level, turn.models, turn.scales)


def damage_of(role, level, totals, turn=None):
    """The damage component of role on totals."""
    role, models, _scales, _armor = _frame(damage_role(role), level, totals, turn, None, 0)
    return damage_worth(role, totals, models)


def damage_first_key(role, level, turn, least_damage, worth, totals):
    """Sort key of a landing: by value when it keeps least_damage, else below, by damage."""
    if least_damage is None:
        return (1, worth)
    damage = damage_of(role, level, totals, turn)
    if damage >= least_damage * (1 - 1e-9):
        return (1, worth)
    return (0, damage)


class DamageFloor:
    """A damage preset's floor: its sets keep (1 - share) of top, the most damage seen."""

    def __init__(self, share, role, level, turn=None, top=0.0):
        self.share = share
        self.role = damage_role(role)
        self.level = level
        self.turn = None if turn is None else damage_turn(turn, role)
        self.top = top or 0.0

    def damage(self, totals):
        return damage_of(self.role, self.level, totals, self.turn)

    def see(self, totals):
        self.top = max(self.top, self.damage(totals))

    def bound(self):
        return (1 - self.share) * self.top

    def holds(self, totals):
        return self.damage(totals) >= self.bound() * (1 - 1e-9)

    def pick(self, rounds):
        """The best round by value among those that hold, else the one with the most damage."""
        rounds = [one for one in rounds if one is not None]
        if not rounds:
            return None
        held = [one for one in rounds if self.holds(one.totals)]
        if held:
            return max(held, key=lambda one: one.value)
        return max(rounds, key=lambda one: self.damage(one.totals))


def _damage_slopes(role, totals, models):
    """{stat key: percent of the damage component per point}, the final damage one included."""
    slopes = [(share, model.damage(totals) if model is not None else turn_damage(part, totals),
               model.weights(totals) if model is not None else _damage_weights(part, totals))
              for share, part, model in _reaches(role, models)]
    if len(slopes) == 1:
        weights = collections.Counter(slopes[0][2])
    else:
        whole = sum(share * worth for share, worth, _ in slopes)
        weights = collections.Counter()
        for share, worth, one in slopes:
            for key, weight in one.items():
                weights[key] += share * worth * weight / whole
    inflicted = role.damage_inflicted + totals.get(FINAL_DAMAGE, 0)
    if inflicted > rule('damage_inflicted_floor_percent'):
        weights[FINAL_DAMAGE] = 100 / (100 + inflicted)
    return weights


def _scale(scales, key):
    if scales is None:
        raise ValueError('a stat component needs the scales of the turns')
    return scales.get(key, 0)


def _armor_gain(name, totals):
    """What the armor component multiplies the armor turn by: 1 + armor_given_percent / 100."""
    if name != 'armor':
        return 1
    return max(1 + totals.get(ARMOR_GIVEN, 0) / 100, 0)


def _worth(name, role, level, totals, models, scales, armor_turn):
    """C of one component, None where the component is left out (no turns were given)."""
    if name == 'damage':
        return damage_worth(role, totals, models)
    if name == 'life':
        return effective_life(level, totals, role.content, armor_turn)
    if name in FAMILY_COMPONENTS:
        if models is None:
            return None
        turn = _need(models, name).damage(totals)
        if name == 'heal':
            return turn
        return 1 + turn * _armor_gain(name, totals)
    if name in SCALED:
        if models is None:
            return None
        scale = _scale(scales, SCALED[name])
        return 1 + max(totals.get(SCALED[name], 0), 0) / scale if scale > 0 else 1.0
    return 1 + max(sum(totals.get(key, 0) for key in MULE_STATS), 0)


def _weights(name, share, role, level, totals, models, scales, armor_turn):
    """{stat key: share x 100 x dC/C per point} of one component."""
    if name == 'damage':
        return {key: share * weight
                for key, weight in _damage_slopes(role, totals, models).items()}
    if name == 'life':
        return defense_weights(share, level, totals, role.content, armor_turn)
    if name in FAMILY_COMPONENTS:
        if models is None:
            return {}
        model = _need(models, name)
        turn = model.damage(totals)
        if turn <= 0:
            return {}
        slopes = model.weights(totals)
        if name == 'heal':
            return {key: share * weight for key, weight in slopes.items()}
        gain = _armor_gain(name, totals)
        worth = 1 + turn * gain
        weights = {key: share * gain * turn * weight / worth
                   for key, weight in slopes.items()}
        if name == 'armor' and gain > 0:
            weights[ARMOR_GIVEN] = share * turn / worth
        return weights
    if name in SCALED:
        if models is None:
            return {}
        key = SCALED[name]
        scale = _scale(scales, key)
        total = totals.get(key, 0)
        if scale <= 0 or total < 0:
            return {}
        return {key: 100 * share / (scale + total)}
    owned = sum(totals.get(key, 0) for key in MULE_STATS)
    if owned < 0:
        return {}
    return {key: 100 * share / (1 + owned) for key in MULE_STATS}


def _aptitude_most(structure, key, top):
    """The most the aptitudes give of a stat at level top: each category's points go to the
    abilities that give the most per point."""
    if not getattr(structure, 'aptitude_abilities', None):
        return 0
    table = wakfu_aptitudes.table(structure, top, False)
    budget = wakfu_aptitudes.budgets(structure, top)
    options = collections.defaultdict(list)
    for category, cap, lines, _notes in table.abilities.values():
        per_point = dict(lines).get(key, 0)
        if per_point > 0:
            options[category].append((per_point, cap))
    total = 0
    for category, found in options.items():
        left = budget.get(category, 0)
        for per_point, cap in sorted(found, reverse=True):
            used = min(cap, left)
            total += per_point * used
            left -= used
    return total


def _rune_most(structure, stat, item, position):
    """The most the sockets of an item give of a stat at a position: every socket holds the
    best rune."""
    sockets = wakfu_runes.sockets_of(item)
    if not sockets or not getattr(structure, 'shards', None):
        return 0
    best = 0
    for rune in wakfu_runes.valued(structure).values():
        if rune.stat == stat.id and wakfu_runes.socket_tier(rune, item) >= 1:
            best = max(best, wakfu_runes.value(
                rune, wakfu_runes.socket_tier(rune, item), position in rune.doubles))
    return sockets * best


def stat_scale(structure, key, top):
    """The most a set could hold of a stat at level top, to scale a 1 + total / scale
    component: over equipment positions the highest value of the stat among the items at or
    below top, their sockets filled with the best rune, plus what the aptitudes give at top."""
    stat = structure.get_stat_by_key(key)
    if stat is None:
        return 0
    places = collections.defaultdict(list)
    for type_id, position in structure.get_type_positions():
        places[type_id].append(position)
    best = {}
    for item in structure.get_available_items_list():
        if item.level > top or getattr(item, 'removed', False):
            continue
        held = sum(amount for stat_id, amount in item.stats if stat_id == stat.id)
        for position in places.get(item.type, ()):
            best[position] = max(best.get(position, 0),
                                 held + _rune_most(structure, stat, item, position))
    return sum(best.values()) + _aptitude_most(structure, key, top)


def stat_scales(structure, top):
    """{stat key: stat_scale} of the stats the lock, dodge and initiative components use."""
    return {key: stat_scale(structure, key, top) for key in SCALED.values()}


def _damage_weights(role, totals):
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
    return weights


class ModelRound(collections.namedtuple('ModelRound',
                                        'weights build worn totals value objective',
                                        defaults=(None,))):
    """weights: what the round solved on; build: the landing totals and value use.

    objective: the round's own objective on its set, None where it was not read.
    """

    @property
    def ids(self):
        return frozenset(item.id for item in self.worn.values())

    @property
    def key(self):
        """What a round settled on: the pieces, the aptitude points, the runes, the
        sublimations with their positions, the specials and the passives."""
        runes = collections.Counter(
            (position, socket.rune, socket.tier)
            for position, sockets in self.worn.runes.items()
            for socket in sockets if socket.rune is not None)
        worn = self.worn
        return (self.ids, tuple(sorted(worn.aptitudes.items())),
                tuple(sorted(key + (count,) for key, count in runes.items())),
                tuple(sorted((worn.sublimation_ids or {}).items())),
                tuple(sorted((worn.special_ids or {}).items())),
                tuple(sorted(worn.passives or ())))


class ModelSolve(collections.namedtuple('ModelSolve', 'rounds best converged')):
    """Every round of a model solve, the best by value, and whether it settled.

    reason: why the last round gave no set (wakfu_model.INFEASIBLE or TIME_LIMIT), else None.
    settled_by: 'key' when a round came back to the incumbent's set (to the set of the round
    before when no sublimation or passive is picked), 'gap' when the gap certificate held, None
    when the loop ran out of rounds or time. gap: the objective a round gained over the
    incumbent's set on its own objective, the last one read, None before any. crashed: (round
    number, message) of the round the solver died on, empty when none did; the loop stops
    there and keeps the incumbent. They are attributes, so the three fields stay what callers
    unpack. When sublimations or passives are picked, the first round is the floor: the best set
    of a plain stage with the sublimations and passives solved on its pieces, whose status is
    wakfu_model.STEPWISE; a crash in a later round of the plain stage or in the floor's own
    solve counts as round 1 and the loop goes on. Only a round CBC proved settles the loop.
    Another plain set solved the same way comes last when it beats every round, and the solve
    is then not settled.

    The damage floor's fields are None, 0 or empty without a floor. damage_floor: the floor
    share the solve kept; damage_top: the most damage of the sets it saw; floor_seconds: the
    seconds the floor's own work took (its damage stage, its damage set probe, its landings on
    the bound and its weight search), which solve adds to the generic model's deadline;
    floor_cut_seconds: the seconds the hard end took from the search without the floor, from
    its round loop or, after a class turn, from the generic model's solve;
    pre_floor: the final set of the search without the floor, judged and landed as the others;
    pre_floor_value: that set's value before it was landed on the bound, the one the search
    without the floor kept it by;
    probes: one record per probe, {kind, t, pieces, damage, life, value, holds, seconds};
    floor_timing: {stage: seconds} of the floor's parts.
    """

    FLOOR_FIELDS = ('damage_top', 'damage_floor', 'floor_seconds', 'floor_cut_seconds',
                    'pre_floor', 'probes', 'floor_timing', 'pre_floor_value')

    def __new__(cls, rounds, best, converged, reason=None, settled_by=None, gap=None,
                crashed=(), damage_top=None, damage_floor=None, floor_seconds=0.0,
                floor_cut_seconds=0.0, pre_floor=None, probes=(), floor_timing=None,
                pre_floor_value=None):
        self = super().__new__(cls, rounds, best, converged)
        self.reason = reason
        self.settled_by = settled_by
        self.gap = gap
        self.crashed = tuple(crashed)
        self.damage_top = damage_top
        self.damage_floor = damage_floor
        self.floor_seconds = floor_seconds
        self.floor_cut_seconds = floor_cut_seconds
        self.pre_floor = pre_floor
        self.probes = tuple(probes)
        self.floor_timing = floor_timing
        self.pre_floor_value = pre_floor_value
        return self

    def _replace(self, **changes):
        converged = changes.get('converged', self.converged)
        return type(self)(changes.get('rounds', self.rounds), changes.get('best', self.best),
                          converged, self.reason,
                          changes.get('settled_by', self.settled_by if converged else None),
                          changes.get('gap', self.gap), self.crashed,
                          **{name: changes.get(name, getattr(self, name))
                             for name in self.FLOOR_FIELDS})


class SolverCrashed(RuntimeError):
    """The solver died on the first round, so there is no set to keep."""


def _crashed_after(classed, crashes):
    """The class turn's solve, not settled, with the generic model's crashed rounds counted
    after its own."""
    return ModelSolve(classed.rounds, classed.best, False, classed.reason, None, classed.gap,
                      classed.crashed + tuple((len(classed.rounds) + number, message)
                                              for number, message in crashes),
                      **{name: getattr(classed, name) for name in ModelSolve.FLOOR_FIELDS})


LANDING_PASSES = 4


def _given(sublimations, passives, opt_in):
    """The sublimation and passive arguments that are not None; none at all is the plain call."""
    asked = {'sublimations': sublimations, 'passives': passives, 'opt_in': opt_in}
    return {name: one for name, one in asked.items() if one is not None}


def blend(point, totals, step):
    return collections.Counter({key: point[key] + step * (totals[key] - point[key])
                                for key in set(point) | set(totals)})


def land(structure, level, role, build, worn, turn=None, locked=(), class_id=None,
         state=None, aptitudes=None, battleground=False, levels=None,
         runes=None, rune_tier=None, sublimations=None, passives=None, opt_in=None,
         least_damage=None):
    """(value, build, totals) of the best landing tried for a set's spread lines.

    Each pass lands them on the weights at the totals the pass before gave. The
    aptitude points, the runes, the sublimations and the passives of the set are held as
    they are, so its totals keep them; the totals are the fight's.
    """
    from .wakfu_model import WakfuBuild

    totals = build.totals(worn)
    tried = [(value(role, level, totals, turn), build, totals)]
    held = None if aptitudes is None else dict(worn.aptitudes)
    for _ in range(LANDING_PASSES):
        build = WakfuBuild(structure, level, linear_weights(role, level, totals, turn),
                           class_id=class_id, state=state, aptitudes=held,
                           battleground=battleground, runes=runes, rune_tier=rune_tier,
                           **_given(sublimations, passives, opt_in),
                           **({'locked': locked} if locked else {}),
                           **({'levels': levels} if levels is not None else {}))
        totals = build.totals(worn)
        if totals == tried[-1][2]:
            break
        tried.append((value(role, level, totals, turn), build, totals))
    return max(tried, key=lambda one: damage_first_key(role, level, turn, least_damage,
                                                       one[0], one[2]))


def element_starts(role):
    """Weights that rank the role's elements in each order, for starting a landing from.

    A spread line goes where the weights rank highest, and the player chooses that place,
    so every order of the role's elements is a landing the game allows. A role without an
    element has none.
    """
    chosen = [name for name in ELEMENTS if name in role.elements]
    if not chosen:
        return
    for order in itertools.permutations(chosen):
        ranked = list(order) + [name for name in ELEMENTS if name not in order]
        yield {key: len(ranked) - rank
               for rank, name in enumerate(ranked)
               for key in (MASTERY_OF[name], RESISTANCE_OF[name])}


def best_landing(structure, level, role, kept, turn=None, locked=(), class_id=None,
                 state=None, aptitudes=None, battleground=False, levels=None,
                 runes=None, rune_tier=None, sublimations=None, passives=None, opt_in=None,
                 least_damage=None):
    """The ModelRound of the best landing among the starts tried, the kept one on a tie.

    The kept round is the baseline; for a role with elements the starts are the empty weights
    and one weighting per order of its elements, each landed as land does, the highest value
    winning. A set that carried a report is reported again on the landing that wins.
    """
    from .wakfu_model import WakfuBuild

    if not kept.build.spread_lines(kept.worn):
        return kept
    best = kept
    reported = bool(kept.worn.sheet_totals)
    held = None if aptitudes is None else dict(kept.worn.aptitudes)
    given = _given(sublimations, passives, opt_in)
    starts = [{}] + list(element_starts(role)) if role.elements else []
    landed = set()
    for weights in starts:
        start = WakfuBuild(structure, level, weights, class_id=class_id, state=state,
                           aptitudes=held, battleground=battleground, runes=runes,
                           rune_tier=rune_tier, **given,
                           **({'levels': levels} if levels is not None else {}))
        lands = tuple(tuple(sorted(elements)) for *_rest, elements
                      in start.spread_lines(kept.worn))
        if lands in landed:
            continue
        landed.add(lands)
        worth, build, totals = land(structure, level, role, start, kept.worn, turn, locked,
                                    class_id, state, aptitudes, battleground, levels, runes,
                                    rune_tier, sublimations, passives, opt_in,
                                    least_damage=least_damage)
        if (damage_first_key(role, level, turn, least_damage, worth, totals)
                > damage_first_key(role, level, turn, least_damage, best.value, best.totals)):
            best = kept._replace(build=build, totals=totals, value=worth)
    if best is not kept and reported:
        best.build.report(best.worn)
    return best


def land_on_floor(guard, one, structure, level, role, turn=None, locked=(), class_id=None,
                  state=None, aptitudes=None, battleground=False, levels=None, runes=None,
                  rune_tier=None, **extras):
    """Round one landed again by best_landing on the bound of DamageFloor guard, a landing
    and no solve, then seen by the guard: the set as the floor judges it."""
    one = best_landing(structure, level, role, one, turn, locked, class_id, state, aptitudes,
                       battleground, levels, runes, rune_tier, least_damage=guard.bound(),
                       **extras)
    guard.see(one.totals)
    return one


def _judged(guard, sets, relanded, top=None):
    """sets as the floor of DamageFloor guard judges them: each one that breaks it landed again
    by relanded. A landing can raise the top past what an earlier set was judged at, so they are
    judged again until the top stops rising; top: the top they were last judged at, None when
    they never were."""
    while top is None or guard.top > top:
        top = guard.top
        sets = [one if guard.holds(one.totals) else relanded(one) for one in sets]
    return sets


def solve(structure, level, role, forbidden=(), rounds=5, full_set=True, turn=None,
          locked=(), deadline=None, class_id=None, state=None, aptitudes=None,
          battleground=False, levels=None, runes=wakfu_runes.OPTIMISTIC, rune_tier=None,
          sublimations=None, passives=None, opt_in=None, damage_floor=None):
    """Best set by value; each round solves on the tangent at a point of the sets found.

    The first round linearizes at the bare character. When sublimations or passives are
    picked, a plain stage on half the time left comes first, and its best set with the
    sublimations and passives solved on its pieces is the incumbent; the first round then
    linearizes at the plain best's totals, and each later round at the totals of the incumbent,
    the best landed set. The stage's other sets with them solved on their pieces never steer
    the rounds; the best of them is kept when it beats every round. With less than
    FLOOR_SECONDS left the plain stage is skipped.
    The loop then stops settled when a round CBC proved returns the incumbent's set, or when the
    round's objective on its own set is within GAP_TOL of the incumbent's on the same objective;
    a round that ended on its clock or was solved in steps settles nothing; a
    round that does not improve and is not within GAP_TOL is followed by one round at the
    midpoint of the two sets' totals, and the loop stops unsettled when that one does not
    improve either. Otherwise the point moves toward each new set by 2/(k+2) of the way, a
    Frank-Wolfe step, the rounds stop settled once a set comes back twice in a row, and
    the best round by value is kept. turn: a
    wakfu_turn.TurnModel; each round then also prices every AP total by the
    turn at that AP (TurnModel.ap_values) instead of one AP weight. The generic
    model's best set, landed and valued on the turn, is then kept in place of
    the rounds' best when it is worth more, so best may be none of the rounds. A crash in
    a round of the generic model leaves the solve not settled, crashed counting that round
    after the class turn's; a crash on its first round keeps the class turn's rounds.

    locked: (item id, position or None) pairs every set wears. deadline: a
    time.monotonic() value; each CBC run is cut to what is left, and no round
    starts with less than MIN_ROUND_SECONDS left, so the solve is then not settled.

    class_id: the breed, whose pieces and base values count. state: the
    PlayerState the pieces' player-state conditions are read against.
    aptitudes, battleground, levels, runes, rune_tier, sublimations, passives and opt_in:
    as in wakfu_model.WakfuBuild. When a joint round that picks them ends on its clock, the
    rounds after it run in two steps and the set they give has the status wakfu_model.STEPWISE;
    such a round starts only with 2 x MIN_ROUND_SECONDS left, as does every joint round after the
    floor, and the generic model's solve after a class turn only with FLOOR_SECONDS left. A
    plain round starts the solver from the best plain round so far; a joint round starts cold.
    damage_floor: a damage preset's floor share (DamageFloor). A damage stage sets top first:
    when sublimations or passives are picked, a stage of one round on the damage alone from the
    plain best's totals, with them solved on its pieces, after the plain stage; otherwise one
    round on the damage alone at the first round's totals, after that round. Right after it the
    damage set probe solves the pieces of the stage's set with the most damage once, at the
    weight rule('damage_floor_weight_least') of the life term, so that the life those pieces
    leave free is taken. The time of both is added to the deadline, never taken from it, except
    that the deadline never passes the hard end: the deadline given plus rule('damage_floor_seconds')
    and SOLVE_MARGIN_SECONDS. After a class turn the generic model's deadline gets back the floor's
    seconds up to rule('damage_floor_seconds'). The seconds those caps take from the search
    without the floor are floor_cut_seconds. The round loop
    then runs as it does without a floor: no floor row, the incumbent by value, the same points,
    starts and time. Every set the search saw is then landed again by best_landing on the floor's
    bound, a landing and no solve, before the floor judges it, and judged again whenever a landing
    raises the top, and best is DamageFloor.pick over every set seen, the generic model's after a
    class turn included: when the pre-floor search's final set keeps the floor after
    best_landing, the floored search never returns a set of lower value. That set is reported as
    pre_floor. Only when no set of the round loop keeps the floor does the weight search run, up
    to the hard end (see _weight_search). rounds are then the sets seen.
    """
    extras = _given(sublimations, passives, opt_in)
    if turn is None:
        return _solve(structure, level, role, forbidden, rounds, full_set,
                      locked=locked, deadline=deadline, class_id=class_id,
                      state=state, aptitudes=aptitudes, battleground=battleground,
                      levels=levels, runes=runes, rune_tier=rune_tier,
                      damage_floor=damage_floor, **extras)
    if turn.damage(resource_ceiling(base_values(structure, class_id))) <= 0:
        raise ValueError('the class turn deals no damage for this role, even with '
                         'AP, MP and WP at their caps')
    classed = _solve(structure, level, role, forbidden, rounds, full_set, turn,
                     locked, deadline, class_id, state, aptitudes, battleground,
                     levels, runes, rune_tier, damage_floor=damage_floor, **extras)
    if deadline is not None and classed.damage_floor is not None:
        # What the cap on floor_seconds takes from the generic solve: its time with all of the
        # floor's seconds given back, less its time now. After a loop that ran to its cut clock
        # this is the loop's own cut again, so the larger of the two is kept
        now = time.monotonic()
        uncapped = deadline + sum((classed.floor_timing or {}).values()) - now
        left = deadline + classed.floor_seconds - now
        classed = classed._replace(floor_cut_seconds=max(
            classed.floor_cut_seconds, max(0.0, uncapped) - max(0.0, left)))
    if deadline is not None:
        deadline += classed.floor_seconds
    if out_of_time(deadline) or (
            deadline is not None and picks_sublimations_or_passives(sublimations, passives)
            and deadline - time.monotonic() < FLOOR_SECONDS):
        return classed._replace(converged=False)
    try:
        generic = _solve(structure, level, role, forbidden, rounds, full_set,
                         locked=locked, deadline=deadline, class_id=class_id,
                         state=state, aptitudes=aptitudes, battleground=battleground,
                         levels=levels, runes=runes, rune_tier=rune_tier, **extras)
    except SolverCrashed as error:
        return _crashed_after(classed, ((1, str(error.__cause__)),))
    if generic.crashed:
        classed = _crashed_after(classed, generic.crashed)
    generic = generic.best
    if generic is None:
        return classed
    worth, landed, totals = land(structure, level, role, generic.build, generic.worn,
                                 turn, locked, class_id, state, aptitudes, battleground,
                                 levels, runes, rune_tier, **extras)
    if classed.damage_floor is None:
        if classed.best is not None and classed.best.value >= worth:
            return classed
        if extras:
            landed.report(generic.worn)
        return classed._replace(
            best=ModelRound(generic.weights, landed, generic.worn, totals, worth))
    guard = DamageFloor(classed.damage_floor, role, level, turn, classed.damage_top)
    if extras:
        landed.report(generic.worn)

    def relanded(one):
        return land_on_floor(guard, one, structure, level, role, turn, locked, class_id, state,
                             aptitudes, battleground, levels, runes, rune_tier, **extras)

    sets = list(classed.rounds) + [relanded(
        ModelRound(generic.weights, landed, generic.worn, totals, worth))]
    # The set the search without the floor would have returned: the class turn's best merged
    # with the generic model's
    before = classed.pre_floor if classed.pre_floor_value >= worth else sets[-1]
    judged = _judged(guard, sets, relanded)
    best = guard.pick(judged)
    if extras:
        best.build.report(best.worn)
    pre_floor = next((now for was, now in zip(sets, judged) if was is before), before)
    return classed._replace(best=best, rounds=tuple(judged), damage_top=guard.top,
                            pre_floor=pre_floor,
                            pre_floor_value=max(classed.pre_floor_value, worth))


def _solve(structure, level, role, forbidden, rounds, full_set, turn=None,
           locked=(), deadline=None, class_id=None, state=None, aptitudes=None,
           battleground=False, levels=None, runes=None, rune_tier=None,
           sublimations=None, passives=None, opt_in=None, damage_floor=None, point=None):
    from .wakfu_model import TIME_LIMIT, STEPWISE, WakfuBuild

    guard = None if damage_floor is None else DamageFloor(damage_floor, role, level, turn)
    given = deadline
    hard_end = (None if guard is None or deadline is None
                else deadline + rule('damage_floor_seconds'))
    base = base_values(structure, class_id)
    point = bare_totals(base) if point is None else point
    minimums = role.minimums(base)
    extras = _given(sublimations, passives, opt_in)
    fight = sublimations is not None or passives is not None
    picking = picks_sublimations_or_passives(sublimations, passives)
    # AP the fight lines can take a set past the out-of-combat cap
    high = None
    if fight:
        high = OUT_OF_COMBAT_CAPS['AP'] + int(wakfu_sublimations.most_added(
            'ap', level if passives == wakfu_sublimations.SOLVE and class_id else None))
    common = dict(forbidden=forbidden, full_set=full_set, minimums=minimums,
                  class_id=class_id, state=state, aptitudes=aptitudes,
                  battleground=battleground, runes=runes, rune_tier=rune_tier)
    done = []
    best = None
    settled_by = gap = None
    damped = False
    stepwise = False
    reason = None
    crashed = ()
    seeded = plain_point = None
    staged = []
    spent = cut = 0.0
    probes = []
    timing = collections.Counter()
    stage_set = {}
    looping = True

    def extend(started, part):
        """Counts the floor's own work since started and, until the round loop ends, gives its
        time back to the loop, up to the hard end; what that cap takes is cut. No deadline is
        read after the loop, so nothing is cut there."""
        nonlocal deadline, spent, cut
        took = time.monotonic() - started
        spent += took
        timing[part] += took
        if deadline is not None and looping:
            grown = deadline + took
            if hard_end is not None and grown > hard_end + SOLVE_MARGIN_SECONDS:
                cut += grown - hard_end - SOLVE_MARGIN_SECONDS
                grown = hard_end + SOLVE_MARGIN_SECONDS
            deadline = grown

    def relanded(one):
        return land_on_floor(guard, one, structure, level, role, turn, locked, class_id,
                             state, aptitudes, battleground, levels, runes, rune_tier, **extras)

    def keep_staged(one):
        """Sees a set of the damage stage and keeps it valued on the role, then landed again
        on the bound when that lands it otherwise; the set as kept."""
        guard.see(one.totals)
        one = one._replace(value=value(role, level, one.totals, turn))
        staged.append(one)
        again = relanded(one)
        if again is not one:
            staged.append(again)
        return again

    def probe_need():
        """The time left a probe needs to start: the longest probe so far, else the rule's."""
        return max((one['seconds'] for one in probes),
                   default=rule('damage_floor_probe_seconds'))

    def probe(one, t, nearest, limit, keep, kind):
        """(the set keep made of it, crashes) of one probe: the pieces of set one pinned,
        everything else solved on the weights of weighted_role(role, t) at the totals of
        nearest, a set on those pieces, from nearest's solution; limit: the monotonic
        deadline of the solve. The role's minimums hold, MP, WP and a ferocity past the
        critical cap at least at the knees of the pieces (_knees). The set is landed on the
        bound, handed to keep, and recorded; None when the solver found none."""
        started = time.monotonic()
        at = nearest.totals
        wrole, wturn = weighted_role(role, t), weighted_turn(turn, role, t)
        weights = linear_weights(wrole, level, at, wturn)
        options = {}
        if turn is not None:
            options['ap_values'] = (wturn.ap_values(at) if high is None
                                    else wturn.ap_values(at, high))
        if levels is not None:
            options['levels'] = levels
        pinned = [(item.id, position) for position, item in one.worn.items()]
        try:
            build = WakfuBuild(structure, level, weights, start=_start_of(nearest),
                               prune_locked_positions=True, **common, **extras,
                               **{**options, 'locked': pinned})
            build.minimums.update(_knees(guard, one.totals, build.totals(one.worn), minimums))
            worn = build.build().solve(limit)
        except pulp.PulpSolverError as error:
            return None, ((len(done) + 1, str(error)),)
        if worn is None:
            return None, ()
        worth, landed, totals = land(structure, level, role, build, worn, turn, locked,
                                     class_id, state, aptitudes, battleground, levels, runes,
                                     rune_tier, least_damage=guard.bound(), **extras)
        if fight:
            landed.report(worn)
        here = keep(ModelRound(weights, landed, worn, totals, worth, build.objective_of(worn)))
        probes.append({
            'kind': kind, 't': t, 'pieces': sorted(item.id for item in one.worn.values()),
            'damage': guard.damage(here.totals), 'value': here.value,
            'life': components(role, level, here.totals, turn).get('life'),
            'holds': guard.holds(here.totals), 'seconds': time.monotonic() - started})
        return here, ()

    def damage_probe():
        """The crashes of the damage set probe: one probe on the pieces of the staged set with
        the most damage, at the least weight of the life term."""
        if not staged:
            return ()
        started = time.monotonic()
        pieces = max(staged, key=lambda one: guard.damage(one.totals))
        stage_set['set'] = pieces
        stage_set['probe'], more = probe(
            pieces, rule('damage_floor_weight_least'), pieces,
            started + rule('damage_floor_probe_seconds'), keep_staged, 'damage set')
        extend(started, 'damage set probe')
        return more

    def damage_round(at):
        """The crashes of one round on the damage alone at point at, its set staged, then the
        damage set probe."""
        started = time.monotonic()
        weights = linear_weights(guard.role, level, at, guard.turn)
        options = {}
        if turn is not None:
            options['ap_values'] = (guard.turn.ap_values(at) if high is None
                                    else guard.turn.ap_values(at, high))
        if levels is not None:
            options['levels'] = levels
        try:
            build = WakfuBuild(structure, level, weights,
                               start=_start_of(max(done, key=lambda one: one.value)),
                               **common, **extras, **options,
                               **({'locked': locked} if locked else {}))
            worn = build.build().solve(deadline)
        except pulp.PulpSolverError as error:
            return ((len(done) + 1, str(error)),)
        finally:
            extend(started, 'damage stage')
        if worn is None:
            return ()
        started = time.monotonic()
        damage, landed, totals = land(structure, level, guard.role, build, worn, guard.turn,
                                      locked, class_id, state, aptitudes, battleground, levels,
                                      runes, rune_tier, **extras)
        if fight:
            landed.report(worn)
        keep_staged(ModelRound(weights, landed, worn, totals, damage))
        extend(started, 'damage stage')
        return damage_probe()

    if picking:
        shared = dict(forbidden=forbidden, rounds=rounds, full_set=full_set, turn=turn,
                      locked=locked, class_id=class_id, state=state, aptitudes=aptitudes,
                      battleground=battleground, levels=levels, runes=runes,
                      rune_tier=rune_tier)
        floor, seeded, plain_point, crashed = _floor(structure, level, role, shared, deadline,
                                                     extras, common, high)
        if floor is not None:
            done.append(floor)
            best = floor
            point = plain_point
        if floor is not None and guard is not None:
            started = time.monotonic()
            found, also, _point, more = _floor(
                structure, level, guard.role,
                {**shared, 'turn': guard.turn, 'rounds': 1, 'point': plain_point},
                deadline, extras, common, high)
            crashed += more
            for one in (found, also):
                if one is not None and (one is found or one.key != found.key):
                    keep_staged(one)
            extend(started, 'damage stage')
            crashed += damage_probe()
    for number in range(max(1, rounds)):
        if done and out_of_time(deadline):
            break
        if ((stepwise or picking) and done and deadline is not None
                and deadline - time.monotonic() < 2 * MIN_ROUND_SECONDS):
            break
        weights = linear_weights(role, level, point, turn)
        options = {}
        if turn is not None:
            options['ap_values'] = (turn.ap_values(point) if high is None
                                    else turn.ap_values(point, high))
        if levels is not None:
            options['levels'] = levels
        try:
            if stepwise:
                build, worn = _in_steps(structure, level, weights, common, locked, options,
                                        extras, best, deadline)
                if worn is not None:
                    worn.status = STEPWISE
            else:
                start = None
                if not picking and done:
                    start = _start_of(max(done, key=lambda one: one.value))
                build = WakfuBuild(structure, level, weights, start=start, **common, **extras,
                                   **options, **({'locked': locked} if locked else {}))
                worn = build.build().solve(joint_deadline(deadline, picking))
        except pulp.PulpSolverError as error:
            if not done:
                raise SolverCrashed(
                    'the solver crashed on the first round: %s' % error) from error
            crashed += ((len(done) + 1, str(error)),)
            break
        if worn is None:
            reason = getattr(build, 'reason', None)
            break
        worth, landed, totals = land(structure, level, role, build, worn, turn,
                                     locked, class_id, state, aptitudes, battleground,
                                     levels, runes, rune_tier, **extras)
        if fight:
            landed.report(worn)
        if not picking:
            done.append(ModelRound(weights, landed, worn, totals, worth))
            if len(done) > 1 and done[-2].key == done[-1].key:
                settled_by = 'key'
                break
            point = blend(point, totals, 2 / (number + 2))
            if guard is not None and number == 0 and not out_of_time(deadline):
                crashed += damage_round(point)
            continue
        here = ModelRound(weights, landed, worn, totals, worth, build.objective_of(worn))
        done.append(here)
        if worn.status == TIME_LIMIT:
            stepwise = True
        if best is None or worth > best.value + 1e-9:
            best = here
            point = totals
            damped = False
            continue
        proven = worn.status not in (TIME_LIMIT, STEPWISE)
        if proven and here.key == best.key:
            # A round CBC proved came back to the incumbent: its status is the round's
            best.worn.status = worn.status
            settled_by, gap = 'key', 0.0
            break
        if damped:
            # The midpoint round did not improve either
            break
        gap = here.objective - build.objective_of(best.worn)
        if proven and gap <= GAP_TOL:
            settled_by = 'gap'
            break
        point = blend(best.totals, totals, 0.5)
        damped = True
    looping = False
    if not done:
        return ModelSolve((), None, False, reason)
    if seeded is not None and seeded.value > best.value + 1e-9:
        done.append(seeded)
        best = seeded
        settled_by = None
    if not picking:
        best = max(done, key=lambda one: one.value)
    if crashed:
        settled_by = None
    if guard is None:
        return ModelSolve(tuple(done), best, settled_by is not None, reason, settled_by, gap,
                          crashed)
    started = time.monotonic()
    looped = done + ([seeded] if seeded is not None and all(one is not seeded for one in done)
                     else [])
    looped = [relanded(one) for one in looped]
    seen = _judged(guard, looped + staged, relanded)
    extend(started, 'judging')
    if not any(guard.holds(one.totals) for one in seen[:len(looped)]):
        started, top = time.monotonic(), guard.top
        crashed += _weight_search(guard, seen, stage_set, probe, probe_need, relanded, hard_end)
        seen = _judged(guard, seen, relanded, top)
        extend(started, 'weight search')
    pre_floor = seen[next(index for index, one in enumerate(done) if one is best)]
    kept = guard.pick(seen)
    if fight:
        kept.build.report(kept.worn)
    if kept.key != best.key or crashed:
        settled_by = None
    return ModelSolve(tuple(seen), kept, settled_by is not None, reason, settled_by, gap,
                      crashed, damage_top=guard.top, damage_floor=damage_floor,
                      floor_seconds=spent if hard_end is None else min(spent, hard_end - given),
                      floor_cut_seconds=cut, pre_floor=pre_floor, probes=probes,
                      floor_timing=dict(timing), pre_floor_value=best.value)


KNEES = ('mp', 'wp')
# Kept at their knee only where one more point adds no damage
FLAT_KNEES = ('ferocity',)


def _knees(guard, totals, own, minimums):
    """{stat key: lowest total} the MP and WP of a probe on the pieces of a set keep, and its
    ferocity where the set's critical chance is at its cap.

    For each the knee of the set: the smallest total, at or below the one of totals, at which
    the damage of totals with that total lowered still equals the set's damage, found by a
    downward scan as TurnModel.ap_values scans. It is at least the role's minimum and at most
    own, the set's total in the probe's model, so the set's own solution stays feasible.
    Ferocity is kept only when one more point adds no damage and its knee is above the role's
    minimum: the weights are the slope just above totals, so past the cap they price it at
    nothing and a probe would sell it below the cap, where each point costs damage."""
    here = guard.damage(totals)
    knees = {}
    for key in KNEES + FLAT_KNEES:
        floor = int(minimums.get(key, 0))
        lowered = collections.Counter(totals)
        knee = int(totals.get(key, 0))
        if key in FLAT_KNEES:
            lowered[key] = knee + 1
            if guard.damage(lowered) > here * (1 + 1e-9):
                continue
        for number in range(knee - 1, floor - 1, -1):
            lowered[key] = number
            if guard.damage(lowered) < here * (1 - 1e-9):
                break
            knee = number
        knee = min(own.get(key, 0), max(floor, knee))
        if key in KNEES or knee > floor:
            knees[key] = knee
    return knees


class _PieceSet:
    """A piece set the weight search narrows: lo, the largest weight of the life term at which
    it kept the floor, hi, the smallest at which it broke (1 until one did), and held, its
    latest probe that kept the floor, the one the next probe starts from."""

    def __init__(self, one, held, lo):
        self.one, self.held, self.lo, self.hi = one, held, lo, 1.0

    @property
    def left(self):
        return self.hi - self.lo


def _pieces_of(one):
    return frozenset((position, item.id) for position, item in one.worn.items())


def _weight_search(guard, seen, stage_set, probe, need, relanded, limit):
    """The crashes of the search on the weight t of the life term, each set it lands added to
    seen.

    The objective is ln(damage) + t x (value - ln(damage)), t = 1 the value and t = 0 the
    damage alone, so a weight between keeps pieces that carry the damage and gives the rest
    to the life. Each probe pins the pieces of one set seen, solves everything else, and is
    landed on the bound, so a set always comes back and is judged as it lands. The pieces are
    those of stage_set['set'], the damage set the damage set probe has already solved at the
    least weight, when that probe kept the floor, then of the sets seen that break it, the
    most damage first, up to rule('damage_floor_weight_sets') probed in all; a set whose value
    is not above the best set that keeps the floor is skipped, since a lower weight on fixed
    pieces only gives value away. A new set is probed at the least weight and dropped when
    that breaks the floor. Each kept set is then narrowed by bisection, the one with the most value
    first, until its weights are rule('damage_floor_weight_step') apart. A probe starts only
    when the time left before limit, a monotonic deadline or None, covers need() seconds; a
    crash ends the search."""
    least = rule('damage_floor_weight_least')
    step = rule('damage_floor_weight_step')

    def keep(raw):
        here = relanded(raw)
        seen.append(here)
        return here

    def ready():
        return limit is None or limit - time.monotonic() >= need()

    def best_value():
        return max((one.value for one in seen if guard.holds(one.totals)), default=-math.inf)

    chosen = []
    first = stage_set.get('probe')
    if first is not None and guard.holds(first.totals):
        chosen.append(_PieceSet(stage_set['set'], first, least))
    known = {_pieces_of(one.one) for one in chosen}
    if 'set' in stage_set:
        known.add(_pieces_of(stage_set['set']))
    others = []
    for one in sorted((one for one in seen if not guard.holds(one.totals)),
                      key=lambda one: -guard.damage(one.totals)):
        if _pieces_of(one) not in known:
            known.add(_pieces_of(one))
            others.append(one)
    probed = len(chosen)
    for one in others:
        if probed >= rule('damage_floor_weight_sets') or not ready():
            break
        if one.value <= best_value():
            continue
        probed += 1
        here, more = probe(one, least, one, limit, keep, 'weight search')
        if more:
            return more
        if here is not None and guard.holds(here.totals):
            chosen.append(_PieceSet(one, here, least))
    while ready():
        open_ = [one for one in chosen if one.left > step + 1e-12]
        if not open_:
            break
        narrowing = max(open_, key=lambda one: one.held.value)
        middle = (narrowing.lo + narrowing.hi) / 2
        here, more = probe(narrowing.one, middle, narrowing.held, limit, keep, 'weight search')
        if more:
            return more
        if here is not None and guard.holds(here.totals):
            narrowing.lo, narrowing.held = middle, here
        else:
            narrowing.hi = middle
    return ()


def _floor(structure, level, role, shared, deadline, extras, common, high):
    """(round, seeded, point, crashed) of the floor, (None, None, None, ()) when it is not run.

    A plain stage on PLAIN_SHARE of the time left finds sets with sublimations and passives
    left out. The floor is the better, on the systems model at the plain best's totals, of the
    plain best itself and the plain best with sublimations and passives solved on its pieces;
    the rounds after the floor climb from it and linearize at the plain best's totals, the
    point. seeded is the best of the floor and of every other distinct plain set (best plain
    value first) with sublimations and passives solved on its pieces, each landed at its own
    totals; it never steers the rounds. Only the pieces are pinned, so each locked solve holds
    the locked piece of a position alone. A solve after the first runs only with
    FLOOR_SECONDS left, and the first is skipped when the plain stage left no time for it.
    crashed: (1, message) of each crash in a later round of the plain stage or in a locked
    solve, as both build round 1.
    """
    from .wakfu_model import STEPWISE, WakfuBuild

    if deadline is not None and deadline - time.monotonic() < FLOOR_SECONDS:
        return None, None, None, ()
    sublimations, passives = plain_modes(extras.get('sublimations'), extras.get('passives'))
    try:
        plain = _solve(structure, level, role, deadline=plain_deadline(deadline),
                       sublimations=sublimations, passives=passives,
                       opt_in=extras.get('opt_in'), **shared)
    except SolverCrashed:
        return None, None, None, ()
    if plain.best is None:
        return None, None, None, ()
    turn, levels, locked = shared['turn'], shared['levels'], shared['locked']
    seeds = [plain.best]
    for one in sorted(plain.rounds, key=lambda one: -one.value):
        if all(one.key != seed.key for seed in seeds):
            seeds.append(one)
    candidates = []
    crashed = tuple((1, message) for _, message in plain.crashed)
    first = None
    for index, seed in enumerate(seeds):
        point = seed.totals
        weights = linear_weights(role, level, point, turn)
        options = {}
        if turn is not None:
            options['ap_values'] = turn.ap_values(point, high)
        if levels is not None:
            options['levels'] = levels
        pinned = [(item.id, position) for position, item in seed.worn.items()]
        build = WakfuBuild(structure, level, weights, start=_start_of(seed),
                           prune_locked_positions=True, **common, **extras,
                           **{**options, 'locked': pinned})
        if first is None:
            first = (build, weights, point)
        if out_of_time(deadline):
            break
        if index and deadline is not None and deadline - time.monotonic() < FLOOR_SECONDS:
            break
        try:
            worn = build.build().solve(joint_deadline(deadline, True))
        except pulp.PulpSolverError as error:
            crashed += ((1, str(error)),)
            continue
        if worn is not None:
            candidates.append((index, worn, build, weights) + land(
                structure, level, role, build, worn, turn, locked, shared['class_id'],
                shared['state'], shared['aptitudes'], shared['battleground'], levels,
                shared['runes'], shared['rune_tier'], **extras))
    build, weights, point = first
    candidates.append((0, plain.best.worn, build, weights) + land(
        structure, level, role, build, plain.best.worn, turn, locked, shared['class_id'],
        shared['state'], shared['aptitudes'], shared['battleground'], levels,
        shared['runes'], shared['rune_tier'], **extras))
    rounds = []
    chosen = []
    for kept in ([one for one in candidates if not one[0]], candidates):
        pick = max(kept, key=lambda one: one[4])
        if chosen and pick is chosen[0]:
            rounds.append(rounds[0]._replace())
            continue
        chosen.append(pick)
        _index, worn, build, weights, worth, landed, totals = pick
        landed.report(worn)
        worn.status = STEPWISE
        rounds.append(ModelRound(weights, landed, worn, totals, worth, build.objective_of(worn)))
    return rounds[0], rounds[1], point, crashed


def _in_steps(structure, level, weights, common, locked, options, extras, best, deadline):
    """(build, worn) of one round solved in two steps, (build, None) when a step gave no set.

    Step 1 is the model without sublimations and passives, the incumbent's counted as lines no
    choice changes, and it picks the pieces; it starts from the incumbent's values. Step 2 is the
    whole model on those pieces, pruned to them, and starts from step 1's values.
    """
    from .wakfu_model import WakfuBuild

    held = {} if best is None else best.build.held_lines(best.worn)
    middle = deadline
    if deadline is not None:
        now = time.monotonic()
        middle = now + FIRST_STEP_SHARE * max(0, deadline - now)
    first = WakfuBuild(structure, level, weights, fight_constants=held, start=_start_of(best),
                       **common, **options, **({'locked': locked} if locked else {}))
    pieces = first.build().solve(middle)
    if pieces is None:
        return first, None
    pinned = [(item.id, position) for position, item in pieces.items()]
    second = WakfuBuild(structure, level, weights, start=pieces.solution_values or None,
                        prune_locked_positions=True, **common, **extras,
                        **{**options, 'locked': pinned})
    return second, second.build().solve(deadline)
