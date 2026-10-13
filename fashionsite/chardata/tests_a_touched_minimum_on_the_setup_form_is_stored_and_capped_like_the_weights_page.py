# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A minimum the player touched on /setup/ is stored on the new build through every door and capped as the weights page caps it."""
from django.test import TestCase

from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_creation_doors_support import DOORS, TouchedDoors, panel_rows
from chardata.weights_minimums import _caps
from fashionistapulp.structure import set_current_game_version


CLAMPED_WHEN_SAVED = ('ap', 'mp', 'range')


def shown(values):
    return {key: value for key, value in values.items() if value != ''}


class TheTouchedMinimumIsStoredTests(TouchedDoors, TestCase):

    def caps(self, version, char):
        set_current_game_version(version)
        return {key: cap for key, cap in _caps(char).items() if cap is not None}

    def test_every_door_stores_the_minimum_as_the_weights_page_does(self):
        for version in VERSIONS:
            _weight_keys, minimum_keys = panel_rows(version)
            for door in DOORS:
                base = self.build(version, door)
                before = self.state(version, base)
                for key in minimum_keys[:1] + minimum_keys[-1:]:
                    with self.subTest(version=version, door=door, key=key):
                        touched = self.build(version, door, [('min_%s' % key, '12')])
                        stored = self.state(version, touched)
                        control = self.weights_page(version, self.build(version, door),
                                                    {'min_%s' % key: '12'})
                        self.assertEqual(control, stored)
                        self.assertNotEqual(before['minimums'], stored['minimums'])
                        self.assertEqual(before['weights'], stored['weights'])

    def test_a_minimum_above_the_cap_is_cut_where_the_weights_page_cuts_it(self):
        capped = 0
        for version in VERSIONS:
            base = self.build(version, 'wizard')
            for key, cap in sorted(self.caps(version, base).items()):
                for door in DOORS:
                    with self.subTest(version=version, door=door, key=key):
                        touched = self.build(version, door, [('min_%s' % key, str(cap + 5))])
                        stored = self.state(version, touched)
                        control = self.weights_page(version, self.build(version, door),
                                                    {'min_%s' % key: str(cap + 5)})
                        self.assertEqual(control, stored)
                        self.assertEqual(cap if key in CLAMPED_WHEN_SAVED else cap + 5,
                                         stored['minimums'][key])
                capped += key in CLAMPED_WHEN_SAVED
        self.assertGreater(capped, 5)

    def test_a_minimum_below_the_cap_is_stored_as_typed(self):
        for version in VERSIONS:
            base = self.build(version, 'wizard')
            for key, cap in sorted(self.caps(version, base).items()):
                for door in DOORS:
                    with self.subTest(version=version, door=door, key=key):
                        touched = self.build(version, door, [('min_%s' % key, str(cap - 1))])
                        self.assertEqual(cap - 1, self.state(version, touched)['minimums'][key])

    def test_an_emptied_minimum_is_removed_as_the_weights_page_removes_it(self):
        for version in VERSIONS:
            for door in ('wizard', 'optimize'):
                base = self.build(version, door)
                keys = sorted(shown(self.state(version, base)['minimums']))
                self.assertTrue(keys, (version, door))
                with self.subTest(version=version, door=door, key=keys[0]):
                    touched = self.build(version, door, [('min_%s' % keys[0], '')])
                    stored = self.state(version, touched)
                    control = self.weights_page(version, self.build(version, door),
                                                {'min_%s' % keys[0]: ''})
                    self.assertEqual(control, stored)
                    self.assertEqual('', stored['minimums'][keys[0]])

    def test_the_hand_door_keeps_only_the_minimums_the_player_touched(self):
        for version in VERSIONS:
            _weight_keys, minimum_keys = panel_rows(version)
            key = minimum_keys[-1]
            with self.subTest(version=version, key=key):
                untouched = self.state(version, self.build(version, 'byhand'))
                self.assertEqual({}, shown(untouched['minimums']))
                touched = self.state(version, self.build(version, 'byhand', [('min_%s' % key, '9')]))
                self.assertEqual({key: 9}, shown(touched['minimums']))

    def test_a_minimum_that_is_not_a_number_is_ignored(self):
        for version in VERSIONS:
            for door in DOORS:
                base = self.state(version, self.build(version, door))
                with self.subTest(version=version, door=door):
                    touched = self.build(version, door, [('min_ap', 'abc'), ('min_vit', 'x1')])
                    self.assertEqual(base, self.state(version, touched))
