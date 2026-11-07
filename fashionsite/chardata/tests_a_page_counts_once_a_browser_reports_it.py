# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Serving a page counts nothing. It counts when a browser reports having shown it, with the token the server gave that page."""
import os
import pickle
import re
import time
from unittest import mock
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.core import signing
from django.http import HttpResponse, StreamingHttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, TestCase

from chardata.account_deletion import forget_the_names
from chardata.encoded_char_id import encode_char_id
from chardata.middleware import (PageHitMiddleware, arrival_source,
                                 normalise_path, read_seen_token, seen_token)
from chardata.models import BuildView, Char, PageHit, VisitSource
from fashionistapulp.fashionista_config import get_fashionista_path
from fashionistapulp.modelresult import ModelResultMinimal

A_BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')

# Minified pages sort attributes and drop optional quotes
SEEN_TOKEN = re.compile(r'data-seen="?([^"\s>]+)')


def the_token_in(page):
    found = SEEN_TOKEN.search(page.content.decode('utf-8'))
    if found is None:
        raise AssertionError('this page offers no report')
    return found.group(1)


def report(client, token, fields=None, **meta):
    """What seen.js sends for a page, from the same browser."""
    meta.setdefault('HTTP_USER_AGENT', A_BROWSER)
    return client.post('/seen/', urlencode(dict(fields or {}, t=token)),
                       content_type='application/x-www-form-urlencoded', **meta)


def read_and_report(client, path, fields=None, **meta):
    """A browser that loads a page and shows it. Answers the page."""
    meta.setdefault('HTTP_USER_AGENT', A_BROWSER)
    page = client.get(path, **meta)
    if page.status_code == 200:
        report(client, the_token_in(page), fields, **meta)
    return page


def _shared_build():
    owner = User.objects.create_user('viewed', 'v@x.test', 'pw-42-solid')
    input_ = {'options': {'ap_exo': False, 'mp_exo': False},
              'origin': 'generated', 'char_level': 200,
              'base_stats_by_attr': {}, 'locked_equips': {}}
    return Char.objects.create(
        name='Star', char_name='star', char_class='Iop', char_build='build',
        level=200, minimum_stats=b'', minimum_crits=b'', stats_weight=b'',
        options=b'', inclusions=b'', exclusions=b'',
        minimal_solution=pickle.dumps(ModelResultMinimal({}, input_, {})),
        owner=owner, link_shared=True, game_version='dofus3')


class ServingAPageCountsNothingTests(TestCase):

    def test_a_browser_that_never_reports_leaves_no_row(self):
        self.assertEqual(200, self.client.get('/about/', HTTP_USER_AGENT=A_BROWSER).status_code)
        self.assertFalse(PageHit.objects.exists())
        self.assertFalse(VisitSource.objects.exists())

    def test_a_shared_build_served_without_a_report_has_no_view(self):
        build = _shared_build()
        self.client.get('/s/star/%s/' % encode_char_id(build.pk), HTTP_USER_AGENT=A_BROWSER)
        self.assertEqual(0, Char.objects.get(pk=build.pk).view_count)
        self.assertFalse(BuildView.objects.exists())


