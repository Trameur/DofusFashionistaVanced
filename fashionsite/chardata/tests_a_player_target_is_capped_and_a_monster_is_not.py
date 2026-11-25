# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The percent stage per version: 0 changes nothing, 100 or more stops the hit, below 0 raises it, only a player is capped; a rounding record is fed whole rolls."""
import math

from django.test import SimpleTestCase

from chardata.targets import ELEMENTS, Target
from fashionistapulp.combat.mitigation import expected_hit, is_immune, mitigated
from fashionistapulp.combat.rules import load_rules
from fashionistapulp.dofus_constants import percent_resist_cap

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
HITS = (1.0, 37.0, 250.5, 1999.0)


def _hits(rules):
    return [hit for hit in HITS if not rules.rounds() or hit == int(hit)]


def _target(version, percent, is_player):
    return Target(version=version, kind='build' if is_player else 'monster',
                  ref=('m', 1, 1), level=200, hp=10000, percent=(percent,) * len(ELEMENTS),
                  is_player=is_player, label='a target')


class ThePercentStageTests(SimpleTestCase):

    def test_zero_percent_is_the_identity(self):
        for version in VERSIONS:
            rules = load_rules(version)
            for hit in _hits(rules):
                with self.subTest(version=version, hit=hit):
                    self.assertEqual(hit, mitigated(hit, 0, rules))

    def test_a_hundred_or_more_stops_the_hit_and_reads_immune(self):
        for version in VERSIONS:
            rules = load_rules(version)
            for percent in (100, 101, 150, 9999):
                target = _target(version, percent, False)
                with self.subTest(version=version, percent=percent):
                    self.assertTrue(is_immune(target.percent_of(ELEMENTS[0])))
                    self.assertEqual(list(ELEMENTS), target.immune_elements())
                    for hit in HITS:
                        self.assertEqual(0, mitigated(hit, target.percent_of(ELEMENTS[0]),
                                                      rules))
                    self.assertEqual(0, expected_hit(HITS, percent, rules))

    def test_minus_fifty_raises_by_half_within_the_tolerance(self):
        for version in VERSIONS:
            rules = load_rules(version)
            for hit in HITS:
                with self.subTest(version=version, hit=hit):
                    self.assertLessEqual(abs(mitigated(hit, -50, rules) - hit * 3 / 2),
                                         rules.tolerance_per_hit)

    def test_an_unknown_resistance_lets_the_hit_through(self):
        for version in VERSIONS:
            rules = load_rules(version)
            with self.subTest(version=version):
                last_floor = rules.enabled('Z') and rules.rounding_of('Z') == 'floor'
                self.assertEqual(math.floor(HITS[2]) if last_floor else HITS[2],
                                 mitigated(HITS[2], None, rules))
                self.assertFalse(is_immune(None))

    def test_a_player_above_the_cap_reads_the_cap_and_a_monster_reads_its_own(self):
        for version in VERSIONS:
            rules = load_rules(version)
            cap = percent_resist_cap(version)
            above = cap + 20
            for element in ELEMENTS:
                player = _target(version, above, True)
                at_cap = _target(version, cap, True)
                monster = _target(version, above, False)
                with self.subTest(version=version, element=element):
                    self.assertEqual(cap, player.percent_of(element))
                    self.assertEqual(above, monster.percent_of(element))
                    for hit in _hits(rules):
                        self.assertEqual(mitigated(hit, at_cap.percent_of(element), rules),
                                         mitigated(hit, player.percent_of(element), rules))
                        below = (self.assertLess if not rules.rounds() or hit == HITS[-1]
                                 else self.assertLessEqual)
                        below(mitigated(hit, monster.percent_of(element), rules),
                              mitigated(hit, player.percent_of(element), rules))
