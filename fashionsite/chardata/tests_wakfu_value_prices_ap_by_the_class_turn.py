import collections
import io
import math
import os
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from chardata.tests_wakfu_turn_counts_rows_under_the_roles_conditions import (
    InventedSpells, totals)
from fashionistapulp import wakfu_turn, wakfu_value

LEVEL = 200
FIRE_AT_DISTANCE = wakfu_value.DamageDealer(('fire',), 'distance')

Stat = collections.namedtuple('Stat', 'id key')
Piece = collections.namedtuple(
    'Piece', 'id name type level stats element_spread flags localized_names')
HELMET, CAPE = 1, 2
STAT_ID = {'ap': 1, 'dmg_fire_percent': 2, 'hp': 3}


def piece(item_id, type_id, **stats):
    return Piece(item_id, 'piece %d' % item_id, type_id, 1,
                 tuple((STAT_ID[key], value) for key, value in stats.items()), (), (),
                 {'fr': 'piece %d' % item_id})


class Catalogue:
    """The part of a Wakfu structure WakfuBuild reads: a head and a back slot."""

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


def catalogue_solve(pieces, weights, ap_values=None):
    from fashionistapulp.wakfu_model import WakfuBuild
    build = WakfuBuild(Catalogue(*pieces), 50, weights, ap_values=ap_values)
    worn = build.build().solve()
    return {item.id for item in worn.values()}, build.totals(worn)['ap'], build


