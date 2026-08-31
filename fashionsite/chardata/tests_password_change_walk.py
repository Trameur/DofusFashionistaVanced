# -*- coding: utf-8 -*-
"""Changing your password from the account page, and still getting back in.

Three places have to agree on where a password gets hashed, and they disagree
on purpose:

  - `login.js` hashes before posting, both for signing in and for the change
    form -- so `change_password` stores what it receives;
  - the reset form posts the **raw** password and `recover_password` hashes it
    itself.

Get that backwards in either direction and the symptom is the same and silent:
the change reports success, and the account can never be signed into again. The
reader is locked out of their own account by a page that told them it worked.

Nothing covered the change path. These tests use the browser's hash, exactly as
login.js sends it, and check that signing in still works afterwards.
"""
import hashlib

from django.contrib.auth.models import User
from django.test import TestCase


def as_the_browser_sends_it(password):
    return hashlib.sha256(('dofusfashionista' + password).encode('utf-8')).hexdigest()


OLD = 'the-old-one'
NEW = 'the-new-one'


class APasswordChangeWalk(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'holder', 'h@example.test', as_the_browser_sends_it(OLD))
        self.user.is_active = True
        self.user.save()

    def change(self, old, new):
        return self.client.post('/change_password/', {
            'username': 'holder',
            'password': as_the_browser_sends_it(old),
            'newPassword': as_the_browser_sends_it(new),
        }).content.decode('utf-8')

    def log_in(self, password):
        self.client.post('/logout/')
        return self.client.post('/local_login/', {
            'username': 'holder',
            'password': as_the_browser_sends_it(password),
        }).content.decode('utf-8')

    def test_the_new_password_opens_the_account(self):
        self.assertEqual('ok', self.change(OLD, NEW))
        self.assertEqual('ok', self.log_in(NEW),
                         'the change reported success and locked the account')
        self.assertEqual('invalid', self.log_in(OLD),
                         'the old password still opens the account')

    def test_a_wrong_current_password_changes_nothing(self):
        self.assertNotEqual('ok', self.change('not-the-old-one', NEW))
        self.assertEqual('ok', self.log_in(OLD),
                         'a refused change altered the password anyway')

    def test_guessing_is_throttled(self):
        """The counters exist because nothing else limited the guessing."""
        answers = [self.change('wrong-%d' % i, NEW) for i in range(15)]
        self.assertIn('too-many', answers,
                      'an unlimited number of passwords can be tried here')

    def test_the_throttle_does_not_shut_out_the_owner_first(self):
        """The half that keeps the other honest: a limit set to zero would
        pass the test above and lock everyone out."""
        self.assertEqual('ok', self.change(OLD, NEW))