class TheReportCountsWhatTheServerVouchedForTests(TestCase):

    def test_the_page_is_counted_under_its_folded_path(self):
        read_and_report(self.client, '/about/')
        read_and_report(self.client, '/about/')
        hit = PageHit.objects.get(path='/about/')
        self.assertEqual(2, hit.count)
        self.assertEqual('dofus3', hit.game_version)

    def test_the_version_and_the_language_come_from_the_page(self):
        page = read_and_report(self.client, '/fr/retro/about/', HTTP_CF_IPCOUNTRY='co')
        self.assertEqual(200, page.status_code)
        hit = PageHit.objects.get()
        self.assertEqual(('/about/', 'retro'), (hit.path, hit.game_version))
        arrival = VisitSource.objects.get()
        self.assertEqual(('fr', 'CO'), (arrival.language, arrival.country))

    def test_the_referrer_host_and_the_campaign_name_the_arrival(self):
        read_and_report(self.client, '/about/', {'r': 'www.google.com'})
        read_and_report(self.client, '/about/', {'us': 'discord', 'uc': 'sets'})
        self.assertEqual(
            [('discord', 'utm', 'sets'), ('google', 'organic', '')],
            sorted(VisitSource.objects.values_list('source', 'medium', 'campaign')))

    def test_a_bare_referrer_host_is_read_like_a_full_address(self):
        for referrer in ('www.google.com', 'https://www.google.com/'):
            self.assertEqual(('google', 'organic', ''),
                             arrival_source('', '', '', referrer, 'dofusfashionista.gg'))
        self.assertIsNone(arrival_source('', '', '', 'www.dofusfashionista.gg',
                                         'dofusfashionista.gg'))

    def test_a_report_sets_no_cookie_and_says_nothing(self):
        token = the_token_in(self.client.get('/about/', HTTP_USER_AGENT=A_BROWSER))
        answer = report(self.client, token)
        self.assertEqual(204, answer.status_code)
        self.assertEqual(b'', answer.content)
        self.assertFalse(answer.cookies)

    def test_a_signed_in_reader_costs_no_session_read(self):
        reader = User.objects.create_user('reader', 'r@x.test', 'pw-42-solid')
        self.client.force_login(reader)
        token = the_token_in(self.client.get('/about/', HTTP_USER_AGENT=A_BROWSER))
        with mock.patch('chardata.page_seen_view._count'):
            with self.assertNumQueries(0):
                answer = report(self.client, token)
        self.assertEqual(204, answer.status_code)
        self.assertFalse(answer.has_header('Cache-Control'))

    def test_the_page_itself_is_a_valid_sender(self):
        read_and_report(self.client, '/about/', HTTP_SEC_FETCH_SITE='same-origin',
                        HTTP_ORIGIN='http://testserver')
        self.assertEqual(1, PageHit.objects.get(path='/about/').count)

    def test_a_browser_with_csrf_checks_on_is_counted(self):
        read_and_report(Client(enforce_csrf_checks=True), '/about/')
        self.assertEqual(1, PageHit.objects.get(path='/about/').count)

    def test_a_token_reported_twice_counts_twice(self):
        # The token only says the server served that page; nginx bounds what a replay adds
        token = the_token_in(self.client.get('/about/', HTTP_USER_AGENT=A_BROWSER))
        report(self.client, token)
        report(self.client, token)
        self.assertEqual(2, PageHit.objects.get(path='/about/').count)

    def test_the_token_holds_nothing_about_the_reader(self):
        build = _shared_build()
        page = self.client.get('/s/star/%s/' % encode_char_id(build.pk),
                               HTTP_USER_AGENT=A_BROWSER, REMOTE_ADDR='203.0.113.7')
        claim = read_seen_token(the_token_in(page))
        self.assertEqual({'p', 'v', 'l', 'b'}, set(claim))
        self.assertEqual(encode_char_id(build.pk), claim['b'])


