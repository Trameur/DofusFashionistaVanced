# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Flat resistances count where the record sources the flat stage, with that version's truncation order; elsewhere they are listed as not counted."""
from unittest import mock

from django.test import SimpleTestCase

from chardata.spell_combo import final_multiplier, row_values
from chardata.spells_view import _target_fields
from chardata.targets import ELEMENTS, build_target
from fashionistapulp.combat.mitigation import mitigated
from fashionistapulp.combat.rules import load_rules
from fashionistapulp.dofus_constants import BaseDamage
from fashionistapulp.structure import get_structure, set_current_game_version

FLAT_VERSIONS = ('dofus2', 'touch')
PERCENT_ONLY = ('dofus3', 'beta', 'retro')
FLAT = 14
CRIT_FLAT = 6


def _stats(version, **values):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update(values)
    return stats


def _build(version):
    values = {'%sres' % element: FLAT for element in ELEMENTS}
    values.update(crires=CRIT_FLAT, hp=3000)
    char = mock.Mock(pk=3, char_class='Iop', level=200)
    char.name = 'flat'
    solution = mock.Mock()
    solution.get_stats_total.return_value = _stats(version, **values)
    return build_target(char, solution, version, 'b3')


class TheFlatStageTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_records_enable_the_flat_stage_only_on_dofus2_and_touch(self):
        for version in FLAT_VERSIONS:
            self.assertTrue(load_rules(version).enabled('F'), version)
        for version in PERCENT_ONLY:
            self.assertFalse(load_rules(version).enabled('F'), version)
            self.assertEqual(('P',), load_rules(version).applied_order(), version)

    def test_a_flat_resistance_takes_off_its_points_only_where_the_stage_is_on(self):
        for version in FLAT_VERSIONS:
            self.assertEqual(100 - FLAT, mitigated(100, 0, load_rules(version), flat=FLAT))
        for version in PERCENT_ONLY:
            self.assertEqual(100, mitigated(100, 0, load_rules(version), flat=FLAT))

    def test_each_version_truncates_in_its_own_order(self):
        dofus2 = load_rules('dofus2')
        self.assertEqual(('F', 'P', 'R'), dofus2.applied_order())
        self.assertEqual(10, mitigated(10, 25, dofus2, dealt=(150,)))
        self.assertEqual(3, mitigated(10, 50, dofus2, flat=3))
        self.assertEqual(0, mitigated(10, 0, dofus2, flat=12))
        touch = load_rules('touch')
        self.assertEqual(('F', 'P', 'Z'), touch.applied_order())
        self.assertEqual(3, mitigated(10, 50, touch, flat=3))
        self.assertEqual(10.5, mitigated(10, 25, touch, dealt=(150,), after=(150,)))
        self.assertEqual(0, mitigated(10, 0, touch, flat=12))

    def test_the_critical_flat_counts_on_critical_rows_only(self):
        for version in FLAT_VERSIONS:
            target = _build(version)
            with self.subTest(version=version):
                self.assertEqual(FLAT, target.flat_of(ELEMENTS[0]))
                self.assertEqual(FLAT + CRIT_FLAT, target.flat_of(ELEMENTS[0], critical=True))

    def test_a_hit_on_a_build_loses_the_flat_where_counted(self):
        row = BaseDamage(min_dam=30, max_dam=30, element='earth')
        for version in FLAT_VERSIONS + PERCENT_ONLY:
            set_current_game_version(version)
            stats = _stats(version)
            target = _build(version)
            plain = row_values([row], stats, False, True, 1.0, target)[1]
            critical = row_values([row], stats, True, True, 1.0, target)[1]
            with self.subTest(version=version):
                if version in FLAT_VERSIONS:
                    self.assertEqual(30 - FLAT, plain)
                    self.assertEqual(30 - FLAT - CRIT_FLAT, critical)
                else:
                    self.assertEqual(30, plain)
                    self.assertEqual(30, critical)

    def test_dofus2_multiplies_the_dealt_percent_after_the_resistances_and_touch_before(self):
        row = BaseDamage(min_dam=10, max_dam=10, element='earth')
        expected = {'dofus2': 10, 'touch': 11}
        for version, landed in expected.items():
            set_current_game_version(version)
            stats = _stats(version, perspedam=50)
            target = _build(version).replace(percent=(25,) * len(ELEMENTS), flat=None,
                                             crit_flat=0)
            with self.subTest(version=version):
                self.assertEqual(landed, row_values([row], stats, False, True, 1.0, target)[1])
                self.assertEqual(15, row_values([row], stats, False, True, 1.0, target)[0])

    def test_where_the_stage_is_off_the_flat_is_listed_as_not_counted(self):
        for version in FLAT_VERSIONS + PERCENT_ONLY:
            notes = ' '.join(_target_fields(_build(version), 1, 1)['not_counted'])
            with self.subTest(version=version):
                if version in FLAT_VERSIONS:
                    self.assertNotIn('Earth Resist %d' % FLAT, notes)
                    self.assertNotIn('Critical Resist', notes)
                else:
                    self.assertIn('Earth Resist %d' % FLAT, notes)
                    self.assertIn('Critical Resist %d' % CRIT_FLAT, notes)

    def test_the_received_melee_ranged_and_weapon_percents_are_listed_as_not_counted(self):
        for version in FLAT_VERSIONS + PERCENT_ONLY:
            target = _build(version).replace(received=(5, 6, 7))
            notes = ' '.join(_target_fields(target, 1, 1)['not_counted'])
            with self.subTest(version=version):
                self.assertIn('% Melee Resist 5', notes)
                self.assertIn('% Ranged Resist 6', notes)
                self.assertIn('% Weapon Resist 7', notes)

    def test_final_damage_and_negative_final_damage_multiply_each_other(self):
        row = BaseDamage(min_dam=10, max_dam=10, element='earth')
        for version in FLAT_VERSIONS:
            set_current_game_version(version)
            stats = _stats(version, final=20, negfinal=20)
            target = _build(version).replace(percent=(0,) * len(ELEMENTS), flat=None,
                                             crit_flat=0)
            rules = load_rules(version)
            factors = {'dealt': (120, 80)} if version == 'dofus2' else {'after': (120, 80)}
            landed = row_values([row], stats, False, True, final_multiplier(stats), target)[1]
            with self.subTest(version=version):
                self.assertEqual(mitigated(10, 0, rules, **factors), landed)
                self.assertNotEqual(10, landed)
