# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A weight or minimum posted with the value the preset already gives leaves the stored build byte for byte as it was."""
from django.test import TestCase

from chardata.models import Char
from chardata.setup_edits import touched_fields
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_creation_doors_support import DOORS, TouchedDoors, panel_rows


def padded(value):
    if value == '':
        return '  '
    return ' %s%d ' % ('' if value < 0 else '00', value)


BLOBS = ('stats_weight', 'minimum_stats', 'minimum_crits', 'options', 'aspects', 'inclusions',
         'exclusions', 'empty_slots', 'stat_overrides')


def raw(char):
    return {name: bytes(getattr(char, name)) for name in BLOBS}


class TheValuesTheSelectedPresetGivesAreNotSavedAsEditsTests(TouchedDoors, TestCase):

    def preset_post(self, version, state, spelled=str):
        weight_keys, minimum_keys = panel_rows(version)
        post = [('weight_%s' % key, spelled(state['weights'][key])) for key in weight_keys]
        post += [('min_%s' % key, spelled(state['minimums'][key])) for key in minimum_keys]
        return post

    def check(self, version, door, spelled=str):
        base = self.build(version, door)
        post = self.preset_post(version, self.state(version, base), spelled)
        self.assertGreater(len(post), 30)
        again = self.build(version, door, post)
        self.assertEqual(raw(Char.objects.get(pk=base.pk)), raw(Char.objects.get(pk=again.pk)))
        self.assertEqual(self.state(version, base), self.state(version, again))

    def test_every_value_of_the_preset_posted_back_changes_no_byte_on_every_door(self):
        for version in VERSIONS:
            for door in DOORS:
                with self.subTest(version=version, door=door):
                    self.check(version, door)

    def test_the_same_values_spelled_with_spaces_and_zeros_change_nothing(self):
        for version in VERSIONS:
            for door in DOORS:
                with self.subTest(version=version, door=door):
                    self.check(version, door, padded)

    def test_the_server_finds_no_touched_field_in_a_post_of_the_preset_values(self):
        for version in VERSIONS:
            base = self.build(version, 'wizard')
            post = dict(self.preset_post(version, self.state(version, base)))
            with self.subTest(version=version):
                self.assertEqual(({}, {}), touched_fields(base, post))

    def test_one_value_moved_is_the_only_touched_field_the_server_finds(self):
        for version in VERSIONS:
            weight_keys, minimum_keys = panel_rows(version)
            base = self.build(version, 'wizard')
            state = self.state(version, base)
            post = dict(self.preset_post(version, state))
            post['weight_%s' % weight_keys[1]] = str(state['weights'][weight_keys[1]] + 1)
            post['min_%s' % minimum_keys[-1]] = '1' if state['minimums'][minimum_keys[-1]] != 1 else '2'
            with self.subTest(version=version):
                weights, minimums = touched_fields(base, post)
                self.assertEqual(['weight_%s' % weight_keys[1]], sorted(weights))
                self.assertEqual(['min_%s' % minimum_keys[-1]], sorted(minimums))
