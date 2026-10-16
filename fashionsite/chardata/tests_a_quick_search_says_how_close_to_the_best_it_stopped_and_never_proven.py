# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build on a quick power step searches within its gap and seconds, and its pages never call the set proven."""
from types import SimpleNamespace

from django.test import RequestFactory, TestCase

from chardata.fashion_action import request_budget, solve_budget_seconds, solves_per_search
from chardata.models import Char
from chardata.options import set_options
from chardata.power_steps import POWER_BY_KEY
from chardata.solution import get_solution
from chardata.solution_view import _build_og_description, _build_share_text
from chardata.tests_a_search_stopped_on_time_can_go_on import (
    BUTTON, GAP, NOT_PROVEN, PROVEN, WIDE_GAP, _FlowMixin, _outcome, _StoppedModel)
from fashionistapulp import lpproblem

QUICK = ('Quick search: the solver stopped as soon as it knew this set is within %s%% of the best '
         'on your criteria. A better set may exist, so this is not a proof.')
OG_QUICK = 'Within %s%% of the best, not a proof.'
NO_GAP = object()


def stopped_within_the_gap(hat, objective, bound):
    return dict(_outcome(hat, objective, bound), finished=True)


def cut_by_the_clock(hat, objective, bound):
    return dict(_outcome(hat, objective, bound), finished=False)


class _GapModel(_StoppedModel):
    """A scripted model that also records the gap each run was given."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gaps = []

    def run(self, retries, warm_start=None, seed=None, gap=NO_GAP):
        self.gaps.append(gap)
        super().run(retries, warm_start, seed)

    def search_finished(self):
        return self.outcome.get('finished', self.outcome['proven'])


class _QuickFlow(_FlowMixin):

    def build_at(self, power):
        char = self.build()
        if power is not None:
            set_options(char, {'power': power})
            char.save()
        return Char.objects.get(pk=char.pk)

    def solve(self, char, *outcomes, overrides=None):
        model = _GapModel(outcomes)
        with self.solver(model, overrides=overrides):
            response = self.client.get('%s/fashion/%d/' % (self.prefix, char.pk))
        self.assertEqual(302, response.status_code)
        char.refresh_from_db()
        return model

    def search_on(self, char, *outcomes, **kwargs):
        model = _GapModel(outcomes)
        with self.solver(model):
            response = self.client.post('%s/continuesearch/%d/' % (self.prefix, char.pk))
        char.refresh_from_db()
        return model, response


class TheStepSetsTheSearchTests(_QuickFlow, TestCase):

    def test_flash_runs_with_its_gap_and_its_seconds(self):
        flash = POWER_BY_KEY['flash']
        model = self.solve(self.build_at('flash'), stopped_within_the_gap(self.hat, 1000.0, 1030.0))
        self.assertEqual([flash.gap], model.gaps)
        self.assertEqual([flash.seconds], model.limits)

    def test_fast_runs_with_its_gap_and_its_seconds(self):
        fast = POWER_BY_KEY['fast']
        model = self.solve(self.build_at('fast'), stopped_within_the_gap(self.hat, 1000.0, 1010.0))
        self.assertEqual([fast.gap], model.gaps)
        self.assertEqual([fast.seconds], model.limits)

    def test_a_build_without_a_step_runs_as_before_with_no_gap(self):
        model = self.solve(self.build_at(None), _outcome(self.hat, 1000.0, proven=True))
        self.assertEqual([NO_GAP], model.gaps)
        self.assertEqual(0, model.inputs[0].gap)

    def test_the_waiting_screen_counts_to_the_budget_of_the_step(self):
        self.assertEqual(95, solve_budget_seconds(self.build_at(None)))
        self.assertEqual(95, solve_budget_seconds(self.build_at('standard')))
        for power in ('flash', 'fast'):
            char = self.build_at(power)
            self.assertEqual(request_budget(POWER_BY_KEY[power], solves_per_search(char)),
                             solve_budget_seconds(char))

    def test_a_stop_within_the_gap_is_remembered_under_the_key_of_the_gap_only(self):
        char = self.build_at('flash')
        self.solve(char, stopped_within_the_gap(self.hat, 1000.0, 1030.0))
        (remembered,) = self.memory.put_inputs
        self.assertEqual(POWER_BY_KEY['flash'].gap, remembered.gap)

    def test_a_flash_search_cut_by_its_seconds_is_not_remembered(self):
        self.solve(self.build_at('flash'), cut_by_the_clock(self.hat, 1000.0, 1200.0))
        self.assertEqual([], self.memory.put_inputs)


class TheBuildPageNeverCallsAQuickSetProvenTests(_QuickFlow, TestCase):

    def test_a_stop_within_the_gap_says_quick_search_with_how_far_and_never_proven(self):
        char = self.build_at('flash')
        self.solve(char, stopped_within_the_gap(self.hat, 1000.0, 1030.0))
        minimal = self.minimal(char)
        self.assertIs(False, minimal.proven)
        self.assertEqual(POWER_BY_KEY['flash'].gap, minimal.tolerance)
        page = self.page(char)
        self.assertIn(QUICK % '3', page)
        self.assertTrue(GAP % '3.0' in page or WIDE_GAP % '3.0' in page)
        self.assertNotIn(PROVEN, page)
        self.assertNotIn('Best set found in', page)
        self.assertIn(BUTTON, page)

    def test_a_flash_search_cut_by_its_seconds_says_it_ran_out_of_time(self):
        char = self.build_at('flash')
        self.solve(char, cut_by_the_clock(self.hat, 1000.0, 1200.0))
        self.assertFalse(hasattr(self.minimal(char), 'tolerance'))
        page = self.page(char)
        self.assertIn(NOT_PROVEN % POWER_BY_KEY['flash'].seconds, page)
        self.assertNotIn('Quick search', page)
        self.assertNotIn(PROVEN, page)

    def test_searching_on_runs_to_a_proof_and_drops_the_quick_search_line(self):
        char = self.build_at('flash')
        self.solve(char, stopped_within_the_gap(self.hat, 1000.0, 1030.0))
        model, response = self.search_on(char, _outcome(self.hat, 1000.0, 1020.0, start=1000.0))
        self.assertEqual(302, response.status_code)
        self.assertEqual([NO_GAP], model.gaps)
        minimal = self.minimal(char)
        self.assertFalse(hasattr(minimal, 'tolerance'))
        page = self.page(char)
        self.assertNotIn('Quick search', page)
        self.assertIn(NOT_PROVEN % (POWER_BY_KEY['flash'].seconds + lpproblem.TIME_LIMIT_SECONDS),
                      page)

    def test_the_share_text_says_quick_search_and_never_proven(self):
        char = self.build_at('flash')
        self.solve(char, stopped_within_the_gap(self.hat, 1000.0, 1030.0))
        request = RequestFactory().get('/')
        request.game_version = self.version
        text = _build_share_text(request, char, get_solution(char))
        self.assertIn(QUICK % '3', text)
        self.assertNotIn(PROVEN, text)
        self.assertNotIn('ran out of time', text)

    def test_the_link_preview_says_how_far_and_not_a_proof(self):
        description = _build_og_description(
            SimpleNamespace(char_class='Cra', level=200, game_version='dofus3'),
            SimpleNamespace(items={}), False, '3')
        self.assertEqual('Cra lvl 200, Dofus 3. ' + OG_QUICK % '3', description)
