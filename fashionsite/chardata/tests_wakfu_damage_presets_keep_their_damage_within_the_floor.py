import collections
import math
import types
from unittest import mock

from django.test import SimpleTestCase

from chardata import tests_a_wakfu_solve_lands_its_spread_lines_on_the_best_order as spread
from chardata import tests_wakfu_role_presets_keep_damage_first as damage_first
from chardata.tests_wakfu_solve_obeys_every_rule_on_invented_items import (
    ALPHA, HELMET, LEVEL, InventedItemsCase, ids, item)

from fashionistapulp import wakfu_model, wakfu_presets, wakfu_turn, wakfu_value
from fashionistapulp.wakfu_model import PROVEN, WakfuBuild
from fashionistapulp.wakfu_value_rules import CHOICE, RULES

ROLE = wakfu_value.Role(('fire',), 'distance', shares={'damage': 1, 'life': 0.25})
NEAR_HELM = 3004
PICKING = ({}, {'sublimations': 'optimistic'})
PICKS_BOTH = {'sublimations': 'optimistic', 'passives': 'solve'}
#: the solver calls of a preset without a floor, as the unchanged solve makes them
HEAD_CALLS = [('plain', 0, True, [(7, 'head')], 0.0),
              ('plain', 900.0, False, [(7, 'head')], 0.0),
              ('plain', 933.333, False, [(7, 'head')], 0.0),
              ('picking', 800, True, [], -400.0)]
SEARCH_RULES = ('damage_floor_seconds', 'damage_floor_weight_least', 'damage_floor_weight_step',
                'damage_floor_weight_sets', 'damage_floor_probe_seconds')


def set_of(mastery, worth):
    """A round whose totals deal the damage of this fire mastery, worth this value."""
    totals = collections.Counter({'ap': 6, 'dmg_fire_percent': mastery})
    return wakfu_value.ModelRound({}, None, None, totals, worth)


class TheWeightedRoleTests(SimpleTestCase):
    TOTALS = collections.Counter({'ap': 6, 'dmg_fire_percent': 100, 'hp': 3000})

    def test_the_weighted_role_is_the_role_at_one_and_its_damage_alone_at_zero(self):
        self.assertEqual(ROLE.shares, wakfu_value.weighted_role(ROLE, 1).shares)
        self.assertEqual({'damage': 1}, wakfu_value.weighted_role(ROLE, 0).shares)
        self.assertEqual(wakfu_value.damage_role(ROLE).shares,
                         wakfu_value.weighted_role(ROLE, 0).shares)
        half = wakfu_value.weighted_role(ROLE, 0.3)
        self.assertEqual({'damage': 1, 'life': 0.25 * 0.3}, half.shares)
        self.assertEqual((ROLE.elements, ROLE.reach), (half.elements, half.reach))
        role = wakfu_value.weighted_role(ROLE, 0.3)
        own = wakfu_value.linear_weights(ROLE, LEVEL, self.TOTALS)
        damage = wakfu_value.linear_weights(wakfu_value.damage_role(ROLE), LEVEL, self.TOTALS)
        weights = wakfu_value.linear_weights(role, LEVEL, self.TOTALS)
        self.assertTrue(set(own) - set(damage))
        for key in set(own) | set(damage):
            self.assertAlmostEqual(0.3 * own.get(key, 0) + 0.7 * damage.get(key, 0),
                                   weights.get(key, 0), places=9)

    def test_the_weighted_turn_prices_ap_on_the_weighted_role(self):
        turn = wakfu_turn.RoleTurns(ROLE, LEVEL, {'damage': object()}, {'ap': 1})
        for t in (0, 0.3, 1):
            made = wakfu_value.weighted_turn(turn, ROLE, t)
            self.assertIs(type(turn), type(made))
            self.assertEqual(wakfu_value.weighted_role(ROLE, t).shares, made.role.shares)
            self.assertEqual((LEVEL, turn.models, turn.scales),
                             (made.level, made.models, made.scales))
        self.assertEqual(wakfu_value.damage_turn(turn, ROLE).role.shares,
                         wakfu_value.weighted_turn(turn, ROLE, 0).role.shares)
        self.assertEqual(wakfu_value.damage_turn(turn, ROLE).models,
                         wakfu_value.weighted_turn(turn, ROLE, 0).models)
        bare = object()
        self.assertIs(bare, wakfu_value.weighted_turn(bare, ROLE, 0.3))
        self.assertIsNone(wakfu_value.weighted_turn(None, ROLE, 0.3))

    def test_the_weight_search_rules_are_choices_and_the_rounds_within_the_floor_are_gone(self):
        for name in SEARCH_RULES:
            self.assertEqual(CHOICE, RULES[name].status, name)
            self.assertTrue(RULES[name].value > 0, name)
        self.assertTrue(0 < RULES['damage_floor_weight_least'].value
                        < RULES['damage_floor_weight_step'].value * 2)
        self.assertTrue(RULES['damage_floor_weight_step'].value < 1)
        self.assertNotIn('damage_floor_rounds_seconds', RULES)
        self.assertNotIn('damage stage found', RULES['damage_floor'].source)
        self.assertIn('every set', RULES['damage_floor'].source)


