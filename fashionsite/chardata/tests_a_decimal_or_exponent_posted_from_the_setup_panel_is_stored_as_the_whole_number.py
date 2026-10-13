# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A weight or a minimum posted from the /setup/ panel as 2.5 or 1e2 is stored as the whole number the panel's box shows, rounding halves up."""
from django.test import SimpleTestCase, TestCase

from chardata.setup_edits import posted_integer
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_creation_doors_support import DOORS, TouchedDoors, panel_rows
from chardata.weights_minimums import _caps
from fashionistapulp.structure import set_current_game_version

WHOLE = (('2.5', 3), ('2.49', 2), ('-2.5', -2), ('-2.51', -3), ('1e2', 100), ('1.5e2', 150),
         ('.5', 1), ('+7', 7), (' 12 ', 12), ('0.49999999999999994', 0), ('7E1', 70))
NOT_A_NUMBER = ('abc', 'inf', '-inf', 'nan', 'Infinity', '1e999', '1_0', '2.5.5', '0x10', '1e', 'e5',
                '--3', '1 2', '', ' ')


class ThePostedIntegerIsWhatTheBoxShowsTests(SimpleTestCase):

    def test_a_decimal_or_exponent_stands_for_its_nearest_whole_number_with_halves_up(self):
        for posted, whole in WHOLE:
            with self.subTest(posted=posted):
                self.assertEqual(whole, posted_integer(posted))

    def test_what_is_not_a_finite_number_stands_for_nothing(self):
        for posted in NOT_A_NUMBER:
            with self.subTest(posted=posted):
                self.assertIsNone(posted_integer(posted))
        self.assertIsNone(posted_integer(None))
        self.assertIsNone(posted_integer('9' * 400))


class ADecimalWeightIsStoredWholeTests(TouchedDoors, TestCase):

    def test_a_weight_of_two_and_a_half_is_stored_as_three_on_every_door(self):
        for version in VERSIONS:
            key = panel_rows(version)[0][0]
            for door in DOORS:
                shown = self.state(version, self.build(version, door))['weights'][key]
                self.assertNotEqual(3, shown)
                with self.subTest(version=version, door=door, key=key):
                    stored = self.state(version, self.build(version, door,
                                                            [('weight_%s' % key, '2.5')]))
                    self.assertEqual(3, stored['weights'][key])

    def test_every_form_of_the_number_is_stored_as_the_weights_page_stores_the_whole_one(self):
        cases = (('7000.5', 7001), ('7000.4', 7000), ('-7000.5', -7000), ('-7000.6', -7001),
                 ('7e3', 7000), ('7.5e3', 7500), ('+7001', 7001))
        for version in VERSIONS:
            key = panel_rows(version)[0][0]
            self.assertNotIn(self.state(version, self.build(version, 'wizard'))['weights'][key],
                             [whole for _posted, whole in cases])
            for posted, whole in cases:
                with self.subTest(version=version, posted=posted):
                    stored = self.state(version, self.build(version, 'wizard',
                                                            [('weight_%s' % key, posted)]))
                    control = self.weights_page(version, self.build(version, 'wizard'),
                                                {'weight_%s' % key: str(whole)})
                    self.assertEqual(whole, stored['weights'][key])
                    self.assertEqual(control, stored)

    def test_a_weight_that_is_not_a_finite_number_leaves_the_build_as_it_was(self):
        for version in VERSIONS:
            key = panel_rows(version)[0][0]
            base = self.state(version, self.build(version, 'wizard'))
            for posted in NOT_A_NUMBER:
                with self.subTest(version=version, posted=posted):
                    touched = self.build(version, 'wizard', [('weight_%s' % key, posted)])
                    self.assertEqual(base, self.state(version, touched))


class ADecimalMinimumIsStoredWholeTests(TouchedDoors, TestCase):

    def free_key(self, version):
        set_current_game_version(version)
        capped = set(_caps(self.build(version, 'wizard')))
        return [key for key in panel_rows(version)[1] if key not in capped][0]

    def test_a_minimum_of_one_e_two_is_stored_as_a_hundred_on_every_door(self):
        for version in VERSIONS:
            key = self.free_key(version)
            for door in DOORS:
                with self.subTest(version=version, door=door, key=key):
                    stored = self.state(version, self.build(version, door,
                                                            [('min_%s' % key, '1e2')]))
                    self.assertEqual(100, stored['minimums'][key])

    def test_every_form_of_the_number_is_stored_as_the_weights_page_stores_the_whole_one(self):
        cases = (('99.5', 100), ('99.4', 99), ('-3.5', -3), ('-3.6', -4), ('1.5e1', 15),
                 ('2e1', 20), ('+31', 31))
        for version in VERSIONS:
            key = self.free_key(version)
            for posted, whole in cases:
                with self.subTest(version=version, posted=posted):
                    stored = self.state(version, self.build(version, 'wizard',
                                                            [('min_%s' % key, posted)]))
                    control = self.weights_page(version, self.build(version, 'wizard'),
                                                {'min_%s' % key: str(whole)})
                    self.assertEqual(whole, stored['minimums'][key])
                    self.assertEqual(control, stored)

    def test_a_minimum_that_is_not_a_finite_number_leaves_the_build_as_it_was(self):
        for version in VERSIONS:
            key = self.free_key(version)
            base = self.state(version, self.build(version, 'wizard'))
            for posted in [value for value in NOT_A_NUMBER if value.strip()]:
                with self.subTest(version=version, posted=posted):
                    touched = self.build(version, 'wizard', [('min_%s' % key, posted)])
                    self.assertEqual(base, self.state(version, touched))
