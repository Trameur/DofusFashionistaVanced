# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A quick power step with a priority keeps time for the priority search after the balanced one."""

from unittest import mock

from django.test import TestCase

from chardata import fashion_action
from chardata.fashion_action import request_budget, solve_budget_seconds, solves_per_search
from chardata.models import Char
from chardata.options import set_options
from chardata.power_steps import POWER_BY_KEY
from chardata.tests_a_priority_keeps_the_safeguard_share_of_the_balanced_build import (
    _BuildMixin, _Clock, _EmptyMemory, _TimedModel)

DOFUS3_FLASH_BALANCED_PAIR_SECONDS = 9.46 + 5.81


class _GapTimedModel(_TimedModel):

    def run(self, retries, seed=None, gap=None):
        super().run(retries)

    def search_finished(self):
        return True


class AQuickStepWithAPriorityTests(_BuildMixin, TestCase):

    def build_at(self, power, priority):
        char = self.build({'str'}, priority)
        set_options(char, {'power': power})
        char.save()
        return Char.objects.get(pk=char.pk)

    def run_fashion(self, char, runs):
        clock = _Clock()
        model = _GapTimedModel(clock, runs, self.hat, proven=False)
        with mock.patch('chardata.fashion_action.MEMORY', _EmptyMemory()), \
                mock.patch('chardata.fashion_action.time', clock), \
                mock.patch('chardata.fashion_action.borrow_model', return_value=model), \
                mock.patch('chardata.fashion_action.return_model'):
            response = self.client.get('/fashion/%d/' % char.pk)
        self.assertEqual(302, response.status_code)
        return model

    def test_flash_runs_the_priority_search_after_a_dofus3_length_balanced_search(self):
        char = self.build_at('flash', 'damage')
        model = self.run_fashion(char, [(DOFUS3_FLASH_BALANCED_PAIR_SECONDS, 'Optimal'),
                                        (POWER_BY_KEY['flash'].seconds, 'Optimal')])
        self.assertEqual([], model.runs)
        char.refresh_from_db()
        facts = self.facts(char)
        self.assertFalse(facts['fallback'])
        self.assertFalse(facts['out_of_time'])

    def test_a_guarded_request_never_gets_more_than_standard(self):
        for step in POWER_BY_KEY.values():
            for solves in (1, 2):
                self.assertLessEqual(request_budget(step, solves, True),
                                     fashion_action.GUARD_BUDGET_SECONDS)

    def test_the_waiting_screen_of_a_guarded_flash_build_counts_to_its_request_budget(self):
        char = self.build_at('flash', 'damage')
        flash = POWER_BY_KEY['flash']
        solves = solves_per_search(char)
        self.assertEqual(request_budget(flash, solves, True), solve_budget_seconds(char))
        self.assertGreater(solve_budget_seconds(char), request_budget(flash, solves))
