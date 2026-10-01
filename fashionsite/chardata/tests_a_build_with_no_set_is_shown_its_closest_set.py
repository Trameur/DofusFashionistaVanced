# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build no set satisfies is shown the set closest to its minimums, which its owner can keep."""
import pickle
from html.parser import HTMLParser
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import closest_set, fashion_action
from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.min_stats import get_min_stats
from chardata.models import SolutionGeneration
from chardata.util import remove_cache_for_char
from fashionistapulp import lpproblem, model_pool
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

ASKED_VITALITY = 99999


def _solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


class _Clock(object):

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now


class _Memory(object):
    """Answers every solve of the build with status and no set, and records what is stored."""

    def __init__(self, status='Infeasible'):
        self.status = status
        self.stored = []

    def get(self, model_input):
        return None if self.status is None else (self.status, None, None)

    def put(self, model_input, result_tuple):
        self.stored.append(result_tuple)

    def keep_better(self, model_input, result_tuple, create):
        self.stored.append(result_tuple)


class _PooledModel(object):
    """Stands in for a pooled model whose solve ends on status without a set."""

    def __init__(self, clock, seconds=2, status='Infeasible'):
        self.clock = clock
        self.seconds = seconds
        self.status = status
        self.calls = []

    def setup(self, model_input):
        self.calls.append('setup')

    def run(self, retries):
        self.calls.append('run')
        self.clock.now += self.seconds

    def get_solved_status(self):
        return self.status

    def solution_is_proven(self):
        return False

    def get_candidate_pool(self):
        return {}

    def get_search_state(self):
        return {}


class _ElasticModel(object):
    """Stands in for the fresh model of the closest solve: each run takes its seconds and ends on its status."""

    def __init__(self, clock, runs, items, shortfall=0.4, build_seconds=0, proven=True):
        self.clock = clock
        self.runs = list(runs)
        self.items = list(items)
        self.shortfall = shortfall
        self.build_seconds = build_seconds
        self.proven = proven
        self.calls = []
        self.limits = []
        self.warm_starts = []
        self.status = None

    def built(self, **kwargs):
        self.clock.now += self.build_seconds
        return self

    def setup(self, model_input):
        self.input = model_input
        self.calls.append('setup')

    def add_elastic_minimums(self, minimum_stats, level):
        self.calls.append('elastic')
        return [('Vitality', None, minimum_stats.get('Vitality'), 1.0 / ASKED_VITALITY)]

    def minimise_shortfall(self, shortfalls):
        self.calls.append('minimise')

    def hold_shortfall(self, shortfalls, ceiling):
        self.calls.append(('hold', ceiling))

    def run(self, retries, warm_start=None, seed=None):
        seconds, self.status = self.runs.pop(0)
        self.limits.append(lpproblem.SOLVER.timeLimit)
        self.warm_starts.append(warm_start)
        self.clock.now += seconds

    def get_solved_status(self):
        return self.status

    def solution_is_proven(self):
        return self.proven

    def get_shortfall(self, shortfalls):
        return self.shortfall

    def get_stats(self):
        return {key: 0 for _name, key in STATS_NAMES}

    def get_result_minimal(self):
        from fashionistapulp.modelresult import ModelResultMinimal
        return ModelResultMinimal.from_item_id_list(self.items, self.input.get_old_input(),
                                                    self.get_stats())

    def get_candidate_pool(self):
        return {'Hat': 3}

    def get_search_state(self):
        return {'values': {'x_%d' % item_id: 1 for item_id in self.items}}


class _SearchingElasticModel(_ElasticModel):
    """Its tie-break stops on time with an objective and a bound to search on from."""
    OBJECTIVE = 120.0
    BOUND = 150.0

    def get_search_state(self):
        return dict(super().get_search_state(), objective=self.OBJECTIVE, bound=self.BOUND,
                    start_objective=None, start_accepted=True)


class _UnreadMinimumModel(_ElasticModel):
    """Has no solver variable behind a minimum."""

    def add_elastic_minimums(self, minimum_stats, level):
        self.calls.append('elastic')
        raise ValueError('no solver variable behind the minimums Vitality')


