# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The import page counts which site a paste comes from, keeps only the site name, and the admin Import tab shows the shares."""

import datetime
import html.parser
import importlib
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.core.signals import got_request_exception
from django.db import IntegrityError, OperationalError, connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.views.debug import SafeExceptionReporterFilter

from chardata import admin_stats, text_build_view
from chardata.dofusbook_import import ImportError_
from chardata.models import Char, ImportSourceHit

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

LINK = 'https://WWW.DofusBook.net/fr/stuff/7894460-zobal-m-200'

ALL_SITES = ('dofusbook', 'dofus-stuffer', 'dofuscreator')


def _rows():
    return sorted((row.source, row.host, row.game_version, row.attempts, row.imported)
                  for row in ImportSourceHit.objects.all())


def _names(count=2):
    from fashionistapulp.structure import get_structure, set_current_game_version
    set_current_game_version('dofus3')
    structure = get_structure('dofus3')
    return [structure.get_item_name_in_language(
                next(item for item in structure.types[200][type_name]
                     if not item.removed and item.ankama_id), 'en')
            for type_name in ('Hat', 'Cloak', 'Belt')[:count]]


class _HiddenInputs(html.parser.HTMLParser):

    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('type') == 'hidden':
            self.values.setdefault(attrs.get('name'), []).append(attrs.get('value'))


def _hidden(page, name):
    parser = _HiddenInputs()
    parser.feed(page.content.decode('utf-8'))
    return parser.values.get(name, [])


