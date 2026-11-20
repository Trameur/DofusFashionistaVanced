# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The dracorune variants of an item as stat id deltas, and the safe pruning of them."""

from collections import namedtuple

from . import dracorunes

Variant = namedtuple('Variant', 'key delta')

PruneContext = namedtuple('PruneContext', 'weights lower upper capped')

UNKNOWN_KEY = 'id%d'


def delta_items(delta):
    return delta.items() if isinstance(delta, dict) else delta


def build_context(weights, lower=(), upper=(), capped=()):
    """Weights by stat id, plus the G (lower bound), L (upper bound) and C (cap) stat ids."""
    weights = dict(weights)
    for stat_id in weights:
        if not isinstance(stat_id, int) or isinstance(stat_id, bool):
            raise TypeError('weights are keyed by stat id, got %r' % (stat_id,))
    return PruneContext(weights, frozenset(lower), frozenset(upper),
                        frozenset(capped))


def classify(stat_id, context):
    """The classes of a stat among 'G', 'L' and 'C', or ('F',) when it has none."""
    found = tuple(letter for letter, members in (
        ('G', context.lower), ('L', context.upper), ('C', context.capped))
        if stat_id in members)
    return found or ('F',)


def condition_bounds(items):
    """(lower, upper) stat ids the equip conditions of these items bound."""
    lower, upper = set(), set()
    for item in items:
        lower.update(stat_id for stat_id, _ in item.min_stats_to_equip)
        upper.update(stat_id for stat_id, _ in item.max_stats_to_equip)
        for gates in item.or_conditions:
            for stat_id, is_max, _ in gates:
                (upper if is_max else lower).add(stat_id)
    return frozenset(lower), frozenset(upper)


def set_cap_stats(sets):
    """The stat ids a set max cap bounds from above."""
    return frozenset(stat_id for item_set in sets
                     for _, stat_id, _ in item_set.max_caps)


def item_cap_stats(items):
    """The stat ids a worn item's max cap bounds from above."""
    return frozenset(stat_id for item in items
                     for stat_id, _ in getattr(item, 'max_caps', None) or ())


def gain_bound(delta, context):
    """(ub, safe): the most the delta adds to the objective, and if it keeps G and L."""
    ub = 0
    safe = True
    for stat_id, change in delta_items(delta):
        if change == 0:
            continue
        gain = context.weights.get(stat_id, 0) * change
        classes = classify(stat_id, context)
        if 'G' in classes or 'L' in classes:
            if 'G' in classes and change > 0:
                safe = False
            if 'L' in classes and change < 0:
                safe = False
            if gain > 0:
                safe = False
        elif 'C' in classes:
            ub += max(0, gain)
        else:
            ub += gain
    return ub, safe


def optimistic_bound(delta, context):
    """ub plus the weight the delta adds on G and L stats, to rank variants."""
    ub, _ = gain_bound(delta, context)
    for stat_id, change in delta_items(delta):
        if change and set(classify(stat_id, context)) & {'G', 'L'}:
            ub += max(0, context.weights.get(stat_id, 0) * change)
    return ub


def dominated(delta, context):
    ub, safe = gain_bound(delta, context)
    return safe and ub <= 0


def _difference(delta, other):
    result = dict(delta_items(delta))
    for stat_id, change in delta_items(other):
        result[stat_id] = result.get(stat_id, 0) - change
    return {stat_id: change for stat_id, change in result.items() if change}


def _drop_dominated_by_base(variants, context):
    return [variant for variant in variants
            if not dominated(variant.delta, context)]


def _drop_dominated_in_item(variants, context):
    """Drop a variant that another kept one of the item beats, smaller key first."""
    kept = []
    for variant in sorted(variants, key=lambda one: one.key):
        if any(dominated(_difference(variant.delta, other.delta), context)
               for other in kept):
            continue
        kept = [other for other in kept
                if not dominated(_difference(other.delta, variant.delta),
                                 context)]
        kept.append(variant)
    return kept


def _ranked(variants, context):
    return sorted(variants,
                  key=lambda one: (-optimistic_bound(one.delta, context), one.key))


def _cap(variants, context, condition_cap, item_cap):
    """The optional size caps, off by default. Returns (variants, capped)."""
    capped = False
    if condition_cap is not None:
        useful = [one for one in variants
                  if optimistic_bound(one.delta, context) > 0]
        only = [one for one in variants
                if optimistic_bound(one.delta, context) <= 0]
        if len(only) > condition_cap:
            capped = True
            only = _ranked(only, context)[:condition_cap]
        variants = useful + only
    if item_cap is not None and len(variants) > item_cap:
        capped = True
        variants = _ranked(variants, context)[:item_cap]
    return variants, capped


def prune_item(variants, context, condition_cap=None, item_cap=None):
    """(kept, capped): the variants of one item that can still beat its base and each other."""
    variants = _drop_dominated_by_base(variants, context)
    variants = _drop_dominated_in_item(variants, context)
    return _cap(variants, context, condition_cap, item_cap)


def prune(candidates, context, condition_cap=None, item_cap=None):
    """(kept, capped) over {item_id: [Variant]}; items left with none vanish."""
    kept = {}
    capped = False
    for item_id, variants in candidates.items():
        one, was_capped = prune_item(variants, context, condition_cap,
                                     item_cap)
        capped = capped or was_capped
        if one:
            kept[item_id] = one
    return kept, capped


def count_variants(candidates):
    return sum(len(variants) for variants in candidates.values())


def _key_of(structure, stat_id):
    stat = structure.get_stat_by_id(stat_id)
    return stat.key if stat is not None and stat.key else UNKNOWN_KEY % stat_id


def variant_delta(base_lines, variant_lines):
    """Non-zero {key: variant value - base value} between two line dicts."""
    delta = {}
    for key in set(base_lines) | set(variant_lines):
        change = variant_lines.get(key, 0) - base_lines.get(key, 0)
        if change:
            delta[key] = change
    return delta


def item_variants(item, runes, structure):
    """The variants of one item, deltas as sorted (stat_id, change) pairs."""
    stats = [(_key_of(structure, stat_id), value)
             for stat_id, value in item.stats]
    base = {}
    for key, value in stats:
        base[key] = base.get(key, 0) + value
    found = []
    for key, lines in dracorunes.variants(stats, runes):
        delta = variant_delta(base, dict(lines))
        if not delta:
            continue
        pairs = []
        for line_key, change in delta.items():
            stat = structure.get_stat_by_key(line_key)
            if stat is None:
                raise ValueError('rune line %s has no stat' % line_key)
            pairs.append((stat.id, change))
        found.append(Variant(key, tuple(sorted(pairs))))
    return found


def is_eligible(item, structure, runes):
    return dracorunes.eligible_item(
        structure.get_type_name_by_id(item.type), item.weapon_key,
        item.ankama_id, structure.game_version, runes)


def candidates(items, runes, structure):
    """({item_id: [Variant]}, [(item_id, message)]) for the eligible items."""
    found = {}
    problems = []
    if not runes:
        return found, problems
    for item in items:
        if not is_eligible(item, structure, runes):
            continue
        try:
            variants = item_variants(item, runes, structure)
        except ValueError as error:
            problems.append((item.id, str(error)))
            continue
        if variants:
            found[item.id] = variants
    return found, problems
