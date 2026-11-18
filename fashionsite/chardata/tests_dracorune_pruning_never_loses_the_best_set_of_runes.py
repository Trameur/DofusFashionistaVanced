# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The safe pruning of dracorune variants keeps the best set of runes, every time."""

import itertools
import random
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp.dracorune_terms import (
    Variant, build_context, optimistic_bound, candidates, classify, condition_bounds, dominated,
    gain_bound, item_variants, prune, prune_item, set_cap_stats,
    variant_delta)

RUNES = {
    'source_tag': 'synthetic',
    'runes': [
        {'item_id': 1, 'kind': 'element', 'target': 'agi'},
        {'item_id': 2, 'kind': 'element', 'target': 'str'},
        {'item_id': 3, 'kind': 'resistance'},
        {'item_id': 4, 'kind': 'power', 'keep': 0.7},
    ],
    'item_types': ['Hat'],
    'rounding': 'floor',
}

KEYS = ('str', 'int', 'cha', 'agi', 'earthdam', 'airdam', 'pow', 'dam',
        'vit', 'earthres', 'airres')


def structure():
    stats = {number: SimpleNamespace(id=number, key=key)
             for number, key in enumerate(KEYS, 1)}
    by_key = {stat.key: stat for stat in stats.values()}
    return SimpleNamespace(
        game_version='beta', get_stat_by_id=stats.get,
        get_stat_by_key=by_key.get,
        get_type_name_by_id={1: 'Hat', 2: 'Weapon'}.get)


def stat_id(key):
    return KEYS.index(key) + 1


def hat(item_id, **lines):
    return SimpleNamespace(
        id=item_id, type=1, weapon_key=None, ankama_id=item_id,
        stats=[(stat_id(key), value) for key, value in lines.items()],
        min_stats_to_equip=[], max_stats_to_equip=[], or_conditions=[])


def best_value(base, groups, context, bounds, caps, runes_allowed):
    """Best objective over every choice of at most runes_allowed variants, one
    per item, or None when no choice meets the bounds."""
    best = None
    options = [[None] + list(variants) for variants in groups]
    for choice in itertools.product(*options):
        if sum(1 for one in choice if one is not None) > runes_allowed:
            continue
        totals = dict(base)
        for one in choice:
            if one is not None:
                for stat, change in one.delta:
                    totals[stat] = totals.get(stat, 0) + change
        if any(totals.get(stat, 0) < low for stat, low in bounds[0].items()):
            continue
        if any(totals.get(stat, 0) > high for stat, high in bounds[1].items()):
            continue
        value = sum(context.weights.get(stat, 0)
                    * min(caps.get(stat, total), total)
                    for stat, total in totals.items())
        if best is None or value > best:
            best = value
    return best


def random_case(seed):
    rng = random.Random(seed)
    stats = list(range(1, 7))
    groups = []
    for _ in range(4):
        variants = []
        for number in range(rng.randint(1, 4)):
            delta = {stat: rng.randint(-6, 6)
                     for stat in rng.sample(stats, rng.randint(1, 3))}
            delta = tuple(sorted((s, d) for s, d in delta.items() if d))
            if delta:
                variants.append(Variant('v%d' % number, delta))
        groups.append(variants)
    weights = {stat: rng.choice((0, 0, 1, 2, -1, 0.5)) for stat in stats}
    lower = set(rng.sample(stats, rng.randint(0, 3)))
    upper = set(rng.sample(stats, rng.randint(0, 2)))
    capped = set(rng.sample(stats, rng.randint(0, 2)))
    base = {stat: rng.randint(0, 20) for stat in stats}
    bounds = ({stat: base[stat] - rng.randint(0, 8) for stat in lower},
              {stat: base[stat] + rng.randint(0, 8) for stat in upper})
    caps = {stat: base[stat] + rng.randint(0, 6) for stat in capped}
    context = build_context(weights, lower, upper, capped)
    return base, groups, context, bounds, caps


