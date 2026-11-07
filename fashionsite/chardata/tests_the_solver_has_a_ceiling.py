# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solver holds a limited number of slots, and one client cannot take them all."""
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from chardata import fashion_action, solver_slots
from chardata.coaching_view import create_build
from chardata.models import RateCounter
from chardata.solver_slots import SolverRefused, solver_turn


class _Session(object):
    def __init__(self, session_key):
        self.session_key = session_key


class _Slots(object):

    def setUp(self):
        super().setUp()
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, True)
        override = override_settings(SOLVER_SLOTS=1, SOLVER_SLOT_DIR=self.directory)
        override.enable()
        self.addCleanup(override.disable)
        self.owner = User.objects.create_user('solver', 'solver@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)
        request = RequestFactory().post('/')
        request.user = self.owner
        self.char = create_build(request, 'Iop', 200, {'str'}, 'dofus3')

    def hold_every_slot(self):
        slots = solver_slots.slot_count()
        descriptors = [solver_slots._take_slot(slots) for _slot in range(slots)]
        self.addCleanup(lambda: [solver_slots._release_slot(held)
                                 for held in descriptors if held is not None])
        return descriptors

    def request(self, key='session-a', address='203.0.113.7', user=None):
        request = RequestFactory().get('/', REMOTE_ADDR=address)
        request.user = user or AnonymousUser()
        request.session = _Session(key)
        return request

    def solved(self):
        return mock.patch.object(fashion_action, '_fashion',
                                 return_value=HttpResponseRedirect('/solution/1/'))

    def assert_busy_page(self, response, refreshes, retry_after=None):
        self.assertEqual(429, response.status_code)
        self.assertEqual(str(retry_after or solver_slots.RETRY_AFTER_SECONDS),
                         response['Retry-After'])
        self.assertEqual('no-store', response['Cache-Control'])
        page = response.content.decode('utf-8')
        self.assertIn('noindex', page)
        self.assertEqual(refreshes, 'http-equiv="refresh"' in page)


class TheSlotsAreFreeAgainTests(_Slots, TestCase):

    def assert_a_slot_is_free(self):
        descriptor = solver_slots._take_slot(1)
        self.assertIsNotNone(descriptor)
        solver_slots._release_slot(descriptor)

    def test_a_slot_is_free_again_after_a_solve_that_answers_a_page(self):
        with mock.patch.object(fashion_action, '_fashion',
                               return_value=HttpResponse('the set')):
            self.assertEqual(200, self.client.get('/fashion/%d/' % self.char.pk).status_code)
        self.assert_a_slot_is_free()

    def test_a_slot_is_free_again_after_a_solve_that_redirects(self):
        with self.solved():
            self.assertEqual(302, self.client.get('/fashion/%d/' % self.char.pk).status_code)
        self.assert_a_slot_is_free()

    def test_a_slot_is_free_again_after_a_solve_that_raises(self):
        with mock.patch.object(fashion_action, '_fashion', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.client.get('/fashion/%d/' % self.char.pk)
        self.assert_a_slot_is_free()


class AFullHostAnswersBusyTests(_Slots, TestCase):

    def test_a_get_door_gives_the_busy_page_that_refreshes_itself_and_never_solves(self):
        self.hold_every_slot()
        with self.solved() as solve:
            response = self.client.get('/fashion/%d/' % self.char.pk)
        self.assert_busy_page(response, refreshes=True)
        solve.assert_not_called()
        self.assertIn('href="/fashion/%d/"' % self.char.pk, response.content.decode('utf-8'))

    def test_a_free_slot_runs_the_solve(self):
        with self.solved() as solve:
            response = self.client.get('/fashion/%d/' % self.char.pk)
        self.assertEqual(302, response.status_code)
        solve.assert_called_once()

    def test_a_post_door_gives_the_busy_page_without_a_refresh_and_a_link_to_the_build(self):
        self.hold_every_slot()
        with self.solved() as solve, mock.patch('chardata.closest_set.read_failure',
                                                return_value={}):
            response = self.client.post('/searchagain/%d/' % self.char.pk)
        self.assert_busy_page(response, refreshes=False)
        solve.assert_not_called()
        self.assertIn('href="/solution/%d/"' % self.char.pk, response.content.decode('utf-8'))

    def test_continue_search_gives_the_busy_page_and_does_not_search(self):
        self.hold_every_slot()
        with mock.patch.object(fashion_action, 'continuation_input', return_value=object()), \
                mock.patch.object(fashion_action, 'read_char_blob', return_value=object()), \
                mock.patch.object(fashion_action, '_continue_search') as searched:
            response = self.client.post('/continuesearch/%d/' % self.char.pk)
        self.assert_busy_page(response, refreshes=False)
        searched.assert_not_called()

    def test_continue_search_runs_when_a_slot_is_free(self):
        with mock.patch.object(fashion_action, 'continuation_input', return_value=object()), \
                mock.patch.object(fashion_action, 'read_char_blob', return_value=object()), \
                mock.patch.object(fashion_action, '_continue_search') as searched:
            response = self.client.post('/continuesearch/%d/' % self.char.pk)
        self.assertEqual(302, response.status_code)
        searched.assert_called_once()

    def test_find_closest_set_gives_the_busy_page_and_does_not_search(self):
        self.hold_every_slot()
        with mock.patch('chardata.closest_set.current_input', return_value=object()), \
                mock.patch('chardata.closest_set.read_failure', return_value={'cause': 'time'}), \
                mock.patch.object(fashion_action, '_without_a_set') as searched:
            response = self.client.post('/closestset/%d/' % self.char.pk)
        self.assert_busy_page(response, refreshes=False)
        searched.assert_not_called()

    def test_find_closest_set_runs_when_a_slot_is_free(self):
        with mock.patch('chardata.closest_set.current_input', return_value=object()), \
                mock.patch('chardata.closest_set.read_failure', return_value={'cause': 'time'}), \
                mock.patch.object(fashion_action, '_without_a_set',
                                  return_value=HttpResponse('closest')) as searched:
            response = self.client.post('/closestset/%d/' % self.char.pk)
        self.assertEqual(200, response.status_code)
        searched.assert_called_once()

    def test_a_stranger_gets_a_403_while_every_slot_is_taken(self):
        self.hold_every_slot()
        stranger = User.objects.create_user('stranger', 's@test.local', 'pw-42-solid')
        self.client.force_login(stranger)
        for method, route in (('get', '/fashion/%d/'), ('post', '/continuesearch/%d/'),
                              ('post', '/searchagain/%d/'), ('post', '/closestset/%d/')):
            with self.subTest(route=route):
                response = getattr(self.client, method)(route % self.char.pk)
                self.assertEqual(403, response.status_code)

    def test_a_busy_answer_costs_the_player_nothing(self):
        self.hold_every_slot()
        with self.solved():
            self.client.get('/fashion/%d/' % self.char.pk)
        self.assertFalse(RateCounter.objects.filter(key__startswith='solve-').exists())

    def test_a_busy_answer_is_not_a_server_error(self):
        self.hold_every_slot()
        with self.solved(), self.assertNoLogs('django.request', level='ERROR'):
            self.client.get('/fashion/%d/' % self.char.pk)


class NoSlotCountMeansNoCeilingTests(_Slots, TestCase):

    def test_without_the_setting_or_the_variable_every_solve_runs(self):
        with override_settings(SOLVER_SLOTS=None), \
                mock.patch.dict('os.environ', {}) as environment:
            environment.pop('SOLVER_SLOTS', None)
            self.assertEqual(0, solver_slots.slot_count())
            with self.solved() as solve:
                for _ in range(3):
                    self.assertEqual(302, self.client.get(
                        '/fashion/%d/' % self.char.pk).status_code)
        self.assertEqual(3, solve.call_count)
        self.assertFalse(RateCounter.objects.filter(key__startswith='solve-').exists())

    def test_the_environment_variable_sets_the_count_when_the_setting_is_missing(self):
        with override_settings(SOLVER_SLOTS=None), \
                mock.patch.dict('os.environ', {'SOLVER_SLOTS': '3'}):
            self.assertEqual(3, solver_slots.slot_count())

    def test_a_zero_count_means_no_ceiling(self):
        with override_settings(SOLVER_SLOTS=0), self.solved() as solve:
            self.client.get('/fashion/%d/' % self.char.pk)
        solve.assert_called_once()


class OneClientCannotRunTheSolverWithoutLimitTests(_Slots, TestCase):

    def fill(self, key, count):
        RateCounter.objects.update_or_create(
            key=key, defaults={'count': count, 'window_start': timezone.now()})

    def enter(self, request):
        with solver_turn(request, self.char):
            pass

    def test_a_logged_in_user_is_refused_at_the_limit_and_accepted_below_it(self):
        request = self.request(user=self.owner)
        self.fill('solve-user:%d' % self.owner.pk, solver_slots.SOLVES_PER_CLIENT - 1)
        self.enter(request)
        with self.assertRaises(SolverRefused) as refused:
            self.enter(request)
        self.assertEqual(solver_slots.TOO_MANY, refused.exception.reason)

    def test_an_anonymous_session_is_refused_at_the_limit_and_accepted_below_it(self):
        request = self.request(key='session-b')
        self.fill('solve-session:session-b', solver_slots.SOLVES_PER_CLIENT - 1)
        self.enter(request)
        with self.assertRaises(SolverRefused) as refused:
            self.enter(request)
        self.assertEqual(solver_slots.TOO_MANY, refused.exception.reason)

    def test_an_address_is_refused_at_its_limit_whatever_the_session(self):
        self.fill('solve-address:198.51.100.9', solver_slots.SOLVES_PER_ADDRESS - 1)
        self.enter(self.request(key='one', address='198.51.100.9'))
        with self.assertRaises(SolverRefused):
            self.enter(self.request(key='two', address='198.51.100.9'))

    def test_a_guild_behind_one_address_may_exceed_the_per_client_ceiling(self):
        self.assertGreater(solver_slots.SOLVES_PER_ADDRESS, solver_slots.SOLVES_PER_CLIENT)
        for member in range(solver_slots.SOLVES_PER_CLIENT + 2):
            self.enter(self.request(key='member-%d' % member, address='198.51.100.10'))

    def test_a_request_without_a_session_key_counts_only_its_address(self):
        self.enter(self.request(key=None, address='198.51.100.11'))
        self.assertEqual(['solve-address:198.51.100.11'],
                         list(RateCounter.objects.filter(key__startswith='solve-')
                              .values_list('key', flat=True)))

    def test_a_solve_counts_once_against_each_ceiling(self):
        self.enter(self.request(key='session-c', address='198.51.100.12'))
        counts = dict(RateCounter.objects.filter(key__startswith='solve-')
                      .values_list('key', 'count'))
        self.assertEqual({'solve-session:session-c': 1, 'solve-address:198.51.100.12': 1},
                         counts)

    def test_a_player_over_the_ceiling_gets_the_page_without_a_refresh(self):
        self.fill('solve-user:%d' % self.owner.pk, solver_slots.SOLVES_PER_CLIENT)
        with self.solved() as solve:
            response = self.client.get('/fashion/%d/' % self.char.pk)
        self.assert_busy_page(response, refreshes=False,
                              retry_after=solver_slots.CLIENT_WINDOW)
        self.assertIn('wait a few minutes', response.content.decode('utf-8'))
        solve.assert_not_called()
