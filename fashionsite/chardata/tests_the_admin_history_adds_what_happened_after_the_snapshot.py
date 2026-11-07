# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The staff history is a stored snapshot plus the live figures counted after its day, and nothing else reads it."""
import copy
import datetime
import io
import json
import os
import sys
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from chardata import admin_history
from chardata.models import (Char, PageHit, SiteSetting, SolutionMemoryHits)

NOW = datetime.datetime(2025, 5, 15, 12, 0, tzinfo=datetime.timezone.utc)
MILESTONE = 'Fake milestone zzq'


def _at(year, month, day, hour=12):
    return datetime.datetime(year, month, day, hour, 0, tzinfo=datetime.timezone.utc)


def _snapshot():
    return {
        'schema': 1, 'as_of': '2025-03-10', 'char_id_floor': None,
        'series': {
            'builds_real': [['2025-01', 100, 'M', None, None],
                            ['2025-02', 110, 'M', None, None],
                            ['2025-03', 50, 'M', 40, 60]],
            'pages_real': [['2025-01', 1000, 'E', None, None],
                           ['2025-02', 2000, 'E', None, None],
                           ['2025-03', 300, 'E', None, None]],
            'visits': [['2025-01', 2000, 'E', None, None],
                       ['2025-02', 4000, 'E', None, None],
                       ['2025-03', 600, 'E', 500, 700]],
            'ch_organic': [['2025-03', 7, 'E', None, None]],
        },
        'eras': [{'id': 'first', 'name': 'Fake era', 'from': '2025-01', 'to': None,
                  'story': 'Fake story.'}],
        'milestones': [{'id': 1, 'date': '2025-01-02', 'month': '2025-01',
                        'shown': '2 January 2025', 'lane': 'game', 'lane_name': 'Fake lane',
                        'major': False, 'title': MILESTONE, 'detail': 'Fake detail.'}],
        'methods': [{'id': 'm1', 'metric': 'Builds', 'period': '2025', 'status': 'Estimated',
                     'confidence': 'good', 'method': 'Fake method.'}],
        'classes': [{'year': '2025', 'class': 'Fake', 'builds': 1, 'share': 0.5}],
        'levels': [{'year': '2025', 'builds': 3, 'low': 1, 'mid': 1, 'high': 1, 'top': 0}],
    }


def _store(snapshot):
    SiteSetting.objects.update_or_create(
        key=admin_history.KEY, defaults={'value': json.dumps(snapshot)})
    admin_history.forget()


def _char(created, name='Mine', **fields):
    build = Char.objects.create(
        name=name, char_name='hero', char_class='Iop', char_build='build', level=200,
        minimum_stats=b'', minimum_crits=b'', stats_weight=b'', options=b'',
        inclusions=b'', exclusions=b'', minimal_solution=b'',
        owner=fields.pop('owner', None), game_version=fields.pop('game_version', 'dofus3'),
        link_shared=fields.pop('link_shared', False), deleted=fields.pop('deleted', False))
    Char.objects.filter(pk=build.pk).update(created_time=created, modified_time=created)
    return build


def _rows(series, metric):
    return {row[0]: row for row in series[metric]}


