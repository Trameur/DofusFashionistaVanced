# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The staff page computes only the tab it shows, caches each section on its own, and fills the overview with the estimated months only when it can."""
import datetime
import json
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from chardata import admin_history, admin_stats, admin_tools_view
from chardata.models import BuildComment, Char, CommentReport, SiteSetting

TAB_SECTIONS = {'overview': {'overview'}, 'versions': {'versions'},
                'community': {'community'}, 'pages': {'pages'},
                'imports': {'imports', 'exports'}, 'solver': {'solver'}}


def _snapshot():
    return {
        'schema': 1, 'as_of': '2024-12-31', 'char_id_floor': None,
        'series': {
            'builds_real': [['2023-01', 3, 'E', 1, 5], ['2023-02', 0, 'G', None, None],
                            ['2024-06', 9, 'M', None, None]],
            'accounts_real': [['2023-01', 5, 'E', 2, 8], ['2023-02', 0, 'G', None, None],
                              ['2024-06', 9, 'M', None, None]],
        },
        'eras': [], 'milestones': [], 'methods': [], 'classes': [], 'levels': [],
    }


def _tag(html, attribute):
    """The opening tag that holds the attribute, whatever order the minifier left them in."""
    found = re.search(r'<[a-z]+[^>]*%s[^>]*>' % re.escape(attribute), html)
    return found.group(0) if found else ''


