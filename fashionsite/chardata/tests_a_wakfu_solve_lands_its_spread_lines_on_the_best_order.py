import io
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.tests_wakfu_build_solves_on_the_damage_model import (
    CAPE, HELMET, Catalogue, piece)

LEVEL = 50


def spread_set():
    """Two pieces whose resistance lines the weights of an empty build land worse than
    another order."""
    helmet = piece(1, HELMET, res_water_percent=300, dmg_fire_percent=50,
                   spread=[('res_in_percent', 100, 1), ('res_in_percent', 100, 3),
                           ('res_in_percent', 100, 2)])
    cape = piece(2, CAPE, dmg_earth_percent=600, dmg_fire_percent=50,
                 spread=[('res_in_percent', 250, 1), ('res_in_percent', 250, 3),
                         ('res_in_percent', 100, 1)])
    return Catalogue(helmet, cape), {'HEAD': helmet, 'BACK': cape}


def legal(item):
    """The piece as an object the legality check reads, which a tuple is not."""
    return SimpleNamespace(**{**item._asdict(), 'removed': False})


class LegalCatalogue(Catalogue):
    """The catalogue with the lookups the legality check reads."""

    def get_item_by_id(self, item_id):
        return next((legal(one) for one in self.pieces if one.id == item_id), None)


def kept_round(role, catalogue, pieces):
    """The round a solve would keep: the set landed from the empty weights."""
    from fashionistapulp import wakfu_value
    from fashionistapulp.wakfu_model import WakfuBuild, WakfuSet
    worn = WakfuSet(pieces)
    worth, build, totals = wakfu_value.land(
        catalogue, LEVEL, role, WakfuBuild(catalogue, LEVEL, {}), worn)
    return wakfu_value.ModelRound({}, build, worn, totals, worth)


