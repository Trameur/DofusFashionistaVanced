# -*- coding: utf-8 -*-
"""A Google account's username is its address's local part: it stays out of every public door."""
import importlib

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase
from social_django.models import UserSocialAuth

from chardata.models import UserAlias, public_handle

LOCAL_PART = 'jean.dupont'

migration = importlib.import_module('chardata.migrations.0051_google_accounts_get_a_public_name')


def google_account(username=LOCAL_PART, uid='1'):
    user = User.objects.create_user(username, username + '@gmail.test')
    UserSocialAuth.objects.create(user=user, provider='google-oauth2', uid=uid)
    return user


def alias_of(user):
    return UserAlias.objects.get(user=user).alias


class TheMigration(TestCase):

    def run_it(self):
        migration.name_the_google_accounts(apps, None)

    def test_an_account_without_a_row_gets_its_handle(self):
        user = google_account()
        self.run_it()
        self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_an_empty_and_a_blank_alias_get_the_handle(self):
        empty = google_account('a', '1')
        blank = google_account('b', '2')
        missing = google_account('c', '3')
        UserAlias.objects.create(user=empty, alias='')
        UserAlias.objects.create(user=blank, alias='   ')
        UserAlias.objects.create(user=missing, alias=None)
        self.run_it()
        for user in (empty, blank, missing):
            self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_a_chosen_alias_is_never_touched(self):
        user = google_account()
        UserAlias.objects.create(user=user, alias='Chosen')
        self.run_it()
        self.assertEqual(alias_of(user), 'Chosen')

    def test_the_other_settings_of_the_row_survive(self):
        user = google_account()
        UserAlias.objects.create(user=user, alias='', notify_comments=False, language='fr',
                                 preview_size=150)
        self.run_it()
        row = UserAlias.objects.get(user=user)
        self.assertEqual((row.notify_comments, row.language, row.preview_size),
                         (False, 'fr', 150))

    def test_a_password_account_is_left_alone(self):
        user = User.objects.create_user('chosen-name', 'p@test.local', 'pw-42-solid')
        self.run_it()
        self.assertFalse(UserAlias.objects.filter(user=user).exists())

    def test_running_it_twice_changes_nothing(self):
        user = google_account()
        self.run_it()
        self.run_it()
        self.assertEqual(UserAlias.objects.filter(user=user).count(), 1)
        self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_the_reverse_clears_handles_only(self):
        handled = google_account('a', '1')
        chosen = google_account('b', '2')
        UserAlias.objects.create(user=chosen, alias='Player0')
        self.run_it()
        migration.clear_the_handles(apps, None)
        self.assertIsNone(alias_of(handled))
        self.assertEqual(alias_of(chosen), 'Player0')


class LoggingIn(TestCase):

    def test_a_new_google_account_gets_its_handle(self):
        user = google_account()
        self.client.force_login(user)
        self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_a_chosen_alias_survives_the_login(self):
        user = google_account()
        UserAlias.objects.create(user=user, alias='Chosen')
        self.client.force_login(user)
        self.assertEqual(alias_of(user), 'Chosen')

    def test_a_password_account_gets_no_handle(self):
        user = User.objects.create_user('chosen-name', 'p@test.local', 'pw-42-solid')
        self.client.force_login(user)
        self.assertNotEqual(alias_of(user), public_handle(user.pk))


class ThePublicDoors(TestCase):

    def test_the_profile_no_longer_opens_with_the_local_part(self):
        google_account()
        self.assertEqual(self.client.get('/user/%s/' % LOCAL_PART).status_code, 404)

    def test_the_profile_opens_with_the_handle(self):
        user = google_account()
        self.client.force_login(user)
        self.client.logout()
        page = self.client.get('/user/%s/' % public_handle(user.pk))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, LOCAL_PART)

    def test_a_password_account_keeps_its_profile_by_username(self):
        User.objects.create_user('chosen-name', 'p@test.local', 'pw-42-solid')
        self.assertEqual(self.client.get('/user/chosen-name/').status_code, 200)

    def test_clearing_the_alias_returns_to_the_handle(self):
        user = google_account()
        self.client.force_login(user)
        answer = self.client.post('/saveaccount/', {'alias': ''}).json()
        self.assertEqual(answer['alias'], public_handle(user.pk))

    def test_the_account_page_offers_the_handle_not_the_local_part(self):
        user = google_account()
        self.client.force_login(user)
        self.assertContains(self.client.get('/manageaccount/'),
                            'var alias = "%s"' % public_handle(user.pk))

    def test_a_google_account_may_pick_its_handle_back(self):
        user = google_account()
        self.client.force_login(user)
        self.client.post('/saveaccount/', {'alias': 'Other'})
        answer = self.client.post('/saveaccount/', {'alias': public_handle(user.pk)}).json()
        self.assertEqual(answer['alias_notice'], '')
        self.assertEqual(answer['alias'], public_handle(user.pk))
