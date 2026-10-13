# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The minimums route and the wizard's AP, MP and Range fields store no minimum too large for the solver, as the weights page does."""
from django.test import TestCase

from chardata.min_stats import get_min_stats_by_key
from chardata.tests_a_minimum_too_large_for_the_solver_is_not_stored import TOO_LARGE
from chardata.tests_the_wizard_saves_every_minimum_of_the_weights_page import _WizardMixin
from chardata.util import safe_int
from chardata.weights_minimums import MINIMUM_LIMIT

FIELDS = ('min_vit', 'min_hp', 'min_powstr')
READABLE = tuple(posted for posted in TOO_LARGE if safe_int(posted) is not None)


class TheMinimumsRouteLeavesOutAValueTooLargeForTheSolverTests(_WizardMixin, TestCase):

    def route_post(self, data):
        response = self.client.post(self.url('minstatspost'), data)
        self.assertEqual(200, response.status_code)
        self.char.refresh_from_db()
        return get_min_stats_by_key(self.char)

    def stored(self, minimums, field):
        key = field[len('min_'):]
        return minimums.get('adv_mins', {}).get(key, minimums.get(key))

    def test_a_value_outside_the_limit_is_left_out_like_an_unreadable_one(self):
        for field in FIELDS:
            unreadable = self.route_post({field: 'abc', 'min_wis': '300'})
            for posted in TOO_LARGE:
                with self.subTest(field=field, posted=posted[:12]):
                    self.assertEqual(unreadable,
                                     self.route_post({field: posted, 'min_wis': '300'}))
                    self.assertIsNone(self.stored(unreadable, field))

    def test_a_value_at_the_limit_is_stored(self):
        for field in FIELDS:
            for posted in (MINIMUM_LIMIT, -MINIMUM_LIMIT):
                with self.subTest(field=field, posted=posted):
                    self.assertEqual(posted, self.stored(self.route_post({field: str(posted)}), field))


class TouchMinimumsRouteLeavesOutAValueTooLargeForTheSolverTests(
        TheMinimumsRouteLeavesOutAValueTooLargeForTheSolverTests):
    version = 'touch'


class RetroMinimumsRouteLeavesOutAValueTooLargeForTheSolverTests(
        TheMinimumsRouteLeavesOutAValueTooLargeForTheSolverTests):
    version = 'retro'


class TheWizardKeepsTheStoredApWhenItsFieldIsTooLargeTests(_WizardMixin, TestCase):
    version = 'retro'

    def test_only_the_exponent_form_is_unreadable_and_turns_into_zero_as_before(self):
        self.assertEqual(('1e300',), tuple(sorted(set(TOO_LARGE) - set(READABLE))))

    def test_a_value_outside_the_limit_keeps_the_stored_minimum(self):
        for field, name, key in (('min_AP', 'AP', 'ap'), ('min_MP', 'MP', 'mp'),
                                 ('min_Range', 'Range', 'range')):
            for posted in READABLE:
                with self.subTest(field=field, posted=posted[:12]):
                    self.store(minimums={name: 3})
                    self.wizard_post({field: posted})
                    self.assertEqual(3, get_min_stats_by_key(self.char).get(key))

    def test_a_value_at_the_limit_is_stored_where_the_version_has_no_cap(self):
        for posted in (MINIMUM_LIMIT, -MINIMUM_LIMIT):
            with self.subTest(posted=posted):
                self.store(minimums={'AP': 3})
                self.wizard_post({'min_AP': str(posted)})
                self.assertEqual(posted, get_min_stats_by_key(self.char).get('ap'))


class Dofus3WizardKeepsTheStoredApWhenItsFieldIsTooLargeTests(_WizardMixin, TestCase):

    def test_a_value_outside_the_limit_keeps_the_stored_minimum_under_the_cap(self):
        for posted in READABLE:
            with self.subTest(posted=posted[:12]):
                self.store(minimums={'AP': 11})
                self.wizard_post({'min_AP': posted})
                self.assertEqual(11, get_min_stats_by_key(self.char).get('ap'))

    def test_a_value_at_the_limit_is_capped_as_before(self):
        self.store(minimums={'AP': 3})
        self.wizard_post({'min_AP': str(MINIMUM_LIMIT)})
        self.assertEqual(12, get_min_stats_by_key(self.char).get('ap'))
