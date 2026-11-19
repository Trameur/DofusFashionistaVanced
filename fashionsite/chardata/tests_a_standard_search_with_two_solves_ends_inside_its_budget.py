# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Standard, the weapon hits solve of a Dofus 3 search runs only in what the first left of the request's budget, so a hard build ends before the proxy gives up."""
from unittest import mock

from django.test import TestCase

from chardata.fashion_action import GUARD_BUDGET_SECONDS
from chardata.models import Char
from chardata.tests_a_search_stopped_on_time_can_go_on import (
    _Clock, _FlowMixin, _outcome, _StoppedModel)
from fashionistapulp import lpproblem

EASY_FIRST_SOLVE_SECONDS = 30
NO_SET_SECONDS = 8.05
RETRO_IOP_STANDARD_SECONDS = 11.7


def no_set(seconds=NO_SET_SECONDS, status='Not Solved'):
    return {'hat': 0, 'objective': None, 'bound': None, 'proven': False, 'start': None,
            'status': status, 'seconds': seconds}


def proven_set(hat, seconds=RETRO_IOP_STANDARD_SECONDS):
    return dict(_outcome(hat, 1000.0, proven=True), seconds=seconds)


def cut_set(hat, seconds):
    return dict(_outcome(hat, 1000.0, 1100.0), seconds=seconds)


class _StatusModel(_StoppedModel):
    """A scripted model whose runs may end without a set and take seconds on a clock."""

    def run(self, retries, warm_start=None, seed=None):
        super().run(retries, warm_start, seed)
        if self.clock is not None:
            self.clock.now += self.outcome.get('seconds', 0)

    def get_solved_status(self):
        return self.outcome.get('status', 'Optimal')


class _RetroFlow(_FlowMixin):
    version = 'retro'
    prefix = '/retro'

    def build_at(self, priority=None):
        char = self.build(priority)
        return Char.objects.get(pk=char.pk)

    def fashion(self, char, *outcomes, clock=None):
        model = _StatusModel(outcomes, clock)
        with self.solver(model, clock):
            response = self.client.get('%s/fashion/%d/' % (self.prefix, char.pk))
        self.assertEqual(302, response.status_code)
        char.refresh_from_db()
        return model, response['Location']

    def assert_on_the_set(self, char, location):
        self.assertEqual('%s/solution/%d/' % (self.prefix, char.pk), location)

    def assert_on_the_no_set_page(self, char, location):
        self.assertEqual('%s/infeasible/%d/' % (self.prefix, char.pk), location)


class AStandardSearchWithTwoSolvesEndsInsideItsBudgetTests(_RetroFlow, TestCase):
    version = 'dofus3'
    prefix = ''

    def search(self, char, *outcomes):
        clock = _Clock()
        started = clock.now
        with mock.patch('chardata.fashion_action.weapon_hit_terms',
                        side_effect=lambda char, result, model_input: (
                            {'weapon': 1} if result is not None else None)), \
                mock.patch('chardata.fashion_action.crit_hinges', return_value=None):
            model, location = self.fashion(char, *outcomes, clock=clock)
        self.assert_on_the_set(char, location)
        return model, clock.now - started

    def hard_search(self, char):
        return self.search(char, cut_set(self.hat, lpproblem.TIME_LIMIT_SECONDS))

    def test_a_first_solve_that_runs_its_limit_keeps_it_and_ends_the_search(self):
        model, seconds = self.hard_search(self.build_at())
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], model.limits)
        self.assertLessEqual(seconds, GUARD_BUDGET_SECONDS)

    def test_the_weapon_hits_solve_gets_what_the_first_left_of_the_budget(self):
        model, _seconds = self.search(self.build_at(),
                                      proven_set(self.hat, EASY_FIRST_SOLVE_SECONDS),
                                      cut_set(self.hat, 10))
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS,
                          GUARD_BUDGET_SECONDS - EASY_FIRST_SOLVE_SECONDS], model.limits)

    def test_a_priority_already_balanced_ends_inside_the_budget_too(self):
        char = self.build_at('damage')
        with mock.patch('chardata.fashion_action.balanced_weights',
                        side_effect=lambda char, values: dict(values)):
            model, seconds = self.hard_search(char)
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], model.limits)
        self.assertLessEqual(seconds, GUARD_BUDGET_SECONDS)
