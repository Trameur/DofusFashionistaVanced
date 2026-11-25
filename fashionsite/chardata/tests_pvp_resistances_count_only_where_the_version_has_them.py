# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build's PvP resistances count only when its version grants them and its record adds them; otherwise they are listed as not counted."""
import copy
from unittest import mock

from django.test import SimpleTestCase

from chardata.spells_view import _target_fields
from chardata.targets import ELEMENTS, build_target
from fashionistapulp.combat.rules import RuleSet, load_rules, read_record, record_path
from fashionistapulp.dofus_constants import percent_resist_cap
from fashionistapulp.structure import get_structure

PERCENT = 20
PVP_PERCENT = 25
PVP_FLAT = 9


def _build(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for element in ELEMENTS:
        stats['%sresper' % element] = PERCENT
        stats['pvp%sresper' % element] = PVP_PERCENT
        stats['pvp%sres' % element] = PVP_FLAT
    stats['hp'] = 3000
    char = mock.Mock(pk=5, char_class='Iop', level=200)
    char.name = 'a build'
    solution = mock.Mock()
    solution.get_stats_total.return_value = stats
    return build_target(char, solution, version, 'b5')


def _adding_rules(version):
    record = copy.deepcopy(read_record(record_path(version)))
    record['pvp_lines'] = 'additive_before_cap'
    record['sources']['pvp_lines'] = copy.deepcopy(record['sources']['P'])
    return RuleSet(record)


class PvpResistancesTests(SimpleTestCase):

    def _check_not_counted(self, version, granted):
        target = _build(version)
        fields = _target_fields(target, 100, 100)
        notes = ' '.join(fields['not_counted'])
        self.assertFalse(target.counts_pvp())
        for element in ELEMENTS:
            self.assertEqual(PERCENT, target.percent_of(element))
            self.assertEqual(0, target.flat_of(element))
        if granted:
            self.assertIsNotNone(target.pvp_percent)
            self.assertIn('PVP %d' % PVP_PERCENT, notes)
        else:
            self.assertIsNone(target.pvp_percent)
            self.assertIsNone(target.pvp_flat)
            self.assertNotIn('PVP', notes)
        return target

    def test_dofus3_has_no_pvp_line(self):
        self.assertEqual('none', load_rules('dofus3').field('pvp_lines'))
        self._check_not_counted('dofus3', granted=False)

    def test_beta_has_no_pvp_line(self):
        self.assertEqual('none', load_rules('beta').field('pvp_lines'))
        self._check_not_counted('beta', granted=False)

    def test_dofus2_grants_none_so_none_is_read(self):
        self.assertEqual('none', load_rules('dofus2').field('pvp_lines'))
        self._check_not_counted('dofus2', granted=False)

    def test_touch_grants_them_but_its_server_rule_is_open_so_they_are_listed(self):
        self.assertEqual('unknown', load_rules('touch').field('pvp_lines'))
        self._check_not_counted('touch', granted=True)

    def test_retro_grants_them_but_how_they_add_is_unsourced_so_they_are_listed(self):
        self.assertEqual('unknown', load_rules('retro').field('pvp_lines'))
        self._check_not_counted('retro', granted=True)

    def test_a_record_that_adds_them_counts_them_before_the_cap(self):
        for version in ('touch', 'retro'):
            target = _build(version)
            with self.subTest(version=version), \
                    mock.patch('chardata.targets.load_rules', return_value=_adding_rules(version)):
                self.assertTrue(target.counts_pvp())
                self.assertFalse(target.counts_pvp(attacker_is_player=False))
                for element in ELEMENTS:
                    self.assertEqual(min(PERCENT + PVP_PERCENT, percent_resist_cap(version)),
                                     target.percent_of(element))
                    self.assertEqual(PERCENT, target.percent_of(element, attacker_is_player=False))
                    self.assertEqual(PVP_FLAT, target.flat_of(element))
