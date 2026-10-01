# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A solve stopped on time without a set says it proves nothing and offers to search again."""
import pickle
from contextlib import contextmanager
from unittest import mock

from django.test import TestCase
from django.utils import translation
from django.utils.translation import gettext

from chardata import fashion_action
from chardata.char_blobs import read_char_blob
from chardata.models import SolutionMemory
from chardata.tests_a_build_with_no_set_is_shown_its_closest_set import (
    _BuildMixin, _Clock, _ElasticModel, _Memory, _PooledModel)
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal

TIME_SENTENCE = ('The solver ran out of time after %d seconds without finding a set. '
                 'That does not prove that none exists.')
TIME_MSGID = ('The solver ran out of time after %(seconds)s seconds without finding a set. '
              'That does not prove that none exists.')
PROOF_SENTENCE = 'The solver proved that no set meets all of your settings at once.'


class _SeededModel(_PooledModel):
    """A pooled model that records the input it is set up with and the seed of each run."""

    def __init__(self, clock, seconds=2, status='Not Solved', items=()):
        super().__init__(clock, seconds, status)
        self.seeds = []
        self.items = list(items)

    def setup(self, model_input):
        self.input = model_input
        super().setup(model_input)

    def run(self, retries, seed=None):
        self.seeds.append(seed)
        super().run(retries)

    def solution_is_proven(self):
        return self.status == 'Optimal'

    def get_stats(self):
        return {key: 0 for _name, key in STATS_NAMES}

    def get_result_minimal(self):
        return ModelResultMinimal.from_item_id_list(self.items, self.input.get_old_input(),
                                                    self.get_stats())


def _found_runs(count):
    return [(4, 'Optimal'), (3, 'Optimal')] * count


class _StopMixin(_BuildMixin):

    @contextmanager
    def solving(self, pooled, elastic, memory=None):
        with mock.patch('chardata.fashion_action.MEMORY', memory or _Memory(None)), \
                mock.patch('chardata.fashion_action.time', pooled.clock), \
                mock.patch('chardata.fashion_action.Model', side_effect=elastic.built), \
                mock.patch('chardata.fashion_action.borrow_model',
                           return_value=pooled) as borrowed, \
                mock.patch('chardata.fashion_action.return_model'):
            yield borrowed

    def stop(self, char, seconds=30, runs=None, memory=None):
        clock = _Clock()
        pooled = _SeededModel(clock, seconds)
        elastic = _ElasticModel(clock, _found_runs(1) if runs is None else runs, [self.hat.id])
        with self.solving(pooled, elastic, memory):
            response = self.client.get('/fashion/%d/' % char.pk)
        return response, pooled, elastic


class AStopOnTimeIsNotCalledAProofTests(_StopMixin, TestCase):

    def test_the_page_says_the_time_ran_out_and_that_it_proves_nothing(self):
        char = self.build()
        response, _pooled, _elastic = self.stop(char, seconds=30)
        self.assertIn('/infeasible/%d/' % char.pk, response.url)
        page = self.page(char)
        self.assertIn(TIME_SENTENCE % 30, page)
        self.assertNotIn(PROOF_SENTENCE, page)
        self.assertIn('action="/searchagain/%d/"' % char.pk, page)
        self.assertIn('onsubmit="loadingAndRunUnchecked(%d);"'
                      % fashion_action.GUARD_BUDGET_SECONDS, page)

    def test_a_proof_says_so_and_offers_no_search_again(self):
        char = self.build()
        clock = _Clock()
        elastic = _ElasticModel(clock, _found_runs(1), [self.hat.id])
        with self.solving(_SeededModel(clock), elastic, _Memory('Infeasible')) as borrowed:
            self.client.get('/fashion/%d/' % char.pk)
        self.assertEqual(0, borrowed.call_count)
        page = self.page(char)
        self.assertIn(PROOF_SENTENCE, page)
        self.assertNotIn('ran out of time after', page)
        self.assertNotIn('/searchagain/', page)

    def test_a_stop_without_a_set_is_never_remembered(self):
        char = self.build()
        memory = _Memory(None)
        self.stop(char, memory=memory)
        self.assertEqual([], memory.stored)

    def test_the_page_speaks_the_language_of_its_reader(self):
        char = self.build()
        self.stop(char, seconds=30)
        page = self.page(char, 'fr')
        with translation.override('fr'):
            sentence = gettext(TIME_MSGID) % {'seconds': 30}
            button = gettext('Search again')
        self.assertNotEqual(TIME_SENTENCE % 30, sentence)
        self.assertIn(sentence, page)
        self.assertIn(button, page)
        self.assertNotIn('ran out of time after', page)


