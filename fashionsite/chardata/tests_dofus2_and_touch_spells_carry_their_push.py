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

"""Dofus 2 and Touch spells carry their push from the client's effects, and a turn prices it with that client's rounding."""
from django.test import SimpleTestCase

from chardata.pushback import pushback_damage
from chardata.spell_combo import best_turn, castable_spells, conditional_extras
from chardata.spell_reference import (push_info, pushing_spell_ids,
                                      strips_pushback_resist, summon_push)
from fashionistapulp.structure import get_structure, set_current_game_version


def _cells(version, spell_id):
    return [rank['cells'] for rank in
            [push_info(version, spell_id, index) for index in range(_ranks(version, spell_id))]]


def _ranks(version, spell_id):
    from chardata.spell_reference import get_spell_reference
    for entries in get_spell_reference(version).values():
        for entry in entries:
            if entry.get('id') == spell_id:
                return len(entry.get('push') or [])
    return 0


class APusherHasItsCellsPerRankTests(SimpleTestCase):

    def test_dofus2_pushers(self):
        expected = {13108: [2, 3, 3], 13055: [2, 3, 4]}
        for spell_id, cells in expected.items():
            with self.subTest(spell_id=spell_id):
                self.assertEqual(cells, _cells('dofus2', spell_id))
                self.assertIn(spell_id, pushing_spell_ids('dofus2'))

    def test_touch_pushers(self):
        expected = {8133: [1, 1, 1, 2, 2, 2], 5799: [1, 1, 2, 2, 3, 4],
                    3208: [2, 2, 2, 2, 2, 2]}
        for version in ('touch', 'touchbeta'):
            for spell_id, cells in expected.items():
                with self.subTest(version=version, spell_id=spell_id):
                    self.assertEqual(cells, _cells(version, spell_id))
                    self.assertIn(spell_id, pushing_spell_ids(version))

    def test_a_push_the_game_states_harmless_is_not_a_pusher(self):
        for version, spell_id in (('dofus2', 14312), ('touch', 2795), ('touchbeta', 2795)):
            with self.subTest(version=version):
                self.assertFalse(push_info(version, spell_id)['damaging'])
                self.assertNotIn(spell_id, pushing_spell_ids(version))

    def test_a_push_that_needs_the_target_in_a_state_does_not_win(self):
        # Pursuit pushes 2 cells, 3 on a target in state 807; Hunt 2, 4 on state 516
        for version, spell_id, cells in (('touch', 8105, 2), ('touchbeta', 8105, 2),
                                         ('dofus2', 13795, 2)):
            with self.subTest(version=version, spell_id=spell_id):
                self.assertEqual({cells}, set(_cells(version, spell_id)))

    def test_a_state_gated_push_names_its_state(self):
        expected = {('dofus2', 13822): {'state': 5282, 'present': True},
                    ('touch', 5529): {'state': 579, 'present': False}}
        for (version, spell_id), needs in expected.items():
            with self.subTest(version=version):
                self.assertEqual(needs, push_info(version, spell_id)['needs'])


class APullIsNotAPushTests(SimpleTestCase):

    def test_attraction(self):
        for version, spell_id in (('dofus2', 12735), ('touch', 5887), ('touchbeta', 5887)):
            with self.subTest(version=version):
                self.assertIsNone(push_info(version, spell_id))
                self.assertNotIn(spell_id, pushing_spell_ids(version))

    def test_the_reader_skips_a_pull_row(self):
        from chardata.tests import itemscraper_module
        reader = itemscraper_module('store_spell_reference')
        pull = {'effects': [{'effectId': 6, 'diceNum': 3, 'diceSide': 0, 'targetMask': 'a,A'}]}
        push = {'effects': [{'effectId': 5, 'diceNum': 3, 'diceSide': 0, 'targetMask': 'a,A'}]}
        self.assertEqual([None, {'cells': 3, 'damaging': True}],
                         reader._push_per_rank(reader._d2o_levels([pull, push])))


class ANonPusherHasNoPushTests(SimpleTestCase):

    def test_pressure(self):
        for version, spell_id in (('dofus2', 13106), ('touch', 8139), ('touchbeta', 8139)):
            with self.subTest(version=version):
                self.assertIsNone(push_info(version, spell_id))
                self.assertEqual(0, strips_pushback_resist(version, spell_id))
                self.assertIsNone(summon_push(version, spell_id))


