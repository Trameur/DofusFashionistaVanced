import collections
import io
import os
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

LEVEL = 110
ELEMENTS = ('fire', 'water')

Stat = collections.namedtuple('Stat', 'id key')
Piece = collections.namedtuple(
    'Piece', 'id name type level stats element_spread flags localized_names')
Outfit = collections.namedtuple('Outfit', 'id stats')

HELMET, CAPE = 1, 2
KEYS = ('hp', 'range', 'mp', 'wp', 'ferocity', 'res_in_percent',
        'res_fire_percent', 'res_water_percent', 'res_earth_percent',
        'res_air_percent')
STAT_ID = {key: number for number, key in enumerate(KEYS, 1)}


def wakfu_structure(case):
    from fashionistapulp.fashionista_config import get_items_db_path
    from fashionistapulp.structure import get_structure
    if not os.path.exists(get_items_db_path('wakfu')):
        case.skipTest('no Wakfu database built; run update_data_wakfu.py')
    return get_structure('wakfu')


def piece(item_id, type_id, spread=(), **stats):
    """A catalogue item; spread holds (key, value, elements) lines."""
    rows = [(STAT_ID[key], value) for key, value in stats.items()]
    lines = tuple((STAT_ID[key], value, elements) for key, value, elements in spread)
    return Piece(item_id, 'piece %d' % item_id, type_id, 1,
                 tuple(rows) + tuple(line[:2] for line in lines), lines, (),
                 {'fr': 'piece %d' % item_id})


class Catalogue:
    """The part of a Wakfu structure WakfuBuild reads, with a head and a back slot."""

    def __init__(self, *pieces):
        self.pieces = pieces
        self.stats = [Stat(number, key) for key, number in STAT_ID.items()]

    def get_type_positions(self):
        return [(HELMET, 'HEAD'), (CAPE, 'BACK')]

    def get_available_items_list(self):
        return list(self.pieces)

    def get_stat_by_key(self, key):
        return next((stat for stat in self.stats if stat.key == key), None)

    def get_stat_by_id(self, stat_id):
        return next((stat for stat in self.stats if stat.id == stat_id), None)


def catalogue_solve(pieces, weights, minimums=None):
    from fashionistapulp.wakfu_model import WakfuBuild
    build = WakfuBuild(Catalogue(*pieces), 50, weights, minimums=minimums)
    worn = build.build().solve()
    return build, worn


def ids(worn):
    return {item.id for item in worn.values()}


