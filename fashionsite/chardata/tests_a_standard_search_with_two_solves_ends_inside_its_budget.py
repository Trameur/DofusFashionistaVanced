# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Standard, the weapon hits solve of a Dofus 3 search runs only in what the first left of the request's budget, so a hard build ends before the proxy gives up."""
from unittest import mock

from django.test import TestCase

from chardata.fashion_action import GUARD_BUDGET_SECONDS
from chardata.tests_a_quick_step_that_runs_out_of_time_without_a_set_searches_again_exactly import (
    _RetroFlow, cut_set, proven_set)
from chardata.tests_a_search_stopped_on_time_can_go_on import _Clock
from fashionistapulp import lpproblem

EASY_FIRST_SOLVE_SECONDS = 30


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
        model, seconds = self.hard_search(self.build_at(None))
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], model.limits)
        self.assertLessEqual(seconds, GUARD_BUDGET_SECONDS)

    def test_the_weapon_hits_solve_gets_what_the_first_left_of_the_budget(self):
        model, _seconds = self.search(self.build_at(None),
                                      proven_set(self.hat, EASY_FIRST_SOLVE_SECONDS),
                                      cut_set(self.hat, 10))
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS,
                          GUARD_BUDGET_SECONDS - EASY_FIRST_SOLVE_SECONDS], model.limits)

    def test_a_priority_already_balanced_ends_inside_the_budget_too(self):
        char = self.build_at(None, 'damage')
        with mock.patch('chardata.fashion_action.balanced_weights',
                        side_effect=lambda char, values: dict(values)):
            model, seconds = self.hard_search(char)
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], model.limits)
        self.assertLessEqual(seconds, GUARD_BUDGET_SECONDS)