class _History(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.snapshot = _snapshot()

    def merged(self):
        return admin_history.merged(self.snapshot, NOW)


class TheLiveFiguresAreAddedAfterTheSnapshotDayTests(_History):

    def test_a_row_after_the_day_raises_the_month_of_the_day_and_keeps_its_range(self):
        _char(_at(2025, 3, 20), owner=User.objects.create_user('u', 'u@x.test', 'pw-42-solid'))
        row = _rows(self.merged(), 'builds_real')['2025-03']
        self.assertEqual(['2025-03', 51, 'M', 41, 61], row)

    def test_a_later_month_is_appended_as_measured_even_when_it_is_empty(self):
        _char(_at(2025, 4, 2))
        rows = _rows(self.merged(), 'builds_real')
        self.assertEqual(['2025-04', 1, 'M', None, None], rows['2025-04'])
        self.assertEqual(['2025-05', 0, 'M', None, None], rows['2025-05'])
        self.assertEqual(['2025-01', '2025-02', '2025-03', '2025-04', '2025-05'],
                         [row[0] for row in self.merged()['builds_real']])

    def test_a_row_dated_on_or_before_the_day_is_not_counted_twice(self):
        _char(_at(2025, 3, 10, hour=23))
        _char(_at(2025, 3, 1))
        self.assertEqual(50, _rows(self.merged(), 'builds_real')['2025-03'][1])
        self.assertEqual({}, admin_history.live_counts(self.snapshot)['builds_real'])

    def test_the_floor_filters_on_the_primary_key(self):
        known = _char(_at(2025, 4, 1))
        new = _char(_at(2025, 4, 2))
        self.snapshot['char_id_floor'] = known.pk
        with CaptureQueriesContext(connection) as queries:
            counts = admin_history.live_counts(self.snapshot)
        self.assertEqual({'2025-04': 1}, counts['builds_real'])
        self.assertTrue(any('"chardata_char"."id" >' in q['sql'] for q in queries.captured_queries))
        self.assertGreater(new.pk, known.pk)

    def test_untouched_copies_and_holes_in_the_ids_are_robots(self):
        _char(_at(2025, 4, 2), name='Hero copy')
        first = _char(_at(2025, 4, 3))
        middle = _char(_at(2025, 4, 4))
        _char(_at(2025, 4, 5))
        Char.objects.filter(pk=middle.pk).delete()
        counts = admin_history.live_counts(self.snapshot)
        self.assertEqual({'2025-04': 2}, counts['builds_real'])
        self.assertEqual({'2025-04': 2}, counts['builds_robots'])
        self.assertLess(first.pk, middle.pk)

    def test_a_deleted_row_still_counts_as_created_and_a_build_counts_per_version(self):
        _char(_at(2025, 4, 2), deleted=True, game_version='retro')
        _char(_at(2025, 4, 3), game_version='dofus3')
        counts = admin_history.live_counts(self.snapshot)
        self.assertEqual({'2025-04': 2}, counts['builds_real'])
        self.assertEqual({'2025-04': 1}, counts['v_retro'])
        self.assertEqual({'2025-04': 1}, counts['v_dofus3'])

    def test_accounts_and_solver_runs_are_counted_by_month(self):
        late = User.objects.create_user('late', 'l@x.test', 'pw-42-solid')
        User.objects.filter(pk=late.pk).update(date_joined=_at(2025, 4, 9))
        early = User.objects.create_user('early', 'e@x.test', 'pw-42-solid')
        User.objects.filter(pk=early.pk).update(date_joined=_at(2025, 3, 9))
        SolutionMemoryHits.objects.create(day=datetime.date(2025, 4, 3), count_hit=3, count_miss=4)
        SolutionMemoryHits.objects.create(day=datetime.date(2025, 3, 10), count_hit=9, count_miss=9)
        counts = admin_history.live_counts(self.snapshot)
        self.assertEqual({'2025-04': 1}, counts['accounts_real'])
        self.assertEqual({'2025-04': 1}, counts['accounts_raw'])
        self.assertEqual({'2025-04': 7}, counts['solver'])

    def test_visits_after_the_day_come_from_the_pages_read_and_the_recent_ratio(self):
        PageHit.objects.create(day=datetime.date(2025, 4, 5), path='/a/', count=10)
        PageHit.objects.create(day=datetime.date(2025, 3, 20), path='/a/', count=5)
        series = self.merged()
        self.assertEqual(305, _rows(series, 'pages_real')['2025-03'][1])
        visits = _rows(series, 'visits')
        self.assertEqual(['2025-03', 610, 'E', 506, 714], visits['2025-03'])
        self.assertEqual(['2025-04', 20, 'E', 12, 28], visits['2025-04'])
        self.assertEqual(['2025-05', 0, 'E', 0, 0], visits['2025-05'])

    def test_a_metric_without_a_live_source_is_left_as_loaded(self):
        self.assertEqual([['2025-03', 7, 'E', None, None]], self.merged()['ch_organic'])

    def test_a_missing_snapshot_is_not_kept_once_one_is_loaded(self):
        first = admin_history.payload()
        self.assertFalse(first['loaded'])
        self.assertIsNone(first['as_of'])
        self.assertEqual({}, first['series'])
        self.assertEqual([], first['eras'])
        SiteSetting.objects.update_or_create(
            key=admin_history.KEY, defaults={'value': json.dumps(_snapshot())})
        self.assertTrue(admin_history.payload()['loaded'])

    def test_a_failed_merge_is_not_kept(self):
        _store(_snapshot())
        with mock.patch.object(admin_history, 'merged', side_effect=RuntimeError('down')):
            self.assertTrue(admin_history.payload()['loaded'])
        with mock.patch.object(admin_history, 'merged', return_value={}) as merged:
            admin_history.payload()
        merged.assert_called_once()

    def test_the_answer_says_which_series_keep_counting(self):
        _store(_snapshot())
        live = admin_history.payload()['live']
        self.assertIn('builds_real', live)
        self.assertIn('visits', live)
        self.assertNotIn('ch_organic', live)
        self.assertNotIn('pages_counted', live)

    def test_the_pages_as_counted_stop_at_the_snapshot(self):
        self.snapshot['series']['pages_counted'] = [['2025-03', 9, 'E', None, None]]
        PageHit.objects.create(day=datetime.date(2025, 4, 5), path='/a/', count=10)
        merged = self.merged()
        self.assertEqual([['2025-03', 9, 'E', None, None]], merged['pages_counted'])
        self.assertEqual(10, _rows(merged, 'pages_real')['2025-04'][1])


class ABadSnapshotNeverRaisesTests(_History):

    def test_nothing_stored_loads_as_none(self):
        self.assertIsNone(admin_history.load())
        self.assertFalse(admin_history.is_loaded())

    def test_unreadable_or_invalid_values_load_as_none(self):
        for value in ('{not json', '[]', 'null', '{"schema": 2}', '', '"text"'):
            with self.subTest(value=value):
                SiteSetting.objects.update_or_create(key=admin_history.KEY,
                                                     defaults={'value': value})
                admin_history.forget()
                self.assertIsNone(admin_history.load())
                self.assertFalse(admin_history.payload(refresh=True)['loaded'])

    def test_a_failing_read_loads_as_none(self):
        with mock.patch.object(SiteSetting.objects, 'filter', side_effect=RuntimeError('down')):
            self.assertIsNone(admin_history.load())

    def test_each_kind_of_damage_is_named(self):
        damaged = {
            'schema': lambda s: s.update(schema=9),
            'as_of': lambda s: s.update(as_of='2025-13-40'),
            'floor': lambda s: s.update(char_id_floor=-1),
            'month': lambda s: s['series']['builds_real'].append(['2025-3', 1, 'M', None, None]),
            'order': lambda s: s['series']['builds_real'].append(['2025-02', 1, 'M', None, None]),
            'status': lambda s: s['series']['builds_real'].append(['2025-04', 1, 'X', None, None]),
            'value': lambda s: s['series']['builds_real'].append(['2025-04', float('nan'), 'M', None, None]),
            'range': lambda s: s['series']['builds_real'].append(['2025-04', 1, 'M', 'a', None]),
            'shape': lambda s: s['series']['builds_real'].append(['2025-04', 1]),
            'no builds': lambda s: s['series'].pop('builds_real'),
            'milestone': lambda s: s['milestones'][0].update(major='no'),
            'era': lambda s: s['eras'][0].update(story=3),
            'list': lambda s: s.update(methods={}),
            'levels': lambda s: s['levels'][0].update(top='1'),
            'huge integer': lambda s: s['series']['builds_real'].append(['2025-04', 10 ** 400, 'M', None, None]),
            'era month': lambda s: s['eras'][0].update(**{'from': 'zz'}),
            'milestone month': lambda s: s['milestones'][0].update(month='y'),
            'future day': lambda s: s.update(as_of='9999-12-31'),
            'ancient day': lambda s: s.update(as_of='1000-01-01'),
        }
        self.assertEqual([], admin_history.validate(self.snapshot))
        for name, damage in damaged.items():
            with self.subTest(name=name):
                snapshot = copy.deepcopy(self.snapshot)
                damage(snapshot)
                self.assertTrue(admin_history.validate(snapshot))
        self.assertTrue(admin_history.validate([]))
        self.assertTrue(admin_history.validate(None))

    def test_the_whole_snapshot_day_after_the_floor_is_counted(self):
        known = _char(_at(2025, 3, 10, hour=1))
        late = _char(_at(2025, 3, 10, hour=20))
        self.snapshot['char_id_floor'] = known.pk
        self.assertEqual({'2025-03': 1}, admin_history.live_counts(self.snapshot)['builds_real'])
        self.assertGreater(late.pk, known.pk)

    def test_the_month_of_the_day_gets_a_zero_row_when_it_was_absent(self):
        self.snapshot['series']['votes'] = [['2025-01', 2, 'M', None, None]]
        rows = _rows(self.merged(), 'votes')
        self.assertEqual(['2025-03', 0, 'M', None, None], rows['2025-03'])

    def test_the_estimated_months_before_a_date_leave_the_measured_ones_out(self):
        self.snapshot['series']['builds_real'] = [
            ['2024-11', 4, 'E', 2, 6], ['2024-12', 0, 'G', None, None],
            ['2025-01', 5, 'M', None, None]]
        _store(self.snapshot)
        rows = admin_history.estimated_before('builds_real', '2025-01')
        self.assertEqual([('2024-11', 4, 'E', 2, 6), ('2024-12', 0, 'G', None, None)], rows)
        self.assertEqual([], admin_history.estimated_before('nothing', '2025-01'))


class TheLoadCommandTests(_History):

    def _file(self, text):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        handle.write(text)
        handle.close()
        self.addCleanup(os.remove, handle.name)
        return handle.name

    def test_a_good_snapshot_is_stored_and_only_its_counts_are_printed(self):
        out = io.StringIO()
        call_command('load_site_history', self._file(json.dumps(self.snapshot)), stdout=out)
        self.assertIn('schema 1', out.getvalue())
        self.assertIn('as_of 2025-03-10', out.getvalue())
        self.assertIn('1 milestones', out.getvalue())
        self.assertNotIn(MILESTONE, out.getvalue())
        self.assertEqual(self.snapshot['as_of'], admin_history.load()['as_of'])

    def test_a_second_load_replaces_the_first(self):
        call_command('load_site_history', self._file(json.dumps(self.snapshot)), stdout=io.StringIO())
        self.snapshot['as_of'] = '2025-03-11'
        call_command('load_site_history', self._file(json.dumps(self.snapshot)), stdout=io.StringIO())
        self.assertEqual(1, SiteSetting.objects.filter(key=admin_history.KEY).count())
        self.assertEqual('2025-03-11', admin_history.load()['as_of'])

    def test_standard_input_works(self):
        data = io.TextIOWrapper(io.BytesIO(json.dumps(self.snapshot).encode('utf-8')))
        with mock.patch.object(sys, 'stdin', data):
            call_command('load_site_history', '-', stdout=io.StringIO())
        self.assertIsNotNone(admin_history.load())

    def test_bad_input_is_refused_with_the_problems_and_nothing_is_written(self):
        self.snapshot['series']['builds_real'][0][2] = 'X'
        with self.assertRaises(CommandError) as raised:
            call_command('load_site_history', self._file(json.dumps(self.snapshot)),
                         stdout=io.StringIO())
        self.assertIn('status', str(raised.exception))
        for text in ('{broken', '[]'):
            with self.assertRaises(CommandError):
                call_command('load_site_history', self._file(text), stdout=io.StringIO())
        with self.assertRaises(CommandError):
            call_command('load_site_history', self._file('x') + '.missing', stdout=io.StringIO())
        self.assertFalse(SiteSetting.objects.filter(key=admin_history.KEY).exists())

    def test_the_size_ceiling_is_two_megabytes(self):
        self.assertEqual(2 * 1024 * 1024, admin_history.MAX_BYTES)
        text = json.dumps(self.snapshot) + ' ' * admin_history.MAX_BYTES
        with self.assertRaises(CommandError) as raised:
            call_command('load_site_history', self._file(text), stdout=io.StringIO())
        self.assertIn('larger', str(raised.exception))


class OnlyStaffReadTheHistoryTests(_History):

    def setUp(self):
        super().setUp()
        _store(self.snapshot)
        self.boss = User.objects.create_superuser('boss', 'b@x.test', 'pw-42-solid')

    def test_a_visitor_and_a_member_get_a_plain_404_everywhere(self):
        member = User.objects.create_user('plain', 'p@x.test', 'pw-42-solid')
        for who in (None, member):
            if who:
                self.client.force_login(who)
            for url in ('/admin-tools/history.json', '/admin-tools/history.json?refresh=1',
                        '/admin-tools/?tab=history&fragment=1', '/admin-tools/?tab=ads&fragment=1',
                        '/admin-tools/?tab=history'):
                with self.subTest(who=who, url=url):
                    page = self.client.get(url)
                    self.assertEqual(404, page.status_code)
                    self.assertNotContains(page, MILESTONE, status_code=404)

    def test_the_json_is_private_and_carries_the_merged_series(self):
        self.client.force_login(self.boss)
        page = self.client.get('/admin-tools/history.json')
        self.assertEqual(200, page.status_code)
        self.assertIn('no-store', page['Cache-Control'])
        self.assertIn('private', page['Cache-Control'])
        data = page.json()
        self.assertTrue(data['loaded'])
        self.assertEqual('2025-03-10', data['as_of'])
        self.assertEqual(MILESTONE, data['milestones'][0]['title'])
        for key in ('now_month', 'series', 'eras', 'methods', 'classes', 'levels', 'generated'):
            self.assertIn(key, data)

    def test_the_json_honours_refresh(self):
        self.client.force_login(self.boss)
        with mock.patch.object(admin_history, 'payload', return_value={'loaded': False}) as payload:
            self.client.get('/admin-tools/history.json')
            self.client.get('/admin-tools/history.json?refresh=1')
        self.assertEqual([mock.call(refresh=False), mock.call(refresh=True)],
                         payload.call_args_list)

    def test_a_damaged_snapshot_gives_a_page_and_a_json_without_error(self):
        SiteSetting.objects.filter(key=admin_history.KEY).update(value='{"schema": 1, "series"')
        admin_history.forget()
        self.client.force_login(self.boss)
        self.assertFalse(self.client.get('/admin-tools/history.json').json()['loaded'])
        page = self.client.get('/admin-tools/')
        self.assertEqual(200, page.status_code)

    def test_nothing_loaded_leaves_a_note_in_the_panel(self):
        SiteSetting.objects.filter(key=admin_history.KEY).delete()
        admin_history.forget()
        self.client.force_login(self.boss)
        page = self.client.get('/admin-tools/')
        self.assertContains(page, 'data-history-url="/admin-tools/history.json"')
        self.assertContains(page, 'No history snapshot is loaded')

    def test_no_public_page_reads_the_setting(self):
        for url in ('/', '/faq/'):
            with self.subTest(url=url):
                page = self.client.get(url)
                self.assertNotContains(page, MILESTONE)
                self.assertNotContains(page, 'Fake story')
