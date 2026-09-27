# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A solve stopped on time says how far from the best it may be, and its owner can search on."""
import pickle
import random
import re
from contextlib import contextmanager
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, SimpleTestCase, TestCase
from pulp import LpMaximize

from chardata import fashion_action, presets
from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.models import Char, SolutionGeneration, SolutionMemory
from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.util import shared_build_path
from fashionistapulp import lpproblem
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.lpproblem import LpProblem2, read_best_bound
from fashionistapulp.model import EFFECTIVE_HP_MINIMUM, Model
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

GAP = 'Nearly optimal set: a better one may exist, at most %s%% better on your criteria.'
WIDE_GAP = 'A better set may exist, at most %s%% better on your criteria.'
BUTTON = 'Continue the search'
NOT_PROVEN = 'Best set found in %d seconds.'
PROVEN = 'Proven optimum.'

MAX_LOG = """Cbc0010I After 0 nodes, 1 on tree, -168 best solution, best possible -588.62716 (0.85 seconds)
Cbc0020I Exiting on maximum time
Cbc0005I Partial search - best objective -545 (best possible -588.62716), took 6738 iterations and 280 nodes (1.99 seconds)

Result - Stopped on time limit

Objective value:                545.00000000
Upper bound:                    588.627
Gap:                            -0.07
"""
NEGATED_LOG = """Cbc0045I MIPStart provided solution with cost -545
Cbc0005I Partial search - best objective -550 (best possible -590.91343), took 183022 iterations and 22959 nodes (3.44 seconds)
Result - Stopped on time limit

Objective value:                -550.00000000
Lower bound:                    -590.913
Gap:                            0.07
"""


def _solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


def _hard_problem():
    """A knapsack CBC finds sets for at once but takes far longer than a second to close."""
    draw = random.Random(3)
    problem = LpProblem2()
    for index in range(300):
        problem.setup_variable('x', index, 0, 3)
    problem.init_objective_function()
    for index in range(300):
        problem.add_to_of('x', index, draw.randint(10, 60))
    problem.finish_objective_function()
    for _row in range(80):
        problem.restriction_lt_eq(draw.randint(200, 400),
                                  [(draw.randint(5, 40), 'x', index) for index in range(300)])
    return problem


class CbcLogBoundTests(SimpleTestCase):

    def test_the_final_line_of_a_maximised_run_gives_the_bound(self):
        self.assertAlmostEqual(588.62716, read_best_bound(MAX_LOG, 545.0))

    def test_a_run_minimising_the_negated_objective_gives_the_same_kind_of_bound(self):
        self.assertAlmostEqual(590.91343, read_best_bound(NEGATED_LOG, 550.0))

    def test_the_summary_serves_when_the_final_line_is_missing(self):
        summary = MAX_LOG.split('Cbc0005I')[0] + MAX_LOG.split('Result')[1]
        self.assertAlmostEqual(588.627, read_best_bound(summary, 545.0))

    def test_a_log_without_a_bound_gives_none(self):
        self.assertIsNone(read_best_bound('Result - Stopped on time limit\n', 545.0))

    def test_a_bound_below_the_set_is_not_believed(self):
        self.assertIsNone(read_best_bound(MAX_LOG, 700.0))


