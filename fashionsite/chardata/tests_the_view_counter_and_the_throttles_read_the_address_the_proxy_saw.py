# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The build view counter and the login and reset-mail throttles count the address our proxies saw, never an X-Forwarded-For entry the caller wrote."""
import pickle

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings

from chardata.encoded_char_id import encode_char_id
from chardata.login_view import (LOGIN_FAIL_MAX_PER_IP, RESET_MAIL_MAX_PER_IP,
                                 login_is_throttled, note_login_failure,
                                 note_reset_mail_sent, reset_mail_is_throttled)
from chardata.middleware import looks_like_a_robot
from chardata.models import BuildView, Char
from chardata.solution_view import get_client_ip
from fashionistapulp.modelresult import ModelResultMinimal

A_READER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


def _a_shared_build():
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


class TheViewCounterReadsTheAddressTheProxySawTests(TestCase):

    def setUp(self):
        self.build = _a_shared_build()
        self.path = '/s/star/%s/' % encode_char_id(self.build.pk)

    def _view(self, agent=A_READER, **meta):
        response = self.client.get(self.path, HTTP_USER_AGENT=agent, **meta)
        self.assertEqual(200, response.status_code)

    def _views(self):
        return Char.objects.get(pk=self.build.pk).view_count

    def test_a_fresh_forwarded_header_each_time_is_still_one_viewer(self):
        for number in range(5):
            self._view(REMOTE_ADDR='203.0.113.7',
                       HTTP_X_FORWARDED_FOR='198.51.100.%d' % number)
        self.assertEqual(1, self._views())
        self.assertEqual(1, BuildView.objects.count())

    def test_the_address_cloudflare_reports_tells_two_viewers_apart(self):
        self._view(REMOTE_ADDR='203.0.113.7', HTTP_CF_CONNECTING_IP='198.51.100.1')
        self._view(REMOTE_ADDR='203.0.113.7', HTTP_CF_CONNECTING_IP='198.51.100.2')
        self.assertEqual(2, self._views())

    def test_one_viewer_reaching_two_edge_servers_is_counted_once(self):
        self._view(REMOTE_ADDR='203.0.113.7', HTTP_CF_CONNECTING_IP='198.51.100.1')
        self._view(REMOTE_ADDR='203.0.113.8', HTTP_CF_CONNECTING_IP='198.51.100.1')
        self.assertEqual(1, self._views())

    def test_the_address_nginx_reports_tells_two_viewers_apart(self):
        self._view(REMOTE_ADDR='10.0.0.2', HTTP_X_REAL_IP='198.51.100.1')
        self._view(REMOTE_ADDR='10.0.0.2', HTTP_X_REAL_IP='198.51.100.2')
        self.assertEqual(2, self._views())

    def test_addresses_of_one_ipv6_network_are_one_viewer(self):
        for last in ('1', '2', 'abcd'):
            self._view(REMOTE_ADDR='2001:db8:1:2::%s' % last)
        self.assertEqual(1, self._views())

    def test_two_ipv6_networks_are_two_viewers(self):
        self._view(REMOTE_ADDR='2001:db8:1:2::1')
        self._view(REMOTE_ADDR='2001:db8:1:3::1')
        self.assertEqual(2, self._views())

    def test_a_crawler_sending_fresh_addresses_is_never_a_view(self):
        for agent in ('Lightpanda/1.0', 'meta-webindexer/1.1', 'GPTBot/1.2'):
            for number in range(3):
                self._view(agent=agent, REMOTE_ADDR='203.0.113.7',
                           HTTP_X_FORWARDED_FOR='198.51.100.%d' % number)
        self.assertEqual(0, self._views())
        self.assertEqual(0, BuildView.objects.count())

    def test_a_head_request_is_never_a_view(self):
        response = self.client.head(self.path, HTTP_USER_AGENT=A_READER,
                                    REMOTE_ADDR='203.0.113.9')
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, self._views())
        self.assertEqual(0, BuildView.objects.count())


class AnAddressTheProxyDidNotReportIsNotInventedTests(TestCase):

    def _get(self, **meta):
        return RequestFactory().get('/', **meta)

    def test_a_forwarded_header_alone_names_no_one(self):
        request = self._get(HTTP_X_FORWARDED_FOR='203.0.113.9, 10.0.0.1')
        request.META.pop('REMOTE_ADDR', None)
        self.assertIsNone(get_client_ip(request))

    def test_the_forwarded_header_never_wins_over_the_connection(self):
        request = self._get(REMOTE_ADDR='192.0.2.5',
                            HTTP_X_FORWARDED_FOR='203.0.113.9')
        self.assertEqual('192.0.2.5', get_client_ip(request))

    def test_junk_in_every_address_header_names_no_one(self):
        request = self._get(REMOTE_ADDR='A' * 100, HTTP_X_REAL_IP='junk',
                            HTTP_CF_CONNECTING_IP='nope')
        self.assertIsNone(get_client_ip(request))


