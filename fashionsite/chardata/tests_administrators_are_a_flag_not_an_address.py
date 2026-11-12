# -*- coding: utf-8 -*-
"""An address on an account grants nothing: administrators carry the account flag."""
import importlib
from unittest import mock

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from chardata.models import Char
from chardata.util import char_belongs_to_user, request_by_super_user

LISTED = 'owner.of.the.site@test.local'

migration = importlib.import_module('chardata.migrations.0050_superusers_by_flag')


def request_from(user):
    request = RequestFactory().get('/')
    request.user = user
    return request


class TheListedAddressGrantsNothing(TestCase):

    def setUp(self):
        patch = mock.patch.dict(settings.GEN_CONFIGS, {'SUPER_USERS_EMAILS': [LISTED]})
        patch.start()
        self.addCleanup(patch.stop)

    def test_an_account_holding_the_listed_address_is_an_ordinary_account(self):
        visitor = User.objects.create_user('visitor', LISTED, 'pw-42-solid')
        self.assertFalse(request_by_super_user(request_from(visitor)))

    def test_an_account_holding_the_listed_address_cannot_read_someone_elses_build(self):
        owner = User.objects.create_user('owner', 'owner@test.local', 'pw-42-solid')
        build = Char(owner=owner, name='private')
        visitor = User.objects.create_user('visitor', LISTED, 'pw-42-solid')
        self.assertFalse(char_belongs_to_user(request_from(visitor), build))

    def test_the_account_flag_is_what_makes_an_administrator(self):
        admin = User.objects.create_user('admin', 'other@test.local', 'pw-42-solid',
                                         is_superuser=True)
        self.assertTrue(request_by_super_user(request_from(admin)))

    def test_an_anonymous_visitor_is_no_administrator(self):
        self.assertFalse(request_by_super_user(request_from(AnonymousUser())))


class TheMigrationFlagsOnlyTheListedAccounts(TestCase):

    def run_it(self, listed):
        with mock.patch.dict(settings.GEN_CONFIGS, {'SUPER_USERS_EMAILS': listed}):
            migration.flag_the_listed_accounts(apps, None)

    def test_every_account_holding_the_exact_address_is_flagged(self):
        by_password = User.objects.create_user('a', LISTED, 'pw-42-solid')
        by_google = User.objects.create_user('b', LISTED, 'pw-42-solid')
        other = User.objects.create_user('c', 'other@test.local', 'pw-42-solid')
        self.run_it([LISTED])
        for user, expected in ((by_password, True), (by_google, True), (other, False)):
            user.refresh_from_db()
            self.assertEqual(user.is_superuser, expected, user.username)

    def test_a_variant_the_database_collation_matches_is_not_flagged(self):
        exact = User.objects.create_user('a', LISTED, 'pw-42-solid')
        variant = User.objects.create_user('b', 'ówner.of.the.site@test.local', 'pw-42-solid')
        with mock.patch.object(User.objects, 'filter', return_value=[exact, variant]):
            self.run_it([LISTED])
        exact.refresh_from_db()
        variant.refresh_from_db()
        self.assertTrue(exact.is_superuser)
        self.assertFalse(variant.is_superuser)

    def test_the_placeholder_of_a_fresh_install_flags_nobody(self):
        user = User.objects.create_user('a', migration.PLACEHOLDER_ADDRESS, 'pw-42-solid')
        self.run_it([migration.PLACEHOLDER_ADDRESS])
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)

    def test_a_config_without_the_list_flags_nobody(self):
        user = User.objects.create_user('a', LISTED, 'pw-42-solid')
        self.run_it([])
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
