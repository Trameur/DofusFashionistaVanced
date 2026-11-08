# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The admin figures leave out anonymous copies nobody touched, page reads from before real browsers were told apart, and direct arrivals of those same days."""
import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from chardata import admin_stats
from chardata.models import Char, PageHit, SupportClick, VisitSource


def _build(name='Hero copy', owner=None, link_shared=False, game_version='dofus3',
           **after_creation):
    build = Char.objects.create(
        name=name, char_name='hero', char_class='Iop', char_build='build', level=200,
        minimum_stats=b'', minimum_crits=b'', stats_weight=b'', options=b'',
        inclusions=b'', exclusions=b'', minimal_solution=b'',
        link_shared=link_shared, owner=owner, game_version=game_version)
    created = build.created_time
    moments = {'modified_time': created}
    for field, seconds in after_creation.items():
        moments[field] = None if seconds is None else created + datetime.timedelta(seconds=seconds)
    Char.objects.filter(pk=build.pk).update(**moments)
    return build


def _counted():
    return admin_stats._builds_in_use().count()


class ACopyNobodyTouchedIsNotInUseTests(TestCase):

    def test_a_copy_as_a_link_leaves_it(self):
        _build()
        self.assertEqual(0, _counted())

    def test_the_writes_of_the_copy_itself_are_not_use(self):
        _build(modified_time=60, solved_time=1, stuff_time=1)
        self.assertEqual(0, _counted())

    def test_a_deleted_build_stays_out(self):
        build = _build(name='Mine')
        Char.objects.filter(pk=build.pk).update(deleted=True)
        self.assertEqual(0, _counted())


class ASignOfUseKeepsTheBuildTests(TestCase):

    def test_an_owner(self):
        _build(owner=User.objects.create_user('o', 'o@x.test', 'pw-42-solid'))
        self.assertEqual(1, _counted())

    def test_a_share(self):
        _build(link_shared=True)
        self.assertEqual(1, _counted())

    def test_a_name_of_its_own(self):
        _build(name='My first Iop')
        self.assertEqual(1, _counted())

    def test_a_save_after_the_copy(self):
        _build(modified_time=61)
        self.assertEqual(1, _counted())

    def test_a_solve_after_the_copy(self):
        _build(solved_time=2)
        self.assertEqual(1, _counted())

    def test_gear_changed_after_the_copy(self):
        _build(stuff_time=2)
        self.assertEqual(1, _counted())

    def test_a_missing_date_cannot_prove_the_copy_untouched(self):
        _build(modified_time=None)
        built = _build()
        Char.objects.filter(pk=built.pk).update(created_time=None)
        self.assertEqual(2, _counted())


class EveryBuildFigureAgreesTests(TestCase):

    def setUp(self):
        self.period = admin_stats.resolve_period('30d')
        for version in admin_stats.VERSIONS:
            _build(game_version=version)
            _build(name='Kept', game_version=version)

    def test_the_created_builds(self):
        tiles = dict(admin_stats.overview(self.period, None)['tiles'])
        self.assertEqual(len(admin_stats.VERSIONS), tiles['Builds created']['recent'])

    def test_the_chart_of_each_version(self):
        chart = admin_stats.overview(self.period, None)['builds_by_version']
        for version in admin_stats.VERSIONS:
            self.assertEqual(1, sum(n for _label, n in chart[version]), version)

    def test_the_table_of_versions(self):
        for row in admin_stats.versions(self.period, None)['rows']:
            self.assertEqual((1, 1), (row['total'], row['new_in_period']), row['slug'])

    def test_the_classes_and_the_levels(self):
        versions = admin_stats.versions(self.period, None)
        for version in admin_stats.VERSIONS:
            self.assertEqual(1, versions['classes'][version][0][1], version)
            self.assertEqual(1, dict(versions['levels'][version])['200'], version)

    def test_the_builds_without_a_solution(self):
        for _label, count in admin_stats.solver(self.period, None)['no_solution']:
            self.assertEqual(1, count, _label)