class TheClassTurnPricesEachStatTests(SimpleTestCase):
    def setUp(self):
        self.spells = InventedSpells()
        self.addCleanup(self.spells.remove)
        self.book = self.spells.book()
        self.addCleanup(self.book.close)

    def model(self, role=FIRE_AT_DISTANCE):
        return wakfu_turn.TurnModel(self.book.spells(self.spells.CLASS, LEVEL), role)

    def change(self, model, sheet, key):
        before, after = model.best(sheet), model.best(wakfu_turn._plus(sheet, key))
        return before, after, 100 * (after.damage - before.damage) / before.damage

    def test_each_weight_is_the_one_point_change_of_the_turn(self):
        model = self.model()
        sheet = totals(ap=11, mp=4, wp=6, dmg_fire_percent=400, ranged_dmg=100, ferocity=30,
                       critical_bonus=50)
        weights = model.weights(sheet)
        for key in ('dmg_fire_percent', 'ranged_dmg', 'critical_bonus', 'ferocity', 'ap'):
            with self.subTest(key=key):
                before, after, change = self.change(model, sheet, key)
                if key != 'ap':
                    self.assertEqual(before.casts, after.casts)
                self.assertAlmostEqual(change, weights[key])
        self.assertNotIn(wakfu_value.ELEMENTAL_MASTERY, weights)
        self.assertNotIn('melee_dmg', weights)

    def test_a_two_element_role_weighs_only_the_element_its_turn_casts(self):
        role = wakfu_value.DamageDealer(('fire', 'water'), 'distance')
        model = self.model(role)
        sheet = totals(ap=2, mp=0, wp=0, dmg_fire_percent=400)
        self.assertEqual((4,), model.best(sheet).casts)
        weights = model.weights(sheet)
        self.assertNotIn('dmg_fire_percent', weights)
        self.assertAlmostEqual(self.change(model, sheet, 'dmg_water_percent')[2],
                               weights['dmg_water_percent'])
        generic = wakfu_value.linear_weights(role, LEVEL, sheet)
        self.assertEqual(generic['dmg_fire_percent'], generic['dmg_water_percent'])

    def test_a_light_hit_on_tied_masteries_goes_to_the_roles_first_element(self):
        sheet = totals(ap=5, mp=0, wp=0, dmg_air_percent=100, dmg_earth_percent=100)
        for elements, first, second in ((('air', 'earth'), 'air', 'earth'),
                                        (('earth', 'air'), 'earth', 'air')):
            with self.subTest(elements=elements):
                model = self.model(wakfu_value.DamageDealer(elements, 'distance'))
                self.assertEqual((5,), model.best(sheet).casts)
                weights = model.weights(sheet)
                self.assertNotIn(wakfu_value.MASTERY_OF[second], weights)
                self.assertAlmostEqual(
                    self.change(model, sheet, wakfu_value.ELEMENTAL_MASTERY)[2],
                    weights[wakfu_value.MASTERY_OF[first]])

    def test_the_ap_table_is_the_turn_at_each_ap_over_the_turn_here(self):
        model = self.model()
        sheet = totals(ap=11, mp=0, wp=0, dmg_fire_percent=400)
        table = model.ap_values(sheet)
        self.assertEqual(list(range(17)), sorted(table))
        here = model.damage(sheet)
        for ap, worth in table.items():
            with self.subTest(ap=ap):
                damage = model.damage(dict(sheet, ap=ap))
                if damage:
                    self.assertAlmostEqual(100 * math.log(damage / here), worth)
                else:
                    self.assertEqual(wakfu_turn.NO_DAMAGE, worth)
        self.assertEqual(0, table[11])
        self.assertEqual(wakfu_turn.NO_DAMAGE, table[2])

    def test_the_value_on_the_class_turn_is_the_log_of_that_turn_plus_the_defence(self):
        model = self.model()
        sheet = totals(ap=11, mp=4, wp=6, dmg_fire_percent=400, hp=2000)
        self.assertAlmostEqual(
            math.log(model.damage(sheet))
            + FIRE_AT_DISTANCE.defense * math.log(wakfu_value.effective_life(LEVEL, sheet)),
            wakfu_value.value(FIRE_AT_DISTANCE, LEVEL, sheet, model))
        self.assertEqual(float('-inf'), wakfu_value.value(
            FIRE_AT_DISTANCE, LEVEL, totals(ap=0, mp=0), model))

    def test_a_role_the_class_has_no_spell_for_stops_the_solve_before_any_set(self):
        ceiling = wakfu_value.resource_ceiling()
        self.assertEqual((16, 8, 20, 0), (ceiling['ap'], ceiling['mp'], ceiling['wp'],
                                          ceiling['dmg_fire_percent']))
        spells = [spell for spell in self.book.spells(self.spells.CLASS, LEVEL) if spell.branch]
        earth = wakfu_turn.TurnModel(spells, wakfu_value.DamageDealer(('earth',), 'distance'))
        self.assertEqual(0, earth.damage(ceiling))
        self.assertGreater(wakfu_turn.TurnModel(spells, FIRE_AT_DISTANCE).damage(ceiling), 0)
        stand_in, solved = scripted(outfit(1, ap=1))
        with mock.patch('fashionistapulp.wakfu_model.WakfuBuild', stand_in):
            with self.assertRaisesMessage(ValueError, 'the class turn deals no damage'):
                wakfu_value.solve(None, LEVEL, earth.role, turn=earth)
        self.assertEqual([], solved)

    def test_the_defence_weights_stay_those_of_the_generic_model(self):
        sheet = totals(ap=11, mp=4, wp=6, dmg_fire_percent=400, hp=2000, block=20,
                       res_fire_percent=150)
        generic = wakfu_value.linear_weights(FIRE_AT_DISTANCE, LEVEL, sheet)
        classed = wakfu_value.linear_weights(FIRE_AT_DISTANCE, LEVEL, sheet, self.model())
        for key in ('hp', 'block') + tuple(wakfu_value.RESISTANCE_OF.values()):
            with self.subTest(key=key):
                self.assertEqual(generic[key], classed[key])


class TheSolverPricesEachApTotalFromATableTests(SimpleTestCase):
    PIECES = (piece(1, HELMET, ap=1), piece(2, HELMET, dmg_fire_percent=10),
              piece(3, CAPE, ap=1), piece(4, CAPE, dmg_fire_percent=25))

    def test_one_weight_per_ap_takes_an_odd_ap_the_table_says_is_worth_nothing(self):
        weights = {'ap': 15, 'dmg_fire_percent': 1}
        self.assertEqual(({1, 4}, 7), catalogue_solve(self.PIECES, weights)[:2])
        self.assertEqual(({2, 4}, 6),
                         catalogue_solve(self.PIECES, weights, {6: 0, 7: 0, 8: 30})[:2])
        self.assertEqual(({1, 3}, 8),
                         catalogue_solve(self.PIECES, weights, {6: 0, 7: 0, 8: 40})[:2])

    def test_an_ap_malus_opens_the_totals_below_the_base(self):
        pieces = (piece(1, HELMET, ap=-1), piece(2, HELMET, dmg_fire_percent=10),
                  piece(3, CAPE, hp=1))
        worn, ap, build = catalogue_solve(pieces, {'dmg_fire_percent': 1, 'hp': 1},
                                          {5: 50, 6: 0})
        self.assertEqual(({1, 3}, 5), (worn, ap))
        self.assertEqual(range(5, 17), build._ap_totals())


