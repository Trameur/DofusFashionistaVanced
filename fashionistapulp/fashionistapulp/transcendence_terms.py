# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the tip and the solver share about transcendence runes."""

from fractions import Fraction
from functools import lru_cache

from .dracorunes import (ELEMENT_PAIRS, POWER_LINE, DAMAGE_LINE,
                         RESISTANCE_ELEMENTS)
from .exo_options import forgeable_type

TRANSCENDENCE_VERSIONS = ('dofus3', 'beta', 'dofus2')


def takes_transcendence_rune(type_name, weapon_key):
    """True when a piece of this type and weapon key can take a transcendence rune."""
    return forgeable_type(type_name, weapon_key)


WEIGHT_CAP = 101

ELEMENT_BLOCKED = frozenset(stat for pair in ELEMENT_PAIRS for stat in pair)
RESISTANCE_BLOCKED = frozenset(
    element + suffix for element in RESISTANCE_ELEMENTS
    for suffix in ('res', 'resper'))
POWER_BLOCKED = ELEMENT_BLOCKED | {POWER_LINE, DAMAGE_LINE, 'neutdam'}

_BLOCKED_BY_KIND = {'element': ELEMENT_BLOCKED,
                    'resistance': RESISTANCE_BLOCKED,
                    'power': POWER_BLOCKED}


def solver_takes_rune(type_name, weapon_key):
    """True when the solver may put a rune on a piece of this type (no weapons)."""
    return bool(forgeable_type(type_name, weapon_key)) and type_name != 'Weapon'


def copy_takes_rune(type_name, weapon_key, overed=False, exo_carrier=False,
                    temporix=False):
    """True when this copy of a piece can take a rune in the solver."""
    return (solver_takes_rune(type_name, weapon_key)
            and not (overed or exo_carrier or temporix))


def _exact(value):
    return Fraction(str(value))


@lru_cache(maxsize=4096, typed=True)
def _fits(weight, density, line):
    used = _exact(weight) + max(_exact(line or 0), 0) * _exact(density)
    return used <= WEIGHT_CAP


def rune_fits(rune, line):
    """True when the rune's weight plus the line's weight stays within the cap."""
    return _fits(rune['weight'], rune['density'], line)


def runes_by_stat(runes):
    """{stat_key: runes sorted by bonus, highest first}."""
    grouped = {}
    for rune in runes:
        grouped.setdefault(rune['stat_key'], []).append(rune)
    return {stat: sorted(group, key=lambda rune: (-_exact(rune['bonus']),
                                                  rune['id']))
            for stat, group in grouped.items()}


def _fitting(by_stat, lines, stat):
    return [rune for rune in by_stat.get(stat, ())
            if rune_fits(rune, lines.get(stat))]


def best_fitting(by_stat, lines, stats):
    """{stat: the highest-bonus rune that fits the copy's line, or None}."""
    result = {}
    for stat in stats:
        fitting = _fitting(by_stat, lines, stat)
        result[stat] = fitting[0] if fitting else None
    return result


def class_key(by_stat, lines, upper_stats):
    """Hashable key: (stat, rank of the best fitting rune or 0) per upper stat."""
    best = best_fitting(by_stat, lines, sorted(upper_stats))
    return tuple((stat, best[stat]['rank'] if best[stat] else 0)
                 for stat in sorted(upper_stats))


def class_runes(by_stat, lines, upper_stats, capped_stats):
    """The runes a class gets: the best per upper stat, plus lower ones for capped stats."""
    chosen = {}
    for stat in sorted(upper_stats):
        fitting = _fitting(by_stat, lines, stat)
        if not fitting:
            continue
        keep = fitting if stat in capped_stats else fitting[:1]
        for rune in keep:
            chosen[rune['id']] = rune
    return [chosen[key] for key in sorted(chosen)]


ROW_BOUND_STATS = frozenset({'ap', 'mp', 'range'})


def blocking_kinds(stat_key):
    """The Dracorune kinds whose block table holds this stat."""
    return frozenset(kind for kind, stats in _BLOCKED_BY_KIND.items()
                     if stat_key in stats)


@lru_cache(maxsize=4096, typed=True)
def _product(weight, bonus):
    return Fraction(str(weight)) * _exact(bonus)


def _gain(rune, weights):
    return _product(weights[rune['stat_key']], rune['bonus'])


def copy_runes(by_stat, lines, upper_stats, capped_stats, pinned, free_weights,
               draconized, bounded_weights=None):
    """class_runes without a rune on a stat no minimum reads that another free rune of the copy beats and blocks no more kinds."""
    runes = class_runes(by_stat, lines, upper_stats, capped_stats)
    weights = dict(bounded_weights or {})
    weights.update(free_weights)
    free = [rune for rune in runes
            if rune['stat_key'] in weights and rune['stat_key'] not in pinned]

    def kinds(rune):
        return blocking_kinds(rune['stat_key'])

    ordered = sorted(free, key=lambda rune: (-_gain(rune, weights),
                                             len(kinds(rune)) if draconized else 0,
                                             rune['id']))
    dominators = []
    dropped = set()
    for rune in ordered:
        gain = _gain(rune, weights)
        if any(other_gain >= gain and (not draconized or kinds(other) <= kinds(rune))
               for other, other_gain in dominators):
            dropped.add(rune['id'])
        elif rune['stat_key'] in free_weights and rune['stat_key'] not in ROW_BOUND_STATS:
            dominators.append((rune, gain))
    return [rune for rune in runes if rune['id'] not in dropped]


def dracorune_kind(variant_key):
    """'element', 'resistance' or 'power' for a Dracorune variant key."""
    return variant_key.split(':', 1)[0]


def rune_allowed_on(kind, stat_key):
    """False when the Dracorune kind blocks this stat; None kind blocks nothing."""
    if kind is None:
        return True
    return stat_key not in _BLOCKED_BY_KIND[kind]


def hall_rows():
    """The four rows as (name, blocked stats or None for all, subtracted kinds)."""
    return (('T1', None, ()),
            ('T2', ELEMENT_BLOCKED, ('element', 'power')),
            ('T3', RESISTANCE_BLOCKED, ('resistance',)),
            ('T4', POWER_BLOCKED, ('power',)))


def rows_hold(class_size, draco_counts_by_kind, rune_counts_by_stat):
    """True when every row's rune count fits what its kinds leave of the class."""
    for _name, stats, kinds in hall_rows():
        wanted = sum(count for stat, count in rune_counts_by_stat.items()
                     if stats is None or stat in stats)
        room = class_size - sum(draco_counts_by_kind.get(kind, 0)
                                for kind in kinds)
        if wanted > room:
            return False
    return True