class TheDamageFloorTests(InventedItemsCase):
    @classmethod
    def catalogue(cls):
        return damage_first.TheDamageComesFirstTests.catalogue()

    def solved(self, role, **options):
        found = wakfu_value.solve(self.structure, LEVEL, role, class_id=ALPHA, rounds=4,
                                  **options)
        self.assertIsNotNone(found.best)
        return found

    def test_the_damage_floor_rule_is_a_choice_for_each_content(self):
        rule = RULES['damage_floor']
        self.assertEqual(CHOICE, rule.status)
        self.assertEqual(set(wakfu_value.CONTENTS), set(rule.value))
        for share in rule.value.values():
            self.assertTrue(0 < share < 1)

    def test_only_the_damage_presets_carry_the_damage_floor(self):
        from fashionistapulp import wakfu_solve
        for content in wakfu_value.CONTENTS:
            for preset in wakfu_presets.DAMAGE_PRESETS:
                self.assertEqual(wakfu_value.rule('damage_floor')[content],
                                 wakfu_solve.damage_floor_of(preset, content))
            others = [key for key in wakfu_presets.PRESETS
                      if key not in wakfu_presets.DAMAGE_PRESETS] + [None]
            for preset in others:
                self.assertIsNone(wakfu_solve.damage_floor_of(preset, content))

    def test_the_damage_floor_keeps_the_damage_helm_that_the_life_share_trades_away(self):
        share = wakfu_value.rule('damage_floor')['pvm']
        free = self.solved(ROLE).best
        floored = self.solved(ROLE, damage_floor=share)
        self.assertIn(damage_first.LIFE_HELM, ids(free.worn))
        self.assertLess(wakfu_value.damage_of(ROLE, LEVEL, free.totals),
                        (1 - share) * floored.damage_top)
        self.assertIn(damage_first.DAMAGE_HELM, ids(floored.best.worn))
        self.assertNotIn(damage_first.LIFE_HELM, ids(floored.best.worn))
        self.assertGreaterEqual(wakfu_value.damage_of(ROLE, LEVEL, floored.best.totals),
                                (1 - share) * floored.damage_top * (1 - 1e-9))
        self.assertEqual(share, floored.damage_floor)

    def test_the_damage_floor_keeps_the_best_value_among_the_sets_within_it(self):
        free = self.solved(ROLE).best
        damage = self.solved(wakfu_value.damage_role(ROLE)).best
        rounds = [one._replace(value=wakfu_value.value(ROLE, LEVEL, one.totals))
                  for one in (free, damage)]
        top = wakfu_value.damage_of(ROLE, LEVEL, damage.totals)
        self.assertIs(rounds[1], wakfu_value.DamageFloor(0.05, ROLE, LEVEL, top=top).pick(rounds))
        self.assertIs(rounds[0], wakfu_value.DamageFloor(0.15, ROLE, LEVEL, top=top).pick(rounds))

    def test_the_picking_solve_keeps_its_damage_top_floor_and_a_set_within_it(self):
        share = wakfu_value.rule('damage_floor')['pvm']
        picked = self.solved(ROLE, sublimations='optimistic', damage_floor=share)
        self.assertTrue(wakfu_value.picks_sublimations_or_passives('optimistic', None))
        self.assertEqual(share, picked.damage_floor)
        self.assertTrue(picked.damage_top > 0)
        self.assertGreaterEqual(wakfu_value.damage_of(ROLE, LEVEL, picked.best.totals),
                                (1 - share) * picked.damage_top * (1 - 1e-9))
        self.assertIn(damage_first.DAMAGE_HELM, ids(picked.best.worn))
        self.assertNotIn(damage_first.LIFE_HELM, ids(picked.best.worn))

    def test_the_damage_top_of_a_floored_solve_is_the_most_damage_of_the_sets_it_saw(self):
        share = wakfu_value.rule('damage_floor')['pvm']
        see = wakfu_value.DamageFloor.see
        for options in PICKING:
            with self.subTest(**options):
                seen = []

                def spy(guard, totals):
                    seen.append(guard.damage(totals))
                    see(guard, totals)

                with mock.patch.object(wakfu_value.DamageFloor, 'see', spy):
                    floored = self.solved(ROLE, damage_floor=share, **options)
                self.assertAlmostEqual(max(seen), floored.damage_top, places=6)
                self.assertAlmostEqual(
                    max(wakfu_value.damage_of(ROLE, LEVEL, one.totals) for one in floored.rounds),
                    floored.damage_top, places=6)
                self.assertIn('damage set', [one['kind'] for one in floored.probes])

    def test_a_probe_starts_from_the_values_of_its_piece_set_and_wears_only_its_pieces(self):
        share = wakfu_value.rule('damage_floor')['pvm']
        for options in PICKING:
            with self.subTest(**options):
                with mock.patch.object(wakfu_model, 'WakfuBuild', wraps=WakfuBuild) as built:
                    floored = self.solved(ROLE, damage_floor=share, **options)
                pinned = [call.kwargs for call in built.call_args_list
                          if call.kwargs.get('prune_locked_positions')]
                self.assertGreaterEqual(len(pinned), len(floored.probes))
                self.assertTrue(floored.probes)
                first = floored.probes[0]
                self.assertEqual('damage set', first['kind'])
                pieces = frozenset(first['pieces'])
                probes = [one for one in pinned
                          if sorted(piece for piece, _ in one['locked']) == sorted(pieces)]
                self.assertTrue(probes)
                locked = probes[0]['locked']
                self.assertTrue(all(position is not None for _, position in locked))
                starts = [one.worn.solution_values for one in floored.rounds
                          if one.ids == pieces and one.worn.solution_values]
                self.assertTrue(starts)
                self.assertIn(probes[0]['start'], starts)
                same = [one for one in floored.rounds if one.ids == pieces]
                self.assertGreaterEqual(len(same), 2)
                self.assertTrue(all(one.ids == pieces for one in same))
                free = [call.kwargs for call in built.call_args_list
                        if not call.kwargs.get('prune_locked_positions')]
                self.assertTrue(free)

    def test_a_probe_keeps_the_mp_and_wp_its_piece_set_rotation_spends(self):
        share = wakfu_value.rule('damage_floor')['pvm']
        knees = wakfu_value._knees
        for options in PICKING:
            with self.subTest(**options):
                seen = []

                def spy(guard, totals, own, minimums):
                    found = knees(guard, totals, own, minimums)
                    seen.append((found, dict(own), dict(minimums)))
                    return found

                with mock.patch.object(wakfu_value, '_knees', spy):
                    floored = self.solved(ROLE, damage_floor=share, **options)
                self.assertEqual(len(floored.probes), len(seen))
                self.assertTrue(seen)
                for found, own, minimums in seen:
                    self.assertLessEqual(set(wakfu_value.KNEES), set(found))
                    self.assertLessEqual(set(found),
                                         set(wakfu_value.KNEES + wakfu_value.FLAT_KNEES))
                    for key, knee in found.items():
                        self.assertGreaterEqual(knee, minimums.get(key, 0))
                        self.assertLessEqual(knee, own.get(key, 0))

    def test_a_floored_solve_reports_its_pre_floor_final_set(self):
        share = wakfu_value.rule('damage_floor')['pvm']
        for options in PICKING:
            with self.subTest(**options):
                floored = self.solved(ROLE, damage_floor=share, **options)
                self.assertIsNone(self.solved(ROLE, **options).pre_floor)
                self.assertIn(floored.pre_floor, floored.rounds)
                if wakfu_value.DamageFloor(share, ROLE, LEVEL, top=floored.damage_top).holds(
                        floored.pre_floor.totals):
                    self.assertGreaterEqual(floored.best.value, floored.pre_floor.value - 1e-9)

    def test_a_replaced_model_solve_keeps_its_damage_top_and_floor(self):
        fields = dict(damage_top=48.0, damage_floor=0.05, floor_seconds=3.5,
                      floor_cut_seconds=0.5, pre_floor=set_of(1000, 1.0),
                      probes=({'kind': 'damage set'},), floor_timing={'judging': 0.1},
                      pre_floor_value=1.5)
        solved = wakfu_value.ModelSolve((), None, False, **fields)
        for again in (solved._replace(converged=False),
                      wakfu_value._crashed_after(solved, ((1, 'crashed'),))):
            for name, given in fields.items():
                self.assertEqual(given, getattr(again, name), name)
        self.assertEqual(tuple(fields), wakfu_value.ModelSolve.FLOOR_FIELDS)


class TheDamageFloorKeepsTheValueTests(InventedItemsCase):
    @classmethod
    def catalogue(cls):
        return damage_first.TheDamageComesFirstTests.catalogue() + [
            item(NEAR_HELM, HELMET, 'Near Helm', dmg_fire_percent=99, hp=2500)]

    def test_a_plain_set_that_keeps_the_floor_is_never_replaced_by_a_lower_value_one(self):
        share = wakfu_value.rule('damage_floor')['pvm']
        for options in PICKING:
            for rounds in (1, 2, 4):
                with self.subTest(rounds=rounds, **options):
                    plain = wakfu_value.solve(self.structure, LEVEL, ROLE, class_id=ALPHA,
                                              rounds=rounds, **options).best
                    floored = wakfu_value.solve(self.structure, LEVEL, ROLE, class_id=ALPHA,
                                                rounds=rounds, damage_floor=share, **options)
                    self.assertIn(NEAR_HELM, ids(plain.worn))
                    self.assertGreaterEqual(wakfu_value.damage_of(ROLE, LEVEL, plain.totals),
                                            (1 - share) * floored.damage_top * (1 - 1e-9))
                    self.assertGreaterEqual(floored.best.value, plain.value - 1e-9)

    def test_a_floored_solve_picking_sublimations_and_passives_values_on_the_role(self):
        share = wakfu_value.rule('damage_floor')['pvm']
        plain = wakfu_value.solve(self.structure, LEVEL, ROLE, class_id=ALPHA, rounds=2,
                                  **PICKS_BOTH).best
        with mock.patch.object(wakfu_value, '_floor', wraps=wakfu_value._floor) as stages:
            floored = wakfu_value.solve(self.structure, LEVEL, ROLE, class_id=ALPHA, rounds=2,
                                        damage_floor=share, **PICKS_BOTH)
        value_stage = stages.call_args_list[0].args
        self.assertIs(ROLE, value_stage[2])
        self.assertNotIn('point', value_stage[3])
        self.assertEqual(2, value_stage[3]['rounds'])
        self.assertIn(NEAR_HELM, ids(plain.worn))
        self.assertGreaterEqual(wakfu_value.damage_of(ROLE, LEVEL, plain.totals),
                                (1 - share) * floored.damage_top * (1 - 1e-9))
        self.assertGreaterEqual(floored.best.value, plain.value - 1e-9)

    def test_a_probe_on_the_pieces_of_the_damage_set_returns_the_life_they_leave_free(self):
        share = wakfu_value.rule('damage_floor')['pvm']
        floored = wakfu_value.solve(self.structure, LEVEL, ROLE, class_id=ALPHA, rounds=1,
                                    damage_floor=share)
        probe = floored.probes[0]
        self.assertTrue(probe['holds'])
        self.assertEqual(wakfu_value.rule('damage_floor_weight_least'), probe['t'])
        self.assertGreaterEqual(probe['value'], max(
            one.value for one in floored.rounds
            if one.ids == frozenset(probe['pieces'])) - 1e-9)


