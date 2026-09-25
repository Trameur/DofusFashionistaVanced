# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each way a build leaves the site counts once per visitor and build per 30 minutes, and the admin Exports section shows the shares."""

import datetime
import importlib
import pickle
import time
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, OperationalError, transaction
from django.test import (SimpleTestCase, TestCase, TransactionTestCase,
                         override_settings)
from django.utils import timezone

from chardata import (admin_stats, dofusbook_export, dofusbook_export_view,
                      export_count, fashionista_build, text_build_view)
from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, ExportHit
from chardata.tests_an_exported_build_comes_back_the_same import (_example_items,
                                                                  _per_slot)
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

ALL_SITES = ('dofusbook', 'dofus-stuffer', 'dofuscreator')


def _rows():
    return sorted((row.destination, row.host, row.game_version, row.count)
                  for row in ExportHit.objects.all())


def _known_to_them(game_version, grouped, opener=None):
    return [{'official': ankama} for group in grouped for ankama in group]


def _prefix(game):
    return '' if game == 'dofus3' else '/' + game


class _ExportFixture:

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('exporter', 'ex@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)
        self.char = self._char()
        catalogue = mock.patch.object(dofusbook_export, 'stuffer_items',
                                      side_effect=_known_to_them)
        catalogue.start()
        self.addCleanup(catalogue.stop)

    def _char(self, game='dofus3', shared=True):
        structure = get_structure(game)
        return Char.objects.create(
            name='Exported', char_name='', char_class='Iop', char_build='', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=pickle.dumps({}),
            options=b'', inclusions=b'', exclusions=b'', owner=self.owner,
            link_shared=shared, game_version=game,
            minimal_solution=pickle.dumps(ModelResultMinimal(
                _per_slot(structure, _example_items(game)),
                {'options': {'ap_exo': False, 'mp_exo': False}, 'origin': 'generated',
                 'char_level': 200, 'locked_equips': {},
                 'base_stats_by_attr': {name: 0 for name, _key in STATS_NAMES}}, {})))

    def _json(self, char=None, client=None, agent=BROWSER, method='get'):
        char = char or self.char
        return getattr(client or self.client, method)(
            '%s/export/fashionista/%d/' % (_prefix(char.game_version), char.id),
            HTTP_USER_AGENT=agent)

    def _dofusbook(self, char=None, agent=BROWSER):
        char = char or self.char
        return self.client.get('%s/export/dofusbook/%d/' % (_prefix(char.game_version), char.id),
                               HTTP_USER_AGENT=agent)

    def _pull(self, char=None, agent=BROWSER, address='203.0.113.9', method='get', **headers):
        char = char or self.char
        return getattr(self.client_class(), method)(
            '/api/v1/shared-builds/%s/fashionista-build/' % encode_char_id(char.id),
            HTTP_USER_AGENT=agent, REMOTE_ADDR=address, **headers)


@override_settings(BUILD_SITES_ENABLED=ALL_SITES)
class _Exports(_ExportFixture, TestCase):
    pass


class EachDestinationCountsOncePerVisitorAndBuildTests(_Exports):

    def test_the_json_button_pressed_twice_counts_one_export(self):
        for _ in range(2):
            answer = self._json()
            self.assertEqual('fashionista-build', answer.json()['format'])
        self.assertEqual([('json', '', 'dofus3', 1)], _rows())

    def test_the_dofusbook_page_opened_twice_counts_one_export(self):
        for _ in range(2):
            page = self._dofusbook()
            self.assertEqual(200, page.status_code)
            self.assertIsNotNone(page.context['link'])
            self.assertIsNone(page.context.get('error'))
        self.assertEqual([('dofusbook', '', 'dofus3', 1)], _rows())

    def test_the_api_counts_one_pull_per_calling_address_cached_answers_included(self):
        with mock.patch.object(fashionista_build, 'export_build',
                               wraps=fashionista_build.export_build) as built:
            for address in ('203.0.113.9', '203.0.113.9', '198.51.100.4'):
                self.assertEqual(200, self._pull(address=address).status_code)
        self.assertEqual(1, built.call_count)
        self.assertEqual([('api', '', 'dofus3', 2)], _rows())

    def test_another_visitor_is_a_new_export(self):
        other = self.client_class()
        other.force_login(self.owner)
        self._json()
        self._json(client=other)
        self.assertEqual([('json', '', 'dofus3', 2)], _rows())

    def test_another_build_is_a_new_export(self):
        self._json()
        self._json(char=self._char())
        self.assertEqual([('json', '', 'dofus3', 2)], _rows())

    def test_one_build_sent_to_each_destination_counts_once_in_each(self):
        self._json()
        self._dofusbook()
        self._pull()
        self.assertEqual([('api', '', 'dofus3', 1), ('dofusbook', '', 'dofus3', 1),
                          ('json', '', 'dofus3', 1)], _rows())

    def test_the_same_visitor_counts_again_once_thirty_minutes_have_passed(self):
        start = time.time()
        self._json()
        self._pull()
        with mock.patch('time.time', return_value=start + text_build_view.ATTEMPT_SECONDS - 60):
            self._json()
            self._pull()
        self.assertEqual([('api', '', 'dofus3', 1), ('json', '', 'dofus3', 1)], _rows())
        with mock.patch('time.time', return_value=start + text_build_view.ATTEMPT_SECONDS + 60):
            self._json()
            self._pull()
        self.assertEqual([('api', '', 'dofus3', 2), ('json', '', 'dofus3', 2)], _rows())

    def test_a_pulled_build_counts_in_its_own_game_version(self):
        retro = self._char('retro')
        self.assertEqual(200, self._pull(char=retro).status_code)
        self.assertEqual(200, self._json(char=retro).status_code)
        self.assertEqual([('api', '', 'retro', 1), ('json', '', 'retro', 1)], _rows())


class WhatIsNeverCountedTests(_Exports):

    def test_a_crawler_counts_nothing_anywhere_and_still_gets_the_build(self):
        for agent in ('Mozilla/5.0 (compatible; Googlebot/2.1)',
                      'Mozilla/5.0 (compatible; AhrefsBot/7.0)'):
            with self.subTest(agent=agent):
                self.assertEqual(200, self._json(agent=agent).status_code)
                self.assertEqual(200, self._dofusbook(agent=agent).status_code)
                self.assertEqual(200, self._pull(agent=agent).status_code)
        self.assertEqual([], _rows())

    def test_a_script_or_an_empty_user_agent_exports_nothing_through_the_buttons(self):
        for agent in ('python-requests/2.31.0', ''):
            with self.subTest(agent=agent):
                self.assertEqual(200, self._json(agent=agent).status_code)
                self.assertEqual(200, self._dofusbook(agent=agent).status_code)
        self.assertEqual([], _rows())

    def test_a_server_pulling_with_any_http_library_counts_as_the_site_it_names(self):
        agents = ('node', 'undici', 'Deno/1.46.3', 'Bun/1.1.29', 'Ruby',
                  'Dart/3.5 (dart:io)', 'python-requests/2.31.0', 'axios/1.7.2',
                  'curl/8.9.1', 'okhttp/4.12.0', 'Go-http-client/2.0', '')
        for number, agent in enumerate(agents):
            with self.subTest(agent=agent):
                pulled = self._pull(agent=agent, address='198.51.100.%d' % number,
                                    HTTP_ORIGIN='https://partner-site.com')
                self.assertEqual('fashionista-build', pulled.json()['format'])
        self.assertEqual([('api', 'partner-site.com', 'dofus3', len(agents))], _rows())

    def test_a_dofusbook_page_that_fails_to_render_counts_nothing_and_the_retry_counts(self):
        broken = mock.patch.object(dofusbook_export_view, 'set_response',
                                   side_effect=RuntimeError('the template broke'))
        with broken, self.assertRaises(RuntimeError), \
                self.assertLogs('django.request', level='ERROR'):
            self._dofusbook()
        self.assertEqual([], _rows())
        self.assertEqual(200, self._dofusbook().status_code)
        self.assertEqual([('dofusbook', '', 'dofus3', 1)], _rows())

    def test_a_head_request_counts_nothing(self):
        self._json(method='head')
        self._pull(method='head')
        self.assertEqual([], _rows())

    def test_a_dofusbook_error_page_counts_nothing(self):
        with mock.patch.object(dofusbook_export, 'stuffer_items',
                               side_effect=dofusbook_export.ExportError('unreachable')):
            page = self._dofusbook()
        self.assertEqual(200, page.status_code)
        self.assertContains(page, 'could not be reached')
        self.assertNotIn('link', page.context)
        self.assertEqual([], _rows())

    def test_a_private_or_unreadable_build_pulled_through_the_api_counts_nothing(self):
        private = self._char(shared=False)
        self.assertEqual(404, self._pull(char=private).status_code)
        answer = self.client.get('/api/v1/shared-builds/not-an-id/fashionista-build/',
                                 HTTP_USER_AGENT=BROWSER)
        self.assertEqual(404, answer.status_code)
        self.assertEqual([], _rows())

    def test_a_build_with_no_gear_counts_nothing(self):
        bare = Char.objects.create(
            name='Bare', char_name='', char_class='Iop', char_build='', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=pickle.dumps({}),
            options=b'', inclusions=b'', exclusions=b'', owner=self.owner,
            link_shared=True, game_version='dofus3', minimal_solution=b'')
        self.assertEqual(404, self._json(char=bare).status_code)
        self.assertEqual(404, self._pull(char=bare).status_code)
        self.assertIn('error', self._dofusbook(char=bare).context)
        self.assertEqual([], _rows())


class TheCounterNeverBreaksTheExportTests(_Exports):

    def test_a_database_error_leaves_every_door_working_and_the_next_export_counts(self):
        broken = mock.patch.object(ExportHit.objects, 'filter',
                                   side_effect=OperationalError('the table is gone'))
        with broken, self.assertLogs('chardata.export_count', level='WARNING') as logs:
            answer = self._json()
            page = self._dofusbook()
            pulled = self._pull()
        self.assertEqual('fashionista-build', answer.json()['format'])
        self.assertEqual(200, page.status_code)
        self.assertIsNotNone(page.context['link'])
        self.assertEqual('fashionista-build', pulled.json()['format'])
        self.assertEqual(3, sum('export not counted' in line for line in logs.output))
        self._json()
        self.assertEqual([('json', '', 'dofus3', 1)], _rows())

    def test_a_row_another_request_creates_between_the_update_and_the_insert_ends_at_two(self):
        today = timezone.localdate()
        real_filter = ExportHit.objects.filter
        for host in ('', 'partner.example'):
            ExportHit.objects.all().delete()
            calls = []

            def filter_losing_the_race(*args, **kwargs):
                calls.append(kwargs)
                if len(calls) > 1:
                    return real_filter(*args, **kwargs)
                first = mock.Mock()

                def update(**_changes):
                    ExportHit.objects.create(day=today, destination='api', host=host,
                                             game_version='dofus3', count=1)
                    return 0
                first.update = update
                return first

            with self.subTest(host=host), mock.patch.object(
                    ExportHit.objects, 'filter', side_effect=filter_losing_the_race):
                self.assertTrue(export_count._add(today, 'dofus3', 'api', host))
                self.assertEqual([('api', host, 'dofus3', 2)], _rows())


@override_settings(BUILD_SITES_ENABLED=ALL_SITES)
class OutsideATransactionTheCounterNeverBreaksTheExportTests(_ExportFixture,
                                                            TransactionTestCase):

    def _spy_on_the_transaction(self):
        seen = []
        real = export_count._add_one

        def add_one(*args):
            seen.append(transaction.get_connection().in_atomic_block)
            return real(*args)
        spy = mock.patch.object(export_count, '_add_one', side_effect=add_one)
        spy.start()
        self.addCleanup(spy.stop)
        return seen

    def test_a_database_error_in_autocommit_leaves_every_door_working_and_the_next_export_counts(self):
        seen = self._spy_on_the_transaction()
        broken = mock.patch.object(ExportHit.objects, 'filter',
                                   side_effect=OperationalError('the table is gone'))
        with broken, self.assertLogs('chardata.export_count', level='WARNING') as logs:
            answer = self._json()
            page = self._dofusbook()
            pulled = self._pull()
        self.assertEqual('fashionista-build', answer.json()['format'])
        self.assertEqual(200, page.status_code)
        self.assertIsNotNone(page.context['link'])
        self.assertEqual('fashionista-build', pulled.json()['format'])
        self.assertEqual(3, sum('export not counted' in line for line in logs.output))
        self._json()
        self.assertEqual([('json', '', 'dofus3', 1)], _rows())
        self.assertEqual([False] * 4, seen)

    def test_an_insert_that_hits_the_unique_key_in_autocommit_is_logged_and_the_next_export_counts(self):
        seen = self._spy_on_the_transaction()
        refused = mock.patch.object(ExportHit.objects, 'get_or_create',
                                    side_effect=IntegrityError('duplicate entry'))
        with refused, self.assertLogs('chardata.export_count', level='WARNING') as logs:
            answer = self._json()
        self.assertEqual(200, answer.status_code)
        self.assertEqual('fashionista-build', answer.json()['format'])
        self.assertEqual(1, sum('export not counted' in line for line in logs.output))
        self.assertEqual([], _rows())
        self._json()
        self.assertEqual([('json', '', 'dofus3', 1)], _rows())
        self.assertEqual([False, False], seen)


class TheApiCountsTheCallingSiteTests(_Exports):

    def test_the_origin_domain_is_counted_without_its_subdomains(self):
        self._pull(HTTP_ORIGIN='https://Builds.Other-Site.co.uk')
        self.assertEqual([('api', 'other-site.co.uk', 'dofus3', 1)], _rows())

    def test_a_referer_gives_its_domain_and_never_its_path_query_port_or_the_caller_address(self):
        referer = 'https://someone:secret@www.Example.org:8443/builds/42?owner=me#top'
        self._pull(HTTP_REFERER=referer, address='203.0.113.77')
        self.assertEqual([('api', 'example.org', 'dofus3', 1)], _rows())
        stored = ' '.join('%s %s %s' % (row.destination, row.host, row.game_version)
                          for row in ExportHit.objects.all())
        for piece in ('/', '?', '#', ':', '@', 'builds', '42', 'owner', 'someone',
                      'secret', '8443', '203.0.113.77'):
            self.assertNotIn(piece, stored)

    def test_the_origin_wins_over_the_referer(self):
        self._pull(HTTP_ORIGIN='https://first.net', HTTP_REFERER='https://second.org/x')
        self.assertEqual([('api', 'first.net', 'dofus3', 1)], _rows())

    def test_an_address_with_no_public_name_counts_as_no_site(self):
        for number, headers in enumerate((
                {'HTTP_ORIGIN': 'http://192.168.1.20:8080'},
                {'HTTP_ORIGIN': 'http://[::1]'},
                {'HTTP_ORIGIN': 'null'},
                {'HTTP_REFERER': 'http://localhost:8000/builds/1'},
                {})):
            self._pull(address='198.51.100.%d' % number, **headers)
        self.assertEqual([('api', '', 'dofus3', 5)], _rows())

    def test_past_the_daily_limit_a_new_site_is_counted_as_no_site(self):
        today = timezone.localdate()
        ExportHit.objects.bulk_create(
            ExportHit(day=today, destination='api', host='s%d.com' % i,
                      game_version='dofus3', count=1)
            for i in range(text_build_view.UNKNOWN_SITES_PER_DAY))
        self._pull(HTTP_ORIGIN='https://brand-new.org', address='198.51.100.1')
        self._pull(HTTP_ORIGIN='https://s0.com', address='198.51.100.2')
        self.assertEqual(1, ExportHit.objects.get(host='').count)
        self.assertEqual(2, ExportHit.objects.get(host='s0.com').count)
        self.assertFalse(ExportHit.objects.filter(host='brand-new.org').exists())

    def test_the_daily_limit_counts_sites_not_their_versions_or_the_unnamed_rows(self):
        today = timezone.localdate()
        versions = ('dofus3', 'dofus3beta', 'retro', 'touch', 'dofus2')
        sites = ['s%d.com' % i
                 for i in range(text_build_view.UNKNOWN_SITES_PER_DAY // len(versions))]
        ExportHit.objects.bulk_create(
            ExportHit(day=today, destination='api', host=host, game_version=version,
                      count=1)
            for version in versions for host in sites + [''])
        self._pull(HTTP_ORIGIN='https://brand-new.org')
        self.assertEqual(1, ExportHit.objects.get(host='brand-new.org').count)
        self.assertEqual(1, ExportHit.objects.get(host='', game_version='dofus3').count)

    def test_past_the_daily_limit_a_site_counted_today_in_another_version_keeps_its_name(self):
        today = timezone.localdate()
        ExportHit.objects.bulk_create(
            ExportHit(day=today, destination='api', host='s%d.com' % i,
                      game_version='dofus3', count=1)
            for i in range(text_build_view.UNKNOWN_SITES_PER_DAY))
        self._pull(char=self._char('retro'), HTTP_ORIGIN='https://s0.com')
        self.assertEqual(1, ExportHit.objects.get(host='s0.com', game_version='retro').count)
        self.assertFalse(ExportHit.objects.filter(host='').exists())


class TheExportSectionShowsTheShareOfEachDestinationTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        today = timezone.localdate()
        for destination, host, version, count, day in (
                ('dofusbook', '', 'dofus3', 6, today),
                ('json', '', 'dofus3', 3, today),
                ('api', 'othersite.com', 'dofus3', 2, today),
                ('api', '', 'dofus3', 1, today),
                ('json', '', 'retro', 4, today),
                ('api', 'old.example.com', 'dofus3', 7,
                 today - datetime.timedelta(days=400))):
            ExportHit.objects.create(day=day, destination=destination, host=host,
                                     game_version=version, count=count)

    def _superuser(self):
        user = User.objects.create_user('boss', 'boss@test.local', 'pw-42-solid')
        user.is_superuser = True
        user.save()
        return user

    def test_the_shares_of_one_version_over_thirty_days(self):
        data = admin_stats.exports(admin_stats.resolve_period('30d'), 'dofus3')
        self.assertEqual(12, data['total'])
        self.assertEqual(
            [('DofusBook', 6, 50.0), ('JSON file', 3, 25.0),
             ('Other sites through the API', 3, 25.0)],
            [(r['label'], r['count'], r['share']) for r in data['rows']])
        self.assertEqual([('othersite.com', 2, 66.7), ('No site named', 1, 33.3)],
                         [(r['label'], r['count'], r['share']) for r in data['sites']])

    def test_every_version_and_a_longer_period_bring_the_other_rows_in(self):
        every_version = admin_stats.exports(admin_stats.resolve_period('30d'), None)
        self.assertEqual(16, every_version['total'])
        self.assertEqual(('JSON file', 7),
                         (every_version['rows'][1]['label'], every_version['rows'][1]['count']))
        today = timezone.localdate()
        longer = admin_stats.resolve_period(
            start=(today - datetime.timedelta(days=500)).isoformat(),
            end=today.isoformat())
        two_years = admin_stats.exports(longer, 'dofus3')
        self.assertEqual(19, two_years['total'])
        self.assertEqual('old.example.com', two_years['sites'][0]['label'])

    def test_three_equal_destinations_add_up_to_a_hundred(self):
        ExportHit.objects.all().delete()
        today = timezone.localdate()
        for destination in ('dofusbook', 'json', 'api'):
            ExportHit.objects.create(day=today, destination=destination, host='',
                                     game_version='dofus3', count=1)
        rows = admin_stats.exports(admin_stats.resolve_period('30d'), 'dofus3')['rows']
        self.assertEqual([33.4, 33.3, 33.3], [row['share'] for row in rows])

    def test_a_week_bar_holds_every_export_of_that_week(self):
        ExportHit.objects.all().delete()
        today = timezone.localdate()
        monday = today - datetime.timedelta(days=today.weekday())
        ExportHit.objects.create(day=monday, destination='json', host='',
                                 game_version='dofus3', count=3)
        ExportHit.objects.create(day=today, destination='api', host='a.com',
                                 game_version='dofus3', count=4)
        period = admin_stats.resolve_period('6m')
        bars = dict(admin_stats.exports(period, None)['per_bucket'])
        self.assertEqual(7, bars[monday.strftime('%d/%m')])
        self.assertEqual(7, sum(bars.values()))

    def test_the_tab_prints_the_exports_section_with_one_decimal(self):
        self.client.force_login(self._superuser())
        page = self.client.get('/admin-tools/', {'period': '30d', 'version': 'dofus3'})
        self.assertEqual(200, page.status_code)
        for text in ('>Import and export</button>', 'id="admin-exports"',
                     'Where builds go', 'DofusBook', 'JSON file',
                     'Other sites through the API', '50.0%', '25.0%',
                     'Sites pulling builds through the API', 'othersite.com', '66.7%',
                     'No site named', '33.3%',
                     'new sites past %d in one day' % text_build_view.UNKNOWN_SITES_PER_DAY,
                     'count browsers only', 'does not start with Mozilla/',
                     "other sites' servers alike",
                     'after a worker restart, counts again',
                     'without subdomains, not checked'):
            self.assertContains(page, text)

    def test_a_visitor_or_a_plain_member_gets_a_404_and_no_figure(self):
        page = self.client.get('/admin-tools/')
        self.assertEqual(404, page.status_code)
        self.assertNotContains(page, 'Sites pulling builds', status_code=404)
        plain = User.objects.create_user('plain', 'p@test.local', 'pw-42-solid')
        self.client.force_login(plain)
        page = self.client.get('/admin-tools/')
        self.assertEqual(404, page.status_code)
        self.assertNotContains(page, 'Sites pulling builds', status_code=404)
        self.assertNotContains(page, 'othersite.com', status_code=404)

    def test_an_empty_table_shows_the_empty_state(self):
        ExportHit.objects.all().delete()
        self.client.force_login(self._superuser())
        page = self.client.get('/admin-tools/')
        self.assertContains(page, 'Exports are recorded from the first one after this '
                                  'release, and nothing earlier is backfilled.')
        self.assertNotContains(page, 'Sites pulling builds through the API')


class ADashboardCachedWithoutTheExportSectionIsNeverServedTests(TestCase):

    def test_a_dict_left_under_the_v3_key_is_ignored(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.assertNotEqual('admin_dashboard_v3', admin_stats.CACHE_KEY)
        stale = {'overview': {}, 'imports': {}, 'generated': 'stale'}
        cache.set('admin_dashboard_v3:%s:all' % admin_stats.DEFAULT_PERIOD, stale, 300)
        data = admin_stats.dashboard()
        self.assertIn('exports', data)
        self.assertNotEqual('stale', data['generated'])


class ThePrivacyPageSaysWhatTheExportsCountTests(TestCase):

    SENTENCES = {
        'en': ('/privacy/', (
            'we count, per day and game version, where each export goes',
            'We never keep which build it was or anything that identifies you.')),
        'fr': ('/fr/privacy/', (
            'nous comptons, par jour et par version du jeu, la destination de chaque export',
            'Nous ne gardons jamais le build concerné '
            'ni rien qui permette de vous identifier.')),
        'es': ('/es/privacy/', (
            'contamos, por día y por versión del juego, adónde va cada exportación',
            'Nunca guardamos qué build era ni nada que te identifique.')),
        'pt': ('/pt/privacy/', (
            'contamos, por dia e por versão do jogo, para onde vai cada exportação',
            'Nunca guardamos qual build era nem nada que identifique você.')),
        'de': ('/de/privacy/', (
            'zählen wir pro Tag und Spielversion, wohin jeder Export geht',
            'Wir speichern weder, um welchen Build es ging, noch irgendetwas, '
            'das Sie identifiziert.')),
    }

    def test_each_language_carries_the_sentence(self):
        for lang, (path, sentences) in self.SENTENCES.items():
            page = self.client.get(path, HTTP_ACCEPT_LANGUAGE=lang)
            for sentence in sentences:
                with self.subTest(lang=lang, sentence=sentence):
                    self.assertContains(page, sentence)


class TheMigrationOnlyCreatesTheExportTableTests(SimpleTestCase):

    def test_0048_holds_a_single_create_model_after_0047(self):
        migration = importlib.import_module(
            'chardata.migrations.0048_exporthit').Migration
        self.assertEqual([('chardata', '0047_importsourcehit')], migration.dependencies)
        self.assertEqual(['CreateModel'],
                         [op.__class__.__name__ for op in migration.operations])
        self.assertEqual('ExportHit', migration.operations[0].name)

    def test_the_table_has_no_column_for_a_build_or_a_visitor(self):
        self.assertEqual(['id', 'day', 'destination', 'host', 'game_version', 'count'],
                         [field.name for field in ExportHit._meta.get_fields()])

    def test_the_counter_names_its_three_destinations(self):
        self.assertEqual(('dofusbook', 'json', 'api'),
                         (export_count.DOFUSBOOK, export_count.JSON, export_count.API))
        self.assertEqual(['dofusbook', 'json', 'api'],
                         [key for key, _label in admin_stats.EXPORT_DESTINATIONS])
