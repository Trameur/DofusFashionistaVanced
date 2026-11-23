# -*- coding: utf-8 -*-
"""A Google login goes through the real begin view, the real social pipeline and the real
complete view, with only the two HTTP calls to Google replaced."""
import time
from unittest import mock, skipUnless
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from social_core.backends.google import GoogleOAuth2
from social_core.backends.oauth import BaseOAuth2
from social_django.models import Nonce, UserSocialAuth

PROVIDER = 'google-oauth2'
EMAIL = 'jean.dupont@gmail.test'
SUB = '104857600000000000001'

HAS_STATE_LIFETIME = hasattr(BaseOAuth2, 'STATE_LIFETIME')


class FakeResponse:
    status_code = 200
    ok = True

    def __init__(self, payload):
        self.payload = payload
        self.text = ''

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


def google_api(sub=SUB, email=EMAIL):
    def answer(method, url, **kwargs):
        if 'userinfo' in url:
            return FakeResponse({'sub': sub, 'email': email, 'email_verified': True,
                                 'name': 'Jean Dupont', 'given_name': 'Jean',
                                 'family_name': 'Dupont'})
        return FakeResponse({'access_token': 'token-for-the-test', 'token_type': 'Bearer',
                             'expires_in': 3599, 'id_token': 'unused'})
    return mock.patch('social_core.backends.base.requests.request', side_effect=answer)


@override_settings(SOCIAL_AUTH_GOOGLE_OAUTH2_KEY='test-client', SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET='test-secret')
class GoogleLogin(TestCase):

    def begin(self):
        response = self.client.post(reverse('social:begin', args=(PROVIDER,)), secure=True)
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlparse(response['Location']).query)
        return query['state'][0]

    def complete(self, state, **extra):
        url = reverse('social:complete', args=(PROVIDER,))
        return self.client.get(url, {'state': state, 'code': 'code-for-the-test'}, secure=True, **extra)

    def logged_in_user_id(self):
        return self.client.session.get('_auth_user_id')

    def login(self):
        state = self.begin()
        with google_api():
            return self.complete(state)


class BackendSetup(TestCase):

    def test_the_backend_is_the_plain_google_one_without_an_id_key(self):
        from django.conf import settings
        self.assertIn('social_core.backends.google.GoogleOAuth2', settings.AUTHENTICATION_BACKENDS)
        self.assertFalse(hasattr(settings, 'SOCIAL_AUTH_GOOGLE_OAUTH2_ID_KEY'))
        self.assertEqual(GoogleOAuth2.name, PROVIDER)


class AnExistingAccount(GoogleLogin):

    def make_old_account(self):
        user = User.objects.create_user('jean.dupont', EMAIL)
        UserSocialAuth.objects.create(user=user, provider=PROVIDER, uid=EMAIL)
        return user

    def test_a_row_stored_under_the_email_signs_the_same_user_in(self):
        user = self.make_old_account()
        response = self.login()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.logged_in_user_id(), str(user.pk))

    def test_no_second_account_and_no_second_row_appear(self):
        self.make_old_account()
        self.login()
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(UserSocialAuth.objects.filter(provider=PROVIDER).count(), 1)

    def test_the_second_login_of_the_same_account_works_too(self):
        user = self.make_old_account()
        self.login()
        self.client.logout()
        self.login()
        self.assertEqual(self.logged_in_user_id(), str(user.pk))
        self.assertEqual(UserSocialAuth.objects.filter(user=user).count(), 1)


class ANewAccount(GoogleLogin):

    def test_a_first_login_creates_one_user_with_one_row_and_signs_it_in(self):
        response = self.login()
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email=EMAIL)
        self.assertEqual(self.logged_in_user_id(), str(user.pk))
        self.assertEqual(UserSocialAuth.objects.filter(user=user, provider=PROVIDER).count(), 1)

    def test_a_new_login_after_it_finds_the_account_it_made(self):
        self.login()
        user = User.objects.get(email=EMAIL)
        self.client.logout()
        self.login()
        self.assertEqual(self.logged_in_user_id(), str(user.pk))
        self.assertEqual(User.objects.count(), 1)