class AReportThatProvesNothingCountsNothingTests(TestCase):

    def assert_not_counted(self, answer):
        self.assertEqual(204, answer.status_code, 'a refused report learns nothing')
        self.assertFalse(PageHit.objects.exists())
        self.assertFalse(VisitSource.objects.exists())

    def a_token(self):
        return the_token_in(self.client.get('/about/', HTTP_USER_AGENT=A_BROWSER))

    def test_a_forged_token(self):
        self.assert_not_counted(report(self.client, self.a_token() + 'x'))
        self.assert_not_counted(report(self.client, 'not-a-token'))
        self.assert_not_counted(self.client.post('/seen/', HTTP_USER_AGENT=A_BROWSER))

    def test_a_token_signed_for_another_purpose(self):
        token = signing.dumps({'p': '/about/', 'v': 'dofus3', 'l': 'en'})
        self.assert_not_counted(report(self.client, token))

    def test_a_token_past_its_hour(self):
        token = self.a_token()
        with mock.patch('django.core.signing.time.time', return_value=time.time() + 3700):
            self.assert_not_counted(report(self.client, token))

    def test_a_report_too_long_to_be_ours(self):
        self.assert_not_counted(report(self.client, self.a_token(), {'us': 'x' * 5000}))

    def test_a_crawler_that_runs_the_script(self):
        token = self.a_token()
        for agent in ('Mozilla/5.0 (compatible; Googlebot/2.1)', 'GPTBot/1.2', ''):
            self.assert_not_counted(report(self.client, token, HTTP_USER_AGENT=agent))

    def test_a_report_sent_from_another_site(self):
        token = self.a_token()
        self.assert_not_counted(report(self.client, token, HTTP_SEC_FETCH_SITE='cross-site'))
        self.assert_not_counted(report(self.client, token, HTTP_SEC_FETCH_SITE='same-site'))
        self.assert_not_counted(report(self.client, token, HTTP_ORIGIN='https://elsewhere.test'))

    def test_the_route_only_takes_a_report(self):
        self.assertEqual(405, self.client.get('/seen/', HTTP_USER_AGENT=A_BROWSER).status_code)

    def test_a_counting_failure_still_answers_and_says_so(self):
        token = self.a_token()
        with mock.patch('chardata.page_seen_view.record_arrival',
                        side_effect=RuntimeError('the table is gone')):
            with self.assertLogs('chardata.page_seen_view', level='WARNING') as logs:
                self.assertEqual(204, report(self.client, token).status_code)
        self.assertIn('the table is gone', logs.output[0])

    def test_a_failing_counter_does_not_lose_the_others(self):
        build = _shared_build()
        path = '/s/star/%s/' % encode_char_id(build.pk)
        token = the_token_in(self.client.get(path, HTTP_USER_AGENT=A_BROWSER))
        with mock.patch('chardata.page_seen_view.record_arrival',
                        side_effect=RuntimeError('the table is gone')):
            with self.assertLogs('chardata.page_seen_view', level='WARNING'):
                report(self.client, token, REMOTE_ADDR='203.0.113.7')
        self.assertEqual(1, PageHit.objects.get().count)
        self.assertEqual(1, Char.objects.get(pk=build.pk).view_count)


class TheReportRouteIsLimitedTests(SimpleTestCase):

    def _read(self, *path):
        with open(os.path.join(get_fashionista_path(), *path), encoding='utf-8') as f:
            return f.read()

    def test_nginx_gives_the_route_its_own_limit(self):
        config = self._read('docker', 'nginx.conf')
        self.assertIn('zone=page_report:', config)
        route = config.split('location = /seen/ {', 1)[1].split('}', 1)[0]
        self.assertIn('limit_req zone=page_report', route)

    def test_a_deploy_makes_nginx_read_a_changed_config(self):
        deploy = self._read('deploy.sh')
        self.assertRegex(deploy, r'if ! docker compose [^\n]*cat /etc/nginx/nginx\.conf \\\n'
                                 r'\s*\| cmp -s - docker/nginx\.conf; then\n'
                                 r'\s*docker compose [^\n]*--force-recreate[^\n]* nginx\n')


class ACountedPathHoldsNoAccountNameTests(TestCase):

    def test_every_route_carrying_a_name_folds_it(self):
        for path, folded in (
                ('/user/holder/', '/user/<id>/'),
                ('/fr/user/holder/', '/user/<id>/'),
                ('/retro/user/holder/', '/user/<id>/'),
                ('/email_confirmed/holder/yes/', '/email_confirmed/<id>/'),
                ('/confirm_email/holder/Tok3n/', '/confirm_email/<id>/'),
                ('/do_recover_password/holder/Tok3n/', '/do_recover_password/<id>/'),
                ('/do_recover_password/john/doe/Tok3n/', '/do_recover_password/<id>/')):
            version = 'retro' if 'retro' in path else 'dofus3'
            self.assertEqual(folded, normalise_path(path, version), path)

    def test_a_longer_route_word_is_left_alone(self):
        self.assertEqual('/users/', normalise_path('/users/', 'dofus3'))
        self.assertEqual('/confirm_email_change/<id>/',
                         normalise_path('/confirm_email_change/Tok3n/', 'dofus3'))

    def test_a_report_arriving_after_the_account_is_gone_holds_no_name(self):
        token = seen_token(normalise_path('/user/holder/', 'dofus3'), 'dofus3', 'en')
        forget_the_names('holder', 'holder', 'holder@x.test')
        report(self.client, token)
        self.assertEqual(['/user/<id>/'], list(PageHit.objects.values_list('path', flat=True)))


