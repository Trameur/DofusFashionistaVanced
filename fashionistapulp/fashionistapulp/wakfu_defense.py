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

"""Wakfu's defensive formulas: life, resistance, block, armor, and their solver weights.

effective life = (life + armor) / (share of a hit taken x block factor); the share
taken averages the four elements over the mix of hits a role receives.
"""

import math

from .wakfu_stats import ELEMENTS as ELEMENT_NAMES
from .wakfu_value_rules import RULES

ELEMENTS = tuple(name.lower() for name in ELEMENT_NAMES)
RESISTANCE_OF = {element: 'res_%s_percent' % element for element in ELEMENTS}
LIFE_PERCENT = 'hp_percent'
ELEMENTAL_RESISTANCE = 'res_in_percent'
CRITICAL_RESISTANCE = 'critical_res'
REAR_RESISTANCE = 'res_backstab'
ARMOR_GIVEN = 'armor_given_percent'
ARMOR_RECEIVED = 'armor_received_percent'
CONTENTS = ('pvm', 'pvp')
NO_SELF_ARMOR = 'no readable self armor row: the class armor turn is 0'


def rule(name):
    return RULES[name].value


def resistance_percent(raw):
    """Resistance percent the game applies: whole percent, toward zero, capped."""
    percent = 100 * (1 - rule('resistance_base') ** (raw / 100))
    # 1 - 0.8 is 0.19999999999999996 in floats
    return min(math.trunc(round(percent, 9)), rule('resistance_cap_percent'))


def share_taken(raw):
    """Share of a hit that goes through a raw resistance, whole percents ignored."""
    floor = 1 - rule('resistance_cap_percent') / 100
    return max(rule('resistance_base') ** (raw / 100), floor)


def raw_life(level, totals):
    """Health points before the percent of health points."""
    return (rule('base_life') + rule('life_per_level') * level
            + totals.get('hp', 0))


def life(level, totals):
    """Maximum health points: the raw ones plus their percent, rounded down."""
    raw = raw_life(level, totals)
    return raw + raw * totals.get(LIFE_PERCENT, 0) // 100


def mean_share_taken(totals):
    """Share of a hit that goes through, averaged over the four elements."""
    plain = totals.get(ELEMENTAL_RESISTANCE, 0)
    return sum(share_taken(totals.get(RESISTANCE_OF[element], 0) + plain)
               for element in ELEMENTS) / len(ELEMENTS)


def block_factor(totals):
    block = min(max(totals.get('block', 0), 0), 100)
    return 1 - (1 - rule('block_multiplier')) * block / 100


def hit_mix(content='pvm'):
    """The hits a role receives: [(critical, rear, share, multiplier)], shares sum to 1.

    A hit comes from the front, the side or the rear; each kind is critical or not.
    """
    if content not in CONTENTS:
        raise KeyError(content)
    critical = rule('received_critical_share')[content]
    rear = rule('received_rear_share')[content]
    side = rule('received_side_share')
    positions = ((False, 1 - rear - side, 1),
                 (False, side, rule('side_hit_multiplier')),
                 (True, rear, rule('rear_hit_multiplier')))
    return [(is_critical, is_rear, share * (critical if is_critical else 1 - critical),
             multiplier * (rule('critical_multiplier') if is_critical else 1))
            for is_critical in (False, True)
            for is_rear, share, multiplier in positions]


def _mean_over_mix(mix, values):
    """Mean of one value per mix entry, weighted by share x multiplier.

    Written as the first value plus the weighted differences, so equal values
    give back that value exactly.
    """
    first = values[0]
    norm = sum(share * multiplier for _, _, share, multiplier in mix)
    return first + sum(share * multiplier * (value - first)
                       for (_, _, share, multiplier), value in zip(mix, values)) / norm


def _raw(totals, element, critical, rear):
    raw = totals.get(RESISTANCE_OF[element], 0) + totals.get(ELEMENTAL_RESISTANCE, 0)
    if critical and rule('critical_resistance_adds_to_raw'):
        raw += totals.get(CRITICAL_RESISTANCE, 0)
    if rear and rule('rear_resistance_adds_to_raw'):
        raw += totals.get(REAR_RESISTANCE, 0)
    return raw