class TheDamageFloorPickAndBoundTests(SimpleTestCase):
    def setUp(self):
        self.guard = wakfu_value.DamageFloor(0.05, ROLE, LEVEL)
        self.guard.see(set_of(1000, 0).totals)
        self.held_low, self.held_high = set_of(980, 1.0), set_of(1000, 2.0)
        self.broken, self.broken_more = set_of(800, 3.0), set_of(700, 4.0)

    def test_the_kept_round_is_the_best_value_within_the_floor_else_the_most_damage(self):
        pick = self.guard.pick
        self.assertIs(self.held_high, pick([self.broken, self.held_low, None, self.held_high,
                                            self.broken_more]))
        self.assertIs(self.held_low, pick([self.broken_more, self.held_low, self.broken]))
        self.assertIs(self.broken, pick([self.broken_more, self.broken]))
        self.assertIsNone(pick([None]))
        self.assertIsNone(pick([]))

    def test_the_top_is_the_most_damage_seen_and_the_bound_follows_it(self):
        top = self.guard.top
        self.guard.see(self.broken.totals)
        self.assertEqual(top, self.guard.top)
        self.assertAlmostEqual(0.95 * top, self.guard.bound())
        self.assertTrue(self.guard.holds(self.held_low.totals))
        self.assertFalse(self.guard.holds(self.broken.totals))
        self.guard.see(set_of(1200, 0).totals)
        self.assertGreater(self.guard.top, top)
        self.assertFalse(self.guard.holds(self.held_low.totals))


class TheLandingKeepsTheDamageFloorTests(SimpleTestCase):
    def fixture(self):
        role = wakfu_value.DamageDealer(('fire', 'water'), 'distance')
        catalogue, pieces = spread.spread_set()
        kept = spread.kept_round(role, catalogue, pieces)
        held = collections.Counter(kept.totals)
        broken = collections.Counter(held)
        broken.update(dmg_fire_percent=-held['dmg_fire_percent'],
                      dmg_water_percent=-held['dmg_water_percent'])
        top = wakfu_value.damage_of(role, spread.LEVEL, held)
        self.assertLess(wakfu_value.damage_of(role, spread.LEVEL, broken), 0.95 * top)
        return role, catalogue, pieces, kept, held, broken, top

    def solve_build(self, catalogue, model, landing, **options):
        from fashionistapulp import wakfu_legality, wakfu_solve
        with mock.patch.object(wakfu_value, 'solve', return_value=model) as solved, \
                mock.patch.object(wakfu_value, 'land', side_effect=landing), \
                mock.patch.object(wakfu_solve, '_checked'), \
                mock.patch.object(wakfu_legality, 'warnings', return_value=[]):
            built = wakfu_solve.solve_build(
                catalogue, level=spread.LEVEL, elements=('fire', 'water'), reach='distance',
                aptitudes=None, runes='none', on_class_turn=False, allow_legacy=True,
                **{'sublimations': None, 'passives': None, **options})
        return built, solved

    def test_solve_build_hands_its_floor_to_the_landing_which_refuses_an_order_below_it(self):
        _role, catalogue, _pieces, kept, held, broken, top = self.fixture()
        seen = []

        def landing(structure, level, role, build, worn, *args, least_damage=None, **kwargs):
            seen.append(least_damage)
            if len(seen) == 1:
                return kept.value + 1.0, build, broken
            return kept.value + 0.5, build, held

        def solved(**floor):
            seen.clear()
            model = wakfu_value.ModelSolve((kept,), kept, True, **floor)
            return self.solve_build(catalogue, model, landing)[0]

        floored = solved(damage_top=top, damage_floor=0.05)
        self.assertGreater(len(seen), 1)
        for bound in seen:
            self.assertAlmostEqual(0.95 * top, bound)
        self.assertEqual(held, floored.totals)
        self.assertAlmostEqual(kept.value + 0.5, floored.value)
        free = solved()
        self.assertEqual([None] * len(seen), seen)
        self.assertEqual(broken, free.totals)
        self.assertAlmostEqual(kept.value + 1.0, free.value)

    def test_solve_build_lands_the_pre_floor_set_on_the_final_bound(self):
        role, catalogue, pieces, kept, held, broken, top = self.fixture()
        before = spread.kept_round(role, catalogue, pieces)
        self.assertIsNot(kept.worn, before.worn)
        landed = {id(kept.worn): [], id(before.worn): []}

        def landing(structure, level, role, build, worn, *args, least_damage=None, **kwargs):
            landed[id(worn)].append(least_damage)
            if worn is kept.worn:
                return kept.value + 1.0, build, held
            return before.value + 0.5, build, broken if least_damage is None else held

        floor = dict(damage_top=top, damage_floor=0.05)
        model = wakfu_value.ModelSolve((kept, before), kept, True, pre_floor=before, **floor)
        built, _solved = self.solve_build(catalogue, model, landing)
        self.assertTrue(landed[id(before.worn)])
        for bound in landed[id(before.worn)] + landed[id(kept.worn)]:
            self.assertAlmostEqual(0.95 * top, bound)
        self.assertEqual(held, built.model.pre_floor.totals)
        self.assertIs(before.worn, built.model.pre_floor.worn)
        self.assertEqual(held, built.model.best.totals)
        landed[id(kept.worn)].clear()
        landed[id(before.worn)].clear()
        model = wakfu_value.ModelSolve((kept,), kept, True, pre_floor=kept, **floor)
        built, _solved = self.solve_build(catalogue, model, landing)
        self.assertIs(built.model.best, built.model.pre_floor)
        self.assertEqual([], landed[id(before.worn)])
        free = wakfu_value.ModelSolve((kept,), kept, True)
        self.assertIsNone(self.solve_build(catalogue, free, landing)[0].model.pre_floor)

    def test_a_floored_solve_gets_the_finish_margin_whether_or_not_it_picks(self):
        from fashionistapulp import wakfu_solve
        _role, catalogue, _pieces, kept, held, _broken, _top = self.fixture()
        model = wakfu_value.ModelSolve((kept,), kept, True)
        margin = min(wakfu_value.FINISH_SECONDS, 90 / 10)

        def landing(structure, level, role, build, worn, *args, **kwargs):
            return kept.value, build, held

        for floor, sublimations, cut in ((0.05, None, margin), (None, None, 0),
                                         (None, 'optimistic', margin),
                                         (0.05, 'optimistic', margin)):
            with self.subTest(floor=floor, sublimations=sublimations):
                with mock.patch.object(wakfu_solve, 'damage_floor_of', return_value=floor), \
                        mock.patch.object(wakfu_solve, 'time',
                                          types.SimpleNamespace(monotonic=lambda: 1000.0)):
                    _built, solved = self.solve_build(catalogue, model, landing, seconds=90,
                                                      sublimations=sublimations)
                self.assertEqual(1090.0 - cut, solved.call_args.kwargs['deadline'])


