import time
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import wakfu_value


class AJointRoundLeavesTimeForTheStepwiseRoundsTests(SimpleTestCase):
    def test_without_fight_lines_the_round_gets_the_whole_deadline(self):
        deadline = time.monotonic() + 80
        self.assertEqual(deadline, wakfu_value.joint_deadline(deadline, False))

    def test_without_a_deadline_the_round_has_none(self):
        self.assertIsNone(wakfu_value.joint_deadline(None, True))

    def test_with_fight_lines_the_round_gets_a_share_of_what_is_left(self):
        with mock.patch.object(time, 'monotonic', return_value=100.0):
            given = wakfu_value.joint_deadline(180.0, True)
        self.assertAlmostEqual(100 + wakfu_value.JOINT_SHARE * 80, given)

    def test_a_deadline_already_past_gives_a_round_that_is_out_of_time_at_once(self):
        with mock.patch.object(time, 'monotonic', return_value=100.0):
            self.assertEqual(100.0, wakfu_value.joint_deadline(90.0, True))

    def test_what_a_cut_round_leaves_is_enough_for_a_stepwise_round(self):
        with mock.patch.object(time, 'monotonic', return_value=0.0):
            given = wakfu_value.joint_deadline(85.0, True)
        left = 85.0 - given
        self.assertGreaterEqual(left, wakfu_value.MIN_ROUND_SECONDS)