class PruningNeverLosesTheBestSetOfRunesTests(SimpleTestCase):

    def test_the_best_value_is_the_same_over_all_variants_and_the_kept_ones(self):
        dropped_somewhere = 0
        for seed in range(300):
            base, groups, context, bounds, caps = random_case(seed)
            kept = [prune_item(variants, context)[0] for variants in groups]
            dropped_somewhere += sum(map(len, groups)) - sum(map(len, kept))
            for allowed in (1, 2, 4):
                full = best_value(base, groups, context, bounds, caps, allowed)
                pruned = best_value(base, kept, context, bounds, caps, allowed)
                self.assertEqual(full, pruned,
                                 'seed %d with %d runes' % (seed, allowed))
        self.assertGreater(dropped_somewhere, 100)

    def test_the_random_cases_reach_a_feasible_best_set(self):
        feasible = 0
        for seed in range(300):
            base, groups, context, bounds, caps = random_case(seed)
            if best_value(base, groups, context, bounds, caps, 2) is not None:
                feasible += 1
        self.assertGreater(feasible, 200)


class TheClassesAndTheBoundTests(SimpleTestCase):

    def test_a_stat_in_no_set_is_free_and_the_others_are_named(self):
        context = build_context({}, lower=[1], upper=[1, 2], capped=[3])
        self.assertEqual(('F',), classify(9, context))
        self.assertEqual(('G', 'L'), classify(1, context))
        self.assertEqual(('L',), classify(2, context))
        self.assertEqual(('C',), classify(3, context))

    def test_a_free_stat_counts_and_a_capped_one_only_when_it_gains(self):
        context = build_context({1: 2, 2: 3}, capped=[2])
        self.assertEqual((10 + 0, True), gain_bound({1: 5, 2: -4}, context))
        self.assertEqual((10 + 6, True), gain_bound({1: 5, 2: 2}, context))

    def test_a_lower_bounded_stat_may_not_rise_and_an_upper_one_may_not_fall(self):
        context = build_context({1: 1, 2: -1}, lower=[1], upper=[2])
        self.assertFalse(gain_bound({1: 3}, context)[1])
        self.assertTrue(gain_bound({1: -3}, context)[1])
        self.assertFalse(gain_bound({2: -3}, context)[1])
        self.assertTrue(gain_bound({2: 3}, context)[1])

    def test_a_bounded_stat_that_gains_weight_is_not_safe(self):
        context = build_context({1: -1}, lower=[1])
        self.assertFalse(gain_bound({1: -3}, context)[1])

    def test_a_delta_is_dominated_when_it_cannot_gain_and_breaks_no_bound(self):
        context = build_context({1: 1, 2: 1}, lower=[2])
        self.assertTrue(dominated({1: -2, 2: -1}, context))
        self.assertFalse(dominated({1: 2, 2: -1}, context))
        self.assertFalse(dominated({1: -2, 2: 1}, context))

    def test_conditions_of_the_items_bound_both_directions(self):
        one = SimpleNamespace(min_stats_to_equip=[(1, 50)],
                              max_stats_to_equip=[(2, 0)],
                              or_conditions=[[(3, False, 5), (4, True, 9)]])
        self.assertEqual(({1, 3}, {2, 4}), tuple(map(set, condition_bounds([one]))))

    def test_set_max_caps_bound_from_above(self):
        item_set = SimpleNamespace(max_caps=[(2, 7, 3), (3, 8, 1)])
        self.assertEqual({7, 8}, set(set_cap_stats([item_set])))