class AWakfuBuildKeepsItsMinimumsTests(SimpleTestCase):
    def test_a_range_floor_holds_on_the_sum_of_the_set(self):
        pieces = (piece(1, HELMET, hp=100, range=-2), piece(2, HELMET, hp=50),
                  piece(3, CAPE, hp=80, range=-1), piece(4, CAPE, hp=60, range=2))
        build, worn = catalogue_solve(pieces, {'hp': 1})
        self.assertEqual({1, 3}, ids(worn))
        self.assertEqual(-3, build.totals(worn)['range'])
        build, worn = catalogue_solve(pieces, {'hp': 1}, {'range': 0})
        self.assertEqual({1, 4}, ids(worn))
        self.assertEqual(0, build.totals(worn)['range'])
        self.assertFalse(worn.full_set_dropped)

    def test_a_floor_counts_the_base_value(self):
        pieces = (piece(1, HELMET, hp=100, mp=-1), piece(2, HELMET, hp=40),
                  piece(3, CAPE, hp=10, mp=1), piece(4, CAPE, hp=50))
        build, worn = catalogue_solve(pieces, {'hp': 1}, {'mp': 3})
        self.assertEqual({1, 3}, ids(worn))
        self.assertEqual(3, build.totals(worn)['mp'])
        self.assertFalse(worn.full_set_dropped)

    def test_the_crit_floor_holds_on_the_gear_sum_without_the_base_crit(self):
        from fashionistapulp.wakfu_stats import CRITICAL_HIT_FLOOR_PERCENT
        from fashionistapulp.wakfu_value_rules import RULES
        both = -12
        self.assertEqual(CRITICAL_HIT_FLOOR_PERCENT,
                         both + RULES['base_critical_hit_percent'].value)
        pieces = (piece(1, HELMET, hp=100, ferocity=both // 2), piece(2, HELMET, hp=10),
                  piece(3, CAPE, hp=100, ferocity=both // 2), piece(4, CAPE, hp=10))
        build, worn = catalogue_solve(pieces, {'hp': 1})
        self.assertEqual(both // 2, build.totals(worn)['ferocity'])


class AModelRoundLandsItsSpreadLinesOnItsOwnStatsTests(SimpleTestCase):
    def test_a_resistance_line_moves_off_the_element_the_set_already_covers(self):
        from fashionistapulp import wakfu_value
        role = wakfu_value.DamageDealer()
        pieces = (piece(1, HELMET, spread=[('res_in_percent', 100, 1)]),
                  piece(2, CAPE, res_fire_percent=300))
        catalogue = Catalogue(*pieces)
        build, worn = catalogue_solve(
            pieces, wakfu_value.linear_weights(role, 50, wakfu_value.bare_totals()))
        self.assertEqual(['res_fire_percent'], build.spread_lines(worn)[0][4])
        worth, landed, totals = wakfu_value.land(catalogue, 50, role, build, worn)
        self.assertNotIn('res_fire_percent', landed.spread_lines(worn)[0][4])
        self.assertEqual(totals, landed.totals(worn))
        self.assertEqual(worth, wakfu_value.value(role, 50, totals))
        self.assertGreater(worth, wakfu_value.value(role, 50, build.totals(worn)))


def outfit(item_id, **stats):
    return {'HEAD': Outfit(item_id, collections.Counter(stats))}


def scripted(*sets):
    """A WakfuBuild stand-in whose solves hand out sets in turn, and the builds solved."""
    from fashionistapulp import wakfu_value
    script = list(sets)
    solved = []

    class ScriptedBuild:
        def __init__(self, structure, level, weights, forbidden=(), full_set=True,
                     minimums=None):
            self.weights = dict(weights)
            self.minimums = minimums

        def build(self):
            return self

        def solve(self):
            solved.append(self)
            return script.pop(0) if script else None

        def totals(self, worn):
            out = wakfu_value.bare_totals()
            for item in worn.values():
                out.update(item.stats)
            return out

    return ScriptedBuild, solved


class TheModelSolveLoopTests(SimpleTestCase):
    def run_solve(self, *sets, rounds=5):
        from fashionistapulp import wakfu_value
        self.role = wakfu_value.DamageDealer()
        stand_in, self.solved = scripted(*sets)
        with mock.patch('fashionistapulp.wakfu_model.WakfuBuild', stand_in):
            return wakfu_value.solve(None, 50, self.role, rounds=rounds)

    def test_no_set_in_the_first_round_gives_no_best(self):
        result = self.run_solve()
        self.assertEqual(((), None, False), tuple(result))
        self.assertEqual(1, len(self.solved))

    def test_a_round_without_a_set_ends_the_solve_unsettled(self):
        result = self.run_solve(outfit(1, ap=6), None, outfit(2, ap=8))
        self.assertEqual(1, len(result.rounds))
        self.assertFalse(result.converged)
        self.assertIs(result.rounds[0], result.best)

    def test_a_set_that_comes_back_ends_the_solve_settled(self):
        result = self.run_solve(outfit(1, ap=6), outfit(2, ap=3), outfit(2, ap=3),
                                outfit(3, ap=9))
        self.assertTrue(result.converged)
        self.assertEqual([1, 2, 2], [min(one.ids) for one in result.rounds])
        self.assertEqual(3, len(self.solved))

    def test_the_best_round_is_kept_even_when_it_is_the_first(self):
        result = self.run_solve(outfit(1, ap=6), outfit(2, ap=1), outfit(2, ap=1))
        self.assertIs(result.rounds[0], result.best)
        self.assertGreater(result.best.value, result.rounds[1].value)

    def test_the_rounds_stop_at_the_limit_unsettled(self):
        result = self.run_solve(*[outfit(number, ap=number) for number in range(1, 9)],
                                rounds=4)
        self.assertEqual(4, len(result.rounds))
        self.assertFalse(result.converged)
        self.assertEqual(4, min(result.best.ids))

    def test_each_round_solves_on_the_tangent_at_the_blend_of_the_sets_found(self):
        self.run_solve(outfit(1, ap=6), outfit(2, ap=3), outfit(3, ap=8), outfit(3, ap=8))
        # AP 6 bare, then 12; 12 + 2/3 x (9 - 12) = 10; 10 + 2/4 x (14 - 10) = 12
        self.assertEqual([100 / 6, 100 / 12, 100 / 10, 100 / 12],
                         [build.weights['ap'] for build in self.solved])

    def test_every_round_keeps_the_role_floors(self):
        self.run_solve(outfit(1, ap=6), outfit(1, ap=6))
        self.assertEqual([self.role.minimums()] * 2,
                         [build.minimums for build in self.solved])


class AWakfuModelSolveTests(SimpleTestCase):
    """One two-element distance solve at level 110, read by every test."""

    result = None

    def setUp(self):
        from fashionistapulp import wakfu_value
        from fashionistapulp.wakfu_exclusions import default_exclusions
        self.structure = wakfu_structure(self)
        self.role = wakfu_value.DamageDealer(ELEMENTS)
        if AWakfuModelSolveTests.result is None:
            AWakfuModelSolveTests.result = wakfu_value.solve(
                self.structure, LEVEL, self.role,
                default_exclusions(self.structure))
        self.result = AWakfuModelSolveTests.result
        self.assertIsNotNone(self.result.best)

    def test_the_rounds_stop_on_a_set_that_came_back(self):
        rounds = self.result.rounds
        self.assertTrue(self.result.converged)
        self.assertGreater(len(rounds), 1)
        self.assertEqual(rounds[-2].ids, rounds[-1].ids)
        self.assertEqual(12, len(self.result.best.worn))

    def test_the_kept_set_has_the_best_value_of_every_round(self):
        best = self.result.best
        self.assertEqual(max(one.value for one in self.result.rounds), best.value)

    def test_every_mastery_line_on_two_elements_or_more_lands_on_both(self):
        best = self.result.best
        role = {'dmg_fire_percent', 'dmg_water_percent'}
        lines = [line for line in best.build.spread_lines(best.worn)
                 if line[2] == 'dmg_in_percent' and line[3] > 0]
        self.assertGreater(sum(len(line[4]) >= 2 for line in lines), 3)
        for position, _item, _key, _value, landed in lines:
            with self.subTest(position=position, landed=landed):
                if len(landed) >= 2:
                    self.assertLessEqual(role, set(landed))
                else:
                    self.assertIn(landed[0], role)

    def test_the_tangent_prices_each_worn_item_within_ten_percent_of_the_value_it_brings(self):
        from fashionistapulp import wakfu_value
        from fashionistapulp.wakfu_model import WakfuBuild
        best = self.result.best
        weights = wakfu_value.linear_weights(self.role, LEVEL, best.totals)
        build = WakfuBuild(self.structure, LEVEL, weights)
        whole = wakfu_value.value(self.role, LEVEL, build.totals(best.worn))
        for position, item in sorted(best.worn.items()):
            rest = {other: piece for other, piece in best.worn.items() if other != position}
            exact = 100 * (whole - wakfu_value.value(self.role, LEVEL, build.totals(rest)))
            with self.subTest(position=position, item=item.id):
                self.assertGreater(exact, 0)
                self.assertLess(abs(build._worth(item) - exact), 0.1 * exact)


class TheRoleFloorsBindOnRealGearTests(SimpleTestCase):
    def test_at_level_200_the_distance_floors_hold_where_the_tangent_alone_breaks_range(self):
        from fashionistapulp import wakfu_value
        from fashionistapulp.wakfu_exclusions import default_exclusions
        from fashionistapulp.wakfu_model import WakfuBuild
        structure = wakfu_structure(self)
        role = wakfu_value.DamageDealer()
        weights = wakfu_value.linear_weights(role, 200, wakfu_value.bare_totals())
        forbidden = default_exclusions(structure)
        free = WakfuBuild(structure, 200, weights, forbidden)
        self.assertLess(free.totals(free.build().solve())['range'], 0,
                        'the range floor no longer binds at level 200')
        kept = WakfuBuild(structure, 200, weights, forbidden, minimums=role.minimums())
        worn = kept.build().solve()
        self.assertFalse(worn.full_set_dropped)
        totals = kept.totals(worn)
        for key, lowest in role.minimums().items():
            with self.subTest(stat=key):
                self.assertGreaterEqual(totals[key], lowest)


class TheWakfuBuildCommandRunsTheDamageModelTests(SimpleTestCase):
    def setUp(self):
        wakfu_structure(self)

    def run_command(self, *args):
        out = io.StringIO()
        call_command('wakfu_build', *args, stdout=out, no_color=True)
        return out.getvalue()

    def test_without_weights_the_command_prints_the_model_rounds_and_weights(self):
        out = self.run_command('--level', '20', '--elements', 'fire')
        lines = out.splitlines()
        header = [line for line in lines if line.startswith('  damage model: ')]
        self.assertEqual(['  damage model: fire, distance, defense 0.25'],
                         [line.split(';')[0] for line in header], out)
        self.assertIn('  kept at least: MP 3, RANGE 0, WP 6', lines, out)
        rounds = [line for line in lines if line.startswith('  round ')]
        self.assertTrue(rounds, out)
        self.assertEqual(1, sum(' * ' in line for line in rounds), out)
        start = lines.index('  weights of the kept round, percent of value per point') + 1
        weights = dict(zip(lines[start].split()[::2], lines[start].split()[1::2]))
        self.assertIn('AP', weights)
        self.assertIn('DMG_FIRE_PERCENT', weights)
        self.assertNotIn('DMG_WATER_PERCENT', weights)
        self.assertNotIn('DMG_IN_PERCENT', weights)

    def test_hand_weights_skip_the_model(self):
        out = self.run_command('--level', '20', '--weights', 'hp=1')
        self.assertNotIn('damage model', out)
        self.assertIn('level 20, ', out)

    def test_an_element_no_gear_sells_is_refused(self):
        with self.assertRaisesMessage(CommandError, 'elements are fire, water, earth, air'):
            self.run_command('--level', '20', '--elements', 'fire,light')
