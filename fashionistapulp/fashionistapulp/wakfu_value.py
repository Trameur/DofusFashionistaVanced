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
    if not armor_turn and models and 'armor' in models and role.shares.get('life'):
        armor_turn = class_armor_turn(models['armor'].best(totals))[0]
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
    """

    def __new__(cls, rounds, best, converged, reason=None, settled_by=None, gap=None,
                crashed=()):
        self = super().__new__(cls, rounds, best, converged)
        self.reason = reason
        self.settled_by = settled_by
        self.gap = gap
        self.crashed = tuple(crashed)
        return self

    def _replace(self, **changes):
        converged = changes.get('converged', self.converged)
        return type(self)(changes.get('rounds', self.rounds), changes.get('best', self.best),
                          converged, self.reason,
                          changes.get('settled_by', self.settled_by if converged else None),
                          changes.get('gap', self.gap), self.crashed)


class SolverCrashed(RuntimeError):
    """The solver died on the first round, so there is no set to keep."""


def _crashed_after(classed, crashes):
    """The class turn's solve, not settled, with the generic model's crashed rounds counted
    after its own."""
    return ModelSolve(classed.rounds, classed.best, False, classed.reason, None, classed.gap,
                      classed.crashed + tuple((len(classed.rounds) + number, message)
                                              for number, message in crashes))


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
         runes=None, rune_tier=None, sublimations=None, passives=None, opt_in=None):
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
    return max(tried, key=lambda one: one[0])


def solve(structure, level, role, forbidden=(), rounds=5, full_set=True, turn=None,
          locked=(), deadline=None, class_id=None, state=None, aptitudes=None,
          battleground=False, levels=None, runes=wakfu_runes.OPTIMISTIC, rune_tier=None,
          sublimations=None, passives=None, opt_in=None):
    """Best set by value; each round solves on the tangent at a point of the sets found.

    The first round linearizes at the bare character. When sublimations or passives are
    picked, a plain stage on half the time left comes first, and the best of its sets with the
    sublimations and passives solved on its pieces is the incumbent; the first round then
    linearizes at the plain best's totals, and each later round at the totals of the incumbent,
    the best landed set. With less than FLOOR_SECONDS left the plain stage is skipped.
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
    """
    extras = _given(sublimations, passives, opt_in)
    if turn is None:
        return _solve(structure, level, role, forbidden, rounds, full_set,
                      locked=locked, deadline=deadline, class_id=class_id,
                      state=state, aptitudes=aptitudes, battleground=battleground,
                      levels=levels, runes=runes, rune_tier=rune_tier, **extras)
    if turn.damage(resource_ceiling(base_values(structure, class_id))) <= 0:
        raise ValueError('the class turn deals no damage for this role, even with '
                         'AP, MP and WP at their caps')
    classed = _solve(structure, level, role, forbidden, rounds, full_set, turn,
                     locked, deadline, class_id, state, aptitudes, battleground,
                     levels, runes, rune_tier, **extras)
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
    if classed.best is not None and classed.best.value >= worth:
        return classed
    if extras:
        landed.report(generic.worn)
    return classed._replace(
        best=ModelRound(generic.weights, landed, generic.worn, totals, worth))


def _solve(structure, level, role, forbidden, rounds, full_set, turn=None,
           locked=(), deadline=None, class_id=None, state=None, aptitudes=None,
           battleground=False, levels=None, runes=None, rune_tier=None,
           sublimations=None, passives=None, opt_in=None):
    from .wakfu_model import TIME_LIMIT, STEPWISE, WakfuBuild

    base = base_values(structure, class_id)
    point = bare_totals(base)
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
    if picking:
        shared = dict(forbidden=forbidden, rounds=rounds, full_set=full_set, turn=turn,
                      locked=locked, class_id=class_id, state=state, aptitudes=aptitudes,
                      battleground=battleground, levels=levels, runes=runes,
                      rune_tier=rune_tier)
        floor, plain_point, crashed = _floor(structure, level, role, shared, deadline, extras,
                                             common, high)
        if floor is not None:
            done.append(floor)
            best = floor
            point = plain_point
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
    if not done:
        return ModelSolve((), None, False, reason)
    if not picking:
        best = max(done, key=lambda one: one.value)
    if crashed:
        settled_by = None
    return ModelSolve(tuple(done), best, settled_by is not None, reason, settled_by, gap,
                      crashed)


def _floor(structure, level, role, shared, deadline, extras, common, high):
    """(round, point, crashed) of the floor, (None, None, ()) when it is not run.

    A plain stage on PLAIN_SHARE of the time left finds sets with sublimations and passives
    left out. The floor is the best, on the systems model at each set's totals, of the plain
    best itself and of every distinct plain set (best plain value first) with sublimations and
    passives solved on its pieces; only the pieces are pinned, so each of those solves holds
    the locked piece of a position alone. A solve after the first runs only with FLOOR_SECONDS
    left. The point is the plain totals of the set the floor came from, where the rounds after
    the floor linearize. The first solve is skipped when the plain stage left no time for it.
    crashed: (1, message) of each crash in a later round of the plain stage or in a locked
    solve, as both build round 1.
    """
    from .wakfu_model import STEPWISE, WakfuBuild

    if deadline is not None and deadline - time.monotonic() < FLOOR_SECONDS:
        return None, None, ()
    sublimations, passives = plain_modes(extras.get('sublimations'), extras.get('passives'))
    try:
        plain = _solve(structure, level, role, deadline=plain_deadline(deadline),
                       sublimations=sublimations, passives=passives,
                       opt_in=extras.get('opt_in'), **shared)
    except SolverCrashed:
        return None, None, ()
    if plain.best is None:
        return None, None, ()
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
            candidates.append((worn, build, weights, point) + land(
                structure, level, role, build, worn, turn, locked, shared['class_id'],
                shared['state'], shared['aptitudes'], shared['battleground'], levels,
                shared['runes'], shared['rune_tier'], **extras))
    build, weights, point = first
    candidates.append((plain.best.worn, build, weights, point) + land(
        structure, level, role, build, plain.best.worn, turn, locked, shared['class_id'],
        shared['state'], shared['aptitudes'], shared['battleground'], levels,
        shared['runes'], shared['rune_tier'], **extras))
    worn, build, weights, point, worth, landed, totals = max(candidates, key=lambda one: one[4])
    landed.report(worn)
    worn.status = STEPWISE
    return (ModelRound(weights, landed, worn, totals, worth, build.objective_of(worn)),
            point, crashed)


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
