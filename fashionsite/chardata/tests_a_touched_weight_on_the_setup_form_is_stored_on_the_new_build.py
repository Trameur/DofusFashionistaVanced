# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A weight the player touched on /setup/ is stored on the new build through every door, as the weights page would store it."""
from django.test import TestCase

from chardata.stats_weights import MAX_STAT_WEIGHT
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_creation_doors_support import DOORS, TouchedDoors, panel_rows


class TheTouchedWeightIsStoredTests(TouchedDoors, TestCase):

    def test_every_door_stores_the_weight_and_leaves_the_others_as_the_weights_page_does(self):
        for version in VERSIONS:
            weight_keys, _minimum_keys = panel_rows(version)
            for door in DOORS:
                base = self.build(version, door)
                shown = self.state(version, base)['weights']
                for key in (weight_keys[0], 'ap', weight_keys[-1]):
                    value = shown[key] + 7
                    with self.subTest(version=version, door=door, key=key):
                        touched = self.build(version, door, [('weight_%s' % key, str(value))])
                        stored = self.state(version, touched)
                        self.assertEqual(value, stored['weights'][key])
                        control = self.weights_page(version, self.build(version, door),
                                                    {'weight_%s' % key: str(value)})
                        self.assertEqual(control, stored)
                        self.assertEqual(self.state(version, base)['minimums'], stored['minimums'])

    def test_a_weight_beyond_the_bounds_is_cut_where_the_weights_page_cuts_it(self):
        for version in VERSIONS:
            for door in DOORS:
                for value in (10 * MAX_STAT_WEIGHT, -10 * MAX_STAT_WEIGHT):
                    with self.subTest(version=version, door=door, value=value):
                        touched = self.build(version, door, [('weight_ap', str(value))])
                        stored = self.state(version, touched)
                        control = self.weights_page(version, self.build(version, door),
                                                    {'weight_ap': str(value)})
                        self.assertEqual(max(-MAX_STAT_WEIGHT, min(MAX_STAT_WEIGHT, value)),
                                         stored['weights']['ap'])
                        self.assertEqual(control, stored)

    def test_several_touched_weights_are_all_stored(self):
        for version in VERSIONS:
            weight_keys, _minimum_keys = panel_rows(version)
            picked = weight_keys[:6]
            for door in DOORS:
                shown = self.state(version, self.build(version, door))['weights']
                post = [('weight_%s' % key, str(shown[key] + 3 + index))
                        for index, key in enumerate(picked)]
                with self.subTest(version=version, door=door):
                    stored = self.state(version, self.build(version, door, post))['weights']
                    control = self.weights_page(version, self.build(version, door), dict(post))
                    self.assertEqual(control['weights'], stored)
                    for index, key in enumerate(picked):
                        self.assertEqual(shown[key] + 3 + index, stored[key], key)

    def test_a_weight_that_is_not_a_number_is_ignored(self):
        for version in VERSIONS:
            for door in DOORS:
                base = self.state(version, self.build(version, door))
                with self.subTest(version=version, door=door):
                    touched = self.build(version, door, [('weight_ap', 'abc'), ('weight_mp', '')])
                    self.assertEqual(base, self.state(version, touched))