class ATimedOutRunReportsItsBoundTests(SimpleTestCase):

    def setUp(self):
        if not _solver_available():
            self.skipTest('no pulp solver available')

    def test_a_run_cut_by_the_limit_is_not_proven_and_reads_a_bound_above_its_set(self):
        problem = _hard_problem()
        with mock.patch.object(lpproblem.SOLVER, 'timeLimit', 1):
            problem.run()
        state = problem.get_search_state()
        self.assertEqual('Optimal', problem.get_status())
        self.assertFalse(problem.solution_is_proven())
        self.assertIsNotNone(state['objective'])
        self.assertGreater(state['bound'], state['objective'])
        self.assertTrue(state['values'])

    def test_a_warm_run_starts_from_the_set_and_never_ends_below_it(self):
        cold = _hard_problem()
        with mock.patch.object(lpproblem.SOLVER, 'timeLimit', 1):
            cold.run()
        start = cold.get_search_state()
        warm = _hard_problem()
        with mock.patch.object(lpproblem.SOLVER, 'timeLimit', 1):
            warm.run(start['values'])
        state = warm.get_search_state()
        self.assertIs(True, state['start_accepted'])
        self.assertIsNone(start['start_accepted'])
        self.assertAlmostEqual(start['objective'], state['start_objective'])
        self.assertGreaterEqual(state['objective'], start['objective'])
        self.assertEqual(LpMaximize, warm.pulp_lp.sense)
        self.assertGreater(lpproblem.value(warm.pulp_lp.objective), 0)

    def test_a_start_cbc_cannot_use_is_reported(self):
        problem = _hard_problem()
        with mock.patch.object(lpproblem.SOLVER, 'timeLimit', 1):
            problem.run({'x_0': 100})
        self.assertIs(False, problem.get_search_state()['start_accepted'])

    def test_a_proven_run_reads_no_bound(self):
        problem = LpProblem2()
        problem.setup_variable('item', 'x', 0, 10)
        problem.init_objective_function()
        problem.add_to_of('item', 'x', 3)
        problem.finish_objective_function()
        problem.restriction_lt_eq(4, [(1, 'item', 'x')])
        problem.run()
        state = problem.get_search_state()
        self.assertTrue(problem.solution_is_proven())
        self.assertEqual(12, state['objective'])
        self.assertIsNone(state['bound'])
        self.assertIsNone(state['start_objective'])


def _outcome(hat, objective, bound=None, proven=False, start=None):
    return {'hat': hat, 'objective': objective, 'bound': bound, 'proven': proven, 'start': start}


class _StoppedModel(object):
    """Stands in for a model: each run ends on the next scripted outcome."""

    def __init__(self, outcomes, clock=None, build_seconds=0, during=None):
        self.outcomes = list(outcomes)
        self.during = during
        self.inputs = []
        self.warm_starts = []
        self.seeds = []
        self.limits = []
        self.clock = clock
        self.build_seconds = build_seconds

    def built(self, **kwargs):
        if self.clock is not None:
            self.clock.now += self.build_seconds
        return self

    def setup(self, model_input):
        self.input = model_input
        self.inputs.append(model_input)

    def run(self, retries, warm_start=None, seed=None):
        self.seeds.append(seed)
        self.warm_starts.append(warm_start)
        self.limits.append(lpproblem.SOLVER.timeLimit)
        self.outcome = self.outcomes.pop(0)
        if self.during is not None:
            self.during()

    def get_solved_status(self):
        return 'Optimal'

    def solution_is_proven(self):
        return self.outcome['proven']

    def get_candidate_pool(self):
        return {'Hat': 3}

    def get_stats(self):
        return {key: 0 for _name, key in STATS_NAMES}

    def get_result_minimal(self):
        input_ = {'options': self.input.options, 'origin': 'generated',
                  'base_stats_by_attr': dict(self.input.base_stats_by_attr),
                  'char_level': self.input.char_level, 'locked_equips': {}}
        return ModelResultMinimal({'hat': self.outcome['hat']}, input_, self.get_stats())

    def get_search_state(self):
        return {'objective': self.outcome['objective'], 'bound': self.outcome['bound'],
                'start_objective': self.outcome['start'],
                'values': {'x_%d' % self.outcome['hat']: 1.0}}


class _Memory(object):

    def __init__(self, remembered=None):
        self.remembered = remembered
        self.put_inputs = []
        self.offered = []

    def get(self, model_input):
        return self.remembered

    def put(self, model_input, result_tuple):
        self.put_inputs.append(model_input)

    def keep_better(self, model_input, result_tuple, create):
        self.offered.append((model_input, result_tuple, create))


class _Clock(object):

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now