class _Rows(HTMLParser):
    """The cells of each shortfall row, and the summary line."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.summary = ''
        self._row = None
        self._cell = None
        self._in_summary = False

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get('class') or '').split()
        if tag == 'tr' and 'infeasible-shortfall-row' in classes:
            self._row = []
        elif tag == 'td' and self._row is not None:
            self._cell = ''
        elif tag == 'p' and 'infeasible-summary' in classes:
            self._in_summary = True

    def handle_endtag(self, tag):
        if tag == 'td' and self._cell is not None:
            self._row.append(self._cell.strip())
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == 'p':
            self._in_summary = False

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data
        if self._in_summary:
            self.summary += data


class _BuildMixin(object):
    version = 'dofus3'

    def setUp(self):
        set_current_game_version(self.version)
        self.owner = User.objects.create_user('closest', 'closest@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)
        structure = get_structure(self.version)
        vitality = structure.get_stat_by_key('vit').id
        hats = structure.get_unique_items_by_type_and_level('Hat', 200)
        self.hat = max(hats, key=lambda item: dict(item.stats).get(vitality, 0))

    def tearDown(self):
        set_current_game_version('dofus3')

    def build(self, minimums=None, char_class='Iop', level=200):
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, char_class, level, {'str'}, self.version)
        asked = dict(get_min_stats(char))
        asked.update(minimums if minimums is not None else {'Vitality': ASKED_VITALITY})
        char.minimum_stats = pickle.dumps(asked)
        char.save()
        return char

    def solve_to_failure(self, char, elastic, memory=None, clock=None, pooled=None):
        clock = clock or elastic.clock
        memory = memory or _Memory()
        with mock.patch('chardata.fashion_action.MEMORY', memory), \
                mock.patch('chardata.fashion_action.time', clock), \
                mock.patch('chardata.fashion_action.Model', side_effect=elastic.built), \
                mock.patch('chardata.fashion_action.borrow_model',
                           return_value=pooled) as borrowed, \
                mock.patch('chardata.fashion_action.return_model') as returned:
            response = self.client.get('/fashion/%d/' % char.pk)
        char.refresh_from_db()
        return response, memory, borrowed, returned

    def ask_for_the_closest_set(self, char, elastic):
        with mock.patch('chardata.fashion_action.MEMORY', _Memory()), \
                mock.patch('chardata.fashion_action.time', elastic.clock), \
                mock.patch('chardata.fashion_action.Model', side_effect=elastic.built):
            return self.client.post('/closestset/%d/' % char.pk)

    def page(self, char, language='en'):
        prefix = '' if language == 'en' else '/' + language
        response = self.client.get('%s/infeasible/%d/' % (prefix, char.pk),
                                   HTTP_ACCEPT_LANGUAGE=language)
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')

    def entry(self, char):
        return self.client.session[closest_set.SESSION_KEY][str(char.pk)]


class TheClosestSetIsShownWithItsShortfallTests(_BuildMixin, TestCase):

    def test_the_shortfall_table_reads_the_totals_of_the_closest_set(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        response, memory, _borrowed, _returned = self.solve_to_failure(char, elastic)
        self.assertIn('/infeasible/', response.url)
        self.assertEqual([], memory.stored)
        entry = self.entry(char)
        self.assertEqual(('found', 'proof'), (entry['state'], entry['cause']))
        self.assertEqual([self.hat.id], entry['items'])

        totals = model_result_from_minimal(self._closest_minimal(char, entry)).get_stats_total()
        parser = _Rows()
        parser.feed(self.page(char))
        by_name = {row[0]: row[1:] for row in parser.rows}
        reached = int(round(totals['vit']))
        self.assertEqual([str(ASKED_VITALITY), str(reached), str(ASKED_VITALITY - reached),
                          str(100 * reached // ASKED_VITALITY)], by_name['Vitality'])
        met = sum(1 for row in parser.rows if row[3] == '0')
        self.assertEqual('%d of %d minimums reached' % (met, len(parser.rows)),
                         ' '.join(parser.summary.split()))
        self.assertLess(met, len(parser.rows))

    def _closest_minimal(self, char, entry):
        from django.contrib.sessions.middleware import SessionMiddleware
        request = RequestFactory().get('/')
        request.user = self.owner
        SessionMiddleware(lambda r: None).process_request(request)
        request.game_version = self.version
        return closest_set.closest_minimal(entry, closest_set.current_input(request, char))

    def test_the_page_names_the_items_of_the_closest_set(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        self.solve_to_failure(char, elastic)
        page = self.page(char)
        self.assertIn('Closest set found', page)
        self.assertIn(self.hat.name, page)
        self.assertIn('/keepclosest/%d/' % char.pk, page)

    def test_the_shortfall_is_minimised_first_then_held_for_the_build_objective(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id],
                                shortfall=0.25)
        self.solve_to_failure(char, elastic)
        self.assertEqual(['setup', 'elastic', 'minimise', ('hold', 0.25)], elastic.calls)
        self.assertIsNone(elastic.warm_starts[0])
        self.assertEqual({'x_%d' % self.hat.id: 1}, elastic.warm_starts[1])
        self.assertEqual(ASKED_VITALITY, elastic.input.minimum_stats['Vitality'])

    def test_the_closest_solve_never_touches_a_pooled_model(self):
        char = self.build()
        clock = _Clock()
        pooled = _PooledModel(clock)
        elastic = _ElasticModel(clock, [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        queues = {version: queue.qsize() for version, queue in model_pool._model_queues.items()}
        _response, _memory, borrowed, returned = self.solve_to_failure(char, elastic, memory=_Memory(None),
                                                           pooled=pooled)
        self.assertEqual(1, borrowed.call_count)
        returned.assert_called_once_with(pooled)
        self.assertEqual(['setup', 'run'], pooled.calls)
        self.assertEqual('found', self.entry(char)['state'])
        self.assertEqual(queues, {version: queue.qsize()
                                  for version, queue in model_pool._model_queues.items()})

    def test_a_proof_with_no_set_is_remembered_and_the_closest_set_is_not(self):
        char = self.build()
        clock = _Clock()
        elastic = _ElasticModel(clock, [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        memory = _Memory(None)
        self.solve_to_failure(char, elastic, memory=memory, pooled=_PooledModel(clock))
        self.assertEqual([('Infeasible', None, None)], memory.stored)


class KeepingTheClosestSetStoresItTests(_BuildMixin, TestCase):

    def keep(self, char):
        return self.client.post('/keepclosest/%d/' % char.pk)

    def test_keeping_stores_the_set_its_stats_and_a_history_entry(self):
        char = self.build()
        char.allow_points_distribution = True
        char.save()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        _response, memory, _borrowed, _returned = self.solve_to_failure(char, elastic)
        before = char.minimal_solution
        generations = SolutionGeneration.objects.filter(char=char).count()
        with mock.patch('chardata.fashion_action.set_stats') as set_stats, \
                mock.patch('chardata.fashion_action.MEMORY', memory):
            response = self.keep(char)
        self.assertEqual(302, response.status_code)
        self.assertIn('/solution/%d/' % char.pk, response.url)
        char.refresh_from_db()
        self.assertNotEqual(bytes(before or b''), bytes(char.minimal_solution))
        kept = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertEqual(self.hat.id, kept.item_per_slot.get('hat'))
        self.assertIsNone(kept.proven)
        self.assertIn('shortfall', kept.closest)
        set_stats.assert_called_once()
        self.assertEqual(generations + 1, SolutionGeneration.objects.filter(char=char).count())
        self.assertEqual([], memory.stored)
        self.assertNotIn(str(char.pk), self.client.session.get(closest_set.SESSION_KEY, {}))

    def test_the_kept_set_shows_its_missed_minimum_in_red_without_a_proof(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        self.solve_to_failure(char, elastic)
        self.keep(char)
        page = self.client.get('/solution/%d/' % char.pk).content.decode('utf-8')
        self.assertIn('Closest set to your minimums: it does not meet all of them.', page)
        self.assertRegex(page, r'solver-why-goal solver-why-goal-missed">Vitality \d+ / %d<'
                         % ASKED_VITALITY)
        self.assertNotIn('Proven optimum.', page)
        self.assertNotIn('Best set found in', page)

    def test_a_kept_set_missing_an_advanced_minimum_names_it(self):
        char = self.build({'Vitality': ASKED_VITALITY,
                           'adv_mins': {'Power + Strength': 50000}})
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        self.solve_to_failure(char, elastic)
        self.keep(char)
        page = self.client.get('/solution/%d/' % char.pk).content.decode('utf-8')
        self.assertRegex(page, r'solver-why-goal-missed">[^<]*\+[^<]* \d+ / 50000<')

    def test_a_stale_set_is_not_kept(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        self.solve_to_failure(char, elastic)
        before = bytes(char.minimal_solution or b'')
        asked = dict(get_min_stats(char), Vitality=ASKED_VITALITY - 1)
        char.minimum_stats = pickle.dumps(asked)
        char.save()
        response = self.keep(char)
        self.assertEqual('/infeasible/%d/?gone=1' % char.pk, response.url)
        char.refresh_from_db()
        self.assertEqual(before, bytes(char.minimal_solution or b''))
        self.assertIn('This set is no longer available', self.page_gone(char))

    def page_gone(self, char):
        return self.client.get('/infeasible/%d/?gone=1' % char.pk).content.decode('utf-8')

    def test_the_new_routes_refuse_a_get_and_a_stranger(self):
        char = self.build()
        stranger = User.objects.create_user('stranger', 's@test.local', 'pw-42-solid')
        for route in ('/keepclosest/%d/', '/searchagain/%d/', '/closestset/%d/'):
            with self.subTest(route=route):
                self.assertEqual(405, self.client.get(route % char.pk).status_code)
        self.client.force_login(stranger)
        for route in ('/keepclosest/%d/', '/searchagain/%d/', '/closestset/%d/'):
            with self.subTest(route=route, who='stranger'):
                self.assertEqual(403, self.client.post(route % char.pk).status_code)


class TheClosestSolveKeepsToTheBudgetTests(_BuildMixin, TestCase):

    def run_with(self, main_seconds, runs, build_seconds, known_build=None):
        clock = _Clock()
        pooled = _PooledModel(clock, main_seconds)
        elastic = _ElasticModel(clock, runs, [self.hat.id], build_seconds=build_seconds)
        known = {} if known_build is None else {self.version: known_build}
        char = self.build()
        with mock.patch.dict(fashion_action._BUILD_SECONDS, known, clear=True):
            self.solve_to_failure(char, elastic, memory=_Memory(None), pooled=pooled)
        return clock, elastic, self.entry(char)

    def test_what_is_left_after_the_failed_solve_and_the_build_is_the_limit(self):
        clock, elastic, entry = self.run_with(80, [(12, 'Optimal')], 3, known_build=3)
        self.assertEqual([12], elastic.limits)
        self.assertEqual('found', entry['state'])
        self.assertLessEqual(clock.now, 1000 + fashion_action.GUARD_BUDGET_SECONDS)

    def test_no_model_is_built_without_the_time_to_build_and_run_it(self):
        clock, elastic, entry = self.run_with(88, [], 3, known_build=3)
        self.assertEqual([], elastic.calls)
        self.assertEqual('no_time', entry['state'])
        self.assertLessEqual(clock.now, 1000 + fashion_action.GUARD_BUDGET_SECONDS)

    def test_the_first_build_of_a_version_is_guessed_before_it_starts(self):
        _clock, elastic, entry = self.run_with(
            fashion_action.GUARD_BUDGET_SECONDS - fashion_action.MIN_SOLVE_SECONDS
            - fashion_action.FIRST_BUILD_SECONDS + 1, [], 3)
        self.assertEqual([], elastic.calls)
        self.assertEqual('no_time', entry['state'])

    def test_a_build_that_eats_the_rest_runs_nothing(self):
        clock, elastic, entry = self.run_with(40, [], 50, known_build=3)
        self.assertEqual(['setup', 'elastic'], elastic.calls)
        self.assertEqual([], elastic.limits)
        self.assertEqual('no_time', entry['state'])
        self.assertLessEqual(clock.now, 1000 + fashion_action.GUARD_BUDGET_SECONDS)

    def test_the_tie_break_runs_only_with_its_least_solve_left(self):
        clock, elastic, entry = self.run_with(20, [(fashion_action.CLOSEST_SECONDS, 'Optimal')],
                                              40, known_build=3)
        self.assertEqual(1, len(elastic.limits))
        self.assertNotIn(('hold', 0.4), elastic.calls)
        self.assertEqual('found', entry['state'])
        self.assertLessEqual(clock.now, 1000 + fashion_action.GUARD_BUDGET_SECONDS)

    def test_both_solves_fit_when_the_failure_was_quick(self):
        clock, elastic, _entry = self.run_with(2, [(30, 'Optimal'), (30, 'Optimal')], 10,
                                               known_build=10)
        self.assertEqual([fashion_action.CLOSEST_SECONDS,
                          fashion_action.CLOSEST_TIE_BREAK_SECONDS], elastic.limits)
        self.assertLessEqual(clock.now, 1000 + fashion_action.GUARD_BUDGET_SECONDS)
        self.assertEqual(lpproblem.TIME_LIMIT_SECONDS, lpproblem.SOLVER.timeLimit)


class AFailureTheLocksCauseNamesTheLocksTests(_BuildMixin, TestCase):

    def test_a_lock_the_class_cannot_wear_is_listed_with_its_reason_and_the_lock_page(self):
        structure = get_structure(self.version)
        other_class = next(item for item in structure.get_available_items_list()
                           if getattr(item, 'classes', ()) and 'Iop' not in item.classes
                           and structure.get_type_name_by_id(item.type) == 'Weapon')
        char = self.build()
        char.inclusions = pickle.dumps({'weapon': other_class.id})
        char.save()
        elastic = _ElasticModel(_Clock(), [(2, 'Infeasible')], [])
        self.solve_to_failure(char, elastic)
        self.assertEqual('locks', self.entry(char)['state'])
        page = self.page(char)
        self.assertIn('Your locked items', page)
        self.assertIn(structure.get_item_name_in_language(other_class, 'en') or other_class.name,
                      page)
        self.assertIn('Still locked, but this build cannot wear it', page)
        self.assertIn('href="/inclusions/%d/"' % char.pk, page)

    def test_without_any_minimum_a_proof_points_at_the_locks_without_solving(self):
        char = self.build()
        char.minimum_stats = pickle.dumps({})
        char.save()
        elastic = _ElasticModel(_Clock(), [], [])
        self.solve_to_failure(char, elastic)
        self.assertEqual([], elastic.calls)
        self.assertEqual(('locks', 'proof'), (self.entry(char)['state'], self.entry(char)['cause']))
        self.assertIn('no set can be built with your options and forbidden items', self.page(char))


class ASetMeetingEveryMinimumAfterAStopIsTheAnswerTests(_BuildMixin, TestCase):

    def test_a_closest_set_with_no_shortfall_after_a_stop_on_time_is_stored(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id],
                                shortfall=0.0, proven=False)
        clock = elastic.clock
        response, memory, _borrowed, _returned = self.solve_to_failure(
            char, elastic, memory=_Memory('Not Solved'),
            pooled=_PooledModel(clock, status='Not Solved'))
        self.assertIn('/solution/%d/' % char.pk, response.url)
        stored = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertEqual(self.hat.id, stored.item_per_slot.get('hat'))
        self.assertIs(False, stored.proven)
        self.assertEqual(fashion_action.CLOSEST_TIE_BREAK_SECONDS, stored.time_limit)
        self.assertFalse(hasattr(stored, 'closest'))
        self.assertEqual([], memory.stored)

    def test_its_search_goes_on_from_where_the_tie_break_stopped(self):
        char = self.build()
        clock = _Clock()
        elastic = _SearchingElasticModel(clock, [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id],
                                         shortfall=0.0, proven=False)
        self.solve_to_failure(char, elastic, memory=_Memory(None),
                              pooled=_PooledModel(clock, status='Not Solved'))
        stored = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertEqual((_SearchingElasticModel.OBJECTIVE, _SearchingElasticModel.BOUND,
                          fashion_action.CLOSEST_TIE_BREAK_SECONDS),
                         (stored.search['objective'], stored.search['bound'],
                          stored.search['limit']))
        page = self.client.get('/solution/%d/' % char.pk).content.decode('utf-8')
        self.assertIn('action="/continuesearch/%d/"' % char.pk, page)

    def test_without_a_tie_break_it_waits_on_the_failure_page_to_be_kept(self):
        char = self.build()
        char.minimum_stats = pickle.dumps({'Vitality': 1})
        char.save()
        before = bytes(char.minimal_solution or b'')
        clock = _Clock()
        elastic = _ElasticModel(clock, [(fashion_action.CLOSEST_SECONDS, 'Optimal')],
                                [self.hat.id], shortfall=0.0, build_seconds=3, proven=False)
        with mock.patch.dict(fashion_action._BUILD_SECONDS, {self.version: 3}, clear=True):
            response, _memory, _borrowed, _returned = self.solve_to_failure(
                char, elastic, memory=_Memory(None),
                pooled=_PooledModel(clock, 55, status='Not Solved'))
        self.assertEqual(1, len(elastic.limits))
        self.assertIn('/infeasible/%d/' % char.pk, response.url)
        self.assertEqual(before, bytes(char.minimal_solution or b''))
        page = self.page(char)
        self.assertIn('This set meets every minimum you asked for.', page)
        self.assertIn('action="/keepclosest/%d/"' % char.pk, page)

    def test_after_a_proof_a_closest_set_is_never_called_the_answer(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id],
                                shortfall=0.0)
        response, _memory, _borrowed, _returned = self.solve_to_failure(char, elastic)
        self.assertIn('/infeasible/', response.url)


class ARealSolveFindsTheClosestSetTests(_BuildMixin, TestCase):

    def test_an_unreachable_vitality_gets_a_set_that_reaches_what_it_can(self):
        if not _solver_available():
            self.skipTest('no pulp solver available')
        char = self.build({'Vitality': ASKED_VITALITY})
        response = self.client.get('/fashion/%d/' % char.pk)
        self.assertIn('/infeasible/', response.url)
        entry = self.entry(char)
        self.assertEqual(('found', 'proof'), (entry['state'], entry['cause']))
        self.assertGreater(entry['shortfall'], 0)
        parser = _Rows()
        parser.feed(self.page(char))
        vitality = {row[0]: row for row in parser.rows}['Vitality']
        self.assertEqual(str(ASKED_VITALITY), vitality[1])
        self.assertGreater(int(vitality[2]), 1000)
        self.assertNotEqual('0', vitality[3])


class ASecondFailureReusesItsClosestSetTests(_BuildMixin, TestCase):

    def test_a_second_failure_on_the_same_settings_builds_no_model(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        self.solve_to_failure(char, elastic)
        self.solve_to_failure(char, elastic)
        self.assertEqual(['setup', 'elastic', 'minimise', ('hold', 0.4)], elastic.calls)
        self.assertEqual(('found', 'proof'), (self.entry(char)['state'], self.entry(char)['cause']))

    def test_a_failure_the_locks_explain_is_not_solved_again(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(2, 'Infeasible')], [])
        self.solve_to_failure(char, elastic)
        self.solve_to_failure(char, elastic)
        self.assertEqual(['setup', 'elastic', 'minimise'], elastic.calls)
        self.assertEqual('locks', self.entry(char)['state'])

    def test_a_failure_left_without_time_is_tried_again(self):
        char = self.build()
        clock = _Clock()
        elastic = _ElasticModel(clock, [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        self.solve_to_failure(char, elastic, memory=_Memory(None), pooled=_PooledModel(clock, 90))
        self.assertEqual(('no_time', []), (self.entry(char)['state'], elastic.calls))
        self.solve_to_failure(char, elastic, memory=_Memory(None), pooled=_PooledModel(clock, 2))
        self.assertEqual('found', self.entry(char)['state'])

    def test_settings_changed_since_are_solved_again(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')] * 2, [self.hat.id])
        self.solve_to_failure(char, elastic)
        char.minimum_stats = pickle.dumps(dict(get_min_stats(char), Vitality=ASKED_VITALITY - 1))
        char.save()
        self.solve_to_failure(char, elastic)
        self.assertEqual(2, elastic.calls.count('elastic'))

    def test_asking_for_the_closest_set_solves_it_again(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')] * 2, [self.hat.id])
        self.solve_to_failure(char, elastic)
        response = self.ask_for_the_closest_set(char, elastic)
        self.assertIn('/infeasible/%d/' % char.pk, response.url)
        self.assertEqual(2, elastic.calls.count('elastic'))


class OnlyAProvenClosestSolveIsCalledTheClosestSetTests(_BuildMixin, TestCase):

    def test_a_closest_solve_stopped_on_time_says_a_closer_set_may_exist(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(fashion_action.CLOSEST_SECONDS, 'Optimal'),
                                           (3, 'Optimal')], [self.hat.id], proven=False)
        self.solve_to_failure(char, elastic)
        self.assertEqual((False, fashion_action.CLOSEST_SECONDS),
                         (self.entry(char)['closest_proven'], self.entry(char)['closest_seconds']))
        page = self.page(char)
        self.assertNotIn('This is the set that comes closest to your minimums', page)
        self.assertIn('This is the closest set to your minimums the solver found in %d seconds'
                      % fashion_action.CLOSEST_SECONDS, page)
        self.assertIn('It ran out of time before it could prove that no set comes closer.', page)

    def test_a_proven_closest_solve_is_called_the_closest_set(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        self.solve_to_failure(char, elastic)
        page = self.page(char)
        self.assertIn('This is the set that comes closest to your minimums', page)
        self.assertNotIn('a closer', page)

    def test_a_kept_set_found_on_time_says_a_closer_one_may_exist(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id],
                                proven=False)
        self.solve_to_failure(char, elastic)
        self.client.post('/keepclosest/%d/' % char.pk)
        char.refresh_from_db()
        kept = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        self.assertEqual({'shortfall': 0.4, 'proven': False, 'limit': fashion_action.CLOSEST_SECONDS},
                         kept.closest)
        page = self.client.get('/solution/%d/' % char.pk).content.decode('utf-8')
        self.assertIn('Closest set to your minimums the solver found before it ran out of time: '
                      'it does not meet all of them, and a closer one may exist.', page)
        self.assertNotIn('Closest set to your minimums: it does not meet all of them.', page)

    def test_a_kept_set_whose_minimums_were_lowered_says_it_meets_them_now(self):
        char = self.build()
        elastic = _ElasticModel(_Clock(), [(4, 'Optimal'), (3, 'Optimal')], [self.hat.id])
        self.solve_to_failure(char, elastic)
        self.client.post('/keepclosest/%d/' % char.pk)
        char.refresh_from_db()
        char.minimum_stats = pickle.dumps({'Vitality': 1})
        char.save()
        remove_cache_for_char(char.pk)
        page = self.client.get('/solution/%d/' % char.pk).content.decode('utf-8')
        self.assertIn('This set was kept from the search for the set closest to your minimums, '
                      'and it meets all of them now.', page)
        self.assertNotIn('it does not meet all of them', page)
        self.assertNotIn('solver-why-goal-missed', page)


class TheFailurePageNeverBreaksOnTheClosestStepTests(_BuildMixin, TestCase):

    def test_locks_that_cannot_be_read_leave_the_generic_line_and_the_lock_page(self):
        char = self.build()
        self.solve_to_failure(char, _ElasticModel(_Clock(), [(2, 'Infeasible')], []))
        with mock.patch('chardata.closest_set.locked_piece_notes',
                        side_effect=RuntimeError('unreadable lock')):
            page = self.page(char)
        self.assertIn('Even without any minimum, no set can be built with your options and '
                      'forbidden items.', page)
        self.assertIn('href="/inclusions/%d/"' % char.pk, page)

    def test_a_minimum_without_a_solver_variable_ends_in_a_failed_search(self):
        char = self.build()
        elastic = _UnreadMinimumModel(_Clock(), [], [self.hat.id])
        self.solve_to_failure(char, elastic)
        self.assertEqual('error', self.entry(char)['state'])
        page = self.page(char)
        self.assertIn('The search for the closest set failed.', page)
        self.assertIn('action="/closestset/%d/"' % char.pk, page)