class TheInItemDominanceTests(SimpleTestCase):

    def test_a_variant_another_one_beats_is_dropped(self):
        context = build_context({1: 1, 2: 1})
        weak = Variant('a', ((1, 3),))
        strong = Variant('b', ((1, 5), (2, 1)))
        kept, capped = prune_item([weak, strong], context)
        self.assertEqual(['b'], [one.key for one in kept])
        self.assertFalse(capped)

    def test_two_variants_with_the_same_effect_keep_the_smaller_key(self):
        context = build_context({1: 1})
        kept, _ = prune_item([Variant('z', ((1, 4),)),
                              Variant('m', ((1, 4),))], context)
        self.assertEqual(['m'], [one.key for one in kept])

    def test_variants_that_each_win_somewhere_both_stay(self):
        context = build_context({1: 1}, lower=[2])
        kept, _ = prune_item([Variant('a', ((1, 3), (2, -1))),
                              Variant('b', ((1, 1),))], context)
        self.assertEqual(['a', 'b'], sorted(one.key for one in kept))

    def test_a_variant_that_only_lowers_what_it_must_not_is_dropped(self):
        context = build_context({1: 1}, lower=[2])
        kept, _ = prune_item([Variant('a', ((1, 3), (2, -1))),
                              Variant('b', ((1, 3), (2, -3)))], context)
        self.assertEqual(['a'], [one.key for one in kept])

    def test_a_variant_that_loses_to_the_base_is_dropped(self):
        context = build_context({1: 1})
        kept, _ = prune_item([Variant('a', ((1, -3),))], context)
        self.assertEqual([], kept)

    def test_an_item_left_with_nothing_leaves_the_result(self):
        context = build_context({1: 1})
        kept, _ = prune({7: [Variant('a', ((1, -3),))],
                         8: [Variant('b', ((1, 3),))]}, context)
        self.assertEqual({8}, set(kept))


class TheSizeCapsStayOffUnlessAskedTests(SimpleTestCase):

    def item_cap_case(self):
        context = build_context({1: 1}, lower=[2, 3, 4])
        found = [Variant('a', ((1, 5), (2, -1))),
                 Variant('b', ((1, 3), (3, -1))),
                 Variant('c', ((1, 1), (4, -1)))]
        return found, context

    def test_no_cap_keeps_every_survivor_and_does_not_flag_it(self):
        found, context = self.item_cap_case()
        kept, capped = prune_item(found, context)
        self.assertEqual(['a', 'b', 'c'], sorted(one.key for one in kept))
        self.assertFalse(capped)

    def test_the_item_cap_keeps_the_best_bound_first_and_flags_it(self):
        found, context = self.item_cap_case()
        kept, capped = prune_item(found, context, item_cap=2)
        self.assertTrue(capped)
        self.assertEqual({'a', 'b'}, {one.key for one in kept})

    def test_an_item_cap_above_the_count_flags_nothing(self):
        found, context = self.item_cap_case()
        self.assertFalse(prune_item(found, context, item_cap=3)[1])

    def condition_case(self):
        context = build_context({1: 1}, lower=[2, 3])
        found = [Variant('w', ((1, 2),)), Variant('x', ((2, 3),)),
                 Variant('y', ((3, 3),))]
        return found, context

    def test_the_condition_cap_limits_the_variants_that_gain_no_weight(self):
        found, context = self.condition_case()
        kept, capped = prune_item(found, context, condition_cap=1)
        self.assertTrue(capped)
        self.assertEqual({'w', 'x'}, {one.key for one in kept})
        kept, capped = prune_item(found, context, condition_cap=0)
        self.assertEqual({'w'}, {one.key for one in kept})

    def test_a_variant_gaining_weight_on_a_bounded_stat_survives_the_condition_cap(self):
        context = build_context({1: 1}, lower=[1])
        found = [Variant('m', ((1, 3), (2, -3)))]
        self.assertEqual(0, gain_bound(found[0].delta, context)[0])
        self.assertEqual(3, optimistic_bound(found[0].delta, context))
        kept, capped = prune_item(found, context, condition_cap=0)
        self.assertEqual(['m'], [one.key for one in kept])
        self.assertFalse(capped)

    def test_the_item_cap_ranks_a_bounded_weight_gain_above_a_free_one(self):
        context = build_context({1: 5, 3: 1}, lower=[1])
        found = [Variant('a', ((1, 3), (2, -3))), Variant('b', ((3, 2),))]
        kept, _ = prune_item(found, context, item_cap=1)
        self.assertEqual(['a'], [one.key for one in kept])

    def test_weights_keyed_by_stat_key_are_refused(self):
        with self.assertRaises(TypeError):
            build_context({'agi': 1})

    def test_a_condition_cap_above_the_count_flags_nothing(self):
        found, context = self.condition_case()
        kept, capped = prune_item(found, context, condition_cap=2)
        self.assertFalse(capped)
        self.assertEqual(3, len(kept))


