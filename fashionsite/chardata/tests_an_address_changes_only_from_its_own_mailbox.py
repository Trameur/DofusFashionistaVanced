# -*- coding: utf-8 -*-
"""A new address on an account takes effect only once the link mailed to it is opened."""
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from chardata import manage_account_view

FORMER = 'former@test.local'
NEW = 'new@test.local'


class _AnAccount(TestCase):

    def setUp(self):
        mail.outbox = []
        self.user = User.objects.create_user('someone', FORMER, 'pw-42-solid')
        self.client.force_login(self.user)

    def save_address(self, address):
        response = self.client.post('/saveaccount/', {'alias': 'someone', 'email': address})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def mailed_link(self):
        match = re.search(r'https?://\S+/confirm_email_change/\S+', mail.outbox[-1].body)
        self.assertIsNotNone(match, mail.outbox[-1].body)
        return match.group(0)

    def stored_address(self):
        self.user.refresh_from_db()
        return self.user.email


class SavingANewAddress(_AnAccount):

    def test_the_stored_address_does_not_move(self):
        answer = self.save_address(NEW)
        self.assertEqual(self.stored_address(), FORMER)
        self.assertEqual(answer['email'], FORMER)

    def test_the_link_goes_to_the_new_address_only(self):
        self.save_address(NEW)
        self.assertEqual([message.to for message in mail.outbox], [[NEW]])

    def test_the_page_is_told_the_link_was_sent(self):
        self.assertIn(NEW, self.save_address(NEW)['email_notice'])

    def test_saving_the_same_address_sends_nothing(self):
        answer = self.save_address(FORMER)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(answer['email_notice'], '')

    def test_a_malformed_address_sends_nothing(self):
        self.save_address('junk-without-at')
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.stored_address(), FORMER)

    def test_a_refused_connection_answers_the_page_and_changes_nothing(self):
        with mock.patch('chardata.manage_account_view.send_mail', side_effect=OSError):
            answer = self.save_address(NEW)
        self.assertTrue(answer['email_notice'])
        self.assertNotIn(NEW, answer['email_notice'])
        self.assertEqual(self.stored_address(), FORMER)

    def test_a_fourth_request_in_the_hour_sends_nothing(self):
        for _ in range(manage_account_view.EMAIL_CHANGE_MAX_PER_USER):
            self.save_address(NEW)
        sent = len(mail.outbox)
        answer = self.save_address(NEW)
        self.assertEqual(len(mail.outbox), sent)
        self.assertNotIn(NEW, answer['email_notice'])

    def test_the_limit_of_one_account_leaves_another_alone(self):
        for _ in range(manage_account_view.EMAIL_CHANGE_MAX_PER_USER):
            self.save_address(NEW)
        other = User.objects.create_user('another', 'another@test.local', 'pw-42-solid')
        self.client.force_login(other)
        sent = len(mail.outbox)
        self.save_address(NEW)
        self.assertEqual(len(mail.outbox), sent + 1)

    def test_an_anonymous_post_sends_nothing(self):
        self.client.logout()
        response = self.client.post('/saveaccount/', {'email': NEW})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(mail.outbox, [])


class OpeningTheLink(_AnAccount):

    def test_the_address_changes_and_the_redirect_drops_the_token(self):
        self.save_address(NEW)
        response = self.client.get(self.mailed_link())
        self.assertEqual(self.stored_address(), NEW)
        self.assertRedirects(response, '/email_change/ok/')

    def test_it_works_from_a_browser_that_is_not_logged_in(self):
        self.save_address(NEW)
        link = self.mailed_link()
        self.client.logout()
        self.client.get(link)
        self.assertEqual(self.stored_address(), NEW)

    def test_the_former_address_is_told(self):
        self.save_address(NEW)
        self.client.get(self.mailed_link())
        self.assertEqual(mail.outbox[-1].to, [FORMER])
        self.assertNotIn('confirm_email_change', mail.outbox[-1].body)

    def test_a_second_opening_after_the_change_is_refused(self):
        self.save_address(NEW)
        link = self.mailed_link()
        self.client.get(link)
        response = self.client.get(link)
        self.assertRedirects(response, '/email_change/invalid/')

    def test_an_address_changed_since_ends_the_older_link(self):
        self.save_address(NEW)
        older = self.mailed_link()
        self.save_address('third@test.local')
        self.client.get(self.mailed_link())
        response = self.client.get(older)
        self.assertRedirects(response, '/email_change/invalid/')
        self.assertEqual(self.stored_address(), 'third@test.local')

    def test_an_expired_link_is_refused(self):
        self.save_address(NEW)
        link = self.mailed_link()
        with mock.patch('chardata.manage_account_view.EMAIL_CHANGE_MAX_AGE', -1):
            response = self.client.get(link)
        self.assertRedirects(response, '/email_change/invalid/')
        self.assertEqual(self.stored_address(), FORMER)

    def test_a_forged_link_is_refused(self):
        self.save_address(NEW)
        link = self.mailed_link()
        response = self.client.get(link[:-3] + 'abc/')
        self.assertRedirects(response, '/email_change/invalid/')
        self.assertEqual(self.stored_address(), FORMER)

    def test_a_link_for_a_deleted_account_is_refused(self):
        self.save_address(NEW)
        link = self.mailed_link()
        self.user.delete()
        response = self.client.get(link)
        self.assertRedirects(response, '/email_change/invalid/')

    def test_a_failed_notice_does_not_undo_the_change(self):
        self.save_address(NEW)
        with mock.patch('chardata.manage_account_view.send_mail', side_effect=OSError):
            self.client.get(self.mailed_link())
        self.assertEqual(self.stored_address(), NEW)


class TheAccountPage(_AnAccount):

    def test_it_has_the_place_for_the_notice(self):
        self.assertContains(self.client.get('/manageaccount/'), 'id="email-notice"')

    def test_the_result_pages_are_not_indexed(self):
        for outcome in ('ok', 'invalid'):
            self.assertContains(self.client.get('/email_change/%s/' % outcome), 'noindex')

    def test_an_unknown_outcome_has_no_page(self):
        self.assertEqual(self.client.get('/email_change/whatever/').status_code, 404)

    def test_robots_keeps_crawlers_out_of_both_routes(self):
        robots = self.client.get('/robots.txt').content.decode()
        self.assertIn('Disallow: */confirm_email_change/', robots)
        self.assertIn('Disallow: */email_change/', robots)