class TheSolveLandsSpreadLinesOnTheBestOrderTests(SimpleTestCase):
    def setUp(self):
        from fashionistapulp import wakfu_value
        self.role = wakfu_value.DamageDealer(('fire', 'water'), 'distance')
        self.catalogue, self.pieces = spread_set()
        self.kept = kept_round(self.role, self.catalogue, self.pieces)
        self.worn_legally = kept_round(self.role, self.catalogue, {
            position: legal(item) for position, item in self.pieces.items()})

    def test_an_order_of_the_elements_beats_the_landing_of_the_round_build(self):
        from fashionistapulp import wakfu_value
        landed = wakfu_value.best_landing(self.catalogue, LEVEL, self.role, self.kept)
        self.assertGreater(landed.value, self.kept.value + 0.01)
        self.assertEqual(landed.value, wakfu_value.value(self.role, LEVEL, landed.totals))
        self.assertEqual(landed.totals, landed.build.totals(self.kept.worn))

    def test_a_round_already_on_the_best_landing_is_kept_as_it_is(self):
        from fashionistapulp import wakfu_value
        best = wakfu_value.best_landing(self.catalogue, LEVEL, self.role, self.kept)
        again = wakfu_value.best_landing(self.catalogue, LEVEL, self.role, best)
        self.assertIs(best, again)

    def test_a_role_without_an_element_starts_from_no_order(self):
        from fashionistapulp import wakfu_value
        mule = wakfu_value.Role((), 'distance', shares={'mule': 1})
        self.assertEqual([], list(wakfu_value.element_starts(mule)))
        kept = kept_round(mule, self.catalogue, self.pieces)
        self.assertIs(kept, wakfu_value.best_landing(self.catalogue, LEVEL, mule, kept))

    def test_the_solve_returns_the_better_value_and_the_landing_that_gives_it(self):
        from fashionistapulp import wakfu_legality, wakfu_solve, wakfu_value
        model = wakfu_value.ModelSolve((self.kept,), self.kept, True)
        with mock.patch.object(wakfu_value, 'solve', return_value=model), \
                mock.patch.object(wakfu_solve, '_checked'), \
                mock.patch.object(wakfu_legality, 'warnings', return_value=[]):
            result = wakfu_solve.solve_build(
                self.catalogue, level=LEVEL, elements=('fire', 'water'), reach='distance',
                aptitudes=None, runes='none', sublimations=None, passives=None,
                on_class_turn=False, allow_legacy=True)
        self.assertGreater(result.value, self.kept.value + 0.01)
        self.assertEqual(result.build.where_the_spread_lands(result.worn),
                         result.worn.spread_landing)
        self.assertNotEqual(self.kept.build.where_the_spread_lands(result.worn),
                            result.worn.spread_landing)
        self.assertEqual(result.value, wakfu_value.value(self.role, LEVEL, result.totals))

    def solve_on_the_real_legality_check(self, model):
        from fashionistapulp import wakfu_legality, wakfu_solve, wakfu_value
        catalogue = LegalCatalogue(*self.catalogue.pieces)
        with mock.patch.object(wakfu_value, 'solve', return_value=model), \
                mock.patch.object(wakfu_legality, 'warnings', return_value=[]):
            return wakfu_solve.solve_build(
                catalogue, level=LEVEL, elements=('fire', 'water'), reach='distance',
                aptitudes=None, runes='none', sublimations=None, passives=None,
                on_class_turn=False, allow_legacy=True)

    def test_a_relanded_set_passes_the_legality_check_with_the_spread_it_landed(self):
        from fashionistapulp import wakfu_value
        model = wakfu_value.ModelSolve((self.worn_legally,), self.worn_legally, True)
        result = self.solve_on_the_real_legality_check(model)
        self.assertGreater(result.value, self.worn_legally.value + 0.01)
        self.assertEqual({1, 2}, {one.id for one in result.worn.values()})

    def test_the_relanded_round_replaces_the_kept_one_in_the_rounds(self):
        from fashionistapulp import wakfu_value
        other = self.worn_legally._replace(value=self.worn_legally.value - 1)
        model = wakfu_value.ModelSolve((other, self.worn_legally), self.worn_legally, True)
        result = self.solve_on_the_real_legality_check(model)
        self.assertIs(result.model.best, result.model.rounds[1])
        self.assertIs(other, result.model.rounds[0])
        self.assertIsNot(self.worn_legally, result.model.best)

    def test_the_command_stars_the_relanded_round_and_prints_no_generic_set(self):
        from chardata.management.commands.wakfu_build import Command
        from fashionistapulp import wakfu_value
        model = wakfu_value.ModelSolve((self.worn_legally,), self.worn_legally, True)
        result = self.solve_on_the_real_legality_check(model)
        out = io.StringIO()
        Command(stdout=out, no_color=True).print_model(
            self.role, LEVEL, result.model, None, self.catalogue)
        lines = out.getvalue().splitlines()
        rounds = [line for line in lines if line.startswith('  round ')]
        self.assertEqual(1, len(rounds), lines)
        self.assertTrue(rounds[0].startswith('  round 1 * value '), lines)
        self.assertFalse([line for line in lines if 'generic set' in line], lines)

    def test_a_set_without_spread_lines_is_kept_without_a_landing(self):
        from fashionistapulp import wakfu_value
        helmet = piece(3, HELMET, dmg_fire_percent=50)
        catalogue = Catalogue(helmet)
        kept = kept_round(self.role, catalogue, {'HEAD': helmet})
        with mock.patch.object(wakfu_value, 'land') as land:
            self.assertIs(kept, wakfu_value.best_landing(catalogue, LEVEL, self.role, kept))
        land.assert_not_called()

    def test_starts_that_land_alike_are_landed_once_and_the_first_best_wins(self):
        from fashionistapulp import wakfu_value
        from fashionistapulp.wakfu_model import WakfuBuild
        role = wakfu_value.DamageDealer(('fire', 'water', 'earth'), 'distance')
        starts = [{}] + list(wakfu_value.element_starts(role))
        every = [wakfu_value.land(self.catalogue, LEVEL, role,
                                  WakfuBuild(self.catalogue, LEVEL, weights),
                                  self.worn_legally.worn)
                 for weights in starts]
        first = max(every, key=lambda one: one[0])
        with mock.patch.object(wakfu_value, 'land', wraps=wakfu_value.land) as land:
            landed = wakfu_value.best_landing(self.catalogue, LEVEL, role, self.worn_legally)
        self.assertLess(land.call_count, len(starts))
        self.assertEqual(first[0], landed.value)
        self.assertEqual(first[2], landed.totals)

    def relanded_with_a_report(self, **modes):
        from fashionistapulp import wakfu_value
        self.kept.build.report(self.kept.worn)
        before = dict(self.kept.worn.sheet_totals)
        landed = wakfu_value.best_landing(self.catalogue, LEVEL, self.role, self.kept, **modes)
        self.assertGreater(landed.value, self.kept.value + 0.01)
        return landed, before

    def test_a_reported_set_relanded_in_fight_mode_is_reported_on_its_new_landing(self):
        from fashionistapulp import wakfu_sublimations
        landed, before = self.relanded_with_a_report(sublimations=wakfu_sublimations.NONE)
        self.assertNotEqual(before, dict(landed.worn.sheet_totals))
        self.assertEqual(landed.build.sheet_totals(landed.worn), landed.worn.sheet_totals)
        self.assertEqual(landed.totals, landed.worn.totals)

    def test_a_reported_set_relanded_with_no_sublimations_or_passives_is_reported_again(self):
        landed, before = self.relanded_with_a_report(opt_in={})
        self.assertNotEqual(before, dict(landed.worn.sheet_totals))
        self.assertEqual(landed.build.sheet_totals(landed.worn), landed.worn.sheet_totals)
        self.assertEqual(landed.totals, landed.worn.totals)

    def test_a_set_that_carried_no_report_is_relanded_without_one(self):
        from fashionistapulp import wakfu_value
        landed = wakfu_value.best_landing(self.catalogue, LEVEL, self.role, self.kept)
        self.assertGreater(landed.value, self.kept.value + 0.01)
        self.assertFalse(landed.worn.sheet_totals)
