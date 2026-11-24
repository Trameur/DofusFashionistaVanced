# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Pushback damage rounds as each client does: Dofus 2 floors [level]/2 and truncates, Touch truncates, Dofus 3 keeps the float."""
from django.test import SimpleTestCase

from chardata.pushback import ROUNDING_BY_VERSION, pushback_damage
from fashionistapulp.game_versions import dofus_versions


class PushbackDamageRoundsAsEachClientDoesTests(SimpleTestCase):

    def _dealt(self, game_version, caster_level, pushback_stat, cells,
               target_resistance=0, intermediates=0):
        return pushback_damage(caster_level, pushback_stat, cells,
                               target_resistance=target_resistance,
                               intermediates=intermediates, game_version=game_version)

    def test_an_odd_level_splits_dofus2_from_touch(self):
        expected = {'dofus2': 196.0, 'touch': 197.0, 'touchbeta': 197.0,
                    'dofus3': 197.25, 'beta': 197.25}
        for version, dealt in expected.items():
            with self.subTest(version=version):
                self.assertEqual(dealt, self._dealt(version, 199, 0, 6))

    def test_an_odd_level_costs_dofus2_a_point_on_an_eight_cell_push(self):
        expected = {'dofus2': 262.0, 'touch': 263.0, 'dofus3': 263.0, 'beta': 263.0}
        for version, dealt in expected.items():
            with self.subTest(version=version):
                self.assertEqual(dealt, self._dealt(version, 199, 0, 8))

    def test_a_quotient_that_is_not_whole_is_truncated_outside_dofus3(self):
        expected = {'dofus2': 80.0, 'touch': 80.0, 'dofus3': 80.25, 'beta': 80.25}
        for version, dealt in expected.items():
            with self.subTest(version=version):
                self.assertEqual(dealt, self._dealt(version, 150, 0, 3))
        expected = {'dofus2': 104.0, 'touch': 104.0, 'dofus3': 104.25, 'beta': 104.25}
        for version, dealt in expected.items():
            with self.subTest(version=version, target_resistance=3):
                self.assertEqual(dealt, self._dealt(version, 200, 10, 3, target_resistance=3))

    def test_one_body_in_the_way_halves_before_truncating(self):
        expected = {'dofus2': 98.0, 'touch': 98.0, 'dofus3': 98.625, 'beta': 98.625}
        for version, dealt in expected.items():
            with self.subTest(version=version):
                self.assertEqual(dealt, self._dealt(version, 199, 0, 6, intermediates=1))

    def test_two_bodies_in_the_way_quarter_before_truncating(self):
        expected = {'dofus2': 49.0, 'touch': 49.0, 'dofus3': 49.3125, 'beta': 49.3125}
        for version, dealt in expected.items():
            with self.subTest(version=version):
                self.assertEqual(dealt, self._dealt(version, 199, 0, 6, intermediates=2))
        expected = {'dofus2': 65.0, 'touch': 65.0, 'dofus3': 65.75, 'beta': 65.75}
        for version, dealt in expected.items():
            with self.subTest(version=version, cells=8):
                self.assertEqual(dealt, self._dealt(version, 199, 0, 8, intermediates=2))

    def test_a_negative_base_is_clamped_to_zero(self):
        for version in ('dofus2', 'touch', 'touchbeta', 'dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertEqual(0.0, self._dealt(version, 200, 0, 4, target_resistance=300))
        for version in ('dofus2', 'touch', 'dofus3', 'beta'):
            with self.subTest(version=version, base='just below zero'):
                dealt = self._dealt(version, 199, 0, 1, target_resistance=132)
                self.assertEqual('0.0', repr(dealt))

    def test_a_whole_quotient_is_the_same_on_every_client(self):
        for version in ('dofus2', 'touch', 'touchbeta', 'dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertEqual(132.0, self._dealt(version, 200, 0, 4))

    def test_every_dofus_version_names_its_rounding(self):
        self.assertEqual([], [version for version in dofus_versions()
                              if version not in ROUNDING_BY_VERSION])
        self.assertIs(ROUNDING_BY_VERSION['touch'], ROUNDING_BY_VERSION['touchbeta'])
        self.assertEqual(ROUNDING_BY_VERSION['dofus3'], ROUNDING_BY_VERSION['beta'])

    def test_retro_still_has_no_number(self):
        for version in ('retro', 'retrobeta'):
            with self.subTest(version=version):
                self.assertIsNone(self._dealt(version, 199, 0, 6))
