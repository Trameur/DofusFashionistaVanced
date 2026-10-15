# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A quick step whose clock runs out before any set searches once more without a gap, on Standard's seconds and budget, before the no-set page."""
import re
from unittest import mock

from django.test import TestCase

from chardata.fashion_action import GUARD_BUDGET_SECONDS, MIN_SOLVE_SECONDS, solve_budget_seconds
from chardata.models import Char
from chardata.options import set_options
from chardata.power_steps import POWER_BY_KEY
from chardata.tests_a_priority_keeps_the_safeguard_share_of_the_balanced_build import (
    BALANCED_OUT_OF_TIME, _answer)
from chardata.tests_a_quick_search_says_how_close_to_the_best_it_stopped_and_never_proven import (
    NO_GAP, _GapModel)
from chardata.tests_a_search_stopped_on_time_can_go_on import (
    NOT_PROVEN, PROVEN, _Clock, _FlowMixin, _Memory, _outcome)
from fashionistapulp import lpproblem

RETRO_IOP_FLASH_SECONDS = 8.05
RETRO_IOP_STANDARD_SECONDS = 11.7


def no_set(seconds=RETRO_IOP_FLASH_SECONDS, status='Not Solved'):
    return {'hat': 0, 'objective': None, 'bound': None, 'proven': False, 'start': None,
            'status': status, 'finished': False, 'seconds': seconds}


def proven_set(hat, seconds=RETRO_IOP_STANDARD_SECONDS):
    return dict(_outcome(hat, 1000.0, proven=True), seconds=seconds)


def cut_set(hat, seconds):
    return dict(_outcome(hat, 1000.0, 1100.0), finished=False, seconds=seconds)


class _StatusModel(_GapModel):
    """A scripted model whose runs may end without a set and take seconds on a clock."""

    def run(self, retries, warm_start=None, seed=None, gap=NO_GAP):
        super().run(retries, warm_start, seed, gap)
        if self.clock is not None:
            self.clock.now += self.outcome.get('seconds', 0)

    def get_solved_status(self):
        return self.outcome.get('status', 'Optimal')


class _StandardKeyMemory(_Memory):
    """Remembers a Standard search cut by its clock, carrying a gap it never had, under the keys without a gap."""

    def __init__(self, hat):
        super().__init__()
        self.hat = hat

    def get(self, model_input):
        if getattr(model_input, 'gap', 0):
            return None
        solved_status, stats, result = _answer(model_input, {'hat': self.hat}, proven=False)
        result.time_limit = lpproblem.TIME_LIMIT_SECONDS
        result.tolerance = POWER_BY_KEY['flash'].gap
        return solved_status, stats, result


class _RetroFlow(_FlowMixin):
    version = 'retro'
    prefix = '/retro'

    def build_at(self, power, priority=None):
        char = self.build(priority)
        if power is not None:
            set_options(char, {'power': power})
            char.save()
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