class _FlowMixin(object):
    version = 'dofus3'
    prefix = ''

    def setUp(self):
        set_current_game_version(self.version)
        self.owner = User.objects.create_user('searcher', 'searcher@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)
        hats = [item for item in get_structure(self.version).get_unique_items_by_type_and_level(
            'Hat', 200) if not item.removed]
        self.hat, self.other_hat = hats[0].id, hats[1].id
        self.memory = _Memory()

    def tearDown(self):
        set_current_game_version('dofus3')

    def build(self, priority=None):
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, 'Iop', 200, {'str'}, self.version)
        if priority:
            presets.apply_setup_choices(char, {'str'}, priority=priority, set_minimums=False)
        return char

    @contextmanager
    def solver(self, model, clock=None, overrides=None):
        patches = [mock.patch('chardata.fashion_action.MEMORY', self.memory),
                   mock.patch('chardata.fashion_action.borrow_model', return_value=model),
                   mock.patch('chardata.fashion_action.return_model'),
                   mock.patch('chardata.fashion_action.Model', side_effect=model.built)]
        if clock is not None:
            patches.append(mock.patch('chardata.fashion_action.time', clock))
        if overrides is not None:
            patches.append(mock.patch('chardata.fashion_action.get_effective_stat_overrides',
                                      return_value=overrides))
        for patch in patches:
            patch.start()
        try:
            yield
        finally:
            for patch in reversed(patches):
                patch.stop()

    def solve(self, char, *outcomes, overrides=None):
        model = _StoppedModel(outcomes)
        with self.solver(model, overrides=overrides):
            response = self.client.get('%s/fashion/%d/' % (self.prefix, char.pk))
        self.assertEqual(302, response.status_code)
        char.refresh_from_db()
        return model

    def search_on(self, char, *outcomes, client=None, clock=None, build_seconds=0,
                  overrides=None, during=None):
        model = _StoppedModel(outcomes, clock, build_seconds, during)
        with self.solver(model, clock, overrides):
            response = (client or self.client).post(
                '%s/continuesearch/%d/' % (self.prefix, char.pk))
        char.refresh_from_db()
        return model, response

    def minimal(self, char):
        return read_char_blob(char.minimal_solution, None, 'minimal_solution', char)

    def page(self, char, client=None, path=None):
        response = (client or self.client).get(
            path or '%s/solution/%d/' % (self.prefix, char.pk), HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')

    def form_action(self, page):
        tag = re.search(r'<form[^>]*solver-continue-search[^>]*>', page)
        return re.search(r'action="([^"]+)"', tag.group(0)).group(1) if tag else None


class TheBuildPageOffersToSearchOnTests(_FlowMixin, TestCase):

    def test_a_solve_stopped_on_time_shows_its_gap_and_the_button(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        page = self.page(char)
        self.assertIn(GAP % '5.0', page)
        self.assertIn(BUTTON, page)
        self.assertIn('The search picks up from this set for up to %d more seconds'
                      % lpproblem.TIME_LIMIT_SECONDS, page)
        self.assertEqual('%s/continuesearch/%d/' % (self.prefix, char.pk), self.form_action(page))
        search = self.minimal(char).search
        self.assertEqual((None, None, None),
                         (search['plan'], search['minimum_stats'], search['objective_values']))
        self.assertEqual(fashion_action._unpack_start(search['start']),
                         {'x_%d' % self.hat: 1.0})

    def test_a_proven_solve_shows_nothing_new(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, proven=True))
        self.assertFalse(hasattr(self.minimal(char), 'search'))
        page = self.page(char)
        self.assertIn(PROVEN, page)
        self.assertNotIn(BUTTON, page)
        self.assertNotIn('Nearly optimal set', page)
        self.assertNotIn('A better set may exist', page)
        self.assertIsNone(self.form_action(page))

    def test_a_wide_gap_is_not_called_nearly_optimal(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1200.0))
        page = self.page(char)
        self.assertIn(WIDE_GAP % '20', page)
        self.assertNotIn('Nearly optimal set', page)
        self.assertIn(BUTTON, page)

    def test_a_gap_past_double_the_set_gives_no_percent(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 2500.0))
        page = self.page(char)
        self.assertNotIn('better on your criteria', page)
        self.assertIn(NOT_PROVEN % lpproblem.TIME_LIMIT_SECONDS, page)
        self.assertIn(BUTTON, page)

    def test_a_gap_without_a_bound_is_not_made_up(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0))
        page = self.page(char)
        self.assertNotIn('better on your criteria', page)
        self.assertIn(BUTTON, page)

    def test_a_visitor_of_the_shared_build_reads_the_gap_without_the_button(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        char.link_shared = True
        char.save()
        page = self.page(char, Client(), shared_build_path(char))
        self.assertIn(GAP % '5.0', page)
        self.assertNotIn(BUTTON, page)

    def test_the_button_goes_once_the_build_settings_change(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        weights = get_stats_weights(char, persist=False)
        weights['vit'] = weights.get('vit', 0) + 7
        set_stats_weights(char, weights)
        page = self.page(char)
        self.assertIn(GAP % '5.0', page)
        self.assertNotIn(BUTTON, page)
        model, response = self.search_on(char, _outcome(self.other_hat, 2000.0))
        self.assertEqual(302, response.status_code)
        self.assertEqual([], model.inputs)
        self.assertEqual(self.hat, self.minimal(char).item_per_slot['hat'])

    def test_the_gap_is_rounded_up(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 3000.0, 3000.5))
        self.assertIn(GAP % '0.1', self.page(char))

    def test_the_sentence_speaks_the_page_language(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1004.0))
        expected = {'fr': ('Set presque optimal : il en existe peut-être un meilleur, mais de '
                           '0,4 % au plus selon vos critères.', 'Continuer la recherche',
                           'La recherche repart de ce set pour 90 secondes de plus au maximum'),
                    'es': ('Conjunto casi óptimo: puede que exista uno mejor, pero como mucho '
                           'un 0,4% mejor según sus criterios.', 'Seguir buscando',
                           'durante 90 segundos más como máximo'),
                    'pt': ('Conjunto quase ótimo: pode existir um melhor, mas no máximo 0,4% '
                           'melhor segundo os seus critérios.', 'Continuar a busca',
                           'por até 90 segundos a mais'),
                    'de': ('Fast optimales Set: Ein besseres könnte existieren, wäre nach Ihren '
                           'Kriterien aber höchstens 0,4 % besser.', 'Suche fortsetzen',
                           'höchstens 90 Sekunden weiter')}
        for language, sentences in expected.items():
            with self.subTest(language=language):
                response = self.client.get('/%s%s/solution/%d/' % (language, self.prefix,
                                                                   char.pk))
                self.assertEqual(200, response.status_code)
                page = response.content.decode('utf-8')
                for sentence in sentences:
                    self.assertIn(sentence, page)

    def test_the_wide_gap_speaks_the_page_language(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1200.0))
        expected = {'fr': 'Il existe peut-être un meilleur set, mais de 20 % au plus selon vos '
                          'critères.',
                    'es': 'Puede que exista un conjunto mejor, pero como mucho un 20% mejor según '
                          'sus criterios.',
                    'pt': 'Pode existir um conjunto melhor, mas no máximo 20% melhor segundo os '
                          'seus critérios.',
                    'de': 'Es könnte ein besseres Set geben, das nach Ihren Kriterien aber '
                          'höchstens 20 % besser wäre.'}
        for language, sentence in expected.items():
            with self.subTest(language=language):
                response = self.client.get('/%s%s/solution/%d/' % (language, self.prefix,
                                                                   char.pk))
                self.assertEqual(200, response.status_code)
                self.assertIn(sentence, response.content.decode('utf-8'))


