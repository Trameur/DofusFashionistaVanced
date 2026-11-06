# -*- coding: utf-8 -*-
"""A reset link only ever reaches the address on the account, and login counters hold."""
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import RequestFactory, TestCase

from chardata import login_view
from chardata.rate_limit import hits
from social_django.models import UserSocialAuth

STORED = 'victim@test.local'


class _Rows(TestCase):

    def setUp(self):
        mail.outbox = []
        self.victim = User.objects.create_user('victim', STORED, 'pw-42-solid')


class TheResetMail(_Rows):

    def test_a_submitted_spelling_of_the_address_gets_nothing(self):
        self.client.post('/recover_password/', {'email': 'VICTIM@test.local'})
        self.assertEqual([message.to for message in mail.outbox], [[STORED]])

    def test_an_accented_spelling_is_another_mailbox(self):
        accented = 'víctim@test.local'
        with mock.patch.object(User.objects, 'filter', return_value=[self.victim]):
            self.assertEqual(login_view._get_non_social_users_for_email(accented), [])

    def test_the_exact_address_finds_the_account(self):
        self.assertEqual(login_view._get_non_social_users_for_email(STORED), [self.victim])

    def test_a_case_variant_finds_the_account(self):
        self.assertEqual(login_view._get_non_social_users_for_email('Victim@Test.Local'),
                         [self.victim])

    def test_spellings_share_one_limit_for_the_mailbox(self):
        for spelling in ('victim@test.local', 'VICTIM@test.local', 'Victim@test.local',
                         'vICTIM@test.local', 'viCTIM@test.local'):
            self.client.post('/recover_password/', {'email': spelling})
        self.assertEqual(len(mail.outbox), login_view.RESET_MAIL_MAX_PER_EMAIL)

    def test_an_address_the_mail_library_refuses_is_not_a_server_error(self):
        with mock.patch('chardata.login_view.send_mail', side_effect=ValueError):
            response = self.client.post('/recover_password/', {'email': STORED})
        self.assertEqual(response.status_code, 200)

    def test_no_address_at_all_finds_nobody(self):
        self.assertEqual(login_view._get_non_social_users_for_email(None), [])

    def test_a_google_account_gets_no_reset_link(self):
        google = User.objects.create_user('google', 'google@test.local')
        UserSocialAuth.objects.create(user=google, provider='google-oauth2', uid='1')
        self.assertEqual(login_view._get_non_social_users_for_email('google@test.local'), [])

    def test_completing_the_reset_clears_the_counter_of_the_username(self):
        for _ in range(login_view.LOGIN_FAIL_MAX_PER_USER):
            self.client.post('/local_login/', {'username': 'victim', 'password': 'wrong'})
        self.client.post('/recover_password/', {'email': STORED})
        link = re.search(r'/do_recover_password/\S+', mail.outbox[-1].body).group(0)
        self.client.post(link, {'new_password': 'a-new-one', 'confirm_password': 'a-new-one'})
        self.assertEqual(hits(login_view._username_key('victim'), login_view.LOGIN_FAIL_WINDOW), 0)


class TheLoginCounters(_Rows):

    def fail(self, username, password='wrong'):
        return self.client.post('/local_login/', {'username': username, 'password': password})

    def test_the_spellings_of_a_username_count_as_one(self):
        self.assertEqual(login_view._username_key('Bób'), login_view._username_key('BOB'))
        self.assertEqual(login_view._username_key(' bob '), login_view._username_key('bob'))

    def test_spellings_reach_the_ceiling_of_the_account(self):
        spellings = ['victim', 'VICTIM', 'Victim', 'víctim', 'vìctim']
        for attempt in range(login_view.LOGIN_FAIL_MAX_PER_USER):
            self.fail(spellings[attempt % len(spellings)])
        self.assertEqual(self.fail('victim').content, b'too-many')

    def test_a_successful_login_leaves_the_counter_of_the_address(self):
        request = RequestFactory().post('/local_login/')
        from chardata.solution_view import get_client_ip
        key = 'login-fail-ip:%s' % get_client_ip(request)
        User.objects.create_user('attacker', 'attacker@test.local', 'pw-42-solid')
        for _ in range(3):
            self.fail('victim')
        self.fail('attacker', 'pw-42-solid')
        self.assertEqual(hits(key, login_view.LOGIN_FAIL_WINDOW), 3)

    def test_a_successful_login_clears_the_counter_of_its_username(self):
        for _ in range(3):
            self.fail('victim')
        self.fail('victim', 'pw-42-solid')
        self.assertEqual(hits(login_view._username_key('victim'), login_view.LOGIN_FAIL_WINDOW), 0)


class ErrorReportsKeepSecretsOut(TestCase):

    def test_the_mail_report_has_no_html_copy_of_the_request(self):
        from django.conf import settings
        admin_handler = settings.LOGGING['handlers']['mail_admins']
        self.assertFalse(admin_handler.get('include_html'))

    def test_each_password_field_is_masked(self):
        factory = RequestFactory()
        expected = {
            login_view.local_login: ('password',),
            login_view.register: ('password',),
            login_view.change_password: ('password', 'newPassword'),
            login_view.recover_password: ('new_password', 'confirm_password'),
        }
        for view, fields in expected.items():
            request = factory.post('/', {name: 'secret' for name in fields})
            request.user = mock.Mock(is_anonymous=True)
            try:
                view(request, 'nobody', 'token') if view is login_view.recover_password else view(request)
            except Exception:
                pass
            self.assertEqual(set(request.sensitive_post_parameters), set(fields), view.__name__)