class AQuickStepOutOfTimeWithoutASetSearchesAgainTests(_RetroFlow, TestCase):

    def test_retro_iop_on_flash_gets_the_set_standard_proves(self):
        char = self.build_at('flash')
        model, location = self.fashion(char, no_set(), proven_set(self.hat))
        self.assert_on_the_set(char, location)
        self.assertEqual([POWER_BY_KEY['flash'].gap, NO_GAP], model.gaps)
        self.assertEqual(0, model.inputs[1].gap)
        self.assertEqual([POWER_BY_KEY['flash'].seconds, lpproblem.TIME_LIMIT_SECONDS],
                         model.limits)
        minimal = self.minimal(char)
        self.assertIs(True, minimal.proven)
        self.assertFalse(hasattr(minimal, 'tolerance'))
        page = self.page(char)
        self.assertIn(PROVEN, page)
        self.assertNotIn('Quick search', page)

    def test_fast_searches_again_too(self):
        char = self.build_at('fast')
        model, location = self.fashion(char, no_set(), proven_set(self.hat))
        self.assert_on_the_set(char, location)
        self.assertEqual([POWER_BY_KEY['fast'].gap, NO_GAP], model.gaps)

    def test_the_search_again_gets_what_is_left_of_the_standard_budget(self):
        clock = _Clock()
        char = self.build_at('flash')
        model, _location = self.fashion(char, no_set(30), cut_set(self.hat, 65), clock=clock)
        self.assertEqual([POWER_BY_KEY['flash'].seconds, GUARD_BUDGET_SECONDS - 30], model.limits)

    def test_a_search_again_cut_by_the_clock_says_it_ran_out_of_time_never_within_a_gap(self):
        clock = _Clock()
        char = self.build_at('flash')
        _model, location = self.fashion(char, no_set(30), cut_set(self.hat, 65), clock=clock)
        self.assert_on_the_set(char, location)
        minimal = self.minimal(char)
        self.assertIs(False, minimal.proven)
        self.assertFalse(hasattr(minimal, 'tolerance'))
        page = self.page(char)
        self.assertIn(NOT_PROVEN % (GUARD_BUDGET_SECONDS - 30), page)
        self.assertNotIn('Quick search', page)
        self.assertNotIn(PROVEN, page)

    def test_a_proof_is_remembered_under_the_standard_key_and_nothing_under_the_gap_key(self):
        char = self.build_at('flash')
        self.fashion(char, no_set(), proven_set(self.hat))
        self.assertEqual([0], [remembered.gap for remembered in self.memory.put_inputs])

    def test_a_search_again_cut_by_the_clock_is_not_remembered(self):
        clock = _Clock()
        char = self.build_at('flash')
        self.fashion(char, no_set(30), cut_set(self.hat, 65), clock=clock)
        self.assertEqual([], self.memory.put_inputs)

    def test_a_remembered_standard_set_not_proven_never_reads_as_within_a_gap(self):
        self.memory = _StandardKeyMemory(self.hat)
        char = self.build_at('flash')
        model, location = self.fashion(char, no_set())
        self.assert_on_the_set(char, location)
        self.assertEqual([POWER_BY_KEY['flash'].gap], model.gaps)
        minimal = self.minimal(char)
        self.assertIs(False, minimal.proven)
        self.assertFalse(hasattr(minimal, 'tolerance'))
        page = self.page(char)
        self.assertIn(NOT_PROVEN % lpproblem.TIME_LIMIT_SECONDS, page)
        self.assertNotIn('Quick search', page)

    def test_a_search_again_without_a_set_ends_on_the_no_set_page(self):
        char = self.build_at('flash')
        model, location = self.fashion(char, no_set(), no_set(RETRO_IOP_STANDARD_SECONDS))
        self.assert_on_the_no_set_page(char, location)
        self.assertEqual(2, len(model.gaps))

    def test_no_search_again_without_the_time_for_one(self):
        clock = _Clock()
        char = self.build_at('flash')
        model, location = self.fashion(
            char, no_set(GUARD_BUDGET_SECONDS - MIN_SOLVE_SECONDS + 1), clock=clock)
        self.assert_on_the_no_set_page(char, location)
        self.assertEqual([POWER_BY_KEY['flash'].gap], model.gaps)

    def test_a_proof_of_no_set_is_not_searched_again(self):
        char = self.build_at('flash')
        model, location = self.fashion(char, no_set(status='Infeasible'))
        self.assert_on_the_no_set_page(char, location)
        self.assertEqual([POWER_BY_KEY['flash'].gap], model.gaps)

    def test_standard_out_of_time_without_a_set_is_not_searched_again(self):
        char = self.build_at(None)
        with mock.patch('chardata.fashion_action._closest_solve', return_value={'state': 'skipped'}):
            model, location = self.fashion(char, no_set(lpproblem.TIME_LIMIT_SECONDS))
        self.assert_on_the_no_set_page(char, location)
        self.assertEqual([NO_GAP], model.gaps)

    def test_a_priority_build_says_its_safeguard_had_no_balanced_build(self):
        char = self.build_at('flash', 'damage')
        model, location = self.fashion(char, no_set(), no_set(), proven_set(self.hat))
        self.assert_on_the_set(char, location)
        self.assertEqual([POWER_BY_KEY['flash'].gap, POWER_BY_KEY['flash'].gap, NO_GAP],
                         model.gaps)
        self.assertEqual(model.inputs[1].objective_values, model.inputs[2].objective_values)
        facts = self.minimal(char).guard
        self.assertTrue(facts['fallback'])
        self.assertTrue(facts['no_reference'])
        self.assertTrue(facts['balanced_out_of_time'])
        self.assertIn(BALANCED_OUT_OF_TIME, self.page(char))

    def test_a_priority_build_whose_balanced_search_found_a_set_never_says_it_ran_out_of_time_on_it(self):
        char = self.build_at('flash', 'damage')
        _model, location = self.fashion(char, _outcome(self.hat, 1000.0, 1100.0), no_set(),
                                        no_set(), proven_set(self.hat))
        self.assert_on_the_set(char, location)
        facts = self.minimal(char).guard
        self.assertTrue(facts['fallback'])
        self.assertFalse(facts['no_reference'])
        self.assertFalse(facts['balanced_out_of_time'])
        self.assertFalse(facts['out_of_time'])
        self.assertNotIn(BALANCED_OUT_OF_TIME, self.page(char))

    def test_a_priority_build_without_a_balanced_search_gets_no_safeguard_facts(self):
        char = self.build_at('flash', 'damage')
        with mock.patch('chardata.fashion_action.balanced_weights',
                        side_effect=lambda _char, weights: weights):
            model, location = self.fashion(char, no_set(), proven_set(self.hat))
        self.assert_on_the_set(char, location)
        self.assertEqual([POWER_BY_KEY['flash'].gap, NO_GAP], model.gaps)
        self.assertIsNone(getattr(self.minimal(char), 'guard', None))
        self.assertNotIn(BALANCED_OUT_OF_TIME, self.page(char))