class _Staff(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.boss = User.objects.create_superuser('boss', 'b@x.test', 'pw-42-solid')
        self.client.force_login(self.boss)

    def watched(self):
        """The section functions replaced by mocks that still do the work."""
        return {name: mock.Mock(wraps=function)
                for name, function in admin_stats.SECTIONS.items()}


class AnTabComputesOnlyWhatItShowsTests(_Staff):

    def test_the_history_tab_computes_no_section_and_no_preview_cache(self):
        for url in ('/admin-tools/', '/admin-tools/?tab=history', '/admin-tools/?tab=nonsense',
                    '/admin-tools/?tab=history&fragment=1'):
            with self.subTest(url=url):
                with mock.patch.object(admin_stats, 'section') as section, \
                        mock.patch.object(admin_tools_view, '_preview_cache') as preview, \
                        mock.patch.object(admin_stats, '_builds_in_use') as in_use, \
                        mock.patch.object(admin_stats, '_first_day_on_record') as first_day:
                    page = self.client.get(url)
                self.assertEqual(200, page.status_code)
                self.assertContains(page, 'data-history-url')
                for call in (section, preview, in_use):
                    call.assert_not_called()
                first_day.assert_not_called()

    def test_each_tab_computes_its_own_sections_and_no_other(self):
        for tab, wanted in TAB_SECTIONS.items():
            cache.clear()
            fakes = self.watched()
            with self.subTest(tab=tab), mock.patch.dict(admin_stats.SECTIONS, fakes):
                page = self.client.get('/admin-tools/', {'tab': tab})
                self.assertEqual(200, page.status_code)
                self.assertEqual(wanted, {name for name, fake in fakes.items() if fake.called})

    def test_the_preview_cache_is_read_by_the_overview_only(self):
        for tab, expected in (('overview', 1), ('versions', 0), ('moderation', 0), ('ads', 0)):
            with self.subTest(tab=tab), mock.patch.object(
                    admin_tools_view, '_preview_cache', return_value=None) as preview:
                self.client.get('/admin-tools/', {'tab': tab})
                self.assertEqual(expected, preview.call_count)

    def test_the_community_note_carries_the_day_browsers_started_counting(self):
        html = self.client.get('/admin-tools/?tab=community&fragment=1').content.decode()
        self.assertNotIn('count since ;', html)
        self.assertIn(admin_stats.REAL_BROWSERS_SINCE.strftime('%Y'), html)

    def test_a_refresh_of_the_history_tab_does_not_build_the_payload(self):
        with mock.patch.object(admin_history, 'payload') as payload:
            self.client.get('/admin-tools/?tab=history&fragment=1&refresh=1')
        payload.assert_not_called()

    def test_an_unknown_tab_falls_back_to_history(self):
        page = self.client.get('/admin-tools/?tab=nonsense')
        self.assertContains(page, 'data-history-url')
        self.assertIn('data-loaded="1"', _tag(page.content.decode('utf-8'), 'data-panel="history"'))

    def test_the_shell_holds_an_empty_container_for_each_other_tab(self):
        html = self.client.get('/admin-tools/?tab=pages').content.decode('utf-8')
        for tab in ('history', 'overview', 'versions', 'community', 'imports', 'solver',
                    'moderation', 'ads'):
            with self.subTest(tab=tab):
                self.assertIn('data-loaded="0"', _tag(html, 'data-panel="%s"' % tab))
                self.assertIn('admin-panel-off', _tag(html, 'data-panel="%s"' % tab))
        self.assertIn('data-loaded="1"', _tag(html, 'data-panel="pages"'))
        self.assertNotIn('admin-panel-off', _tag(html, 'data-panel="pages"'))

    def test_a_fragment_is_only_the_panel(self):
        for tab in ('history', 'overview', 'pages', 'imports', 'moderation', 'ads'):
            with self.subTest(tab=tab):
                page = self.client.get('/admin-tools/', {'tab': tab, 'fragment': '1'})
                self.assertEqual(200, page.status_code)
                text = page.content.decode('utf-8')
                self.assertTrue(text.lstrip().startswith('<section'))
                self.assertIn('data-panel="%s"' % tab, text)
                self.assertNotIn('<html', text)
                self.assertNotIn('admin-tabs', text)
                self.assertIn('no-store', page['Cache-Control'])

    def test_the_ads_form_is_on_the_ads_tab(self):
        page = self.client.get('/admin-tools/?tab=ads')
        self.assertContains(page, 'id="admin-ads-form"')
        self.assertContains(page, 'Show ads on the site')
        self.assertNotContains(self.client.get('/admin-tools/?tab=history'), 'id="admin-ads-form"')

    def test_the_moderation_badge_counts_pending_reports_on_every_tab(self):
        author = User.objects.create_user('author', 'a@x.test', 'pw-42-solid')
        build = Char.objects.create(
            name='B', char_name='b', char_class='Iop', char_build='b', level=1,
            minimum_stats=b'', minimum_crits=b'', stats_weight=b'', options=b'',
            inclusions=b'', exclusions=b'', owner=author, link_shared=True)
        comment = BuildComment.objects.create(user=author, build=build, content='text')
        CommentReport.objects.create(user=author, comment=comment, reason='spam')
        for tab in ('history', 'moderation'):
            with self.subTest(tab=tab):
                page = self.client.get('/admin-tools/', {'tab': tab})
                self.assertContains(page, 'Moderation <span class="admin-badge">1</span></button>')

    def test_the_filter_links_carry_the_tab_and_the_tab_buttons_submit_without_script(self):
        period = admin_stats.resolve_period('30d')
        links = admin_stats.filters(period, 'retro', 'pages')
        for link in links['periods'] + links['versions']:
            self.assertIn('tab=pages', link['url'])
        self.assertTrue(links['refresh_url'].endswith('&refresh=1&tab=pages'))
        page = self.client.get('/admin-tools/', {'tab': 'pages', 'period': '30d', 'version': 'retro'})
        self.assertContains(page, 'type="submit"')
        self.assertContains(page, 'name="tab"')
        self.assertIn('method="get"', _tag(page.content.decode('utf-8'), 'id="admin-tabs"'))

    def test_the_filters_are_hidden_on_the_tabs_they_do_not_apply_to(self):
        for tab, hidden in (('history', True), ('moderation', True), ('ads', True),
                            ('overview', False), ('solver', False)):
            with self.subTest(tab=tab):
                html = self.client.get('/admin-tools/', {'tab': tab}).content.decode('utf-8')
                self.assertEqual(hidden, bool(re.search(r'\shidden\b', _tag(html, 'id="admin-filters"'))))

    def test_the_all_time_period_does_not_scan_on_a_tab_without_one(self):
        with mock.patch.object(admin_stats.Char.objects, 'aggregate') as scan:
            page = self.client.get('/admin-tools/', {'tab': 'history', 'period': 'all'})
        self.assertEqual(200, page.status_code)
        scan.assert_not_called()


class ASectionIsComputedOnceThenCachedTests(_Staff):

    def _section(self, name='solver', **kw):
        period = kw.pop('period', None) or admin_stats.resolve_period('30d')
        return admin_stats.section(name, period, kw.pop('version', None), **kw)

    def test_a_second_call_is_served_from_the_cache(self):
        fake = mock.Mock(return_value={'x': 1})
        with mock.patch.dict(admin_stats.SECTIONS, {'solver': fake}):
            first = self._section()
            second = self._section()
        self.assertEqual(1, fake.call_count)
        self.assertEqual(first, second)
        self.assertEqual({'x': 1}, first[0])

    def test_refresh_computes_again_and_stores_the_new_answer(self):
        fake = mock.Mock(side_effect=[{'n': 1}, {'n': 2}, {'n': 3}])
        with mock.patch.dict(admin_stats.SECTIONS, {'solver': fake}):
            self._section()
            self.assertEqual({'n': 2}, self._section(refresh=True)[0])
            self.assertEqual({'n': 2}, self._section()[0])

    def test_a_period_and_a_version_each_get_their_own_key(self):
        fake = mock.Mock(side_effect=lambda period, version: {'v': version, 'p': period.key})
        with mock.patch.dict(admin_stats.SECTIONS, {'solver': fake}):
            self._section()
            self._section(version='retro')
            self._section(period=admin_stats.resolve_period('7d'))
            self._section()
        self.assertEqual(3, fake.call_count)

    def test_a_custom_range_is_never_cached(self):
        fake = mock.Mock(return_value={})
        period = admin_stats.resolve_period(start='2026-03-05', end='2026-03-20')
        with mock.patch.dict(admin_stats.SECTIONS, {'solver': fake}):
            self._section(period=period)
            self._section(period=period)
        self.assertEqual(2, fake.call_count)

    def test_the_whole_dashboard_still_works(self):
        data = admin_stats.dashboard(period_key='30d')
        for key in ('overview', 'versions', 'community', 'pages', 'imports', 'exports',
                    'solver', 'filters', 'generated'):
            self.assertIn(key, data)


class TheOverviewIsFilledWithTheEstimatedMonthsTests(_Staff):

    def setUp(self):
        super().setUp()
        old = User.objects.create_user('old', 'o@x.test', 'pw-42-solid')
        User.objects.filter(pk=old.pk).update(
            date_joined=datetime.datetime(2024, 6, 15, tzinfo=datetime.timezone.utc))
        SiteSetting.objects.update_or_create(
            key=admin_history.KEY, defaults={'value': json.dumps(_snapshot())})
        admin_history.forget()

    def overview(self, **query):
        query.setdefault('tab', 'overview')
        return self.client.get('/admin-tools/', query).content.decode('utf-8')

    def test_all_time_with_no_version_adds_hatched_estimates_to_both_charts(self):
        html = self.overview(period='all')
        self.assertIn('est-accounts-0', html)
        self.assertIn('est-builds-0', html)
        self.assertIn('data-s="estimated or corrected" data-tip="01/23" data-v="5"', html)
        self.assertIn('data-s="estimated or corrected" data-tip="01/23" data-v="3"', html)
        self.assertIn('</i>estimated or corrected</span>', html)
        self.assertIn('Months before the first record are estimates', html)
        self.assertIn('?tab=history', html)

    def test_weekly_or_daily_buckets_get_no_fill(self):
        for unit in ('week', 'day'):
            period = mock.Mock(key='all', custom=False, approximate=False, unit=unit,
                               buckets=[datetime.date(2024, 7, 1)])
            self.assertEqual({}, admin_tools_view._estimated_months(period, None))
        period = mock.Mock(key='all', custom=False, approximate=False, unit='month',
                           buckets=[datetime.date(2024, 7, 1)])
        self.assertIn('builds', admin_tools_view._estimated_months(period, None))

    def test_the_note_carries_no_figure_of_the_history(self):
        html = self.overview(period='all')
        note = html[html.index('Months before the first record'):].split('</p>')[0]
        self.assertFalse(any(ch.isdigit() for ch in note.replace('?tab=history', '')))

    def test_any_other_period_or_a_version_filter_shows_measured_bars_only(self):
        for query in ({'period': '6m'}, {'period': '12m'}, {'period': 'all', 'version': 'retro'},
                      {'from': '2024-01-01', 'to': '2024-12-01'}):
            with self.subTest(query=query):
                html = self.overview(**query)
                self.assertNotIn('est-accounts', html)
                self.assertNotIn('est-builds', html)
                self.assertNotIn('Months before the first record', html)

    def test_without_a_snapshot_the_overview_is_unchanged(self):
        SiteSetting.objects.filter(key=admin_history.KEY).delete()
        admin_history.forget()
        html = self.overview(period='all')
        self.assertNotIn('est-accounts', html)
        self.assertNotIn('Months before the first record', html)
        self.assertIn('data-panel="overview"', html)

    def test_the_tiles_stay_measured(self):
        before = SiteSetting.objects.get(key=admin_history.KEY).value
        tiles = admin_stats.overview(admin_stats.resolve_period('all'), None)['tiles']
        self.assertEqual(4, len(tiles))
        self.assertEqual(before, SiteSetting.objects.get(key=admin_history.KEY).value)
