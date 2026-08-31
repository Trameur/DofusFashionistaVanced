# -*- coding: utf-8 -*-
"""Signing up, and the confirmation mail that finishes it.

The other half of the account flow. Like the password reset, its middle link is
an email, so neither `check_pages` nor `check_actions` can join the chain -- and
`register` sits behind a captcha, which is very likely why nothing tested it:
Django forces DEBUG off in tests, so the view demands a real Google answer. The
captcha check is replaced here, and nothing else is.

Four decisions in this view are worth keeping, and each has a test below:

  - the account is created **inactive**, and `local_login` says so rather than
    letting an unconfirmed address in;
  - usernames collide case-insensitively, because the MySQL index does;
  - an address that already has an account is sent to password recovery instead
    of quietly getting a second one;
  - `email_confirmed_page` echoes the username back into the page, so it 404s
    on a name that does not exist -- the url carries no token and anyone can
    put anything in it.
"""
import hashlib
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from chardata.models import UserAlias


def as_the_browser_sends_it(password):
    return hashlib.sha256(('dofusfashionista' + password).encode('utf-8')).hexdigest()


PASSWORD = as_the_browser_sends_it('a-first-password')


class ARegistrationWalk(TestCase):

    def setUp(self):
        patch = mock.patch('chardata.login_view.recaptcha_ok', return_value=True)
        patch.start()
        self.addCleanup(patch.stop)
        mail.outbox = []

    def register(self, username='newcomer', email='new@example.test'):
        return self.client.post('/register/', {'username': username,
                                               'email': email,
                                               'password': PASSWORD})

    def confirmation_link(self):
        self.assertEqual(1, len(mail.outbox), 'no welcome mail was sent')
        found = re.search(r'(/confirm_email/\S+/)', mail.outbox[0].body)
        self.assertIsNotNone(found, 'the mail carries no confirmation link:\n%s'
                             % mail.outbox[0].body)
        return found.group(1)

    def log_in(self, username='newcomer', password=PASSWORD):
        return self.client.post('/local_login/',
                                {'username': username, 'password': password}
                                ).content.decode('utf-8')

    def test_the_whole_walk(self):
        response = self.register()
        self.assertEqual(302, response.status_code)
        self.assertIn('check_your_email', response['Location'])

        user = User.objects.get(username='newcomer')
        self.assertFalse(user.is_active, 'the account was live before the mail')
        self.assertTrue(UserAlias.objects.filter(user=user).exists(),
                        'no alias was made for the new account')

        self.assertEqual('confirm-email', self.log_in(),
                         'an unconfirmed address could sign in')

        self.assertEqual(302, self.client.get(self.confirmation_link()).status_code)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual('ok', self.log_in(), 'the confirmed account cannot sign in')

    def test_a_wrong_token_leaves_the_account_shut(self):
        self.register()
        link = self.confirmation_link()
        head, token = link.rstrip('/').rsplit('/', 1)
        forged = '%s/%s/' % (head, token[:-1] + ('a' if token[-1] != 'a' else 'b'))
        self.assertIn('invalid token',
                      self.client.get(forged).content.decode('utf-8'))
        self.assertFalse(User.objects.get(username='newcomer').is_active)

    def test_the_same_name_in_another_case_is_refused(self):
        self.register(username='Newcomer')
        self.assertEqual(403, self.register(username='newcomer').status_code)
        self.assertEqual(1, User.objects.filter(username__iexact='newcomer').count())

    def test_an_address_that_already_has_an_account_goes_to_recovery(self):
        self.register()
        mail.outbox = []
        response = self.register(username='another-name')
        self.assertEqual(302, response.status_code)
        self.assertIn('recover_password', response['Location'],
                      'a second account was made for the same address')
        self.assertFalse(User.objects.filter(username='another-name').exists())

    def test_confirming_twice_is_not_an_error(self):
        """The link lives in an inbox; a second click must not break."""
        self.register()
        link = self.confirmation_link()
        self.client.get(link)
        second = self.client.get(link)
        self.assertEqual(302, second.status_code)
        self.assertIn('yes', second['Location'],
                      'the second visit does not say the account was already on')

    def test_the_confirmed_page_refuses_a_name_it_does_not_know(self):
        """It echoes the url segment into the page and carries no token."""
        self.assertEqual(404, self.client.get(
            '/email_confirmed/nobody-at-all/no/').status_code)

    def test_a_mail_server_that_refuses_the_connection_leaves_no_half_account(self):
        """A refused connection is a bare OSError, not an SMTPException.

        The view only caught the smtplib family, so an unreachable mail server
        answered 500 with the inactive account still in the table -- and the
        visitor who tried again was told their chosen name was taken, by an
        account they could never confirm.
        """
        with mock.patch('chardata.login_view.send_mail',
                        side_effect=ConnectionRefusedError('smtp is down')):
            response = self.register()
        self.assertEqual(200, response.status_code,
                         'an unreachable mail server still takes the page down')
        self.assertFalse(User.objects.filter(username='newcomer').exists(),
                         'an account survived a mail that never went out')

    def test_the_name_is_free_again_after_a_mail_failure(self):
        """The half that matters to the reader: they can try again."""
        with mock.patch('chardata.login_view.send_mail',
                        side_effect=ConnectionRefusedError('smtp is down')):
            self.register()
        mail.outbox = []
        self.assertEqual(302, self.register().status_code,
                         'the name they chose is still taken')
        self.assertEqual(1, len(mail.outbox))