class AQuickStepWithTwoSolvesKeepsTimeForTheSecondWhenItSearchesAgainTests(_RetroFlow, TestCase):
    version = 'dofus3'
    prefix = ''

    def test_the_first_solve_of_the_search_again_leaves_the_second_its_floor(self):
        clock = _Clock()
        char = self.build_at('flash')
        model, _location = self.fashion(char, no_set(30), cut_set(self.hat, 55), clock=clock)
        self.assertEqual(POWER_BY_KEY['flash'].gap, model.gaps[0])
        self.assertEqual(NO_GAP, model.gaps[1])
        self.assertEqual(GUARD_BUDGET_SECONDS - MIN_SOLVE_SECONDS - 30, model.limits[1])

    def test_the_second_solve_of_the_search_again_runs_to_the_end_of_the_standard_budget(self):
        clock = _Clock()
        char = self.build_at('flash')
        with mock.patch('chardata.fashion_action.weapon_hit_terms',
                        side_effect=lambda char, result, model_input: (
                            {'weapon': 1} if result is not None else None)), \
                mock.patch('chardata.fashion_action.crit_hinges', return_value=None):
            model, _location = self.fashion(char, no_set(10), proven_set(self.hat, 5),
                                             cut_set(self.hat, 70), clock=clock)
        self.assertEqual([POWER_BY_KEY['flash'].gap, NO_GAP, NO_GAP], model.gaps)
        self.assertEqual(GUARD_BUDGET_SECONDS - MIN_SOLVE_SECONDS - 10, model.limits[1])
        self.assertEqual(GUARD_BUDGET_SECONDS - 15, model.limits[2])


class TheNoSetPageOfAQuickStepCountsItsSearchAgainTests(_RetroFlow, TestCase):

    def again(self, location):
        page = self.client.get(location, HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        return (re.findall(r'for up to (\d+) seconds', page),
                [re.search(r'loadingAndRunUnchecked\((\d+)\)', form).group(1)
                 for form in re.findall(r'<form[^>]*infeasible-again[^>]*>', page)])

    def test_after_running_out_of_time_search_again_promises_what_its_search_again_may_take(self):
        char = self.build_at('flash')
        _model, location = self.fashion(char, no_set(), no_set(30))
        self.assert_on_the_no_set_page(char, location)
        self.assertLess(solve_budget_seconds(char), GUARD_BUDGET_SECONDS)
        seconds, budgets = self.again(location)
        self.assertEqual([str(GUARD_BUDGET_SECONDS)], seconds)
        self.assertEqual([str(GUARD_BUDGET_SECONDS)], budgets)