class OlderPageReadsAreNotMixedInTests(TestCase):

    def setUp(self):
        self.today = timezone.localdate()
        self.since = self.today - datetime.timedelta(days=2)
        since = mock.patch.object(admin_stats, 'REAL_BROWSERS_SINCE', self.since)
        since.start()
        self.addCleanup(since.stop)
        cache.clear()
        PageHit.objects.create(day=self.today, path='/new/', game_version='dofus3', count=3)
        PageHit.objects.create(day=self.since, path='/new/', game_version='retro', count=2)
        PageHit.objects.create(day=self.since - datetime.timedelta(days=1), path='/old/',
                               game_version='dofus3', count=5000)

    def _pages(self, key='30d', version=None):
        return admin_stats.pages(admin_stats.resolve_period(key), version)

    def test_only_rows_from_that_day_on_are_read(self):
        pages = self._pages()
        self.assertEqual([('/new/', 5)], pages['top'])
        self.assertEqual(5, sum(n for _label, n in pages['per_week']))
        self.assertEqual(5, sum(n for _label, n in pages['by_version']))
        self.assertTrue(pages['hides_older_days'])

    def test_the_chart_starts_that_day_so_its_bars_can_be_read(self):
        pages = self._pages('12m')
        self.assertEqual('per day', pages['unit_word'])
        self.assertEqual(3, len(pages['per_week']))

    def test_the_old_rows_stay_in_the_database(self):
        self._pages()
        self.assertTrue(PageHit.objects.filter(path='/old/').exists())

    def test_a_period_after_that_day_hides_nothing(self):
        with mock.patch.object(admin_stats, 'REAL_BROWSERS_SINCE',
                               self.today - datetime.timedelta(days=400)):
            self.assertFalse(self._pages('7d')['hides_older_days'])

    def test_the_version_filter_still_applies(self):
        self.assertEqual([('/new/', 2)], self._pages(version='retro')['top'])

    def test_the_page_says_what_it_hides(self):
        admin = User.objects.create_superuser('boss', 'b@x.test', 'pw-42-solid')
        self.client.force_login(admin)
        html = self.client.get('/admin-tools/').content.decode('utf-8')
        self.assertIn('are not shown', html)
        self.assertIn('anonymous copies nobody touched', html)
        self.assertNotIn('/old/', html)


class OlderArrivalsAreNotMixedInTests(TestCase):

    URL = '/admin-tools/provenance/'

    def setUp(self):
        self.client.force_login(User.objects.create_superuser('boss', 'b@x.test', 'pw-42-solid'))
        today = timezone.localdate()
        since = mock.patch.object(admin_stats, 'REAL_BROWSERS_SINCE', today)
        since.start()
        self.addCleanup(since.stop)
        self.yesterday = today - datetime.timedelta(days=1)

    def _html(self):
        return self.client.get(self.URL).content.decode('utf-8')

    def _periods(self):
        return self.client.get(self.URL).context['periods']

    def test_an_older_direct_arrival_is_hidden(self):
        VisitSource.objects.create(day=self.yesterday, source='direct', medium='none',
                                   language='ko', country='KR', count=98765)
        html = self._html()
        self.assertNotIn('98765', html)
        self.assertNotIn('98,765', html)
        self.assertNotIn('>KR<', html)
        self.assertTrue(VisitSource.objects.filter(count=98765).exists())

    def test_an_older_arrival_with_a_source_is_hidden_too(self):
        VisitSource.objects.create(day=self.yesterday, source='google', medium='organic',
                                   language='fr', country='FR', count=7)
        self.assertEqual([[], []], [period['rows'] for period in self._periods()])
        self.assertTrue(VisitSource.objects.filter(source='google').exists())

    def test_the_support_rate_only_reads_clicks_of_the_same_days(self):
        today = timezone.localdate()
        VisitSource.objects.create(day=today, source='direct', medium='none', count=100)
        SupportClick.objects.create(day=today, language='fr', count=1)
        SupportClick.objects.create(day=self.yesterday, language='fr', count=50)
        self.assertEqual([1.0, 1.0], [period['support_rate'] for period in self._periods()])

    def test_shares_add_up_over_the_same_days(self):
        today = timezone.localdate()
        VisitSource.objects.create(day=today, source='direct', medium='none', count=3)
        VisitSource.objects.create(day=today, source='google', medium='organic', count=1)
        VisitSource.objects.create(day=self.yesterday, source='google', medium='organic', count=900)
        for period in self._periods():
            self.assertEqual({'direct': 75.0, 'google': 25.0},
                             {row['source']: row['share'] for row in period['rows']})

    def test_the_window_is_the_period_once_the_day_is_old_enough(self):
        today = timezone.localdate()
        with mock.patch.object(admin_stats, 'REAL_BROWSERS_SINCE',
                               today - datetime.timedelta(days=400)):
            self.assertEqual([today - datetime.timedelta(days=6), today - datetime.timedelta(days=29)],
                             [period['since'] for period in self._periods()])

    def test_a_direct_arrival_since_that_day_shows(self):
        VisitSource.objects.create(day=timezone.localdate(), source='direct', medium='none',
                                   language='fr', country='FR', count=4)
        self.assertIn('direct', self._html())

    def test_the_page_says_so(self):
        self.assertIn('This page starts on', self._html())