class TheServerOffersTheReportOnReadablePagesTests(TestCase):

    def run_through(self, response, method='get', path='/about/'):
        request = getattr(RequestFactory(), method)(path)
        return PageHitMiddleware(lambda _request: response)(request)

    def a_page(self, **kwargs):
        return HttpResponse('<html><body><p>x</p></body></html>', **kwargs)

    def test_the_script_sits_at_the_end_of_the_body(self):
        html = self.run_through(self.a_page()).content.decode('utf-8')
        self.assertRegex(html, r'<script[^>]+seen\.js[^>]+data-seen="[^"]+" defer></script></body>')

    def test_the_script_is_a_file_the_site_serves(self):
        self.assertIsNotNone(finders.find('chardata/seen.js'))

    def test_the_length_header_stays_true(self):
        page = self.a_page()
        page['Content-Length'] = str(len(page.content))
        served = self.run_through(page)
        self.assertEqual(str(len(served.content)), served['Content-Length'])

    def test_the_real_page_gets_it_once(self):
        page = self.client.get('/about/', HTTP_USER_AGENT=A_BROWSER)
        self.assertEqual(1, len(SEEN_TOKEN.findall(page.content.decode('utf-8'))))

    def test_what_nobody_reads_is_left_alone(self):
        untouched = {
            'a post': lambda: self.run_through(self.a_page(), method='post'),
            'a head': lambda: self.run_through(self.a_page(), method='head'),
            'an error': lambda: self.run_through(self.a_page(status=404)),
            'no html': lambda: self.run_through(self.a_page(content_type='application/json')),
            'a path that is not a page': lambda: self.run_through(self.a_page(), path='/admin-tools/'),
            'no body tag': lambda: self.run_through(HttpResponse('<p>x</p>')),
        }
        for name, serve in untouched.items():
            self.assertNotIn(b'data-seen', serve().content, name)

    def test_a_streamed_page_is_not_read_into_memory(self):
        page = b'<html><body></body></html>'
        with self.assertNoLogs('chardata.middleware', level='WARNING'):
            served = self.run_through(StreamingHttpResponse(iter([page])))
        self.assertEqual(page, b''.join(served.streaming_content))


class AReportOfASharedBuildIsOneViewTests(TestCase):

    def setUp(self):
        self.build = _shared_build()
        self.path = '/s/star/%s/' % encode_char_id(self.build.pk)

    def the_token(self):
        return the_token_in(self.client.get(self.path, HTTP_USER_AGENT=A_BROWSER))

    def test_another_page_never_counts_as_a_view_of_the_build(self):
        read_and_report(self.client, '/about/', REMOTE_ADDR='203.0.113.7')
        self.assertEqual(0, Char.objects.get(pk=self.build.pk).view_count)

    def test_a_build_unshared_after_the_page_was_served_gets_no_view(self):
        token = self.the_token()
        Char.objects.filter(pk=self.build.pk).update(link_shared=False)
        report(self.client, token, REMOTE_ADDR='203.0.113.7')
        self.assertEqual(0, Char.objects.get(pk=self.build.pk).view_count)
        self.assertFalse(BuildView.objects.exists())

    def test_a_build_deleted_after_the_page_was_served_gets_no_view(self):
        token = self.the_token()
        Char.objects.filter(pk=self.build.pk).update(deleted=True)
        report(self.client, token, REMOTE_ADDR='203.0.113.7')
        self.assertEqual(0, Char.objects.get(pk=self.build.pk).view_count)
        self.assertFalse(BuildView.objects.exists())

    def test_a_build_gone_since_the_page_was_served_breaks_nothing(self):
        token = self.the_token()
        Char.objects.filter(pk=self.build.pk).delete()
        self.assertEqual(204, report(self.client, token, REMOTE_ADDR='203.0.113.7').status_code)
        self.assertEqual(1, PageHit.objects.get().count)