class TheThrottlesCountTheAddressTheProxySawTests(TestCase):

    def _from(self, forwarded):
        return RequestFactory().post('/', REMOTE_ADDR='203.0.113.7',
                                     HTTP_X_FORWARDED_FOR=forwarded)

    def test_a_fresh_forwarded_header_does_not_reset_the_login_throttle(self):
        for number in range(LOGIN_FAIL_MAX_PER_IP):
            note_login_failure(self._from('198.51.100.%d' % number),
                               'victim%d' % number)
        self.assertTrue(login_is_throttled(self._from('198.51.100.250'),
                                           'someone-new'))

    def test_a_different_caller_is_not_throttled_by_the_first(self):
        for number in range(LOGIN_FAIL_MAX_PER_IP):
            note_login_failure(self._from('198.51.100.1'), 'victim%d' % number)
        other = RequestFactory().post('/', REMOTE_ADDR='203.0.113.99')
        self.assertFalse(login_is_throttled(other, 'someone-new'))

    def test_a_fresh_forwarded_header_does_not_reset_the_reset_mail_throttle(self):
        for number in range(RESET_MAIL_MAX_PER_IP):
            note_reset_mail_sent(self._from('198.51.100.%d' % number),
                                 'target%d@x.test' % number)
        self.assertTrue(reset_mail_is_throttled(self._from('198.51.100.250'),
                                                'another@x.test'))


class TheCrawlerListNamesTheMetaIndexerTests(TestCase):

    def test_the_bare_token_is_a_crawler(self):
        for agent in ('meta-webindexer/1.1', 'Meta-WebIndexer/1.1',
                      'Lightpanda/1.0'):
            request = RequestFactory().get('/', HTTP_USER_AGENT=agent)
            self.assertTrue(looks_like_a_robot(request), agent)

    def test_a_reader_is_not(self):
        request = RequestFactory().get('/', HTTP_USER_AGENT=A_READER)
        self.assertFalse(looks_like_a_robot(request))


@override_settings(CLIENT_ADDRESS_PROXY_HOPS=1)
class BehindOneLoadBalancerTheAddressIsTheOneItAppendedTests(TestCase):

    def _get(self, **meta):
        meta.setdefault('REMOTE_ADDR', '10.0.1.5')
        return RequestFactory().get('/', **meta)

    def test_the_last_entry_of_the_forwarded_chain_is_the_visitor(self):
        request = self._get(HTTP_X_FORWARDED_FOR='198.51.100.77, 203.0.113.50')
        self.assertEqual('203.0.113.50', get_client_ip(request))

    def test_a_forged_real_ip_or_cloudflare_header_is_not_believed(self):
        request = self._get(HTTP_X_FORWARDED_FOR='203.0.113.50',
                            HTTP_X_REAL_IP='198.51.100.1',
                            HTTP_CF_CONNECTING_IP='198.51.100.2')
        self.assertEqual('203.0.113.50', get_client_ip(request))

    def test_an_ipv6_visitor_is_counted_by_its_network(self):
        request = self._get(HTTP_X_FORWARDED_FOR='2001:db8:1:2::9')
        self.assertEqual('2001:db8:1:2::/64', get_client_ip(request))

    def test_no_forwarded_chain_falls_back_to_the_connection(self):
        self.assertEqual('10.0.1.5', get_client_ip(self._get()))

    def test_a_junk_last_entry_falls_back_to_the_connection(self):
        request = self._get(HTTP_X_FORWARDED_FOR='203.0.113.50, junk')
        self.assertEqual('10.0.1.5', get_client_ip(request))

    def test_one_visitor_forging_the_front_of_the_chain_is_one_viewer(self):
        build = _a_shared_build()
        path = '/s/star/%s/' % encode_char_id(build.pk)
        for number in range(5):
            self.client.get(path, HTTP_USER_AGENT=A_READER, REMOTE_ADDR='10.0.1.5',
                            HTTP_X_FORWARDED_FOR='198.51.100.%d, 203.0.113.50' % number)
        self.assertEqual(1, Char.objects.get(pk=build.pk).view_count)

    def test_two_visitors_behind_one_balancer_are_two_viewers(self):
        build = _a_shared_build()
        path = '/s/star/%s/' % encode_char_id(build.pk)
        for visitor in ('203.0.113.50', '203.0.113.51'):
            self.client.get(path, HTTP_USER_AGENT=A_READER, REMOTE_ADDR='10.0.1.5',
                            HTTP_X_FORWARDED_FOR=visitor)
        self.assertEqual(2, Char.objects.get(pk=build.pk).view_count)

    def test_the_login_throttle_does_not_lock_out_every_visitor(self):
        for number in range(LOGIN_FAIL_MAX_PER_IP):
            note_login_failure(self._get(HTTP_X_FORWARDED_FOR='203.0.113.50'),
                               'victim%d' % number)
        self.assertTrue(login_is_throttled(
            self._get(HTTP_X_FORWARDED_FOR='203.0.113.50'), 'someone-new'))
        self.assertFalse(login_is_throttled(
            self._get(HTTP_X_FORWARDED_FOR='203.0.113.51'), 'someone-new'))


@override_settings(CLIENT_ADDRESS_PROXY_HOPS=2)
class BehindTwoProxiesTheAddressIsTheOneTheNearestOneAppendedTests(TestCase):

    def _get(self, **meta):
        meta.setdefault('REMOTE_ADDR', '10.0.2.7')
        return RequestFactory().get('/', **meta)

    def test_the_second_entry_from_the_right_is_the_visitor(self):
        request = self._get(HTTP_X_FORWARDED_FOR='198.51.100.9, 203.0.113.50, 10.0.9.9')
        self.assertEqual('203.0.113.50', get_client_ip(request))

    def test_a_chain_shorter_than_the_proxies_falls_back_to_the_connection(self):
        request = self._get(HTTP_X_FORWARDED_FOR='198.51.100.9')
        self.assertEqual('10.0.2.7', get_client_ip(request))