class _ImportPage(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _build(self):
        from fashionistapulp.structure import get_structure
        structure = get_structure('dofus3')
        ids = [next(item.id for item in structure.types[200][type_name]
                    if not item.removed)
               for type_name in ('Hat', 'Cloak', 'Belt')]
        return {'game_version': 'dofus3', 'source_host': 'www.dofusbook.net',
                'build_id': '7894460', 'name': 'Zobal M 200', 'level': 200,
                'item_ids': ids, 'missing': [], 'base_points': {},
                'base_scrolled': {}, 'class_is_unknown': True}

    def _read_build_returns(self, build=None, reason=None):
        def fake(url, opener=None):
            if reason is not None:
                raise ImportError_(reason)
            return build

        patcher = mock.patch.object(text_build_view, 'read_build', fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _open(self, client=None):
        (client or self.client).get('/import/text/', HTTP_USER_AGENT=BROWSER)

    def _post(self, data, agent=BROWSER, client=None):
        return (client or self.client).post('/import/text/', data, HTTP_USER_AGENT=agent)

    def _preview_then_confirm(self, text, **extra):
        self._open()
        preview = self._post(dict({'text': text}, **extra))
        token = _hidden(preview, 'count_token')
        self.assertEqual(1, len(token))
        done = self._post(dict({'text': text, 'confirm': '1', 'char_class': 'Iop',
                                'level': '200', 'count_token': token[0]}, **extra))
        self.assertEqual(302, done.status_code)
        return preview, token[0]


@override_settings(BUILD_SITES_ENABLED=ALL_SITES)
class ALinkFromASiteWeReadIsCountedUnderItsReaderTests(_ImportPage):

    def test_a_preview_counts_one_link_attempt_under_the_readers_site(self):
        self._read_build_returns(self._build())
        page = self._post({'text': LINK})
        self.assertEqual(200, page.status_code)
        self.assertEqual([('link', 'dofusbook.net', 'dofus3', 1, 0)], _rows())

    def test_the_confirm_step_adds_one_import_and_no_attempt(self):
        self._read_build_returns(self._build())
        self._open()
        preview = self._post({'text': LINK})
        token = _hidden(preview, 'count_token')[0]
        self._post({'text': LINK, 'confirm': '1', 'level': '200', 'count_token': token})
        self.assertEqual([('link', 'dofusbook.net', 'dofus3', 1, 0)], _rows())
        done = self._post({'text': LINK, 'confirm': '1', 'char_class': 'Iop',
                           'level': '200', 'count_token': token})
        self.assertEqual(302, done.status_code)
        self.assertEqual(1, Char.objects.count())
        self.assertEqual([('link', 'dofusbook.net', 'dofus3', 1, 1)], _rows())

    def test_a_known_site_that_refuses_the_link_counts_a_failed_link(self):
        self._read_build_returns(reason='not_found')
        page = self._post({'text': LINK})
        self.assertContains(page, 'No public build at that link')
        self.assertEqual([('link_failed', 'dofusbook.net', 'dofus3', 1, 0)], _rows())

    def test_a_retro_link_and_a_short_link_count_under_the_same_reader(self):
        self._read_build_returns(reason='short_link')
        self._post({'text': 'https://retro.dofusbook.net/fr/stuff/7894460-x'})
        self._post({'text': 'https://d-bk.net/aBc12'})
        self.assertEqual([('link_failed', 'dofusbook.net', 'dofus3', 2, 0)], _rows())


@override_settings(BUILD_SITES_ENABLED=ALL_SITES)
class ASiteWeCannotReadIsCountedByItsSiteNameOnlyTests(_ImportPage):

    def test_neither_the_path_the_query_the_user_nor_the_port_is_stored(self):
        link = 'https://someone:secret@WWW.Example.org:8443/builds/42?owner=me#top'
        self._post({'text': link})
        self.assertEqual([('link_unknown', 'example.org', 'dofus3', 1, 0)], _rows())
        for row in ImportSourceHit.objects.all():
            stored = ' '.join(str(value) for value in (
                row.source, row.host, row.game_version))
            for piece in ('/', '?', '#', ':', '@', 'builds', '42', 'owner',
                          'someone', 'secret', '8443', link):
                self.assertNotIn(piece, stored)

    def test_only_the_first_site_of_a_paste_is_counted(self):
        self._post({'text': 'https://a-site.com/b/1\nwww.a-site.com/b/2\n'
                            'https://other.net/x'})
        self.assertEqual([('link_unknown', 'a-site.com', 'dofus3', 1, 0)], _rows())

    def test_an_address_inside_the_path_or_query_of_a_bare_link_is_never_the_site(self):
        for text in ('www.site.com/go?to=//alice-smith.example.fr/x',
                     'site.com/r//bob.jones.net/',
                     'www.example.org/r?u=https://other.com/x'):
            self._post({'text': text})
        self.assertEqual([('link_unknown', 'example.org', 'dofus3', 1, 0),
                          ('link_unknown', 'site.com', 'dofus3', 2, 0)], _rows())

    def test_a_subdomain_is_folded_into_its_site(self):
        for text in ('https://alice.github.io/builds',
                     'https://x7f3k2.ngrok-free.app/b',
                     'https://www.bbc.co.uk/x'):
            self._post({'text': text})
        self.assertEqual([('link_unknown', 'bbc.co.uk', 'dofus3', 1, 0),
                          ('link_unknown', 'github.io', 'dofus3', 1, 0),
                          ('link_unknown', 'ngrok-free.app', 'dofus3', 1, 0)], _rows())

    def test_a_link_with_no_public_name_counts_as_an_unnamed_site_not_as_text(self):
        for text in ('nas.local/share/b', 'http://192.168.1.20/build/1'):
            self._post({'text': text})
        self.assertEqual([('link_unknown', '', 'dofus3', 2, 0)], _rows())


@override_settings(BUILD_SITES_ENABLED=ALL_SITES)
class APasteWritesOneRowAtMostTests(_ImportPage):

    def test_a_40000_character_paste_of_distinct_sites_writes_one_row_in_four_queries_at_most(self):
        text = '\n'.join('a%d.io/' % i for i in range(9000))[:text_build_view.MAX_CARACTERES]
        self.assertGreater(len(text_build_view.separe_les_liens(text)[2]), 4000)
        with CaptureQueriesContext(connection) as queries:
            self._post({'text': text})
        on_the_table = [q['sql'] for q in queries.captured_queries
                        if 'chardata_importsourcehit' in q['sql']]
        self.assertLessEqual(len(on_the_table), 4)
        self.assertEqual([('link_unknown', 'a0.io', 'dofus3', 1, 0)], _rows())

    def test_past_the_daily_limit_a_new_site_is_counted_as_an_unnamed_site(self):
        today = timezone.localdate()
        ImportSourceHit.objects.bulk_create(
            ImportSourceHit(day=today, source='link_unknown', host='s%d.com' % i,
                            game_version='dofus3', attempts=1)
            for i in range(text_build_view.UNKNOWN_SITES_PER_DAY))
        self._post({'text': 'https://brand-new.org/b'})
        self._post({'text': 'https://s0.com/b'})
        self.assertEqual(1, ImportSourceHit.objects.get(host='').attempts)
        self.assertEqual(2, ImportSourceHit.objects.get(host='s0.com').attempts)
        self.assertFalse(ImportSourceHit.objects.filter(host='brand-new.org').exists())


class PastedTextIsCountedAsTextTests(_ImportPage):

    def test_item_names_count_as_text(self):
        self._post({'text': 'Coiffe du Bouftou\nCape du Bouftou'})
        self.assertEqual([('text', '', 'dofus3', 1, 0)], _rows())

    def test_text_from_the_screenshot_reader_counts_as_a_screenshot(self):
        page = self._post({'text': 'Coiffe du Bouftou', 'used_screenshot': '1'})
        self.assertEqual([('screenshot', '', 'dofus3', 1, 0)], _rows())
        self.assertTrue(page.context['used_screenshot'])

    def test_a_paste_on_a_version_page_is_counted_in_that_version(self):
        self.client.post('/retro/import/text/', {'text': 'Coiffe du Bouftou'},
                         HTTP_USER_AGENT=BROWSER)
        self.assertEqual([('text', '', 'retro', 1, 0)], _rows())

    def test_a_confirmed_text_paste_adds_one_import_to_text(self):
        self._preview_then_confirm('\n'.join(_names()))
        self.assertEqual([('text', '', 'dofus3', 1, 1)], _rows())

    def test_both_forms_of_a_screenshot_preview_keep_the_flag_and_its_confirm_adds_one_import(self):
        preview, _token = self._preview_then_confirm('\n'.join(_names()),
                                                     used_screenshot='1')
        self.assertEqual(['1', '1'], _hidden(preview, 'used_screenshot'))
        self.assertEqual([('screenshot', '', 'dofus3', 1, 1)], _rows())


@override_settings(BUILD_SITES_ENABLED=ALL_SITES)
class ABuildFromNamesBesideAnUnknownLinkIsCreditedToNoSiteTests(_ImportPage):

    def test_the_attempt_goes_to_the_site_and_no_import_is_added_anywhere(self):
        self._preview_then_confirm('https://dofusroom.com/build/123\n' + '\n'.join(_names()))
        self.assertEqual(1, Char.objects.count())
        self.assertEqual([('link_unknown', 'dofusroom.com', 'dofus3', 1, 0)], _rows())


class APasteSentAgainCountsOnceTests(_ImportPage):

    def test_the_same_preview_sent_twice_counts_one_attempt(self):
        self._open()
        text = '\n'.join(_names())
        first = self._post({'text': text})
        again = self._post({'text': text})
        self.assertEqual([('text', '', 'dofus3', 1, 0)], _rows())
        payload = lambda page: [signing.loads(token, salt=text_build_view._TOKEN_SALT)
                                for token in _hidden(page, 'count_token')]
        self.assertTrue(payload(first))
        self.assertEqual(payload(first), payload(again))

    def test_another_visitor_sending_the_same_paste_is_a_new_attempt(self):
        other = self.client_class()
        text = '\n'.join(_names())
        for client in (self.client, other):
            self._open(client)
            self._post({'text': text}, client=client)
        self.assertEqual([('text', '', 'dofus3', 2, 0)], _rows())

    def test_a_second_confirm_of_the_same_preview_adds_no_second_import(self):
        text = '\n'.join(_names())
        _preview, token = self._preview_then_confirm(text)
        again = self._post({'text': text, 'confirm': '1', 'char_class': 'Iop',
                            'level': '200', 'count_token': token})
        self.assertEqual(302, again.status_code)
        self.assertEqual([('text', '', 'dofus3', 1, 1)], _rows())

    def test_a_confirm_with_no_preview_or_a_forged_token_adds_no_import(self):
        text = '\n'.join(_names())
        self._open()
        for token in ('', 'eyJuIjoiYSJ9:forged:signature'):
            done = self._post({'text': text, 'confirm': '1', 'char_class': 'Iop',
                               'level': '200', 'count_token': token})
            self.assertEqual(302, done.status_code)
        self.assertEqual([], _rows())

    def test_a_preview_before_midnight_confirmed_after_it_credits_the_preview_day(self):
        today = timezone.localdate()
        yesterday = today - datetime.timedelta(days=1)
        text = '\n'.join(_names())
        self._open()
        with mock.patch.object(timezone, 'localdate', return_value=yesterday):
            token = _hidden(self._post({'text': text}), 'count_token')[0]
        self._post({'text': text, 'confirm': '1', 'char_class': 'Iop',
                    'level': '200', 'count_token': token})
        self.assertEqual([(yesterday, 1, 1)],
                         [(row.day, row.attempts, row.imported)
                          for row in ImportSourceHit.objects.all()])


class WhatIsNeverCountedTests(_ImportPage):

    def test_a_crawler_or_an_empty_user_agent_counts_nothing(self):
        for agent in ('Mozilla/5.0 (compatible; Googlebot/2.1)',
                      'python-requests/2.31.0', ''):
            self._post({'text': 'https://example.org/b/1'}, agent=agent)
        self.assertEqual([], _rows())

    def test_an_empty_paste_counts_nothing(self):
        self._post({'text': '   \n  '})
        self.assertEqual([], _rows())

    def test_a_crawler_confirming_a_browsers_preview_adds_no_import(self):
        text = '\n'.join(_names())
        self._open()
        token = _hidden(self._post({'text': text}), 'count_token')[0]
        done = self._post({'text': text, 'confirm': '1', 'char_class': 'Iop',
                           'level': '200', 'count_token': token},
                          agent='Mozilla/5.0 (compatible; Googlebot/2.1)')
        self.assertEqual(302, done.status_code)
        self.assertEqual([('text', '', 'dofus3', 1, 0)], _rows())


class OnlyASiteNameIsEverStoredAsAHostTests(SimpleTestCase):

    def test_an_address_with_no_public_name_gives_no_site(self):
        for link in ('http://192.168.1.20/build/1', 'http://localhost:8000/b/1',
                     'nas.local/share/b', 'http://router.lan/x', 'http://[::1]/x',
                     'http://[broken/x',
                     'https://%scom/b/1' % (('a' * 60 + '.') * 5),
                     'https://exa mple.org/b'):
            with self.subTest(link=link):
                self.assertEqual('', text_build_view._site_name(link))

    def test_a_domain_gives_its_bare_lowercase_site(self):
        for link, site in (
                ('www.Dofus-Stuffer.Is-Great.net?stuff=kA', 'dofus-stuffer.is-great.net'),
                ('https://Shop.Example.COM.br/x', 'example.com.br'),
                ('https://' + chr(0x43f) + chr(0x440) + chr(0x438) + chr(0x43c)
                 + chr(0x435) + chr(0x440) + '.' + chr(0x440) + chr(0x444) + '/b',
                 'xn--e1afmkfd.xn--p1ai')):
            with self.subTest(link=link):
                self.assertEqual(site, text_build_view._site_name(link))


class TheCounterNeverBreaksTheImportTests(_ImportPage):

    def test_a_database_error_while_counting_leaves_the_preview_and_the_import_working(self):
        broken = mock.patch.object(ImportSourceHit.objects, 'filter',
                                   side_effect=OperationalError('the table is gone'))
        text = '\n'.join(_names())
        self._open()
        with broken, self.assertLogs('chardata.text_build_view', level='WARNING') as logs:
            page = self._post({'text': text})
            done = self._post({'text': text, 'confirm': '1', 'char_class': 'Iop',
                               'level': '200'})
        self.assertEqual(200, page.status_code)
        self.assertTrue(page.context['confirm'])
        self.assertEqual([], _hidden(page, 'count_token'))
        self.assertEqual(302, done.status_code)
        self.assertEqual(1, Char.objects.count())
        self.assertEqual(1, sum('import source not counted' in line
                                for line in logs.output))

    def test_a_row_another_request_creates_between_the_update_and_the_insert_ends_at_two(self):
        today = timezone.localdate()
        real_filter = ImportSourceHit.objects.filter
        calls = []

        def filter_losing_the_race(*args, **kwargs):
            calls.append(kwargs)
            if len(calls) > 1:
                return real_filter(*args, **kwargs)
            first = mock.Mock()

            def update(**_changes):
                ImportSourceHit.objects.create(day=today, source='text', host='',
                                               game_version='dofus3', attempts=1)
                return 0
            first.update = update
            return first

        with mock.patch.object(ImportSourceHit.objects, 'filter',
                               side_effect=filter_losing_the_race):
            self.assertTrue(text_build_view._count_import(
                today, 'dofus3', ('text', ''), 'attempts'))
        self.assertEqual([('text', '', 'dofus3', 2, 0)], _rows())

    def test_an_insert_that_hits_the_unique_key_is_logged_and_reported(self):
        refused = mock.patch.object(ImportSourceHit.objects, 'get_or_create',
                                    side_effect=IntegrityError('duplicate entry'))
        with refused, self.assertLogs('chardata.text_build_view', level='WARNING'):
            self.assertFalse(text_build_view._count_import(
                timezone.localdate(), 'dofus3', ('text', ''), 'attempts'))


class APageCrashNeverMailsThePastedTextTests(_ImportPage):

    def test_the_error_report_hides_the_text_field(self):
        seen = []

        def remember(sender, request=None, **kwargs):
            seen.append(request)

        got_request_exception.connect(remember)
        self.addCleanup(got_request_exception.disconnect, remember)
        crash = mock.patch.object(text_build_view, 'read_items',
                                  side_effect=RuntimeError('reader crashed'))
        with crash, self.assertRaises(RuntimeError), \
                self.assertLogs('django.request', level='ERROR'):
            self._post({'text': 'my secret paste'})
        shown = SafeExceptionReporterFilter().get_post_parameters(seen[0])
        self.assertEqual(SafeExceptionReporterFilter.cleansed_substitute, shown['text'])


class TheImportTabShowsTheShareOfEachSourceTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        today = timezone.localdate()
        for source, host, version, attempts, imported, day in (
                ('link', 'dofusbook.net', 'dofus3', 6, 3, today),
                ('link_failed', 'dofusbook.net', 'dofus3', 2, 0, today),
                ('link', 'dofuscreator.com', 'dofus3', 4, 4, today),
                ('text', '', 'dofus3', 4, 1, today),
                ('screenshot', '', 'dofus3', 1, 0, today),
                ('link_unknown', 'example.org', 'dofus3', 2, 0, today),
                ('link_unknown', '', 'dofus3', 1, 0, today),
                ('link', 'dofusbook.net', 'retro', 5, 2, today),
                ('link_unknown', 'old.example.com', 'dofus3', 7, 0,
                 today - datetime.timedelta(days=400))):
            ImportSourceHit.objects.create(
                day=day, source=source, host=host, game_version=version,
                attempts=attempts, imported=imported)

    def _superuser(self):
        user = User.objects.create_user('boss', 'boss@test.local', 'pw-42-solid')
        user.is_superuser = True
        user.save()
        return user

    def test_the_shares_and_rates_of_one_version_over_thirty_days(self):
        data = admin_stats.imports(admin_stats.resolve_period('30d'), 'dofus3')
        self.assertEqual(20, data['total'])
        self.assertEqual(
            [('dofusbook.net', 8, 40.0, 3, 37.5),
             ('dofuscreator.com', 4, 20.0, 4, 100.0),
             ('Pasted text', 4, 20.0, 1, 25.0),
             ('Screenshots', 1, 5.0, 0, 0.0),
             ('Sites we cannot read yet', 3, 15.0, None, None)],
            [(r['label'], r['attempts'], r['share'], r['imported'], r['rate'])
             for r in data['rows']])
        self.assertEqual([('example.org', 2, 10.0), ('Other addresses', 1, 5.0)],
                         [(r['label'], r['attempts'], r['share'])
                          for r in data['unknown']])

    def test_every_version_and_a_longer_period_bring_the_other_rows_in(self):
        every_version = admin_stats.imports(admin_stats.resolve_period('30d'), None)
        self.assertEqual(25, every_version['total'])
        self.assertEqual(('dofusbook.net', 13, 5),
                         tuple(every_version['rows'][0][key]
                               for key in ('label', 'attempts', 'imported')))
        today = timezone.localdate()
        longer = admin_stats.resolve_period(
            start=(today - datetime.timedelta(days=500)).isoformat(),
            end=today.isoformat())
        two_years = admin_stats.imports(longer, 'dofus3')
        self.assertEqual(27, two_years['total'])
        self.assertEqual('old.example.com', two_years['unknown'][0]['label'])

    def test_the_tab_prints_the_percentages_with_one_decimal_and_no_import_for_unknown_sites(self):
        self.client.force_login(self._superuser())
        page = self.client.get('/admin-tools/', {'period': '30d', 'version': 'dofus3'})
        self.assertEqual(200, page.status_code)
        for text in ('data-panel="imports"', 'Counting since',
                     'Only the site name is stored, never the link or who pasted it.',
                     'dofusbook.net', '40.0%', '37.5%', '100.0%',
                     'Pasted text', 'Screenshots', 'Sites we cannot read yet',
                     'example.org', '10.0%', 'Other addresses',
                     'new sites past %d in one day' % text_build_view.UNKNOWN_SITES_PER_DAY):
            self.assertContains(page, text)
        unknown_row = re.search(r'<td>Sites we cannot read yet</td>(.*?)</tr>',
                                page.content.decode('utf-8'), re.S).group(1)
        self.assertEqual(2, unknown_row.count('>-</span>'))

    def test_a_visitor_or_a_plain_member_gets_a_404_and_no_figure(self):
        page = self.client.get('/admin-tools/')
        self.assertEqual(404, page.status_code)
        self.assertNotContains(page, 'Sites we cannot read yet', status_code=404)
        plain = User.objects.create_user('plain', 'p@test.local', 'pw-42-solid')
        self.client.force_login(plain)
        page = self.client.get('/admin-tools/')
        self.assertEqual(404, page.status_code)
        self.assertNotContains(page, 'Sites we cannot read yet', status_code=404)


class TheSharesAddUpToAHundredTests(TestCase):

    def test_three_equal_sources_show_one_hundred_in_total(self):
        today = timezone.localdate()
        for source in ('text', 'screenshot', 'link_unknown'):
            ImportSourceHit.objects.create(day=today, source=source, host='',
                                           game_version='dofus3', attempts=1)
        rows = admin_stats.imports(admin_stats.resolve_period('30d'), 'dofus3')['rows']
        self.assertEqual([33.4, 33.3, 33.3], [row['share'] for row in rows])

    def test_a_share_or_a_rate_that_ends_in_a_half_is_rounded_up(self):
        self.assertEqual(6.3, admin_stats._percent(1, 16))
        self.assertEqual(100.0, sum(admin_stats._shares([8, 4, 3, 1, 3])))


class TheImportChartAddsUpEachBarTests(TestCase):

    def test_a_week_bar_holds_every_day_of_that_week(self):
        today = timezone.localdate()
        monday = today - datetime.timedelta(days=today.weekday())
        ImportSourceHit.objects.create(day=monday, source='text', host='',
                                       game_version='dofus3', attempts=3)
        ImportSourceHit.objects.create(day=today, source='screenshot', host='',
                                       game_version='dofus3', attempts=4)
        period = admin_stats.resolve_period('6m')
        self.assertEqual('week', period.unit)
        bars = dict(admin_stats.imports(period, None)['per_bucket'])
        self.assertEqual(7, bars[monday.strftime('%d/%m')])
        self.assertEqual(7, sum(bars.values()))

    def test_a_month_bar_holds_every_day_of_that_month(self):
        today = timezone.localdate()
        ImportSourceHit.objects.create(day=today.replace(day=1), source='text',
                                       host='', game_version='dofus3', attempts=3)
        ImportSourceHit.objects.create(day=today, source='screenshot', host='',
                                       game_version='dofus3', attempts=4)
        period = admin_stats.resolve_period('12m')
        self.assertEqual('month', period.unit)
        bars = dict(admin_stats.imports(period, None)['per_bucket'])
        self.assertEqual(7, bars[today.strftime('%m/%y')])
        self.assertEqual(7, sum(bars.values()))


class TheImportTabSaysWhenNothingIsCountedTests(TestCase):

    def test_an_empty_table_shows_the_empty_state(self):
        cache.clear()
        self.addCleanup(cache.clear)
        user = User.objects.create_user('chief', 'c@test.local', 'pw-42-solid')
        user.is_superuser = True
        user.save()
        self.client.force_login(user)
        page = self.client.get('/admin-tools/')
        self.assertContains(page, 'Import sources are recorded from the first paste '
                                  'after this release, and nothing earlier is backfilled.')


class ADashboardCachedWithoutTheImportTabIsNeverServedTests(TestCase):

    def test_a_dict_left_under_the_old_key_is_ignored(self):
        cache.clear()
        self.addCleanup(cache.clear)
        stale = {'overview': {}, 'generated': 'stale'}
        cache.set('admin_dashboard_v2:%s:all' % admin_stats.DEFAULT_PERIOD, stale, 300)
        data = admin_stats.dashboard()
        self.assertIn('imports', data)
        self.assertNotEqual('stale', data['generated'])


class ThePrivacyPageSaysWhatTheImportPageCountsTests(TestCase):

    SENTENCES = {
        'en': ('/privacy/', (
            'we count, per day and game version, where each import comes from',
            'We never keep the link, the pasted text or who pasted it.')),
        'fr': ('/fr/privacy/', (
            'nous comptons, par jour et par version du jeu',
            'Nous ne gardons jamais le lien, le texte collé ni qui')),
        'es': ('/es/privacy/', (
            'contamos, por día y por versión del juego',
            'Nunca guardamos el enlace, el texto pegado ni quién lo pegó.')),
        'pt': ('/pt/privacy/', (
            'contamos, por dia e por versão do jogo',
            'Nunca guardamos o link, o texto colado nem quem o colou.')),
        'de': ('/de/privacy/', (
            'zählen wir pro Tag und Spielversion, woher jeder Import stammt',
            'Den Link, den eingefügten Text und wer ihn eingefügt hat, '
            'speichern wir nie.')),
    }

    def test_each_language_carries_the_sentence(self):
        for lang, (path, sentences) in self.SENTENCES.items():
            page = self.client.get(path, HTTP_ACCEPT_LANGUAGE=lang)
            for sentence in sentences:
                with self.subTest(lang=lang, sentence=sentence):
                    self.assertContains(page, sentence)


class TheMigrationOnlyCreatesTheImportTableTests(SimpleTestCase):

    def test_0047_holds_a_single_create_model_after_0046(self):
        migration = importlib.import_module(
            'chardata.migrations.0047_importsourcehit').Migration
        self.assertEqual([('chardata', '0046_workshopundo')], migration.dependencies)
        self.assertEqual(['CreateModel'],
                         [op.__class__.__name__ for op in migration.operations])
        self.assertEqual('ImportSourceHit', migration.operations[0].name)

    def test_the_table_has_no_column_for_a_link_or_a_visitor(self):
        self.assertEqual(['id', 'day', 'source', 'host', 'game_version',
                          'attempts', 'imported'],
                         [field.name for field in ImportSourceHit._meta.get_fields()])
