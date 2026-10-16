# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The budget a quick step shows counts the solves its request runs, so the slowest measured requests end inside it."""
import math
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import presets
from chardata.coaching_view import create_build
from chardata import fashion_action
from chardata.fashion_action import (GUARD_BUDGET_SECONDS, SOLVE_MARGIN_SECONDS,
                                     solve_budget_seconds, solves_per_search)
from chardata.models import Char
from chardata.options import set_options
from chardata.power_steps import POWER_BY_KEY
from chardata.tests_a_quick_step_that_runs_out_of_time_without_a_set_searches_again_exactly import (
    _RetroFlow, _StatusModel, proven_set)
from chardata.tests_a_search_stopped_on_time_can_go_on import _Clock
from fashionistapulp import lpproblem

SLOWEST_FLASH_WITHOUT_A_PRIORITY = {'dofus3': 24.17, 'beta': 8.75, 'dofus2': 8.14,
                                    'touch': 4.88, 'retro': 8.67}
SLOWEST_FLASH_WITH_A_PRIORITY = {'dofus3': 38.12, 'beta': 18.36, 'touch': 12.1}
SLOWEST_FAST_WITH_A_PRIORITY = {'dofus3': 53.2}


class AQuickStepBudgetCountsTheSolvesTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('budget', 'budget@test.local', 'pw-42-solid')

    def budget(self, version, power, priority=None):
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, 'Iop', 200, {'str'}, version)
        if priority:
            presets.apply_setup_choices(char, {'str'}, priority=priority, set_minimums=False)
        if power != 'standard':
            set_options(char, {'power': power})
        char.save()
        return solve_budget_seconds(Char.objects.get(pk=char.pk))

    def test_the_slowest_flash_requests_without_a_priority_end_inside_their_budget(self):
        for version, seconds in SLOWEST_FLASH_WITHOUT_A_PRIORITY.items():
            with self.subTest(version=version):
                self.assertLess(seconds, self.budget(version, 'flash'))

    def test_the_slowest_quick_requests_with_a_priority_end_inside_their_budget(self):
        for power, slowest in (('flash', SLOWEST_FLASH_WITH_A_PRIORITY),
                               ('fast', SLOWEST_FAST_WITH_A_PRIORITY)):
            for version, seconds in slowest.items():
                with self.subTest(power=power, version=version):
                    self.assertLess(seconds, self.budget(version, power, 'damage'))

    def test_dofus3_counts_its_weapon_hits_solve(self):
        for power in ('flash', 'fast'):
            with self.subTest(power=power):
                self.assertEqual(2 * self.budget('retro', power), self.budget('dofus3', power))

    def test_a_priority_doubles_the_budget_never_past_standard(self):
        for version in ('dofus3', 'retro'):
            for power in ('flash', 'fast'):
                with self.subTest(version=version, power=power):
                    self.assertEqual(min(2 * self.budget(version, power), GUARD_BUDGET_SECONDS),
                                     self.budget(version, power, 'damage'))

    def test_standard_keeps_its_budget_on_every_version(self):
        for version in SLOWEST_FLASH_WITHOUT_A_PRIORITY:
            with self.subTest(version=version):
                self.assertEqual(GUARD_BUDGET_SECONDS, self.budget(version, 'standard'))
                self.assertEqual(GUARD_BUDGET_SECONDS, self.budget(version, 'standard', 'damage'))

    def test_a_quick_step_never_promises_less_than_its_seconds_per_solve(self):
        for power in ('flash', 'fast'):
            with self.subTest(power=power):
                self.assertGreater(self.budget('retro', power), POWER_BY_KEY[power].seconds)


class AQuickStepOnAModelOfItsOwnCountsABuildPerSolveTests(AQuickStepBudgetCountsTheSolvesTests):

    BUILD_SECONDS = 20

    def budget(self, version, power, priority=None):
        with mock.patch.dict(fashion_action._BUILD_SECONDS, {version: self.BUILD_SECONDS},
                             clear=True), \
                mock.patch.dict(fashion_action._SOLVE_BUILD_SECONDS, {}, clear=True), \
                mock.patch('chardata.fashion_action.get_effective_stat_overrides',
                           return_value={'vit': 100}):
            return super().budget(version, power, priority)

    def expected(self, version, power, priority=None):
        request = RequestFactory().post('/')
        request.user = self.owner
        solves = solves_per_search(create_build(request, 'Iop', 200, {'str'}, version))
        budget = solves * (POWER_BY_KEY[power].seconds + self.BUILD_SECONDS + SOLVE_MARGIN_SECONDS)
        return min(2 * budget if priority else budget, GUARD_BUDGET_SECONDS)

    def test_every_solve_of_the_request_counts_its_own_model_build(self):
        for version in ('dofus3', 'retro'):
            for power in ('flash', 'fast'):
                for priority in (None, 'damage'):
                    with self.subTest(version=version, power=power, priority=priority):
                        self.assertEqual(self.expected(version, power, priority),
                                         self.budget(version, power, priority))

    def test_dofus3_counts_its_weapon_hits_solve(self):
        for power in ('flash', 'fast'):
            with self.subTest(power=power):
                self.assertEqual(min(2 * self.budget('retro', power), GUARD_BUDGET_SECONDS),
                                 self.budget('dofus3', power))

    def test_standard_keeps_its_budget_on_every_version(self):
        for version in SLOWEST_FLASH_WITHOUT_A_PRIORITY:
            with self.subTest(version=version):
                self.assertEqual(lpproblem.TIME_LIMIT_SECONDS + self.BUILD_SECONDS,
                                 self.budget(version, 'standard'))


class AModelOfItsOwnMeasuresItsBuildForTheBudgetTests(_RetroFlow, TestCase):

    def test_a_quick_solve_on_a_model_of_its_own_records_how_long_the_model_took_to_build(self):
        char = self.build_at('flash')
        clock = _Clock()
        model = _StatusModel([proven_set(self.hat, 5)], clock)
        model.build_seconds = 0.6
        with mock.patch.dict(fashion_action._SOLVE_BUILD_SECONDS, {}, clear=True):
            with self.solver(model, clock, {'vit': 100}):
                response = self.client.get('%s/fashion/%d/' % (self.prefix, char.pk))
            self.assertEqual(302, response.status_code)
            self.assertAlmostEqual(0.6, fashion_action._SOLVE_BUILD_SECONDS[self.version])
            with mock.patch('chardata.fashion_action.get_effective_stat_overrides',
                            return_value={'vit': 100}):
                self.assertEqual(
                    math.ceil(POWER_BY_KEY['flash'].seconds + 0.6 + SOLVE_MARGIN_SECONDS),
                    solve_budget_seconds(Char.objects.get(pk=char.pk)))

    def test_standard_keeps_its_budget_after_a_solve_on_a_model_of_its_own(self):
        char = self.build_at(None)
        clock = _Clock()
        model = _StatusModel([proven_set(self.hat, 5)], clock)
        model.build_seconds = 0.6
        with mock.patch.dict(fashion_action._SOLVE_BUILD_SECONDS, {}, clear=True), \
                mock.patch.dict(fashion_action._BUILD_SECONDS, {}, clear=True):
            with self.solver(model, clock, {'vit': 100}):
                self.client.get('%s/fashion/%d/' % (self.prefix, char.pk))
            with mock.patch('chardata.fashion_action.get_effective_stat_overrides',
                            return_value={'vit': 100}):
                self.assertEqual(
                    lpproblem.TIME_LIMIT_SECONDS + fashion_action.FIRST_BUILD_SECONDS,
                    solve_budget_seconds(Char.objects.get(pk=char.pk)))
