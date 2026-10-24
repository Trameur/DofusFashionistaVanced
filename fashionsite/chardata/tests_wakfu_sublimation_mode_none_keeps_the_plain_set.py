import collections

from django.test import SimpleTestCase

from chardata.tests_wakfu_build_solves_on_the_damage_model import outfit, wakfu_structure
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, LEVEL, SublimationModelCase, state)

ROLE = ('fire',), 'distance'
REAL_LEVEL = 20


def role():
    from fashionistapulp import wakfu_value
    return wakfu_value.DamageDealer(*ROLE)


class TheSublimationAndPassiveModesNoneKeepThePlainSetTests(SublimationModelCase):
    def solve(self, **options):
        from fashionistapulp import wakfu_value
        return wakfu_value.solve(self.structure, LEVEL, role(), class_id=ALPHA, **options)

    def test_modes_none_give_the_set_and_the_value_the_solve_without_them_gives(self):
        self.invent({3: state(lines=[('A', 'ferocity', 40, 0, ())])},
                    {120: (3, 1, 'normal', ())})
        before = self.solve()
        after = self.solve(sublimations='none', passives='none')
        self.assertEqual(before.best.ids, after.best.ids)
        self.assertAlmostEqual(before.best.value, after.best.value, places=9)

    def test_modes_none_place_no_sublimation_and_no_passive(self):
        self.invent({3: state(lines=[('A', 'ferocity', 40, 0, ())])},
                    {120: (3, 1, 'normal', ())})
        worn = self.solve(sublimations='none', passives='none').best.worn
        self.assertEqual({}, worn.sublimations)
        self.assertEqual({}, worn.specials)
        self.assertEqual([], worn.passives)
        self.assertEqual(worn.totals, worn.sheet_totals)

    def test_optimistic_places_the_sublimation_modes_none_leaves_out(self):
        self.invent({3: state(lines=[('A', 'ferocity', 40, 0, ())])},
                    {120: (3, 1, 'normal', ())})
        worn = self.solve(sublimations='optimistic').best.worn
        self.assertTrue(worn.sublimations)
        self.assertGreater(worn.totals['ferocity'], worn.sheet_totals['ferocity'])

    def test_a_bad_mode_is_refused(self):
        self.invent()
        with self.assertRaisesRegex(ValueError, 'sublimations are'):
            self.solve(sublimations='all')
        with self.assertRaisesRegex(ValueError, 'passives are'):
            self.solve(passives='all')


class TheRealCatalogueKeepsThePlainSetTests(SimpleTestCase):
    def test_modes_none_give_the_set_of_the_solve_without_them_on_the_real_catalogue(self):
        from fashionistapulp import wakfu_value
        from fashionistapulp.wakfu_exclusions import default_exclusions
        structure = wakfu_structure(self)
        forbidden = default_exclusions(structure)
        before = wakfu_value.solve(structure, REAL_LEVEL, role(), forbidden)
        after = wakfu_value.solve(structure, REAL_LEVEL, role(), forbidden,
                                  sublimations='none', passives='none')
        self.assertEqual(before.best.ids, after.best.ids)
        self.assertAlmostEqual(before.best.value, after.best.value, places=6)


class AModelRoundKeyNamesEveryChoiceTests(SimpleTestCase):
    def round_of(self, sublimation=None, special=None, passives=None):
        from fashionistapulp import wakfu_value
        worn = outfit(1, ap=3)
        worn.sublimations = None if sublimation is None else {'HEAD': sublimation}
        worn.specials = None if special is None else {'HEAD': special}
        worn.passives = passives
        return wakfu_value.ModelRound({}, None, worn, collections.Counter(), 0.0)

    def test_two_rounds_that_differ_only_by_a_sublimation_have_two_keys(self):
        self.assertNotEqual(self.round_of((5, 1, 1, ())).key, self.round_of((6, 1, 1, ())).key)
        self.assertNotEqual(self.round_of((5, 1, 1, ())).key, self.round_of().key)

    def test_the_same_sublimation_in_another_position_is_another_key(self):
        one = self.round_of((5, 1, 1, ()))
        other = self.round_of((5, 1, 1, ()))
        other.worn.sublimations = {'NECK': (5, 1, 1, ())}
        self.assertNotEqual(one.key, other.key)

    def test_two_rounds_that_differ_only_by_a_special_or_a_passive_have_two_keys(self):
        self.assertNotEqual(self.round_of(special=(7, 1, 'epic')).key, self.round_of().key)
        self.assertNotEqual(self.round_of(passives=[701]).key, self.round_of(passives=[]).key)
        self.assertNotEqual(self.round_of(passives=[701]).key,
                            self.round_of(passives=[702]).key)

    def test_two_rounds_with_the_same_choices_have_one_key(self):
        self.assertEqual(self.round_of((5, 1, 1, ()), passives=[701]).key,
                         self.round_of((5, 1, 1, ()), passives=[701]).key)