class NoTimeLeftOffersTheClosestSetLaterTests(_StopMixin, TestCase):

    def test_with_no_time_left_the_page_offers_to_look_for_the_closest_set(self):
        char = self.build()
        _response, _pooled, elastic = self.stop(char, seconds=90, runs=[])
        self.assertEqual([], elastic.calls)
        self.assertEqual('no_time', self.entry(char)['state'])
        page = self.page(char)
        self.assertIn('There was no time left to look for the closest set.', page)
        self.assertIn('action="/closestset/%d/"' % char.pk, page)

    def test_looking_for_it_later_gets_a_budget_of_its_own_and_keeps_the_cause(self):
        char = self.build()
        self.stop(char, seconds=90, runs=[])
        clock = _Clock()
        clock.now = 5000.0
        pooled = _SeededModel(clock)
        elastic = _ElasticModel(clock, _found_runs(1), [self.hat.id])
        with self.solving(pooled, elastic) as borrowed:
            response = self.client.post('/closestset/%d/' % char.pk)
        self.assertEqual(0, borrowed.call_count)
        self.assertIn('/infeasible/%d/' % char.pk, response.url)
        entry = self.entry(char)
        self.assertEqual(('found', 'time', 90), (entry['state'], entry['cause'], entry['seconds']))
        self.assertEqual([fashion_action.CLOSEST_SECONDS,
                          fashion_action.CLOSEST_TIE_BREAK_SECONDS], elastic.limits)
        self.assertLessEqual(clock.now, 5000.0 + fashion_action.GUARD_BUDGET_SECONDS)


class SearchingAgainTakesAnotherPathTests(_StopMixin, TestCase):

    def test_each_search_again_takes_the_next_seed(self):
        char = self.build()
        clock = _Clock()
        pooled = _SeededModel(clock, 2)
        elastic = _ElasticModel(clock, _found_runs(3), [self.hat.id])
        with self.solving(pooled, elastic):
            self.client.get('/fashion/%d/' % char.pk)
            attempts = [self.entry(char)['attempt']]
            for _ in range(2):
                self.client.post('/searchagain/%d/' % char.pk)
                attempts.append(self.entry(char)['attempt'])
        self.assertEqual([None, 1, 2], pooled.seeds)
        self.assertEqual([0, 1, 2], attempts)

    def test_a_search_again_without_a_failure_on_record_starts_at_the_first_seed(self):
        char = self.build()
        clock = _Clock()
        pooled = _SeededModel(clock, 2)
        elastic = _ElasticModel(clock, _found_runs(1), [self.hat.id])
        with self.solving(pooled, elastic):
            self.client.post('/searchagain/%d/' % char.pk)
        self.assertEqual([1], pooled.seeds)


class ARememberedStopWithoutASetIsSolvedAgainTests(_StopMixin, TestCase):

    def remembered_stop(self, char):
        _response, pooled, _elastic = self.stop(char)
        SolutionMemory(input_hash=pooled.input.cache_key(), input=pickle.dumps(pooled.input),
                       stored=pickle.dumps(('Not Solved', None, None))).save()
        return pooled.input.cache_key()

    def test_the_remembered_stop_is_solved_again_and_replaced_by_the_set_found(self):
        char = self.build()
        key = self.remembered_stop(char)
        clock = _Clock()
        pooled = _SeededModel(clock, 2, status='Optimal', items=[self.hat.id])
        elastic = _ElasticModel(clock, [], [])
        with mock.patch('chardata.fashion_action.time', clock), \
                mock.patch('chardata.fashion_action.Model', side_effect=elastic.built), \
                mock.patch('chardata.fashion_action.borrow_model', return_value=pooled), \
                mock.patch('chardata.fashion_action.return_model'):
            response = self.client.get('/fashion/%d/' % char.pk)
        self.assertIn('/solution/%d/' % char.pk, response.url)
        self.assertEqual(['setup', 'run'], pooled.calls)
        stored = read_char_blob(SolutionMemory.objects.get(input_hash=key).stored, None,
                                'memoized solution')
        self.assertEqual('Optimal', stored[0])
        self.assertEqual(self.hat.id, stored[2].item_per_slot.get('hat'))

    def test_a_remembered_stop_proved_infeasible_is_replaced_by_the_proof(self):
        char = self.build()
        key = self.remembered_stop(char)
        clock = _Clock()
        elastic = _ElasticModel(clock, _found_runs(1), [self.hat.id])
        borrowed = []
        for _visit in range(2):
            pooled = _SeededModel(clock, 2, status='Infeasible')
            with mock.patch('chardata.fashion_action.time', clock), \
                    mock.patch('chardata.fashion_action.Model', side_effect=elastic.built), \
                    mock.patch('chardata.fashion_action.borrow_model',
                               return_value=pooled) as borrow, \
                    mock.patch('chardata.fashion_action.return_model'):
                response = self.client.get('/fashion/%d/' % char.pk)
            borrowed.append(borrow.call_count)
            self.assertIn('/infeasible/%d/' % char.pk, response.url)
        self.assertEqual([1, 0], borrowed)
        stored = read_char_blob(SolutionMemory.objects.get(input_hash=key).stored, None,
                                'memoized solution')
        self.assertEqual(('Infeasible', None, None), stored)
        self.assertEqual('proof', self.entry(char)['cause'])

    def test_a_remembered_proof_is_served_without_solving(self):
        char = self.build()
        key = self.remembered_stop(char)
        SolutionMemory.objects.filter(input_hash=key).update(
            stored=pickle.dumps(('Infeasible', None, None)))
        clock = _Clock()
        pooled = _SeededModel(clock, 2)
        elastic = _ElasticModel(clock, _found_runs(1), [self.hat.id])
        with mock.patch('chardata.fashion_action.time', clock), \
                mock.patch('chardata.fashion_action.Model', side_effect=elastic.built), \
                mock.patch('chardata.fashion_action.borrow_model',
                           return_value=pooled) as borrowed, \
                mock.patch('chardata.fashion_action.return_model'):
            self.client.get('/fashion/%d/' % char.pk)
        self.assertEqual(0, borrowed.call_count)
        self.assertEqual('proof', self.entry(char)['cause'])