Outfit = collections.namedtuple('Outfit', 'id stats')


def outfit(item_id, **stats):
    return {'HEAD': Outfit(item_id, collections.Counter(stats))}


class FakeTurn:
    """A TurnModel stand-in: AP x per_ap damage, and the points its AP table was asked at."""

    def __init__(self, per_ap=10):
        self.per_ap = per_ap
        self.tables = []

    def damage(self, sheet):
        return self.per_ap * sheet.get('ap', 0)

    def weights(self, sheet):
        return {'dmg_fire_percent': 0.5}

    def ap_values(self, sheet):
        self.tables.append(sheet['ap'])
        return {6: 0.0, 7: 1.0, 8: 3.0 + sheet['ap']}


def scripted(*sets):
    solved = []

    class ScriptedBuild:
        def __init__(self, structure, level, weights, forbidden=(), full_set=True,
                     minimums=None, **options):
            self.weights = dict(weights)
            self.options = options

        def build(self):
            return self

        def solve(self):
            solved.append(self)
            return sets[len(solved) - 1] if len(solved) <= len(sets) else None

        def totals(self, worn):
            out = wakfu_value.bare_totals()
            for item in worn.values():
                out.update(item.stats)
            return out

    return ScriptedBuild, solved


class TheModelSolveUsesTheClassTurnTests(SimpleTestCase):
    def run_solve(self, turn, *sets):
        stand_in, solved = scripted(*sets)
        with mock.patch('fashionistapulp.wakfu_model.WakfuBuild', stand_in):
            result = wakfu_value.solve(None, 50, wakfu_value.DamageDealer(), rounds=3,
                                       turn=turn)
        return result, solved

    def test_each_round_takes_its_weights_and_ap_table_from_the_turn_at_its_point(self):
        turn = FakeTurn()
        result, solved = self.run_solve(turn, outfit(1, ap=2), outfit(2, ap=1),
                                        outfit(2, ap=1))
        # AP 6 bare, then 8; 8 + 2/3 x (7 - 8)
        points = [6, 8, 8 - 2 / 3]
        for wanted, asked in zip(points, turn.tables):
            self.assertAlmostEqual(wanted, asked)
        self.assertEqual(3, len(turn.tables))
        for build, point in zip(solved, points):
            self.assertAlmostEqual(3 + point, build.options['ap_values'][8])
            self.assertEqual(0.5, build.weights['dmg_fire_percent'])
            self.assertNotIn('ap', build.weights)
        first = result.rounds[0]
        self.assertAlmostEqual(math.log(80) + 0.25 * math.log(
            wakfu_value.effective_life(50, first.totals)), first.value)

    def test_without_a_turn_no_round_gets_an_ap_table(self):
        _result, solved = self.run_solve(None, outfit(1, ap=2), outfit(1, ap=2))
        self.assertEqual([{}, {}], [build.options for build in solved])

    def test_the_generic_set_is_kept_when_the_class_turn_values_it_higher(self):
        result, solved = self.run_solve(FakeTurn(), outfit(1, ap=1), outfit(1, ap=1),
                                        outfit(2, ap=4), outfit(2, ap=4))
        self.assertEqual(4, len(solved))
        self.assertEqual([{1}, {1}], [set(one.ids) for one in result.rounds])
        self.assertTrue(result.converged)
        self.assertEqual({2}, set(result.best.ids))
        self.assertFalse(any(one is result.best for one in result.rounds))
        self.assertIn('ap', result.best.weights)
        self.assertAlmostEqual(math.log(100) + 0.25 * math.log(
            wakfu_value.effective_life(50, result.best.totals)), result.best.value)

    def test_the_class_turn_set_stays_when_the_generic_set_is_worth_no_more(self):
        result, solved = self.run_solve(FakeTurn(), outfit(1, ap=4), outfit(1, ap=4),
                                        outfit(2, ap=1), outfit(2, ap=1))
        self.assertEqual(4, len(solved))
        self.assertIs(result.rounds[0], result.best)

    def test_a_turn_that_deals_nothing_even_at_the_caps_stops_the_solve_before_any_set(self):
        stand_in, solved = scripted(outfit(1, ap=1))
        with mock.patch('fashionistapulp.wakfu_model.WakfuBuild', stand_in):
            with self.assertRaisesMessage(ValueError, 'the class turn deals no damage'):
                wakfu_value.solve(None, 50, wakfu_value.DamageDealer(), turn=FakeTurn(0))
        self.assertEqual([], solved)


