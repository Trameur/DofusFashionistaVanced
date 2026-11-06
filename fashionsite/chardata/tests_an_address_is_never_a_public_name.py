# -*- coding: utf-8 -*-
"""An address typed as a username was copied into the public name: it stays private."""
import importlib
from unittest import mock

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import UserAlias, public_handle
from chardata.public_name import default_public_name, looks_like_an_address

ADDRESS = 'someone@mail.test'

migration = importlib.import_module('chardata.migrations.0052_addresses_are_not_public_names')


def alias_of(user):
    return UserAlias.objects.get(user=user).alias


class TheShape(TestCase):

    def test_an_address_is_recognised(self):
        self.assertTrue(looks_like_an_address('a.b+c@sub.mail.test'))

    def test_a_name_with_an_at_sign_is_not_an_address(self):
        for name in ('bob@home', '@bob', 'bob@', 'a b@mail.test', 'a@b@mail.test'):
            self.assertFalse(looks_like_an_address(name), name)


class TheMigration(TestCase):

    def run_it(self):
        migration.hide_the_addresses(apps, None)

    def test_an_alias_copied_from_the_address_becomes_the_handle(self):
        user = User.objects.create_user(ADDRESS, ADDRESS, 'pw-42-solid')
        UserAlias.objects.create(user=user, alias=ADDRESS)
        self.run_it()
        self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_another_address_as_alias_becomes_the_handle(self):
        user = User.objects.create_user('plain', 'p@mail.test', 'pw-42-solid')
        UserAlias.objects.create(user=user, alias='former@mail.test')
        self.run_it()
        self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_an_address_username_without_a_row_gets_the_handle(self):
        user = User.objects.create_user(ADDRESS, ADDRESS, 'pw-42-solid')
        self.run_it()
        self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_an_address_username_with_a_blank_alias_gets_the_handle(self):
        user = User.objects.create_user(ADDRESS, ADDRESS, 'pw-42-solid')
        UserAlias.objects.create(user=user, alias=' ')
        self.run_it()
        self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_an_address_username_keeps_a_chosen_alias(self):
        user = User.objects.create_user(ADDRESS, ADDRESS, 'pw-42-solid')
        UserAlias.objects.create(user=user, alias='Chosen')
        self.run_it()
        self.assertEqual(alias_of(user), 'Chosen')

    def test_a_name_with_an_at_sign_is_kept(self):
        user = User.objects.create_user('plain', 'p@mail.test', 'pw-42-solid')
        UserAlias.objects.create(user=user, alias='bob@home')
        self.run_it()
        self.assertEqual(alias_of(user), 'bob@home')

    def test_the_login_with_the_address_keeps_working(self):
        user = User.objects.create_user(ADDRESS, ADDRESS, 'pw-42-solid')
        UserAlias.objects.create(user=user, alias=ADDRESS)
        self.run_it()
        user.refresh_from_db()
        self.assertEqual(user.username, ADDRESS)
        self.assertTrue(user.check_password('pw-42-solid'))


class SigningUp(TestCase):

    def test_an_address_as_username_is_not_copied_into_the_public_name(self):
        with mock.patch('chardata.login_view.recaptcha_ok', return_value=True):
            response = self.client.post('/register/', {
                'username': ADDRESS, 'password': 'pw-42-solid', 'email': ADDRESS})
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email=ADDRESS)
        self.assertEqual(user.username, ADDRESS)
        self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_a_plain_username_is_still_the_public_name(self):
        with mock.patch('chardata.login_view.recaptcha_ok', return_value=True):
            self.client.post('/register/', {
                'username': 'plain', 'password': 'pw-42-solid', 'email': ADDRESS})
        self.assertEqual(alias_of(User.objects.get(email=ADDRESS)), 'plain')


class TheAccountPage(TestCase):

    def test_an_address_is_refused_and_the_page_is_told(self):
        user = User.objects.create_user('plain', 'p@mail.test', 'pw-42-solid')
        self.client.force_login(user)
        self.client.post('/saveaccount/', {'alias': 'nick'})
        answer = self.client.post('/saveaccount/', {'alias': ADDRESS}).json()
        self.assertEqual(answer['alias'], 'nick')
        self.assertTrue(answer['alias_notice'])
        self.assertEqual(alias_of(user), 'nick')

    def test_clearing_the_alias_of_an_address_username_gives_the_handle(self):
        user = User.objects.create_user(ADDRESS, ADDRESS, 'pw-42-solid')
        self.client.force_login(user)
        answer = self.client.post('/saveaccount/', {'alias': ''}).json()
        self.assertEqual(answer['alias'], public_handle(user.pk))


class ThePublicDoors(TestCase):

    def test_the_profile_does_not_open_with_the_address(self):
        User.objects.create_user(ADDRESS, ADDRESS, 'pw-42-solid')
        self.assertEqual(self.client.get('/user/%s/' % ADDRESS).status_code, 404)

    def test_logging_in_gives_the_handle_to_a_blank_alias(self):
        user = User.objects.create_user(ADDRESS, ADDRESS, 'pw-42-solid')
        self.client.force_login(user)
        self.assertEqual(alias_of(user), public_handle(user.pk))

    def test_the_default_of_a_plain_username_is_itself(self):
        user = User.objects.create_user('plain', 'p@mail.test', 'pw-42-solid')
        self.assertEqual(default_public_name(user), 'plain')