class SearchingOnIsAnOwnersPostTests(_FlowMixin, TestCase):

    def test_a_get_answers_405_and_changes_nothing(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        before = char.minimal_solution
        response = self.client.get('%s/continuesearch/%d/' % (self.prefix, char.pk))
        self.assertEqual(405, response.status_code)
        char.refresh_from_db()
        self.assertEqual(before, char.minimal_solution)

    def test_someone_else_cannot_search_on(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        stranger = Client()
        stranger.force_login(User.objects.create_user('stranger', 's@test.local', 'pw-42-solid'))
        for client in (stranger, Client()):
            with self.subTest(logged_in=client is stranger):
                model, response = self.search_on(char, _outcome(self.other_hat, 2000.0),
                                                 client=client)
                self.assertEqual(403, response.status_code)
                self.assertEqual([], model.inputs)
        self.assertEqual(self.hat, self.minimal(char).item_per_slot['hat'])


class ASearchThatGoesOnKeepsTheBetterSetTests(_FlowMixin, TestCase):

    def test_it_starts_from_the_stored_set_on_the_same_input(self):
        char = self.build()
        first = self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        model, response = self.search_on(char, _outcome(self.hat, 1000.0, 1040.0, start=1000.0))
        self.assertEqual(302, response.status_code)
        self.assertEqual([{'x_%d' % self.hat: 1.0}], model.warm_starts)
        self.assertEqual(first.inputs[0].cache_key(), model.inputs[0].cache_key())

    def test_a_worse_set_found_on_the_way_never_replaces_the_stored_one(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        generations = SolutionGeneration.objects.filter(char=char).count()
        self.search_on(char, _outcome(self.other_hat, 900.0, 1020.0, start=1000.0))
        minimal = self.minimal(char)
        self.assertEqual(self.hat, minimal.item_per_slot['hat'])
        self.assertIs(False, minimal.proven)
        self.assertEqual(1050.0, minimal.search['bound'])
        self.assertEqual(generations, SolutionGeneration.objects.filter(char=char).count())
        self.assertEqual([], self.memory.offered)

    def test_nothing_better_keeps_the_set_tightens_the_gap_and_keeps_the_button(self):
        char = self.build()
        first = self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        generations = SolutionGeneration.objects.filter(char=char).count()
        once, _response = self.search_on(char, _outcome(self.other_hat, 1000.0, 1080.0,
                                                        start=1000.0))
        twice, _response = self.search_on(char, _outcome(self.hat, 1000.0, 1020.0, start=1000.0))
        self.assertEqual([None, None, 2], first.seeds + once.seeds + twice.seeds)
        minimal = self.minimal(char)
        self.assertEqual(self.hat, minimal.item_per_slot['hat'])
        self.assertEqual(1020.0, minimal.search['bound'])
        self.assertEqual(3 * lpproblem.TIME_LIMIT_SECONDS, minimal.search['limit'])
        self.assertEqual(generations, SolutionGeneration.objects.filter(char=char).count())
        page = self.page(char)
        self.assertIn(GAP % '2.0', page)
        self.assertIn(NOT_PROVEN % (3 * lpproblem.TIME_LIMIT_SECONDS), page)
        self.assertIn(BUTTON, page)

    def test_a_better_set_is_kept_with_its_own_gap(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        generations = SolutionGeneration.objects.filter(char=char).count()
        self.search_on(char, _outcome(self.other_hat, 1030.0, 1060.0, start=1000.0))
        minimal = self.minimal(char)
        self.assertEqual(self.other_hat, minimal.item_per_slot['hat'])
        self.assertIs(False, minimal.proven)
        self.assertEqual((1030.0, 1050.0), (minimal.search['objective'], minimal.search['bound']))
        self.assertEqual({'x_%d' % self.other_hat: 1.0},
                         fashion_action._unpack_start(minimal.search['start']))
        self.assertEqual(generations + 1, SolutionGeneration.objects.filter(char=char).count())
        (offered_input, offered, create), = self.memory.offered
        self.assertTrue(create)
        self.assertNotIn('key', offered[2].search)
        page = self.page(char)
        self.assertIn(GAP % '2.0', page)
        self.assertIn(BUTTON, page)

    def test_a_proof_ends_the_search(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        self.search_on(char, _outcome(self.other_hat, 1000.0, proven=True, start=1000.0))
        minimal = self.minimal(char)
        self.assertEqual(self.hat, minimal.item_per_slot['hat'])
        self.assertIs(True, minimal.proven)
        self.assertIsNone(minimal.search)
        page = self.page(char)
        self.assertIn(PROVEN, page)
        self.assertNotIn(BUTTON, page)
        self.assertNotIn('Nearly optimal set', page)

    def test_a_better_set_that_meets_the_bound_is_proven(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        self.search_on(char, _outcome(self.other_hat, 1050.0, 1070.0, start=1000.0))
        minimal = self.minimal(char)
        self.assertEqual(self.other_hat, minimal.item_per_slot['hat'])
        self.assertIs(True, minimal.proven)
        self.assertFalse(getattr(minimal, 'search', None))
        self.assertIn(PROVEN, self.page(char))

    def test_settings_edited_during_the_search_stay_and_so_does_the_set(self):
        char = self.build()
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
        generations = SolutionGeneration.objects.filter(char=char).count()
        vit = get_stats_weights(char, persist=False).get('vit', 0)

        def edit_weights():
            stored = Char.objects.get(pk=char.pk)
            weights = get_stats_weights(stored, persist=False)
            weights['vit'] = vit + 7
            set_stats_weights(stored, weights)
        self.search_on(char, _outcome(self.other_hat, 1030.0, 1040.0, start=1000.0),
                       during=edit_weights)
        self.assertEqual(vit + 7, get_stats_weights(char, persist=False)['vit'])
        self.assertEqual(self.hat, self.minimal(char).item_per_slot['hat'])
        self.assertEqual(generations, SolutionGeneration.objects.filter(char=char).count())

    def test_a_set_saved_during_the_search_is_never_overwritten(self):
        for outcome in (_outcome(self.hat, 1000.0, 1020.0, start=1000.0),
                        _outcome(self.hat, 1030.0, 1040.0, start=1000.0)):
            with self.subTest(objective=outcome['objective']):
                char = self.build()
                self.solve(char, _outcome(self.hat, 1000.0, 1050.0))
                generations = SolutionGeneration.objects.filter(char=char).count()
                other = self.minimal(char)
                other.item_per_slot = {'hat': self.other_hat}
                other.proven, other.search = True, None
                saved = pickle.dumps(other)

                def save_other():
                    Char.objects.filter(pk=char.pk).update(minimal_solution=saved)
                self.search_on(char, outcome, during=save_other)
                self.assertEqual(saved, bytes(char.minimal_solution))
                self.assertEqual(generations,
                                 SolutionGeneration.objects.filter(char=char).count())

    def test_a_search_on_fits_the_budget_of_one_request(self):
        char = self.build()
        overrides = {self.hat: {'Vitality': 1}}
        self.solve(char, _outcome(self.hat, 1000.0, 1050.0), overrides=overrides)
        model, _response = self.search_on(char, _outcome(self.hat, 1000.0, 1040.0, start=1000.0),
                                          clock=_Clock(), build_seconds=30, overrides=overrides)
        self.assertEqual([fashion_action.GUARD_BUDGET_SECONDS - 30], model.limits)
        self.assertEqual(lpproblem.TIME_LIMIT_SECONDS, lpproblem.SOLVER.timeLimit)
        self.assertEqual(lpproblem.TIME_LIMIT_SECONDS + fashion_action.GUARD_BUDGET_SECONDS - 30,
                         self.minimal(char).search['limit'])


class _FirstAnswerMemory(_Memory):

    def get(self, model_input):
        remembered, self.remembered = self.remembered, None
        return remembered


class ARememberedSetIsServedAsItIsTests(_FlowMixin, TestCase):

    def remembered(self, proven, search=None):
        input_ = {'origin': 'generated', 'options': {}, 'locked_equips': {}, 'char_level': 200,
                  'base_stats_by_attr': {}}
        minimal = ModelResultMinimal({'hat': self.hat}, input_,
                                     {key: 0 for _name, key in STATS_NAMES})
        minimal.proven = proven
        if search is not None:
            minimal.search = search
        return ('Optimal', dict(minimal.stats), minimal)

    def test_a_remembered_set_is_served_without_solving_whatever_its_proof(self):
        for remembered in (self.remembered(True), self.remembered(False),
                           self.remembered(False, {'objective': 1.0, 'bound': 2.0,
                                                   'start': fashion_action._pack_start({})})):
            with self.subTest(proven=remembered[2].proven,
                              search=hasattr(remembered[2], 'search')):
                char = self.build()
                self.memory = _Memory(remembered)
                model = self.solve(char)
                self.assertEqual([], model.inputs)
                self.assertEqual([], self.memory.offered)
                self.assertEqual(self.hat, self.minimal(char).item_per_slot['hat'])

    def test_a_guarded_build_takes_a_remembered_stopped_balanced_set_without_solving_it(self):
        plain = self.build()
        self.solve(plain, _outcome(self.hat, 1000.0, 1050.0))
        stopped = self.minimal(plain)
        del stopped.search
        char = self.build('damage')
        self.memory = _FirstAnswerMemory(('Optimal', dict(stopped.stats), stopped))
        model = self.solve(char, _outcome(self.other_hat, 1000.0, 1050.0))
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], model.limits)
        guarded, = model.inputs
        self.assertIn(EFFECTIVE_HP_MINIMUM, guarded.minimum_stats)
        self.assertEqual(self.other_hat, self.minimal(char).item_per_slot['hat'])
        self.assertEqual([], self.memory.offered)


class _Keyed(object):

    def cache_key(self):
        return 4242


class TheMemoryKeepsTheBetterSetTests(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.memory = fashion_action.MEMORY
        self.input = _Keyed()

    def remembered(self):
        stored = read_char_blob(SolutionMemory.objects.get(input_hash=4242).stored, None, 'memo')
        return stored[2]

    def result(self, proven, objective=None):
        minimal = ModelResultMinimal({}, {'origin': 'generated'}, {})
        minimal.proven = proven
        if objective is not None:
            minimal.search = {'objective': objective}
        return ('Optimal', {}, minimal)

    def test_without_a_row_only_a_creation_is_stored(self):
        self.memory.keep_better(self.input, self.result(False, 10.0), False)
        self.assertFalse(SolutionMemory.objects.filter(input_hash=4242).exists())
        self.memory.keep_better(self.input, self.result(False, 10.0), True)
        self.assertEqual(10.0, self.remembered().search['objective'])

    def test_a_higher_score_or_a_proof_replaces_and_nothing_replaces_a_proof(self):
        self.memory.keep_better(self.input, self.result(False, 10.0), True)
        self.memory.keep_better(self.input, self.result(False, 9.0), True)
        self.assertEqual(10.0, self.remembered().search['objective'])
        self.memory.keep_better(self.input, self.result(False, 11.0), True)
        self.assertEqual(11.0, self.remembered().search['objective'])
        self.memory.keep_better(self.input, self.result(True), True)
        self.assertIs(True, self.remembered().proven)
        self.memory.keep_better(self.input, self.result(False, 50.0), True)
        self.assertIs(True, self.remembered().proven)

    def test_a_stopped_row_of_unknown_score_gives_way_to_a_proof_only(self):
        self.memory.keep_better(self.input, self.result(False), True)
        self.memory.keep_better(self.input, self.result(False, 10.0), True)
        self.assertIsNone(getattr(self.remembered(), 'search', None))
        self.memory.keep_better(self.input, self.result(True), True)
        self.assertIs(True, self.remembered().proven)


class AGuardedBuildSearchesOnWithItsSafeguardTests(_FlowMixin, TestCase):

    def test_the_search_goes_on_under_the_floors_it_was_solved_with(self):
        char = self.build('damage')
        first = self.solve(char, _outcome(self.hat, 900.0, proven=True),
                           _outcome(self.hat, 1000.0, 1050.0))
        guarded = first.inputs[1]
        search = self.minimal(char).search
        self.assertEqual(guarded.minimum_stats, search['minimum_stats'])
        self.assertIsNone(search['objective_values'])
        self.assertEqual(presets.guard_plan(char), search['plan'])
        self.assertIn(BUTTON, self.page(char))
        model, _response = self.search_on(
            char, _outcome(self.other_hat, 1030.0, 1040.0, start=1000.0))
        self.assertEqual(guarded.cache_key(), model.inputs[0].cache_key())
        minimal = self.minimal(char)
        self.assertEqual(self.other_hat, minimal.item_per_slot['hat'])
        kept = presets.guard_reading(char, minimal, 'effective_hp')['value']
        self.assertAlmostEqual(kept, minimal.guard['kept'])

    def test_another_safeguard_share_takes_the_button_away(self):
        char = self.build('damage')
        self.solve(char, _outcome(self.hat, 900.0, proven=True),
                   _outcome(self.hat, 1000.0, 1050.0))
        kind, percent = presets.guard_plan(char)
        with mock.patch('chardata.fashion_action.guard_plan', return_value=(kind, percent + 5)):
            self.assertNotIn(BUTTON, self.page(char))

    def test_a_continued_set_that_falls_behind_the_balanced_build_says_so(self):
        char = self.build('damage')
        values = iter([2000.0, 2000.0, 1500.0])
        real = presets.guard_reading

        def reading(char, result, kind):
            got = real(char, result, kind)
            got['value'] = next(values)
            return got
        with mock.patch('chardata.fashion_action.guard_reading', side_effect=reading), \
                mock.patch('chardata.presets._panel_turn', side_effect=[3000.0, 2500.0]):
            self.solve(char, _outcome(self.hat, 900.0, proven=True),
                       _outcome(self.hat, 1000.0, 1050.0))
            facts = self.minimal(char).guard
            self.assertEqual(3000.0, facts['other_balanced'])
            self.assertNotIn('other_kept', facts)
            self.search_on(char, _outcome(self.other_hat, 1030.0, 1040.0, start=1000.0))
        self.assertEqual((1500.0, 2500.0), (self.minimal(char).guard['kept'],
                                            self.minimal(char).guard['other_kept']))
        self.assertIn('This set trails the balanced build on both counts: best turn 2500 '
                      'against 3000, effective HP 1500 against 2000.', self.page(char))


class TouchSearchesOnUnderItsPrefixTests(TheBuildPageOffersToSearchOnTests):
    version = 'touch'
    prefix = '/touch'

    def test_the_sentence_speaks_the_page_language(self):
        """Covered on dofus3; the prefixed pages carry the same catalogue."""

    def test_the_wide_gap_speaks_the_page_language(self):
        """Covered on dofus3; the prefixed pages carry the same catalogue."""


class RetroSearchesOnUnderItsPrefixTests(ASearchThatGoesOnKeepsTheBetterSetTests):
    version = 'retro'
    prefix = '/retro'


class ARealSolveStoppedOnTimeGoesOnTests(TestCase):
    """CBC itself, cut by a limit short enough to stop the build's search before its proof."""
    version = 'dofus3'
    prefix = ''

    def setUp(self):
        if not _solver_available():
            self.skipTest('no pulp solver available')
        set_current_game_version(self.version)
        self.owner = User.objects.create_user('realsearch', 'real@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)

    def tearDown(self):
        set_current_game_version('dofus3')

    def _stopped_build(self):
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, 'Iop', 200, {'str'}, self.version)
        for limit in (3, 2, 5, 1):
            SolutionMemory.objects.all().delete()
            with mock.patch.object(lpproblem.SOLVER, 'timeLimit', limit):
                self.client.get('%s/fashion/%d/' % (self.prefix, char.pk))
            char.refresh_from_db()
            minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
            if getattr(minimal, 'proven', None) is False:
                return char, minimal, limit
        self.skipTest('every limit tried either proved the optimum or found no set')

    def test_a_short_limit_leaves_a_set_with_its_gap_and_the_search_goes_on_from_it(self):
        char, minimal, limit = self._stopped_build()
        before = minimal.search
        self.assertGreaterEqual(before['bound'], before['objective'])
        page = self.page(char)
        self.assertIn(BUTTON, page)
        gap = fashion_action.search_gap(before)
        if gap is not None and gap <= 1:
            self.assertIn('better on your criteria', page)
        states = []
        reader = Model.get_search_state

        def recorded(model):
            state = reader(model)
            states.append(state)
            return state
        with mock.patch.object(lpproblem.SOLVER, 'timeLimit', limit), \
                mock.patch.object(Model, 'get_search_state', autospec=True,
                                  side_effect=recorded):
            response = self.client.post('%s/continuesearch/%d/' % (self.prefix, char.pk))
        self.assertEqual(302, response.status_code)
        state, = states
        self.assertAlmostEqual(before['objective'], state['start_objective'], places=3)
        self.assertGreaterEqual(state['objective'], state['start_objective'] - 1e-6)
        char.refresh_from_db()
        after = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        if not after.proven:
            self.assertGreaterEqual(after.search['objective'], before['objective'])
            self.assertLessEqual(after.search['bound'], before['bound'])

    def page(self, char):
        response = self.client.get('%s/solution/%d/' % (self.prefix, char.pk),
                                   HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')


class ARealTouchSolveStoppedOnTimeGoesOnTests(ARealSolveStoppedOnTimeGoesOnTests):
    version = 'touch'
    prefix = '/touch'
