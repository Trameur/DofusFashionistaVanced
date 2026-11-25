# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build target meets min(cap, its % resistance) in every version; the payload shows both the build's value and the one counted."""
from unittest import mock

from django.test import SimpleTestCase

from chardata.spells_view import _target_fields
from chardata.targets import ELEMENTS, build_target
from fashionistapulp.combat.mitigation import mitigated
from fashionistapulp.combat.rules import load_rules
from fashionistapulp.dofus_constants import percent_resist_cap
from fashionistapulp.structure import get_structure

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
VALUES = (95, 60, -15, 0, 34)


def _build(version, values):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for element, value in zip(ELEMENTS, values):
        stats['%sresper' % element] = value
    stats['hp'] = 2500
    char = mock.Mock(pk=8, char_class='Sram', level=180)
    char.name = 'capped'
    solution = mock.Mock()
    solution.get_stats_total.return_value = stats
    return build_target(char, solution, version, 'b8')


class ABuildTargetCapTests(SimpleTestCase):

    def test_each_element_reads_the_lower_of_the_cap_and_the_build(self):
        for version in VERSIONS:
            cap = percent_resist_cap(version)
            target = _build(version, VALUES)
            with self.subTest(version=version):
                self.assertTrue(target.is_player)
                self.assertLess(cap, VALUES[0])
                self.assertEqual([min(cap, value) for value in VALUES],
                                 [target.percent_of(element) for element in ELEMENTS])
                self.assertEqual([], target.immune_elements())

    def test_a_hit_on_a_resistance_above_the_cap_lands_as_on_the_cap(self):
        for version in VERSIONS:
            rules = load_rules(version)
            target = _build(version, VALUES)
            capped = _build(version, (percent_resist_cap(version),) + VALUES[1:])
            with self.subTest(version=version):
                self.assertEqual(mitigated(300.0, capped.percent_of(ELEMENTS[0]), rules),
                                 mitigated(300.0, target.percent_of(ELEMENTS[0]), rules))
                self.assertGreater(mitigated(300.0, target.percent_of(ELEMENTS[0]), rules), 0)

    def test_the_payload_shows_the_builds_value_and_the_counted_one(self):
        for version in VERSIONS:
            cap = percent_resist_cap(version)
            fields = _target_fields(_build(version, VALUES), 500, 800)
            with self.subTest(version=version):
                self.assertEqual('build', fields['target']['kind'])
                self.assertNotIn('monster_id', fields['target'])
                self.assertEqual(list(VALUES),
                                 [line['percent'] for line in fields['target']['resistances']])
                self.assertEqual([min(cap, value) for value in VALUES],
                                 [line['counted'] for line in fields['target']['resistances']])
                self.assertEqual(20, fields['target']['hp_share'])
