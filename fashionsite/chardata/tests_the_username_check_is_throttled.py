"""The sign-up form's name check answers too-many past a ceiling per session and per address."""
from unittest import mock

from django.test import TestCase

from chardata import login_view


class TheNameCheck(TestCase):

    def check(self, **extra):
        return self.client.post('/check_username/', {'username': 'somebody'},
                                **extra).content.decode('utf-8')

    def test_an_ordinary_check_answers_ok(self):
        self.assertEqual('ok', self.check())

    def test_the_address_ceiling_stops_the_checks(self):
        with mock.patch.object(login_view, 'NAME_CHECKS_PER_ADDRESS', 3):
            answers = [self.check() for _ in range(4)]
        self.assertEqual(['ok', 'ok', 'ok', 'too-many'], answers)

    def test_the_session_ceiling_stops_a_client_that_changes_address(self):
        self.client.cookies['csrftoken'] = 'b' * 32
        with mock.patch.object(login_view, 'NAME_CHECKS_PER_SESSION', 2):
            answers = [self.check(REMOTE_ADDR='10.0.1.%d' % i) for i in range(3)]
        self.assertEqual(['ok', 'ok', 'too-many'], answers)
