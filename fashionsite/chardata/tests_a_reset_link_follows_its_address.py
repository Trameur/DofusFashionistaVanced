# -*- coding: utf-8 -*-
"""A reset link is good for the address it went to, and a private address does not reach Google."""
import re
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from chardata.login_view import _generate_token_for_password_reset
from chardata.manage_account_view import _email_change_token

ADDRESS = 'someone@test.local'


class TheResetMail(TestCase):

    def setUp(self):
        mail.outbox = []
        self.user = User.objects.create_user('someone', ADDRESS, 'pw-42-solid')

    def ask(self, typed):
        return self.client.post(reverse('recover_password_page'), {'email': typed})

    def test_a_stray_space_still_finds_the_account(self):
        self.ask(' %s ' % ADDRESS)
        self.assertEqual([message.to for message in mail.outbox], [[ADDRESS]])

    def test_only_spaces_find_nothing(self):
        self.ask('   ')
        self.assertEqual(mail.outbox, [])

    def test_the_mailed_link_opens_the_form(self):
        self.ask(ADDRESS)
        link = re.search(r'https?://\S+', mail.outbox[-1].body).group(0)
        self.assertEqual(self.client.get(link).status_code, 200)

    def test_a_changed_address_ends_the_link(self):
        token = _generate_token_for_password_reset('someone', self.user.password, ADDRESS)
        link = reverse('recover_password', args=('someone', token))
        self.assertEqual(self.client.get(link).status_code, 200)
        self.user.email = 'elsewhere@test.local'
        self.user.save()
        self.assertEqual(self.client.get(link).status_code, 403)


class PagesWithAPrivateAddress(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('someone', ADDRESS, 'pw-42-solid')
        patched = mock.patch.dict(settings.GEN_CONFIGS, {'google_analytics_id': 'G-PINNED'})
        patched.start()
        self.addCleanup(patched.stop)

    def assert_private(self, response, status=200):
        self.assertEqual(response.status_code, status)
        self.assertNotContains(response, 'googletagmanager', status_code=status)
        self.assertContains(response, 'content="strict-origin"', status_code=status)

    def test_an_ordinary_page_keeps_its_analytics_and_referrer(self):
        response = self.client.get('/email_change/ok/')
        self.assertContains(response, 'googletagmanager')
        self.assertNotContains(response, 'content="strict-origin"')

    def test_the_confirmed_page_holding_a_username(self):
        self.assert_private(
            self.client.get(reverse('email_confirmed_page', args=('someone', 'no'))))

    def test_the_not_found_page_of_a_confirmed_url(self):
        self.assert_private(
            self.client.get(reverse('email_confirmed_page', args=('nobody', 'no'))), 404)

    def test_the_forbidden_page_of_a_dead_reset_link(self):
        self.assert_private(
            self.client.get(reverse('recover_password', args=('someone', 'dead-token'))), 403)

    def test_the_reset_form_holding_a_token(self):
        token = _generate_token_for_password_reset('someone', self.user.password, ADDRESS)
        link = reverse('recover_password', args=('someone', token))
        self.assert_private(self.client.get(link))
        self.assert_private(self.client.post(link, {'new_password': ''}))

    def test_the_page_after_the_reset(self):
        token = _generate_token_for_password_reset('someone', self.user.password, ADDRESS)
        link = reverse('recover_password', args=('someone', token))
        self.assert_private(self.client.post(link, {
            'new_password': 'pw-43-solid', 'confirm_password': 'pw-43-solid'}))

    def test_the_confirm_page_holding_a_token(self):
        link = reverse('confirm_email_change',
                       args=(_email_change_token(self.user, 'new@test.local'),))
        self.assert_private(self.client.get(link))
