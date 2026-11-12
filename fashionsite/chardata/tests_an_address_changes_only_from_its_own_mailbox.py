# -*- coding: utf-8 -*-
"""A new address on an account takes effect only from the page behind the link mailed to it."""
import re
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from social_django.models import UserSocialAuth

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
        self.save_address('elsewhere@test.local')
        self.assertEqual(len(mail.outbox), sent + 1)

    def test_one_mailbox_is_not_flooded_from_many_accounts(self):
        for index in range(manage_account_view.EMAIL_CHANGE_MAX_PER_ADDRESS + 2):
            account = User.objects.create_user('account%d' % index, 'a%d@test.local' % index,
                                               'pw-42-solid')
            self.client.force_login(account)
            self.save_address(NEW)
        self.assertEqual(len(mail.outbox), manage_account_view.EMAIL_CHANGE_MAX_PER_ADDRESS)

    def test_one_caller_cannot_mail_mailboxes_from_many_accounts(self):
        for index in range(manage_account_view.EMAIL_CHANGE_MAX_PER_IP + 2):
            account = User.objects.create_user('account%d' % index, 'a%d@test.local' % index,
                                               'pw-42-solid')
            self.client.force_login(account)
            self.save_address('target%d@test.local' % index)
        self.assertEqual(len(mail.outbox), manage_account_view.EMAIL_CHANGE_MAX_PER_IP)

    def test_the_mail_names_the_account(self):
        self.save_address(NEW)
        self.assertIn('someone', mail.outbox[-1].body)

    def test_an_anonymous_post_sends_nothing(self):
        self.client.logout()
        response = self.client.post('/saveaccount/', {'email': NEW})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(mail.outbox, [])


class OpeningTheLink(_AnAccount):

    def test_opening_the_link_changes_nothing(self):
        self.save_address(NEW)
        link = self.mailed_link()
        self.client.logout()
        response = self.client.get(link)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Use %s as the email address of the account someone?' % NEW)
        self.assertContains(response, 'noindex')
        self.assertEqual(self.stored_address(), FORMER)

    def test_a_post_without_the_page_token_changes_nothing(self):
        self.save_address(NEW)
        response = Client(enforce_csrf_checks=True).post(self.mailed_link())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.stored_address(), FORMER)

    def test_the_button_works_from_the_page_it_is_on(self):
        self.save_address(NEW)
        link = self.mailed_link()
        browser = Client(enforce_csrf_checks=True)
        page = browser.get(link).content.decode()
        token = re.search(r'csrfmiddlewaretoken"?[^>]*?value="?([^"\s>]+)', page).group(1)
        browser.post(link, {'csrfmiddlewaretoken': token})
        self.assertEqual(self.stored_address(), NEW)

    def test_the_address_changes_and_the_redirect_drops_the_token(self):
        self.save_address(NEW)
        response = self.client.post(self.mailed_link())
        self.assertEqual(self.stored_address(), NEW)
        self.assertRedirects(response, '/email_change/ok/')

    def test_it_works_from_a_browser_that_is_not_logged_in(self):
        self.save_address(NEW)
        link = self.mailed_link()
        self.client.logout()
        self.client.post(link)
        self.assertEqual(self.stored_address(), NEW)

    def test_the_former_address_is_told(self):
        self.save_address(NEW)
        self.client.post(self.mailed_link())
        self.assertEqual(mail.outbox[-1].to, [FORMER])
        self.assertNotIn('confirm_email_change', mail.outbox[-1].body)

    def test_a_second_opening_after_the_change_is_refused(self):
        self.save_address(NEW)
        link = self.mailed_link()
        self.client.post(link)
        response = self.client.get(link)
        self.assertRedirects(response, '/email_change/invalid/')

    def test_a_used_link_stays_dead_after_a_round_trip(self):
        self.save_address(NEW)
        first = self.mailed_link()
        self.client.post(first)
        self.save_address(FORMER)
        self.client.post(self.mailed_link())
        self.assertEqual(self.stored_address(), FORMER)
        response = self.client.post(first)
        self.assertRedirects(response, '/email_change/invalid/')
        self.assertEqual(self.stored_address(), FORMER)

    def test_an_unused_link_stays_dead_after_a_round_trip(self):
        self.save_address(NEW)
        unused = self.mailed_link()
        self.save_address('third@test.local')
        self.client.post(self.mailed_link())
        self.save_address(FORMER)
        self.client.post(self.mailed_link())
        self.assertEqual(self.stored_address(), FORMER)
        response = self.client.post(unused)
        self.assertRedirects(response, '/email_change/invalid/')
        self.assertEqual(self.stored_address(), FORMER)

    def test_a_password_change_ends_the_link(self):
        self.save_address(NEW)
        link = self.mailed_link()
        self.user.set_password('another-pw-42')
        self.user.save()
        response = self.client.post(link)
        self.assertRedirects(response, '/email_change/invalid/')
        self.assertEqual(self.stored_address(), FORMER)

    def test_an_address_of_another_password_account_is_refused(self):
        self.save_address(NEW)
        link = self.mailed_link()
        User.objects.create_user('holder', NEW, 'pw-42-solid')
        for response in (self.client.get(link), self.client.post(link)):
            self.assertRedirects(response, '/email_change/taken/')
        self.assertEqual(self.stored_address(), FORMER)

    def test_an_address_of_a_google_account_is_accepted(self):
        self.save_address(NEW)
        link = self.mailed_link()
        holder = User.objects.create_user('holder', NEW, 'pw-42-solid')
        UserSocialAuth.objects.create(user=holder, provider='google-oauth2', uid='holder')
        self.client.post(link)
        self.assertEqual(self.stored_address(), NEW)

    def test_an_address_changed_since_ends_the_older_link(self):
        self.save_address(NEW)
        older = self.mailed_link()
        self.save_address('third@test.local')
        self.client.post(self.mailed_link())
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
            self.client.post(self.mailed_link())
        self.assertEqual(self.stored_address(), NEW)


class TheAccountPage(_AnAccount):

    def test_it_has_the_place_for_the_notice(self):
        self.assertContains(self.client.get('/manageaccount/'), 'id="email-notice"')

    def test_the_result_pages_are_not_indexed(self):
        for outcome in ('ok', 'invalid', 'taken'):
            self.assertContains(self.client.get('/email_change/%s/' % outcome), 'noindex')

    def test_an_unknown_outcome_has_no_page(self):
        self.assertEqual(self.client.get('/email_change/whatever/').status_code, 404)

    def test_robots_keeps_crawlers_out_of_both_routes(self):
        robots = self.client.get('/robots.txt').content.decode()
        for route in ('confirm_email_change', 'email_change'):
            self.assertIn('Disallow: /%s/' % route, robots)
            self.assertIn('Disallow: /*/%s/' % route, robots)