class TheCommandSaysWhichSetItKeptTests(SimpleTestCase):
    ROLE = wakfu_value.DamageDealer()

    def kept_round(self, item_id, ap, weights, turn):
        sheet = wakfu_value.bare_totals()
        sheet['ap'] += ap
        return wakfu_value.ModelRound(weights, None, outfit(item_id, ap=ap), sheet,
                                      wakfu_value.value(self.ROLE, 50, sheet, turn))

    def printed(self, model, turn):
        from chardata.management.commands.wakfu_build import Command
        out = io.StringIO()
        Command(stdout=out, no_color=True).print_model(self.ROLE, 50, model, turn)
        return out.getvalue().splitlines()

    def test_a_generic_set_the_class_turn_values_higher_prints_on_its_own_line(self):
        turn = FakeTurn()
        rounds = (self.kept_round(1, 1, {'dmg_fire_percent': 0.5}, turn),)
        kept = self.kept_round(2, 4, {'ap': 5.0, 'dmg_fire_percent': 0.5}, turn)
        lines = self.printed(wakfu_value.ModelSolve(rounds, kept, True), turn)
        self.assertTrue(lines[3].startswith('  round 1   value '), lines)
        self.assertIn('  turn 70 over 7 AP  ', lines[3])
        self.assertTrue(lines[4].startswith('  generic set * value '), lines)
        self.assertIn('  turn 100 over 10 AP  ', lines[4])
        self.assertEqual('  weights of the kept round, percent of value per point, from the '
                         'generic solve, whose set the class turn values higher', lines[5])
        self.assertIn('AP 5', lines[6].split('  '))

    def test_a_kept_class_turn_round_prints_its_turn_and_no_ap_weight(self):
        turn = FakeTurn()
        kept = self.kept_round(1, 2, {'ap': 5.0, 'dmg_fire_percent': 0.5}, turn)
        lines = self.printed(wakfu_value.ModelSolve((kept,), kept, False), turn)
        self.assertTrue(lines[3].startswith('  round 1 * value '), lines)
        self.assertIn('  turn 80 over 8 AP  ', lines[3])
        self.assertFalse(any(line.startswith('  generic set') for line in lines))
        self.assertEqual('  weights of the kept round, percent of value per point, each AP '
                         'total priced by the class turn', lines[4])
        self.assertEqual(['', 'DMG_FIRE_PERCENT 0.5'], lines[5].split('  '))


class TheCommandSolvesOnTheClassTurnTests(SimpleTestCase):
    def setUp(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        if not os.path.exists(get_items_db_path('wakfu')):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')

    def test_the_class_turn_option_solves_on_that_class_turn(self):
        out = io.StringIO()
        call_command('wakfu_build', '--level', '110', '--elements', 'fire', '--rounds', '1',
                     '--class-id', '19', '--class-turn', stdout=out, no_color=True)
        lines = out.getvalue().splitlines()
        self.assertTrue(any(line.startswith('  damage model: fire, distance, defense 0.25, '
                                            'on the class turn; 1 rounds') for line in lines),
                        out.getvalue())
        self.assertTrue(any(line.startswith('  best turn of class 19: ') for line in lines))
        header = lines.index('  weights of the kept round, percent of value per point, each '
                             'AP total priced by the class turn')
        self.assertFalse(any(part.startswith('AP ') for part in lines[header + 1].split('  ')))

    def test_the_class_turn_option_needs_a_class(self):
        with self.assertRaisesMessage(CommandError, '--class-turn needs --class-id'):
            call_command('wakfu_build', '--class-turn', stdout=io.StringIO())

    def test_a_role_the_class_casts_nothing_for_is_refused_before_the_solve(self):
        # Ankama class id 8 is the Iop, who has no water spell
        with self.assertRaisesMessage(CommandError, 'class 8 has no damage turn for water at '
                                                    'distance, even with AP, MP and WP at '
                                                    'their caps'):
            call_command('wakfu_build', '--level', '110', '--elements', 'water', '--rounds',
                         '1', '--class-id', '8', '--class-turn', stdout=io.StringIO())

    def test_the_movement_option_needs_a_class_and_the_damage_model(self):
        for args in (('--movement', '0.5'),
                     ('--movement', '0.5', '--class-id', '8', '--weights', 'hp=1')):
            with self.subTest(args=args):
                with self.assertRaisesMessage(CommandError,
                                              '--movement needs --class-id and no --weights'):
                    call_command('wakfu_build', *args, stdout=io.StringIO())
