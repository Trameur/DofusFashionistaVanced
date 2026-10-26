from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import wakfu_family, wakfu_turn, wakfu_value
from fashionistapulp.wakfu_value_rules import RULES, Rule, ASSUMPTION

BASE = {'ap': (6, 6), 'mp': (3, 3), 'wp': (6, 6)}
ROLE = wakfu_value.DamageDealer(('fire',), 'distance')


def totals(**stats):
    out = wakfu_value.bare_totals(BASE)
    out.update(stats)
    return out


def removal(action=55, amount=4):
    return wakfu_family.FamilyRow(
        action, action, wakfu_family.REMOVED[action], amount, None, 'none')


def hindered(stats, rows):
    found = wakfu_family.FamilySpell(1, 'x', 5, None, 3, 0, 0, 1, 5, 1, 245, tuple(rows), ())
    model = wakfu_turn.TurnModel([found], ROLE, 'hindrance', casts_per_spell=1)
    return model.best(totals(**stats))


class RemovalShareTests(SimpleTestCase):
    def test_equal_willpower_removes_half(self):
        self.assertEqual(0.5, wakfu_family.removal_share(0, 0))
        self.assertEqual(0.5, wakfu_family.removal_share(40, 40))

    def test_a_hundred_points_above_removes_all_and_below_removes_none(self):
        self.assertEqual(1.0, wakfu_family.removal_share(100, 0))
        self.assertEqual(0.0, wakfu_family.removal_share(-100, 0))

    def test_ten_points_of_difference_move_the_share_by_a_twentieth(self):
        self.assertAlmostEqual(0.55, wakfu_family.removal_share(10, 0))
        self.assertAlmostEqual(0.45, wakfu_family.removal_share(0, 10))

    def test_past_the_hundred_the_share_stays_between_none_and_all(self):
        self.assertEqual(1.0, wakfu_family.removal_share(500, 0))
        self.assertEqual(0.0, wakfu_family.removal_share(-500, 0))

    def test_the_target_willpower_comes_from_the_rule_when_none_is_given(self):
        self.assertEqual(0, RULES['target_willpower'].value)
        patched = dict(RULES, target_willpower=Rule(100, ASSUMPTION, 'test'))
        with mock.patch.dict(RULES, patched):
            self.assertEqual(0.0, wakfu_family.removal_share(0))
            self.assertEqual(0.5, wakfu_family.removal_share(100))


class HindranceTurnTests(SimpleTestCase):
    def test_a_removal_is_worth_its_points_times_the_share(self):
        self.assertEqual(2.0, hindered({}, [removal()]).damage)
        self.assertEqual(4.0, hindered({'willpower': 100}, [removal()]).damage)
        self.assertEqual(0.0, hindered({'willpower': -100}, [removal()]).damage)

    def test_more_willpower_never_removes_less(self):
        values = [hindered({'willpower': will}, [removal()]).damage
                  for will in range(-120, 121, 10)]
        self.assertEqual(sorted(values), values)
        self.assertEqual(0.0, values[0])
        self.assertEqual(4.0, values[-1])

    def test_each_resource_removed_is_a_part_of_the_turn(self):
        turn = hindered({}, [removal(55, 2), removal(48, 1), removal(161, 3), removal(194, 1)])
        self.assertEqual({'ap': 1.0, 'mp': 0.5, 'range': 1.5, 'wp': 0.5}, turn.elements)
        self.assertEqual(3.5, turn.damage)

    def test_a_max_removal_counts_with_the_resource_it_takes(self):
        turn = hindered({}, [removal(56, 2), removal(57, 2), removal(192, 2)])
        self.assertEqual({'ap': 1.0, 'mp': 1.0, 'wp': 1.0}, turn.elements)

    def test_willpower_gets_a_weight_in_the_hindrance_turn(self):
        found = wakfu_family.FamilySpell(1, 'x', 5, None, 3, 0, 0, 1, 5, 1, 245,
                                         (removal(),), ())
        model = wakfu_turn.TurnModel([found], ROLE, 'hindrance', casts_per_spell=1)
        weights = model.weights(totals())
        self.assertIn('willpower', weights)
        self.assertGreater(weights['willpower'], 0)