class TouchbetaReadsLikeTouchTests(SimpleTestCase):

    def test_same_push_and_stripped_resistance(self):
        for spell_id in (5799, 8133, 3208, 2795, 5529):
            with self.subTest(spell_id=spell_id):
                for index in range(6):
                    self.assertEqual(push_info('touch', spell_id, index),
                                     push_info('touchbeta', spell_id, index))
                    self.assertEqual(strips_pushback_resist('touch', spell_id, index),
                                     strips_pushback_resist('touchbeta', spell_id, index))


class StrippedResistanceAndSummonPushTests(SimpleTestCase):

    def test_stripped_pushback_resistance_per_rank(self):
        self.assertEqual([60, 80], [strips_pushback_resist('dofus2', 13866, index)
                                    for index in range(2)])
        for version in ('touch', 'touchbeta'):
            with self.subTest(version=version):
                self.assertEqual([10, 15, 20, 25, 30, 40],
                                 [strips_pushback_resist(version, 3208, index)
                                  for index in range(6)])

    def test_the_turret_pushes_on_its_own_turn(self):
        for version, spell_id in (('dofus2', 13831), ('touch', 3214), ('touchbeta', 3214)):
            with self.subTest(version=version):
                self.assertEqual({'least': 2, 'most': 6}, summon_push(version, spell_id))
                self.assertIsNone(push_info(version, spell_id))


class ATurnPricesThePushWithTheClientsRoundingTests(SimpleTestCase):

    LEVEL = 199

    def _setup(self, version, char_class, spell_id, pshdam, level):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(version)
        stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
        stats.update({'str': 300, 'ap': 12, 'pshdam': pshdam})
        spells = castable_spells(char_class, level, version)
        return stats, spells, next(c for c in spells if c.spell_id == spell_id)

    def _check(self, version, char_class, spell_id, pshdam, cells, by_hand, level=LEVEL):
        stats, spells, pusher = self._setup(version, char_class, spell_id, pshdam, level)
        self.assertEqual(cells, pusher.push_cells)
        self.assertEqual(by_hand, pushback_damage(level, pshdam, cells,
                                                  game_version=version))
        extras = conditional_extras(stats, spells, [(pusher.name, 0.0)],
                                    game_version=version, caster_level=level)
        self.assertEqual([(pusher.name, 'pushback into an obstacle', by_hand)], extras)
        counted, _order = best_turn(stats, [pusher], pusher.cost, game_version=version,
                                    caster_level=level, pushback=True)
        left_out, _order = best_turn(stats, [pusher], pusher.cost, game_version=version,
                                     caster_level=level, pushback=False)
        self.assertAlmostEqual(by_hand / 2, counted - left_out)

    def test_dofus2_intimidation(self):
        # floor(199 / 2) = 99; (99 + 0 + 32) * 3 / 4 = 98.25
        self._check('dofus2', 'Iop', 13108, 0, 3, 98.0)
        # (99 + 10 + 32) * 3 / 4 = 105.75
        self._check('dofus2', 'Iop', 13108, 10, 3, 105.0)

    def test_dofus2_retreating_shot(self):
        # (99 + 0 + 32) * 4 / 4 = 131
        self._check('dofus2', 'Cra', 13055, 0, 4, 131.0)

    def test_touch_intimidation(self):
        for version in ('touch', 'touchbeta'):
            with self.subTest(version=version):
                # (99.5 + 0 + 32) * 2 / 4 = 65.75
                self._check(version, 'Iop', 8133, 0, 2, 65.0)
                # (99.5 + 10 + 32) * 2 / 4 = 70.75
                self._check(version, 'Iop', 8133, 10, 2, 70.0)

    def test_touch_retreat_arrow(self):
        # (99.5 + 0 + 32) * 4 / 4 = 131.5
        self._check('touch', 'Cra', 5799, 0, 4, 131.0)

    def test_touch_rounds_three_cells_at_an_odd_level_without_flooring_the_half_level(self):
        # level 99: (49.5 + 0 + 32) * 3 / 4 = 61.125, a floored half level gives 60.75
        self._check('touch', 'Cra', 5799, 0, 3, 61.0, level=99)