def taken(totals, content='pvm'):
    """Share of a hit that goes through, over the four elements and the mix of hits.

    Critical and rear resistance join the raw resistance on the hits they apply
    to, before the cap; with both at 0 this is mean_share_taken.
    """
    mix = hit_mix(content)
    return sum(_mean_over_mix(mix, [share_taken(_raw(totals, element, critical, rear))
                                    for critical, rear, _, _ in mix])
               for element in ELEMENTS) / len(ELEMENTS)


def armor(level, totals, armor_turn=0):
    """Health points of armor held: armor_turns_held turns of the class's self armor.

    armor_turn is the armor the class gives itself in one turn, before the gear's
    percents; armor never passes armor_cap_share_of_life of the life.
    """
    gear = ((1 + totals.get(ARMOR_GIVEN, 0) / 100)
            * (1 + totals.get(ARMOR_RECEIVED, 0) / 100))
    held = armor_turn * rule('armor_turns_held') * max(gear, 0)
    return min(held, rule('armor_cap_share_of_life') * life(level, totals))


def class_armor_turn(turn):
    """(armor_turn, notes) from the armor family turn of the class.

    turn: the Turn of wakfu_turn.TurnModel(spells, role, 'armor'), or None. A class whose
    spells hold no readable armor row for its caster has no armor turn: 0 and a note.
    """
    if turn is None or turn.damage <= 0:
        return 0.0, (NO_SELF_ARMOR,)
    return float(turn.damage), ()


def effective_life(level, totals, content='pvm', armor_turn=0):
    return ((life(level, totals) + armor(level, totals, armor_turn))
            / (taken(totals, content) * block_factor(totals)))


def defense_weights(defense, level, totals, content='pvm', armor_turn=0):
    """{stat key: percent of value per point} of defense x log(effective life).

    The slope just above totals; a stat past its cap, or at the edge of its band,
    carries no weight.
    """
    mix = hit_mix(content)
    through = taken(totals, content)
    held = armor(level, totals, armor_turn)
    current = life(level, totals)
    cap = rule('armor_cap_share_of_life')
    capped = held >= cap * current
    # the life term of the weights shrinks by the armor it sits next to
    scale = current / (current + held) if armor_turn and not capped else 1
    weights = {
        'hp': 100 * defense / raw_life(level, totals) * scale,
        LIFE_PERCENT: 100 * defense / (100 + totals.get(LIFE_PERCENT, 0)) * scale,
    }
    slope = math.log(1 / rule('resistance_base')) / 100
    floor = 1 - rule('resistance_cap_percent') / 100

    def reach(elements, critical_only=False, rear_only=False):
        total = 0
        for element in elements:
            total += _mean_over_mix(mix, [
                _uncapped(totals, element, critical, rear, floor)
                if (critical or not critical_only) and (rear or not rear_only) else 0
                for critical, rear, _, _ in mix])
        return total

    for element in ELEMENTS:
        through_here = reach((element,))
        if through_here:
            weights[RESISTANCE_OF[element]] = (
                100 * defense * slope * through_here / len(ELEMENTS) / through)
    for key, name, critical_only, rear_only in (
            (CRITICAL_RESISTANCE, 'critical_resistance_adds_to_raw', True, False),
            (REAR_RESISTANCE, 'rear_resistance_adds_to_raw', False, True)):
        through_here = reach(ELEMENTS, critical_only, rear_only) if rule(name) else 0
        if through_here:
            weights[key] = 100 * defense * slope * through_here / len(ELEMENTS) / through
    if 0 <= totals.get('block', 0) < 100:
        weights['block'] = (100 * defense * (1 - rule('block_multiplier')) / 100
                            / block_factor(totals))
    given = 1 + totals.get(ARMOR_GIVEN, 0) / 100
    received = 1 + totals.get(ARMOR_RECEIVED, 0) / 100
    if armor_turn and not capped and given > 0 and received > 0:
        base = armor_turn * rule('armor_turns_held') / (current + held)
        weights[ARMOR_GIVEN] = defense * base * received
        weights[ARMOR_RECEIVED] = defense * base * given
    return weights


def _uncapped(totals, element, critical, rear, floor):
    """Share a hit takes while it is above the cap; 0 once resistance stops counting."""
    here = rule('resistance_base') ** (_raw(totals, element, critical, rear) / 100)
    return here if here > floor else 0
