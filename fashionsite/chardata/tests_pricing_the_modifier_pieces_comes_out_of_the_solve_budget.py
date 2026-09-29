# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The priced solve only gets what the unpriced solve and the pricing left of the request budget; without the setting the limits are the usual ones."""

from unittest import mock

from django.test import TestCase, override_settings

from chardata import fashion_action
from chardata.tests_a_priority_keeps_the_safeguard_share_of_the_balanced_build import (
    _BuildMixin, _Clock, _EmptyMemory, _TimedModel)
from fashionistapulp import lpproblem

PRICED = {1: {12: 500}}


class _Pricing(_BuildMixin, TestCase):

    def run_fashion(self, char, runs, pricing_seconds=0):
        clock = _Clock()
        model = _TimedModel(clock, runs, self.hat, proven=True)
        inputs = []
        setup = model.setup

        def record(model_input):
            inputs.append(model_input)
            setup(model_input)
        model.setup = record

        def priced(game_version, char_class, level, weights, stats, temporix=False,
                   weapon=None):
            clock.now += pricing_seconds
            return dict(PRICED), {}
        with mock.patch('chardata.fashion_action.MEMORY', _EmptyMemory()), \
                mock.patch('chardata.fashion_action.time', clock), \
                mock.patch('chardata.fashion_action.borrow_model', return_value=model), \
                mock.patch('chardata.fashion_action.return_model'), \
                mock.patch('chardata.fashion_action.modifier_values', side_effect=priced), \
                mock.patch('chardata.fashion_action.pays_at_the_true_turn', return_value=True):
            response = self.client.get('/fashion/%d/' % char.pk)
        self.assertEqual(302, response.status_code)
        self.assertEqual([], model.runs)
        return model.limits, [model_input.modifier_values for model_input in inputs]


class WithoutTheSettingTheLimitsAreTheUsualOnesTests(_Pricing):

    def test_a_plain_build_is_solved_once_with_the_usual_limit(self):
        limits, priced = self.run_fashion(self.build({'str'}), [(5, 'Optimal')], 12)
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], limits)
        self.assertEqual([{}], priced)

    def test_a_guarded_build_is_solved_with_the_usual_limits(self):
        limits, priced = self.run_fashion(self.build({'str'}, 'damage'),
                                          [(5, 'Optimal'), (20, 'Optimal')], 12)
        self.assertEqual([fashion_action.BALANCED_SECONDS, lpproblem.TIME_LIMIT_SECONDS],
                         limits)
        self.assertEqual([{}, {}], priced)


@override_settings(PRICE_SPELL_MODIFIERS=True)
class APricedSolveGetsWhatIsLeftOfTheBudgetTests(_Pricing):

    def test_the_priced_solve_gets_what_the_unpriced_solve_and_the_pricing_left(self):
        limits, priced = self.run_fashion(self.build({'str'}),
                                          [(5, 'Optimal'), (5, 'Optimal')], 12)
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS,
                          fashion_action.GUARD_BUDGET_SECONDS - 5 - 12], limits)
        self.assertEqual([{}, PRICED], priced)
        self.assertEqual(lpproblem.TIME_LIMIT_SECONDS, lpproblem.SOLVER.timeLimit)

    def test_no_priced_solve_starts_with_less_than_the_shortest_solve_left(self):
        pricing = fashion_action.GUARD_BUDGET_SECONDS - 80 - fashion_action.MIN_SOLVE_SECONDS + 1
        limits, priced = self.run_fashion(self.build({'str'}), [(80, 'Optimal')], pricing)
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], limits)
        self.assertEqual([{}], priced)

    def test_the_priced_guarded_solve_gets_what_is_left_of_the_guard_budget(self):
        limits, priced = self.run_fashion(self.build({'str'}, 'damage'),
                                          [(5, 'Optimal'), (20, 'Optimal'), (5, 'Optimal')],
                                          12)
        self.assertEqual([fashion_action.BALANCED_SECONDS, lpproblem.TIME_LIMIT_SECONDS,
                          fashion_action.GUARD_BUDGET_SECONDS - 5 - 20 - 12], limits)
        self.assertEqual([{}, {}, PRICED], priced)