class TheStateOfALogin(GoogleLogin):

    def test_a_wrong_state_signs_nobody_in(self):
        self.begin()
        with google_api():
            response = self.complete('not-the-state')
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.logged_in_user_id())
        self.assertEqual(User.objects.count(), 0)

    def test_a_missing_state_signs_nobody_in(self):
        with google_api():
            response = self.client.get(reverse('social:complete', args=(PROVIDER,)), {'code': 'x'}, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.logged_in_user_id())

    @skipUnless(HAS_STATE_LIFETIME, 'the state has no lifetime before social-auth-core 6.2')
    def test_the_state_lifetime_is_1800_seconds(self):
        self.assertEqual(GoogleOAuth2.STATE_LIFETIME, 1800)

    @skipUnless(HAS_STATE_LIFETIME, 'the state has no lifetime before social-auth-core 6.2')
    def test_a_state_just_inside_its_lifetime_still_works(self):
        state = self.begin()
        now = time.time()
        with google_api(), mock.patch('social_core.backends.oauth._time', return_value=now + 1790):
            self.complete(state)
        self.assertIsNotNone(self.logged_in_user_id())

    @skipUnless(HAS_STATE_LIFETIME, 'the state has no lifetime before social-auth-core 6.2')
    def test_a_state_past_its_lifetime_signs_nobody_in(self):
        state = self.begin()
        now = time.time()
        with google_api(), mock.patch('social_core.backends.oauth._time', return_value=now + 1810):
            response = self.complete(state)
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.logged_in_user_id())
        self.assertEqual(User.objects.count(), 0)

    @skipUnless(HAS_STATE_LIFETIME, 'a state is single use only from social-auth-core 6.2')
    def test_a_state_works_once_and_a_replay_signs_nobody_in(self):
        state = self.begin()
        with google_api():
            self.complete(state)
            self.client.logout()
            response = self.complete(state)
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.logged_in_user_id())

    @skipUnless(HAS_STATE_LIFETIME, 'a login in flight only fails with social-auth-core 6.2')
    def test_a_login_started_before_the_upgrade_fails_once_then_the_next_one_works(self):
        session = self.client.session
        session['%s_state' % PROVIDER] = 'state-from-the-old-version'
        session.save()
        with google_api():
            response = self.complete('state-from-the-old-version')
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(self.logged_in_user_id())
        self.assertEqual(User.objects.count(), 0)
        self.login()
        self.assertIsNotNone(self.logged_in_user_id())

    @skipUnless(HAS_STATE_LIFETIME, 'nonces are written only from social-auth-core 6.2')
    def test_a_login_start_writes_one_nonce_row(self):
        self.begin()
        self.assertEqual(Nonce.objects.count(), 1)


class TheCleanupAtBoot(GoogleLogin):

    def test_it_never_removes_an_account(self):
        user = User.objects.create_user('jean.dupont', EMAIL)
        UserSocialAuth.objects.create(user=user, provider=PROVIDER, uid=EMAIL)
        call_command('clearsocial')
        self.assertEqual(UserSocialAuth.objects.filter(user=user).count(), 1)

    @skipUnless(HAS_STATE_LIFETIME, 'nonce timestamps are Unix seconds from social-django 7.2')
    def test_it_drops_old_nonces_and_keeps_recent_ones(self):
        now = int(time.time())
        Nonce.objects.create(server_url='scope', timestamp=now - 20 * 86400, salt='old')
        Nonce.objects.create(server_url='scope', timestamp=now - 60, salt='recent')
        call_command('clearsocial')
        self.assertEqual(list(Nonce.objects.values_list('salt', flat=True)), ['recent'])
