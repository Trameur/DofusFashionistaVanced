import collections
import types

from django.test import SimpleTestCase

from chardata.tests_wakfu_role_value_sums_share_times_log_of_its_components import (
    LEVEL, role, sheet, turns)
from fashionistapulp import wakfu_turn, wakfu_value
from fashionistapulp.wakfu_model import WakfuBuild

ALL = wakfu_value.ELEMENTAL_MASTERY
ELEMENT_LINES = tuple(wakfu_value.MASTERY_OF.values())
LINES = (ALL,) + ELEMENT_LINES + ('heal_in_percent', 'ranged_dmg', 'melee_dmg', 'critical_bonus')
STEP = 1e-3


def lp_worth(weights, key):
    """What the solver's model gives one point of a plain line with these weights."""
    stub = types.SimpleNamespace(weights=weights)
    stub._element_weights = lambda generic: WakfuBuild._element_weights(stub, generic)
    return WakfuBuild._plain_weight(stub, key)


def slope(found, every, stats, key):
    up, down = collections.Counter(stats), collections.Counter(stats)
    up[key] += STEP
    down[key] -= STEP
    return 100 * (wakfu_value.value(found, LEVEL, up, every)
                  - wakfu_value.value(found, LEVEL, down, every)) / (2 * STEP)


class TheHealWeightsAreCountedOnceTests(SimpleTestCase):
    def check(self, shares):
        found = role('distance', shares)
        every = turns(found)
        stats = sheet()
        weights = wakfu_value.linear_weights(found, LEVEL, stats, every)
        for key in LINES:
            worth, expected = lp_worth(weights, key), slope(found, every, stats, key)
            with self.subTest(line=key):
                self.assertAlmostEqual(expected, worth, delta=max(1e-3 * abs(expected), 1e-9))

    def test_every_line_is_worth_the_slope_of_its_value_with_a_heal_and_a_damage_share(self):
        self.check({'damage': 1, 'heal': 1, 'life': 0.25})

    def test_every_line_is_worth_the_slope_of_its_value_with_a_heal_share_only(self):
        self.check({'heal': 1, 'life': 0.25})

    def test_an_element_the_heal_does_not_read_is_worth_nothing(self):
        found = role('distance', {'heal': 1, 'life': 0.25})
        every = turns(found)
        weights = wakfu_value.linear_weights(found, LEVEL, sheet(), every)
        for element, key in wakfu_value.MASTERY_OF.items():
            with self.subTest(element=element):
                if element == 'water':
                    self.assertGreater(lp_worth(weights, key), 0)
                else:
                    self.assertEqual(0, lp_worth(weights, key))
        self.assertEqual(lp_worth(weights, 'dmg_water_percent'), lp_worth(weights, ALL))

    def test_elemental_mastery_has_no_weight_of_its_own_in_a_heal_turn(self):
        self.assertNotIn(ALL, wakfu_turn.FAMILY_STATS['heal'])
        found = role('distance', {'heal': 1, 'life': 0.25})
        weights = wakfu_value.linear_weights(found, LEVEL, sheet(), turns(found))
        self.assertNotIn(ALL, weights)
