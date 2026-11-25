# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""One hit on a target through the stages its version's record enables."""

import math
from decimal import ROUND_HALF_UP, Decimal

from fashionistapulp.dofus_constants import percent_resist_cap


def percent_resisted(value, is_player, game_version):
    """The % resistance a hit meets: a player's stops at the version's cap, a monster's never does."""
    if value is None:
        return None
    if is_player:
        return min(value, percent_resist_cap(game_version))
    return value


def is_immune(percent):
    return percent is not None and percent >= 100


def _rounded(value, rounding):
    if rounding == 'floor':
        return float(math.floor(value))
    if rounding == 'round':
        return float(Decimal(repr(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return value


def percent_stage(value, percent, rules):
    """value after a % resistance: 100 or more stops it, below 0 raises it; an unknown one lets it through."""
    if percent is None:
        return value
    if is_immune(percent):
        return 0.0
    return _rounded(value * (100 - percent) / 100.0, rules.rounding_of('P'))


def mitigated(value, percent, rules, flat=0, dealt=(), after=()):
    """One hit of value on the target through the enabled stages in the record's order; dealt and after are percent factors, 100 being neutral."""
    if value <= 0:
        return value
    for stage in rules.applied_order():
        if stage == 'F':
            value = _rounded(value - (flat or 0), rules.rounding_of('F'))
        elif stage == 'P':
            value = max(percent_stage(value, percent, rules), 0)
        elif stage == 'R':
            for factor in dealt:
                value = max(_rounded(value * factor / 100.0, rules.rounding_of('R')), 0)
        elif stage == 'Z':
            value = _rounded(max(value, 0), rules.rounding_of('Z'))
        else:
            raise ValueError('stage %s has no code' % stage)
    for factor in after:
        value = value * factor / 100.0
    return max(value, 0)


def expected_hit(rolls, percent, rules, flat=0, dealt=(), after=()):
    """Mean of one hit on the target over its rolls: the two ends unless a stage rounds, then every roll."""
    rolls = list(rolls)
    return sum(mitigated(value, percent, rules, flat, dealt, after)
               for value in rolls) / len(rolls)


def needs_every_roll(rules):
    return rules.rounds()