class TheVariantDeltasTests(SimpleTestCase):

    def test_a_delta_lists_only_the_lines_that_changed(self):
        self.assertEqual({'agi': 30, 'str': -30},
                         variant_delta({'str': 30, 'vit': 5},
                                       {'agi': 30, 'vit': 5}))

    def test_an_element_rune_gives_stat_id_deltas(self):
        runes = dict(RUNES, runes=[RUNES['runes'][0]])
        found = item_variants(hat(1, str=30, earthdam=4, vit=5), runes,
                              structure())
        self.assertEqual(
            [Variant('element:str>agi', tuple(sorted([
                (stat_id('str'), -30), (stat_id('earthdam'), -4),
                (stat_id('agi'), 30), (stat_id('airdam'), 4)])))], found)

    def test_a_merged_line_adds_to_the_line_it_lands_on(self):
        runes = dict(RUNES, runes=[RUNES['runes'][3]])
        found = item_variants(hat(1, str=100, earthdam=10, pow=5), runes,
                              structure())
        delta = dict(found[0].delta)
        self.assertEqual(70, delta[stat_id('pow')])
        self.assertEqual(-100, delta[stat_id('str')])

    def test_a_variant_with_the_same_lines_as_the_item_is_never_a_candidate(self):
        runes = dict(RUNES, runes=[RUNES['runes'][3]])
        item = hat(1, str=30, vit=50)
        same = [('power', {'str': 30, 'vit': 50})]
        with mock.patch('fashionistapulp.dracorune_terms.dracorunes.variants',
                        return_value=same):
            self.assertEqual([], item_variants(item, runes, structure()))
            found, problems = candidates([item], runes, structure())
        self.assertEqual({}, found)
        self.assertEqual([], problems)
        self.assertEqual([], item_variants(hat(1, vit=50), runes, structure()))

    def test_a_line_whose_stat_has_no_key_is_left_untouched(self):
        keyless = structure()
        stats = keyless.get_stat_by_id
        keyless.get_stat_by_id = lambda number: (
            SimpleNamespace(id=99, key=None) if number == 99 else stats(number))
        runes = dict(RUNES, runes=[RUNES['runes'][0]])
        item = hat(1, str=30)
        item.stats.append((99, 7))
        item.stats.append((98, 4))
        self.assertIsNone(keyless.get_stat_by_id(98))
        found = item_variants(item, runes, keyless)
        self.assertEqual(1, len(found))
        moved = [number for number, _ in found[0].delta]
        self.assertNotIn(99, moved)
        self.assertNotIn(98, moved)

    def test_only_eligible_items_get_candidates(self):
        weapon = hat(5, str=10)
        weapon.type = 2
        found, _ = candidates([hat(1, str=10), weapon], RUNES, structure())
        self.assertEqual({1}, set(found))

    def test_a_version_without_runes_has_no_candidates(self):
        self.assertEqual(({}, []), candidates([hat(1, str=10)], None,
                                              structure()))

    def test_a_rune_line_without_a_stat_sets_the_item_aside(self):
        sparse = structure()
        sparse.get_stat_by_key = {'str': SimpleNamespace(id=1, key='str')}.get
        runes = dict(RUNES, runes=[RUNES['runes'][0]])
        found, problems = candidates([hat(1, str=10)], runes, sparse)
        self.assertEqual({}, found)
        self.assertEqual([1], [item_id for item_id, _ in problems])