class Worn(dict):
    """A scripted set: one piece whose id is the set's name."""

    def __init__(self, name):
        super().__init__(head=types.SimpleNamespace(id=name))
        self.name, self.runes, self.aptitudes = name, {}, {}
        self.sublimation_ids = self.special_ids = self.passives = None
        self.solution_values = {'solved': name}
        self.status = PROVEN


class TheScriptedFloorSearchTests(SimpleTestCase):
    """The floored search on scripted sets, each given its damage, value and objective.

    The script names the set each solve returns, in call order; a probe past the script takes
    the damage and value that curve(pieces, t) gives, and by default breaks the floor. now is
    the clock; a solve takes the seconds of its set, else of '*', or runs to its deadline when
    its set is in to_clock."""

    def setUp(self):
        self.sets, self.landed, self.relanded, self.script = {}, {}, {}, []
        self.points, self.bounds, self.relandings, self.builds = [], [], [], []
        self.extra, self.own, self.seconds, self.to_clock = {}, {}, {}, set()
        self.curve = lambda pieces, t: (0, 0.0)
        self.role, self.damage = mock.Mock(), types.SimpleNamespace(name='damage alone')
        self.role.minimums = lambda base: {'mp': 3, 'wp': 6}
        self.stages, self.deadlines = {}, []
        self.now, self.stage_seconds = 0.0, 0.0
        self.sets['P'] = (500, 1.0, 0.0)
        for patch in (
                mock.patch.object(wakfu_value, 'time',
                                  types.SimpleNamespace(monotonic=lambda: self.now)),
                mock.patch.object(wakfu_value.DamageFloor, 'damage',
                                  lambda floor, totals: totals['damage']),
                mock.patch.object(wakfu_value, 'damage_role', lambda role: self.damage),
                mock.patch.object(wakfu_value, 'damage_turn', lambda turn, role: turn),
                mock.patch.object(wakfu_value, 'weighted_role',
                                  lambda role, t: types.SimpleNamespace(weighted=True, t=t)),
                mock.patch.object(wakfu_value, 'weighted_turn', lambda turn, role, t: turn),
                mock.patch.object(wakfu_value, 'components',
                                  lambda role, level, totals, turn=None: collections.Counter(
                                      {'life': totals['life']})),
                mock.patch.object(wakfu_value, 'linear_weights', self.weights),
                mock.patch.object(wakfu_value, 'base_values', lambda *args: collections.Counter()),
                mock.patch.object(wakfu_value, 'bare_totals', lambda base: collections.Counter()),
                mock.patch.object(wakfu_value, 'value',
                                  lambda role, level, totals, turn=None: totals['worth']),
                mock.patch.object(wakfu_value, 'land', self.land),
                mock.patch.object(wakfu_value, 'best_landing', self.best_landing),
                mock.patch.object(wakfu_value, '_floor', self.stage),
                mock.patch.object(wakfu_model, 'WakfuBuild', self.build)):
            patch.start()
            self.addCleanup(patch.stop)

    def given(self, **sets):
        for name, (damage, worth, *objective) in sets.items():
            self.sets[name] = (damage, worth, objective[0] if objective else 0.0)

    def totals(self, name, damage=None, worth=None):
        given = self.sets[name]
        return collections.Counter({'damage': given[0] if damage is None else damage,
                                    'worth': given[1] if worth is None else worth, name: 1,
                                    'mp': 7, 'wp': 9, **self.extra.get(name, {})})

    def model_totals(self, name):
        return collections.Counter({**self.totals(name), 'mp': 4, 'wp': 7,
                                    **self.own.get(name, {})})

    def round_of(self, name):
        if name is None:
            return None
        return wakfu_value.ModelRound({}, mock.Mock(), Worn(name), self.totals(name),
                                      self.sets[name][1], self.sets[name][2])

    def weights(self, role, level, totals, *args):
        self.points.append((role, dict(totals)))
        return {'t': role.t if getattr(role, 'weighted', None) is True else None,
                'at': round(totals['damage'], 3)}

    def land(self, structure, level, role, build, worn, *args, least_damage=None, **kwargs):
        self.bounds.append(least_damage)
        damage, worth = self.landed.get(worn.name, self.sets[worn.name][:2])
        return worth, mock.Mock(), self.totals(worn.name, damage, worth)

    def best_landing(self, structure, level, role, kept, *args, least_damage=None, **kwargs):
        self.relandings.append(least_damage)
        if kept.worn.name not in self.relanded:
            return kept
        given = self.relanded[kept.worn.name]
        damage, worth = given(least_damage) if callable(given) else given
        return kept._replace(totals=self.totals(kept.worn.name, damage, worth), value=worth)

    def stage(self, structure, level, role, shared, deadline, extras, common, high):
        """The value stage on the role itself, the damage stage on the damage role from a point
        in one round; any other call fails."""
        if role is self.role and 'point' not in shared:
            return self.stages['value']
        if role is self.damage and shared.get('point') is not None and shared['rounds'] == 1:
            self.now += self.stage_seconds
            return self.stages['damage']
        raise AssertionError('unexpected _floor call on %r with %s' % (role, sorted(shared)))

    def build(self, structure, level, weights, start=None, **options):
        if self.script:
            name = self.script.pop(0)
        elif weights.get('t') is not None and options.get('prune_locked_positions'):
            pieces, t = options['locked'][0][0], weights['t']
            name = '%s@%.5f' % (pieces, t)
            self.sets[name] = self.curve(pieces, t) + (0.0,)
        else:
            raise AssertionError('a round past the script')
        record = {'name': name, 't': weights.get('t'), 'start': start,
                  'locked': options.get('locked'), 'prune': options.get('prune_locked_positions'),
                  'minimums': dict(options.get('minimums') or {}), 'weights': weights}
        self.builds.append(record)

        def solve(deadline):
            self.deadlines.append(deadline)
            record['started'], record['deadline'] = self.now, deadline
            if name in self.to_clock and deadline is not None:
                self.now = max(self.now, deadline)
            else:
                self.now += self.seconds.get(name, self.seconds.get('*', 0.0))
            return Worn(name)

        solved = types.SimpleNamespace(solve=solve)
        return types.SimpleNamespace(build=lambda: solved, minimums=record['minimums'],
                                     objective_of=lambda worn: self.sets[worn.name][2],
                                     totals=lambda worn: self.model_totals(worn.name))

    def names(self):
        return [one['name'] for one in self.builds]

    def probes(self):
        return [one for one in self.builds if one['prune']]

    def picking(self, floor, stage, joint, seeded=None, rounds=1, probe='P', **options):
        self.script = [probe] + list(joint)
        self.stages = {'value': (self.round_of(floor), self.round_of(seeded), self.totals(floor),
                                 ()),
                       'damage': (self.round_of(stage), None, None, ())}
        return wakfu_value.solve(None, LEVEL, self.role, rounds=rounds,
                                 sublimations='optimistic', damage_floor=0.05, **options)

    def plain(self, script, rounds=1, **options):
        self.script = list(script)
        return wakfu_value.solve(None, LEVEL, self.role, rounds=rounds, damage_floor=0.05,
                                 **options)

    def least(self):
        return wakfu_value.rule('damage_floor_weight_least')

    def test_the_damage_top_is_the_most_damage_any_set_of_the_search_reached(self):
        for floor, seeded, stage, landed, top in ((1000, None, 900, 900, 1000),
                                                  (900, 1300, 1000, 1000, 1300),
                                                  (900, None, 1100, 1000, 1100),
                                                  (900, None, 1000, 1200, 1200)):
            with self.subTest(floor=floor, seeded=seeded, stage=stage, landed=landed):
                self.given(F=(floor, 5.0), S=(stage, 4.0), J=(500, 1.0))
                if seeded is not None:
                    self.given(E=(seeded, 0.5))
                self.relanded = {'S': (landed, 4.0)}
                solved = self.picking('F', 'S', ['J'], seeded='E' if seeded else None)
                self.assertEqual(top, solved.damage_top)

    def test_the_damage_top_is_the_most_damage_over_every_set_seen_probes_included(self):
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(1050, 3.9))
        self.assertEqual(1050, self.plain(['V', 'D', 'P']).damage_top)
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(990, 4.9))
        self.relanded = {'P': lambda bound: (990, 4.9) if bound < 1000 else (1060, 4.8)}
        self.curve = lambda pieces, t: (1100, 3.0)
        self.script, self.builds = ['V', 'D', 'P'], []
        solved = wakfu_value.solve(None, LEVEL, self.role, rounds=1, damage_floor=0.05)
        self.assertGreater(len(self.probes()), 1)
        self.assertEqual(1100, solved.damage_top)
        self.assertEqual(({'P'}, 4.8), (solved.best.ids, solved.best.value))

    def test_a_set_that_keeps_the_floor_only_once_relanded_on_its_bound_is_kept(self):
        self.given(F=(900, 5.0), S=(1000, 4.0), J=(940, 5.5))
        self.relanded = {'J': (960, 5.4)}
        solved = self.picking('F', 'S', ['J'])
        self.assertEqual({'J'}, solved.best.ids)
        self.assertEqual(5.4, solved.best.value)
        self.assertTrue(any(bound is not None and abs(bound - 950) < 1e-6
                            for bound in self.relandings))

    def test_the_weight_search_never_runs_when_a_pre_floor_set_keeps_the_floor(self):
        self.given(V=(960, 5.0), D=(1000, 4.0), P=(990, 4.9))
        solved = self.plain(['V', 'D', 'P'])
        self.assertEqual(['V', 'D', 'P'], self.names())
        self.assertEqual({'V'}, solved.best.ids)
        self.builds = []
        self.given(F=(960, 5.0), S=(1000, 4.0), J=(500, 1.0))
        solved = self.picking('F', 'S', ['J'])
        self.assertEqual(['P', 'J'], self.names())
        self.assertEqual({'F'}, solved.best.ids)
        self.builds = []
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(500, 1.0))
        self.plain(['V', 'D', 'P'])
        self.assertEqual(['V', 'D', 'P', 'V@%.5f' % self.least()], self.names())

    def test_a_floored_solve_never_returns_less_value_than_its_pre_floor_final_set_when_that_set_keeps_the_floor(self):
        self.curve = lambda pieces, t: (1200, 1.0)
        self.given(V=(960, 5.0), D=(1000, 4.0), P=(990, 4.9))
        solved = self.plain(['V', 'D', 'P'])
        self.assertEqual({'V'}, solved.pre_floor.ids)
        self.assertEqual({'V'}, solved.best.ids)
        self.assertGreaterEqual(solved.best.value, solved.pre_floor.value)
        for probe, relanded, kept in (((940, 9.0), {}, ({'V'}, 5.0)),
                                      ((1100, 3.0), {'V': lambda bound: (
                                          (960, 5.0) if bound < 1000 else (1050, 4.8))},
                                       ({'V'}, 4.8))):
            with self.subTest(probe=probe):
                self.given(V=(960, 5.0), D=(1000, 4.0), P=probe)
                self.relanded = relanded
                solved = self.plain(['V', 'D', 'P'])
                self.assertEqual(kept, (solved.best.ids, solved.best.value))
                self.assertTrue(wakfu_value.DamageFloor(
                    0.05, self.role, LEVEL, top=solved.damage_top).holds(
                        solved.pre_floor.totals))
                self.assertGreaterEqual(solved.best.value, solved.pre_floor.value - 1e-9)

    def test_a_binding_solve_returns_the_damage_set_pieces_with_the_life_they_left_free(self):
        self.curve = lambda pieces, t: (990, 4.9) if pieces in ('D', 'S') and t <= self.least() \
            else (900, 6.0)
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(990, 4.9))
        solved = self.plain(['V', 'D', 'P'])
        self.assertEqual(({'P'}, 4.9), (solved.best.ids, solved.best.value))
        probe = self.probes()[0]
        self.assertEqual(('P', self.least(), [('D', 'head')]),
                         (probe['name'], probe['t'], probe['locked']))
        self.assertEqual(['D'], solved.probes[0]['pieces'])
        self.assertTrue(solved.probes[0]['holds'])
        self.builds = []
        self.given(F=(800, 5.0), S=(1000, 4.0), J=(700, 4.5))
        solved = self.picking('F', 'S', ['J'])
        self.assertEqual(({'P'}, 4.9), (solved.best.ids, solved.best.value))
        probe = self.probes()[0]
        self.assertEqual(('P', self.least(), [('S', 'head')]),
                         (probe['name'], probe['t'], probe['locked']))
        self.assertEqual(['P', 'J'], self.names()[:2])

    def test_the_damage_set_probe_runs_after_the_damage_stage_and_its_time_is_added_to_the_deadline(self):
        probe_seconds = wakfu_value.rule('damage_floor_probe_seconds')
        self.now, self.stage_seconds, self.seconds = 100.0, 7.0, {'P': 0.5}
        self.given(F=(960, 5.0), S=(1000, 4.0), J=(500, 1.0))
        solved = self.picking('F', 'S', ['J'], deadline=1100.0)
        self.assertEqual(['P', 'J'], self.names())
        self.assertAlmostEqual(107.0 + probe_seconds, self.builds[0]['deadline'])
        self.assertAlmostEqual(
            107.5 + wakfu_value.JOINT_SHARE * (1107.5 - 107.5), self.builds[1]['deadline'])
        self.assertAlmostEqual(7.5, solved.floor_seconds)
        self.assertEqual('damage set', solved.probes[0]['kind'])
        self.builds, self.deadlines, self.now = [], [], 100.0
        self.seconds = {'V': 20.0, 'D': 7.0, 'P': 0.5}
        self.given(V=(900, 5.0), D=(1000, 4.0), V2=(910, 5.1))
        solved = self.plain(['V', 'D', 'P', 'V2'], rounds=2, deadline=1100.0)
        self.assertEqual(['V', 'D', 'P', 'V2'], self.names()[:4])
        self.assertEqual([1100.0, 1100.0], self.deadlines[:2])
        self.assertAlmostEqual(127.0 + probe_seconds, self.deadlines[2])
        self.assertAlmostEqual(1107.5, self.deadlines[3])
        self.assertAlmostEqual(7.5, solved.floor_seconds)

    def test_the_damage_stage_adds_its_time_to_the_deadline_of_the_rounds_after_it(self):
        joint = {}
        for seconds in (0.0, 7.0):
            with self.subTest(seconds=seconds):
                self.now, self.stage_seconds, self.deadlines = 100.0, seconds, []
                self.given(F=(960, 5.0), S=(1000, 4.0), J=(500, 1.0))
                solved = self.picking('F', 'S', ['J'], deadline=1100.0)
                self.assertEqual(2, len(self.deadlines))
                joint[seconds] = self.deadlines[1]
                self.assertEqual(seconds, solved.floor_seconds)
        self.assertAlmostEqual(7.0, joint[7.0] - joint[0.0])

    def test_every_probe_is_judged_on_its_landing_on_the_bound(self):
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(940, 4.0))
        self.landed = {'P': (960, 4.9)}
        solved = self.plain(['V', 'D', 'P'])
        self.assertEqual(({'P'}, 4.9), (solved.best.ids, solved.best.value))
        self.assertTrue(solved.probes[0]['holds'])
        self.assertEqual(960, solved.probes[0]['damage'])
        self.assertEqual([None, None], self.bounds[:2])
        self.assertGreater(len(self.bounds), 3)
        for bound in self.bounds[2:]:
            self.assertAlmostEqual(950, bound)
        self.builds, self.bounds = [], []
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(990, 5.0))
        self.landed = {'P': (900, 5.0)}
        solved = self.plain(['V', 'D', 'P'])
        self.assertEqual({'D'}, solved.best.ids)
        self.assertFalse(solved.probes[0]['holds'])
        least, self.landed = self.least(), {}
        self.curve = lambda pieces, t: (1000 - 100 * t, 5 + t)
        for relanded, index, holds, value, times in (
                ({'D@0.52500': (960, 5.6)}, 1, True, 5.6,
                 [least, 0.525, 0.7625, 0.64375, 0.584375]),
                ({'D@0.28750': (900, 9.0)}, 2, False, 5.228125,
                 [least, 0.525, 0.2875, 0.16875, 0.228125])):
            with self.subTest(relanded=sorted(relanded)):
                self.builds, self.relanded = [], relanded
                self.given(V=(900, 4.5), D=(1000, 4.0), P=(990, 4.9))
                solved = self.plain(['V', 'D', 'P'])
                record = solved.probes[index]
                self.assertEqual(('weight search', next(iter(relanded.values()))[0], holds),
                                 (record['kind'], record['damage'], record['holds']))
                self.assertTimes(times)
                self.assertAlmostEqual(value, solved.best.value)
                self.assertTrue(wakfu_value.DamageFloor(
                    0.05, self.role, LEVEL, top=solved.damage_top).holds(solved.best.totals))

    def assertTimes(self, expected):
        found = [one['t'] for one in self.probes()]
        self.assertEqual(len(expected), len(found))
        for given, probed in zip(expected, found):
            self.assertAlmostEqual(given, probed, places=9)

    def test_the_weight_search_bisects_toward_the_largest_weight_that_keeps_the_floor(self):
        self.curve = lambda pieces, t: (1000 - 100 * t, 5 + t)
        self.given(V=(900, 4.5), D=(1000, 4.0), P=(990, 4.9))
        solved = self.plain(['V', 'D', 'P'])
        self.assertTimes([self.least(), 0.525, 0.2875, 0.40625, 0.465625])
        self.assertLessEqual(0.525 - 0.465625, wakfu_value.rule('damage_floor_weight_step'))
        self.assertEqual({'D@%.5f' % 0.465625}, solved.best.ids)
        self.assertAlmostEqual(5.465625, solved.best.value)
        self.assertEqual(['damage set'] + ['weight search'] * 4,
                         [one['kind'] for one in solved.probes])
        self.assertEqual([True, False, True, True, True],
                         [one['holds'] for one in solved.probes])
        self.builds = []
        self.curve = lambda pieces, t: (1000 - 100 * t, 5 + t) if t < 0.3 else (900, 9.0)
        self.plain(['V', 'D', 'P'])
        self.assertTimes([self.least(), 0.525, 0.2875, 0.40625, 0.346875])

    def test_the_weight_search_probes_the_other_sets_it_saw_by_damage_and_drops_those_that_break(self):
        least = self.least()
        self.curve = lambda pieces, t: ({'V3': (990, 6.05), 'V4': (990, 6.4)}.get(pieces, (0, 0.0))
                                        if t <= least else (0, 0.0))
        self.given(V1=(920, 6.0), V2=(940, 6.5), W=(935, 3.0), V3=(930, 6.2), V4=(925, 6.1),
                   D=(1000, 4.0), P=(500, 1.0))
        solved = self.plain(['V1', 'D', 'P', 'V2', 'W', 'V3', 'V4'], rounds=5)
        self.assertEqual(['V1', 'D', 'P', 'V2', 'W', 'V3', 'V4'], self.names()[:7])
        searched = [one['name'].split('@')[0] for one in self.builds[7:]]
        self.assertEqual(['V2', 'V3', 'V4'], searched[:3])
        self.assertEqual([least] * 3, [one['t'] for one in self.builds[7:10]])
        for left_out in ('V1', 'W', 'P', 'D'):
            self.assertNotIn(left_out, searched)
        self.assertEqual(['V4'] * 4 + ['V3'] * 4, searched[3:])
        self.assertEqual(({'V4@%.5f' % least}, 6.4), (solved.best.ids, solved.best.value))

    def test_a_floored_solve_ends_by_its_given_deadline_plus_the_floor_seconds(self):
        cap = 8.0 + wakfu_value.SOLVE_MARGIN_SECONDS
        self.assertEqual(8.0, wakfu_value.rule('damage_floor_seconds'))
        self.now, self.to_clock = 100.0, {'V2'}
        self.seconds = {'V': 20.0, 'D': 11.5, 'P': 0.5, '*': 0.5}
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(990, 4.9), V2=(910, 5.1))
        solved = self.plain(['V', 'D', 'P', 'V2'], rounds=2, deadline=190.0)
        self.assertEqual(['V', 'D', 'P', 'V2'], self.names())
        self.assertEqual([190.0, 190.0], self.deadlines[:2])
        self.assertAlmostEqual(190.0 + cap, self.deadlines[3])
        self.assertTrue(max(self.deadlines[:2] + self.deadlines[3:]) <= 190.0 + cap + 1e-9)
        self.assertAlmostEqual(8.0, solved.floor_seconds)
        self.assertEqual(['damage set'], [one['kind'] for one in solved.probes])
        self.builds, self.deadlines, self.now = [], [], 100.0
        self.to_clock = set()
        self.seconds = {'V': 20.0, 'D': 11.5, 'P': 0.5, 'V2': 64.9, '*': 0.5}
        solved = self.plain(['V', 'D', 'P', 'V2'], rounds=2, deadline=190.0)
        searched = [one for one in self.builds if '@' in one['name']]
        self.assertEqual(2, len(searched))
        for one in searched:
            self.assertEqual(198.0, one['deadline'])
            self.assertGreaterEqual(198.0 - one['started'], 0.5 - 1e-9)
        self.assertLess(198.0 - self.now, 0.5)
        self.assertAlmostEqual(8.0, solved.floor_seconds)
        self.builds, self.deadlines, self.now, self.seconds = [], [], 100.0, {
            'V': 5.0, 'D': 11.5, 'P': 0.5, 'G': 1.0, '*': 0.5}
        self.given(V=(960, 5.0), G=(1000, 3.0))
        turn = mock.Mock(damage=lambda totals: 1)
        self.script = ['V', 'D', 'P', 'G']
        with mock.patch.object(wakfu_value, '_solve', wraps=wakfu_value._solve) as made:
            wakfu_value.solve(None, LEVEL, self.role, rounds=1, turn=turn, damage_floor=0.05,
                              deadline=190.0)
        self.assertEqual(2, len(made.call_args_list))
        self.assertEqual(198.0, made.call_args_list[1].kwargs['deadline'])

    def test_the_hard_end_records_what_it_took_from_the_round_loop(self):
        for stage, cut, spent in ((3.0, 0.0, 3.5), (11.5, 1.0, 8.0)):
            with self.subTest(stage=stage):
                self.now, self.builds, self.deadlines = 100.0, [], []
                self.seconds = {'V': 20.0, 'D': stage, 'P': 0.5}
                self.given(V=(900, 3.0), D=(1000, 4.0), P=(500, 1.0), V2=(910, 3.1))
                solved = self.plain(['V', 'D', 'P', 'V2'], rounds=2, deadline=190.0)
                self.assertAlmostEqual(cut, solved.floor_cut_seconds)
                self.assertAlmostEqual(spent, solved.floor_seconds)
                self.assertAlmostEqual(190.0 + min(stage + 0.5, 11.0), self.deadlines[3])
        self.now, self.builds, self.deadlines = 100.0, [], []
        self.seconds = {'V': 20.0, 'D': 11.5, 'P': 0.5}
        self.given(V=(960, 3.0), D=(1000, 4.0), V2=(910, 3.1))
        no_deadline = self.plain(['V', 'D', 'P', 'V2'], rounds=2)
        self.assertEqual(0.0, no_deadline.floor_cut_seconds)
        self.assertAlmostEqual(12.0, no_deadline.floor_seconds)
        self.now, self.builds, self.deadlines = 100.0, [], []
        self.seconds = {'V': 20.0, 'D': 10.5, 'P': 0.5, '*': 2.0}
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(500, 1.0))
        searched = self.plain(['V', 'D', 'P'], deadline=190.0)
        self.assertEqual(['damage set', 'weight search'], [one['kind'] for one in searched.probes])
        self.assertAlmostEqual(2.0, searched.floor_timing['weight search'])
        self.assertEqual(0.0, searched.floor_cut_seconds)

    def test_the_hard_end_records_what_it_took_from_the_generic_solve(self):
        turn = mock.Mock(damage=lambda totals: 1)
        for stage, cut in ((3.0, 0.0), (9.0, 1.5), (11.5, 4.0)):
            with self.subTest(stage=stage):
                self.now, self.builds, self.deadlines = 100.0, [], []
                self.seconds = {'V': 5.0, 'D': stage, 'P': 0.5, 'G': 1.0}
                self.given(V=(960, 5.0), D=(1000, 4.0), P=(990, 4.9), G=(1000, 3.0))
                self.script = ['V', 'D', 'P', 'G']
                solved = wakfu_value.solve(None, LEVEL, self.role, rounds=1, turn=turn,
                                           damage_floor=0.05, deadline=190.0)
                self.assertEqual(['V', 'D', 'P', 'G'], self.names())
                self.assertAlmostEqual(190.0 + min(stage + 0.5, 8.0), self.builds[3]['deadline'])
                self.assertAlmostEqual(cut, solved.floor_cut_seconds)

    def test_a_probe_starts_from_the_values_of_its_piece_set_and_wears_only_its_pieces(self):
        self.curve = lambda pieces, t: (1000 - 100 * t, 5 + t)
        self.given(V=(900, 4.5), D=(1000, 4.0), P=(990, 4.9))
        self.plain(['V', 'D', 'P'])
        probes = self.probes()
        self.assertEqual(5, len(probes))
        for one in probes:
            self.assertEqual([('D', 'head')], one['locked'])
        self.assertEqual([{'solved': 'D'}, {'solved': 'P'}, {'solved': 'P'},
                          {'solved': 'D@0.28750'}, {'solved': 'D@0.40625'}],
                         [one['start'] for one in probes])
        free = [one for one in self.builds if not one['prune']]
        self.assertEqual(['V', 'D'], [one['name'] for one in free])
        self.assertEqual([None, {'solved': 'V'}], [one['start'] for one in free])
        steered = [(role.t, totals) for role, totals in self.points
                   if getattr(role, 'weighted', None) is True]
        self.assertEqual(dict(self.totals('D')), steered[0][1])
        self.assertEqual(dict(self.totals('P')), steered[1][1])
        self.assertEqual(dict(self.totals('D@0.28750')), steered[3][1])

    def test_a_probe_keeps_the_mp_and_wp_its_piece_set_rotation_spends(self):
        penalty = mock.patch.object(wakfu_value.DamageFloor, 'damage',
                                    lambda floor, totals: totals['damage'] - 50 * max(
                                        0, 5 - totals['mp']))
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(990, 4.9))
        for minimums, own, knees in (({'mp': 3, 'wp': 6}, {'mp': 4, 'wp': 7}, {'mp': 4, 'wp': 6}),
                                     ({'mp': 3, 'wp': 6}, {'mp': 9, 'wp': 9}, {'mp': 5, 'wp': 6}),
                                     ({'mp': 6, 'wp': 6}, {'mp': 9, 'wp': 9}, {'mp': 6, 'wp': 6}),
                                     ({'mp': 3, 'wp': 8}, {'mp': 9, 'wp': 8}, {'mp': 5, 'wp': 8})):
            with self.subTest(minimums=minimums, own=own), penalty:
                self.builds, self.own = [], {'D': own}
                self.role.minimums = lambda base, minimums=minimums: dict(minimums)
                self.plain(['V', 'D', 'P'])
                probe = self.probes()[0]
                self.assertEqual(knees, probe['minimums'])
                for key, knee in knees.items():
                    self.assertGreaterEqual(knee, minimums[key])
                    self.assertLessEqual(knee, own[key])
                for one in self.builds:
                    if not one['prune']:
                        self.assertEqual(minimums, one['minimums'])

    def test_a_probe_keeps_the_ferocity_its_piece_set_holds_past_the_critical_cap(self):
        capped = mock.patch.object(wakfu_value.DamageFloor, 'damage',
                                   lambda floor, totals: totals['damage'] - 50 * max(
                                       0, 97 - totals['ferocity']))
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(990, 4.9))
        for held, own, knee in ((187, 187, 97), (97, 97, 97), (187, 120, 97), (187, 90, 90),
                                (60, 60, None)):
            with self.subTest(held=held, own=own), capped:
                self.builds = []
                self.extra = {name: {'ferocity': held} for name in ('V', 'D', 'P')}
                self.own = {'D': {'ferocity': own}}
                self.plain(['V', 'D', 'P'])
                probe = self.probes()[0]
                self.assertEqual(knee, probe['minimums'].get('ferocity'))
                for one in self.builds:
                    if not one['prune']:
                        self.assertNotIn('ferocity', one['minimums'])

    def test_a_floored_solve_reports_its_pre_floor_final_set(self):
        self.given(V=(960, 5.0), D=(1000, 4.0), P=(990, 4.9))
        solved = self.plain(['V', 'D', 'P'])
        self.assertEqual(({'V'}, 5.0), (solved.pre_floor.ids, solved.pre_floor.value))
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(990, 4.9))
        self.relanded = {'V': (960, 5.2)}
        solved = self.plain(['V', 'D', 'P'])
        self.assertEqual(({'V'}, 5.2), (solved.pre_floor.ids, solved.pre_floor.value))
        self.assertEqual(960, solved.pre_floor.totals['damage'])
        self.relanded = {}
        solved = self.plain(['V', 'D', 'P'])
        self.assertEqual({'P'}, solved.best.ids)
        self.assertEqual(({'V'}, 900), (solved.pre_floor.ids, solved.pre_floor.totals['damage']))
        self.script = ['V']
        self.assertIsNone(wakfu_value.solve(None, LEVEL, self.role, rounds=1).pre_floor)
        self.given(F=(800, 5.0), S=(1000, 4.0), J=(500, 1.0), E=(700, 6.0), K=(500, 7.0))
        for seeded, joint, pre in ((None, 'J', 'F'), ('E', 'J', 'E'), (None, 'K', 'K')):
            with self.subTest(seeded=seeded, joint=joint):
                solved = self.picking('F', 'S', [joint], seeded=seeded)
                self.assertEqual({pre}, solved.pre_floor.ids)
                self.assertIn(solved.pre_floor, solved.rounds)
        for generic, pre in ((6.0, 'G'), (4.0, 'C')):
            with self.subTest(generic=generic):
                self.given(C=(1000, 5.0), G=(1100, generic))
                solved = self.generic(['C'], 'C', 1000, 'G')
                self.assertEqual({pre}, solved.pre_floor.ids)
        for landed, raw, pre in ((4.9, 5.2, 'C'), (5.1, 4.8, 'G')):
            with self.subTest(landed=landed, raw=raw):
                self.given(C=(1000, landed), G=(800, 5.0))
                solved = self.generic(['C'], 'C', 1000, 'G', pre_value=raw)
                self.assertEqual({'C'}, solved.best.ids)
                self.assertEqual(({pre}, max(raw, 5.0)),
                                 (solved.pre_floor.ids, solved.pre_floor_value))

    def test_the_round_loop_steers_by_value_whether_or_not_a_set_keeps_the_floor(self):
        self.given(F=(800, 5.0), S=(1000, 4.0), J=(700, 6.0), H=(950, 5.5), K=(500, 1.0))
        solved = self.picking('F', 'S', ['J', 'K'], rounds=2)
        steered = [totals for role, totals in self.points if role is self.role]
        self.assertEqual([dict(self.totals('F')), dict(self.totals('J'))], steered[-2:])
        self.assertEqual(['P', 'J', 'K'], self.names()[:3])
        self.points = []
        self.given(J=(700, 4.5, 1.0))
        self.picking('F', 'S', ['J', 'K'], rounds=2)
        steered = [totals for role, totals in self.points if role is self.role]
        self.assertEqual([dict(self.totals('F')),
                          dict(wakfu_value.blend(self.totals('F'), self.totals('J'), 0.5))],
                         steered[-2:])

    def test_a_set_judged_before_the_top_rises_is_judged_again_on_the_raised_bound(self):
        self.given(F=(960, 5.0), S=(1000, 4.0), J=(500, 1.0))
        self.relanded = {'F': lambda bound: ((960, 5.0) if bound < 1000 else
                                             (1050, 5.0) if bound < 1200 else (1350, 4.9)),
                         'S': lambda bound: (1000, 4.0) if bound < 1000 else (1400, 3.5),
                         'J': (1100, 3.0)}
        solved = self.picking('F', 'S', ['J'])
        self.assertEqual(1400, solved.damage_top)
        self.assertEqual(({'F'}, 4.9), (solved.best.ids, solved.best.value))
        self.given(A=(1000, 6.0), B=(1000, 4.0), G=(1100, 5.0))
        self.relanded = {'A': lambda bound: (1050, 5.8) if bound < 1100 else (1240, 5.5),
                         'B': (1300, 4.5)}
        solved = self.generic(['A', 'B'], 'A', 1000, 'G')
        self.assertEqual(1300, solved.damage_top)
        self.assertEqual(({'A'}, 5.5), (solved.best.ids, solved.best.value))
        self.given(V=(900, 5.0), D=(1000, 4.0), P=(1200, 4.2))
        self.relanded = {'D': lambda bound: (1000, 4.0) if bound < 1100 else (1150, 4.6)}
        solved = self.plain(['V', 'D', 'P'])
        self.assertEqual(1200, solved.damage_top)
        self.assertEqual(({'D'}, 4.6), (solved.best.ids, solved.best.value))

    def test_the_generic_solve_gets_back_the_seconds_of_the_floor(self):
        self.given(C=(1000, 5.0), G=(1100, 6.0))
        self.generic(['C'], 'C', 1000, 'G', deadline=1100.0, floor_seconds=7.0)
        self.assertEqual(1100.0, self.solver.call_args_list[0].args[8])
        self.assertEqual(1107.0, self.solver.call_args_list[1].kwargs['deadline'])

    def test_a_set_the_raised_top_leaves_below_the_floor_is_landed_again_on_its_bound(self):
        self.given(F=(960, 5.0), S=(1000, 4.0), J=(1000, 5.5))
        self.relanded = {'J': (1100, 5.2)}
        solved = self.picking('F', 'S', ['J'])
        self.assertEqual(1100, solved.damage_top)
        self.assertEqual({'J'}, solved.best.ids)
        self.assertTrue(any(bound is not None and abs(bound - 1045) < 1e-6
                            for bound in self.relandings))
        self.given(C=(1000, 5.0), G=(1200, 6.0))
        self.relanded, self.relandings = {}, []
        self.generic(['C'], 'C', 1000, 'G')
        self.assertEqual(2, len(self.relandings))
        self.assertAlmostEqual(1140, self.relandings[1])

    def test_the_damage_round_sets_the_top_and_the_kept_set_is_the_best_that_keeps_it(self):
        for plain, kept in ((900, 'D'), (960, 'V')):
            with self.subTest(plain=plain):
                self.given(V=(plain, 5.0), D=(1000, 4.0), P=(500, 1.0))
                solved = self.plain(['V', 'D', 'P'])
                self.assertEqual(1000, solved.damage_top)
                self.assertEqual({kept}, solved.best.ids)

    def generic(self, classed, best, top, generic, deadline=None, floor_seconds=0.0, pre=None,
                pre_value=None):
        """solve() on a class turn whose own solve returns the sets classed, as judged, and
        best; pre_value: the pre-floor set's value before its landing on the bound, its value
        as judged when None."""
        turn = mock.Mock(damage=lambda totals: 1)
        rounds = tuple(self.round_of(one) for one in classed)
        pre_floor = rounds[classed.index(pre or best)]
        solves = [wakfu_value.ModelSolve(rounds, rounds[classed.index(best)], True,
                                         damage_top=top, damage_floor=0.05,
                                         floor_seconds=floor_seconds, pre_floor=pre_floor,
                                         pre_floor_value=pre_floor.value if pre_value is None
                                         else pre_value),
                  wakfu_value.ModelSolve((self.round_of(generic),), self.round_of(generic),
                                         True)]
        with mock.patch.object(wakfu_value, '_solve', side_effect=solves) as self.solver:
            return wakfu_value.solve(None, LEVEL, self.role, turn=turn, damage_floor=0.05,
                                     deadline=deadline)

    def test_the_generic_set_raises_the_top_and_is_kept_only_within_the_floor(self):
        for damage, top, kept in ((1200, 1200, 'G'), (800, 1000, 'C'), (1000, 1000, 'G')):
            with self.subTest(damage=damage):
                self.given(C=(1000, 5.0), G=(damage, 6.0))
                self.bounds, self.relandings = [], []
                solved = self.generic(['C'], 'C', 1000, 'G')
                self.assertEqual(top, solved.damage_top)
                self.assertEqual({kept}, solved.best.ids)
                self.assertEqual([None], self.bounds)
                self.assertAlmostEqual(950, self.relandings[0])

    def test_a_classed_round_beyond_its_best_is_kept_when_the_generic_set_raises_the_top(self):
        self.given(P=(1050, 5.5), B=(1000, 6.0), G=(1100, 5.0))
        solved = self.generic(['P', 'B'], 'B', 1000, 'G')
        self.assertEqual(1100, solved.damage_top)
        self.assertEqual({'P'}, solved.best.ids)

    def head_calls(self):
        """The solver calls of a preset without a floor: kind, the point its weights were taken
        at, whether it started cold, the locks and the deadline less the one given."""
        calls = []
        self.now = 100.0
        self.given(V1=(900, 5.0), V2=(950, 5.5), V3=(940, 5.6), J1=(800, 5.0), J2=(850, 5.2))
        self.script = ['V1', 'V2', 'V3']
        wakfu_value.solve(None, LEVEL, self.role, rounds=3, locked=[(7, 'head')],
                          deadline=1100.0)
        calls.extend(self.recorded('plain', 1100.0))
        self.builds, self.deadlines = [], []
        self.script = ['J1', 'J2']
        self.stages = {'value': (self.round_of('J1'), None, self.totals('J1'), ())}
        wakfu_value.solve(None, LEVEL, self.role, rounds=2, sublimations='optimistic',
                          deadline=1100.0)
        calls.extend(self.recorded('picking', 1100.0))
        return calls

    def recorded(self, kind, given):
        return [(kind, one['weights']['at'], one['start'] is None, one['locked'] or [],
                 round(one['deadline'] - given, 6)) for one in self.builds]

    def test_a_preset_without_a_floor_makes_the_same_solver_calls_as_head(self):
        self.assertEqual(HEAD_CALLS, self.head_calls())
