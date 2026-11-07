# -*- coding: utf-8 -*-
"""Nothing is deleted before the owner proves the account is theirs, and a button on a mailed page is the only thing that deletes."""
import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.db import DatabaseError
from django.test import Client, TestCase
from django.utils import timezone
from social_django.models import UserSocialAuth

from chardata import manage_account_view
from chardata.account_deletion_fixtures import (ADDRESS, PASSWORD, a_build,
                                                a_google_account,
                                                a_password_account, mailed_link,
                                                outcome_of)
from chardata.login_view import (LOGIN_FAIL_MAX_PER_USER, LOGIN_FAIL_WINDOW,
                                 _prehash_password, _username_key)
from chardata.models import Char, RateCounter
from chardata.rate_limit import hits


class _AnAccount(TestCase):

    def setUp(self):
        mail.outbox = []
        self.user = a_password_account()
        self.client.force_login(self.user)

    def still_there(self):
        return User.objects.filter(pk=self.user.pk).exists()

    def ask_for_the_link(self):
        return self.client.post('/delete_account/')

    def type_the_password(self, password=PASSWORD, prehashed=True):
        sent = _prehash_password(password) if prehashed else password
        return self.client.post('/delete_account_password/', {'password': sent})

    def let_a_day_pass(self):
        RateCounter.objects.filter(key__in=[
            manage_account_view._deletion_hold_key(self.user),
            manage_account_view._applied_key(self.user)]).update(
            window_start=timezone.now() - datetime.timedelta(hours=25))

    def change_the_address(self, address):
        self.client.post('/saveaccount/', {'alias': 'Holder', 'email': address})
        link = mailed_link(route='confirm_email_change')
        response = self.client.post(link)
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, address)


def manage_account_view_url(user):
    from django.urls import reverse
    return reverse('confirm_account_deletion',
                   args=(manage_account_view._deletion_token(user),))


class TheActionRoutes(_AnAccount):

    def test_a_get_on_either_action_route_is_refused(self):
        self.assertEqual(self.client.get('/delete_account/').status_code, 405)
        self.assertEqual(self.client.get('/delete_account_password/').status_code, 405)
        self.assertEqual(mail.outbox, [])
        self.assertTrue(self.still_there())

    def test_an_action_post_without_csrf_is_refused(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post('/delete_account/').status_code, 403)
        self.assertEqual(strict.post('/delete_account_password/',
                                     {'password': _prehash_password(PASSWORD)}).status_code, 403)
        self.assertEqual(mail.outbox, [])

    def test_a_signed_out_visitor_is_sent_to_login(self):
        visitor = Client()
        for route in ('/delete_account/', '/delete_account_password/'):
            response = visitor.post(route, {'password': _prehash_password(PASSWORD)})
            self.assertRedirects(response, '/login_page/', fetch_redirect_response=False)
        self.assertEqual(mail.outbox, [])
        self.assertTrue(self.still_there())

    def test_the_request_mails_one_link_and_deletes_nothing(self):
        build = a_build(self.user)
        response = self.ask_for_the_link()
        self.assertEqual(outcome_of(response), 'sent')
        self.assertEqual([message.to for message in mail.outbox], [[ADDRESS]])
        self.assertTrue(self.still_there())
        build.refresh_from_db()
        self.assertFalse(build.deleted)
        self.assertEqual(build.owner_id, self.user.pk)

    def test_the_sent_page_names_the_address(self):
        page = self.client.get(self.ask_for_the_link()['Location'])
        self.assertContains(page, ADDRESS)

    def test_an_account_without_address_is_told_to_add_one(self):
        self.user.email = ''
        self.user.save()
        self.assertEqual(outcome_of(self.ask_for_the_link()), 'no_address')
        self.assertEqual(mail.outbox, [])

    def test_a_refused_connection_deletes_nothing_and_logs_no_address(self):
        with mock.patch('chardata.manage_account_view.send_mail',
                        side_effect=OSError(ADDRESS)):
            with self.assertLogs('chardata.manage_account_view', level='ERROR') as logged:
                response = self.ask_for_the_link()
        self.assertEqual(outcome_of(response), 'mail_failed')
        self.assertNotIn(ADDRESS, '\n'.join(logged.output))
        self.assertTrue(self.still_there())

    def test_a_fourth_request_in_the_hour_sends_nothing(self):
        for _ in range(manage_account_view.ACCOUNT_DELETION_MAX_PER_USER):
            self.assertEqual(outcome_of(self.ask_for_the_link()), 'sent')
        sent = len(mail.outbox)
        self.assertEqual(outcome_of(self.ask_for_the_link()), 'too_many')
        self.assertEqual(len(mail.outbox), sent)

    def test_no_counter_key_holds_the_address(self):
        self.ask_for_the_link()
        keys = list(RateCounter.objects.values_list('key', flat=True))
        self.assertTrue(keys)
        self.assertFalse([key for key in keys if 'holder@' in key])


class TheMailedLink(_AnAccount):

    def test_a_get_or_head_on_the_link_deletes_nothing(self):
        build = a_build(self.user)
        self.ask_for_the_link()
        link = mailed_link()
        self.assertEqual(self.client.get(link).status_code, 200)
        self.assertEqual(self.client.head(link).status_code, 200)
        self.assertTrue(self.still_there())
        build.refresh_from_db()
        self.assertFalse(build.deleted)

    def test_the_page_names_the_account_and_counts_the_builds(self):
        a_build(self.user, 'One')
        a_build(self.user, 'Two')
        a_build(self.user, 'Three', deleted=True)
        page = self.client.get(manage_account_view_url(self.user))
        self.assertContains(page, 'Holder')
        self.assertEqual(page.context['builds'], 2)

    def test_the_post_without_the_box_deletes_nothing(self):
        link = manage_account_view_url(self.user)
        response = self.client.post(link)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['box_missing'])
        self.assertTrue(self.still_there())

    def test_the_link_ends_after_one_hour(self):
        link = manage_account_view_url(self.user)
        with mock.patch('django.core.signing.time.time',
                        return_value=timezone.now().timestamp()
                        + manage_account_view.ACCOUNT_DELETION_MAX_AGE + 60):
            response = self.client.post(link, {'understood': '1'})
        self.assertEqual(outcome_of(response), 'invalid')
        self.assertTrue(self.still_there())

    def test_a_changed_password_ends_the_link(self):
        link = manage_account_view_url(self.user)
        self.user.set_password(_prehash_password('another-one'))
        self.user.save()
        response = self.client.post(link, {'understood': '1'})
        self.assertEqual(outcome_of(response), 'invalid')
        self.assertTrue(self.still_there())

    def test_a_changed_address_ends_the_link(self):
        link = manage_account_view_url(self.user)
        self.user.email = 'else@test.local'
        self.user.save()
        self.assertEqual(outcome_of(self.client.get(link)), 'invalid')
        self.assertEqual(outcome_of(self.client.post(link, {'understood': '1'})), 'invalid')
        self.assertTrue(self.still_there())

    def test_a_forged_link_is_invalid(self):
        response = self.client.post('/confirm_account_deletion/not-a-token/', {'understood': '1'})
        self.assertEqual(outcome_of(response), 'invalid')


class AGoogleAccount(TestCase):

    def setUp(self):
        mail.outbox = []
        self.user = a_google_account()
        self.client.force_login(self.user)

    def test_a_google_account_deletes_through_the_mail_link(self):
        self.assertEqual(outcome_of(self.client.post('/delete_account/')), 'sent')
        link = mailed_link()
        self.assertEqual(self.client.get(link).status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        response = self.client.post(link, {'understood': '1'})
        self.assertEqual(outcome_of(response), 'deleted')
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(UserSocialAuth.objects.filter(uid='42').exists())

    def test_a_google_account_is_not_offered_the_password_form(self):
        page = self.client.get('/manageaccount/').content.decode('utf-8')
        self.assertIn('delete_account/', page)
        self.assertNotIn('delete_account_password', page)

    def test_a_password_account_is_offered_both(self):
        self.client.force_login(a_password_account())
        page = self.client.get('/manageaccount/').content.decode('utf-8')
        self.assertIn('delete_account/', page)
        self.assertIn('delete_account_password', page)


class ThePasswordRoute(_AnAccount):

    def test_the_right_prehashed_password_opens_the_confirm_page_without_a_mail(self):
        response = self.type_the_password()
        self.assertEqual(response.status_code, 302)
        self.assertIn('/confirm_account_deletion/', response['Location'])
        self.assertEqual(self.client.get(response['Location']).status_code, 200)
        self.assertEqual(mail.outbox, [])
        self.assertTrue(self.still_there())

    def test_the_password_alone_deletes_nothing(self):
        build = a_build(self.user)
        self.type_the_password()
        build.refresh_from_db()
        self.assertFalse(build.deleted)
        self.assertTrue(self.still_there())

    def test_a_raw_password_is_refused(self):
        self.assertEqual(outcome_of(self.type_the_password(prehashed=False)), 'wrong_password')
        self.assertTrue(self.still_there())

    def test_a_wrong_password_deletes_nothing_and_counts_as_a_login_failure(self):
        before = hits(_username_key(self.user.username), LOGIN_FAIL_WINDOW)
        self.assertEqual(outcome_of(self.type_the_password('not-it')), 'wrong_password')
        self.assertEqual(hits(_username_key(self.user.username), LOGIN_FAIL_WINDOW), before + 1)
        self.assertTrue(self.still_there())

    def test_the_password_route_stops_at_the_login_ceiling(self):
        for _ in range(LOGIN_FAIL_MAX_PER_USER):
            self.type_the_password('not-it')
        self.assertEqual(outcome_of(self.type_the_password()), 'too_many')

    def test_a_right_password_clears_the_failures(self):
        self.type_the_password('not-it')
        self.type_the_password()
        self.assertEqual(hits(_username_key(self.user.username), LOGIN_FAIL_WINDOW), 0)

    def test_a_google_account_has_no_password_to_type(self):
        google = a_google_account('someone.else', 'someone.else@gmail.test', uid='7')
        self.client.force_login(google)
        self.assertEqual(outcome_of(self.type_the_password('')), 'wrong_password')
        self.assertTrue(User.objects.filter(pk=google.pk).exists())


class AfterAnAddressChange(_AnAccount):

    def test_every_route_is_refused_for_a_day_after_an_address_change(self):
        self.change_the_address('new@test.local')
        mail.outbox = []
        self.assertEqual(outcome_of(self.ask_for_the_link()), 'too_soon')
        self.assertEqual(outcome_of(self.type_the_password()), 'too_soon')
        link = manage_account_view_url(self.user)
        self.assertEqual(outcome_of(self.client.get(link)), 'too_soon')
        self.assertEqual(outcome_of(self.client.post(link, {'understood': '1'})), 'too_soon')
        self.assertEqual(mail.outbox, [])
        self.assertTrue(self.still_there())

    def test_the_day_passes(self):
        self.change_the_address('new@test.local')
        self.let_a_day_pass()
        self.assertIsNone(manage_account_view._deletion_refusal(self.user))

    def test_a_second_address_change_restarts_the_day(self):
        self.change_the_address('new@test.local')
        self.let_a_day_pass()
        self.assertIsNone(manage_account_view._deletion_refusal(self.user))
        self.change_the_address('newer@test.local')
        self.assertEqual(manage_account_view._deletion_refusal(self.user), 'too_soon')


class AnAdministrator(TestCase):

    def refuse_everywhere(self, user):
        mail.outbox = []
        self.client.force_login(user)
        self.assertEqual(outcome_of(self.client.post('/delete_account/')), 'refused')
        self.assertEqual(
            outcome_of(self.client.post('/delete_account_password/',
                                        {'password': _prehash_password(PASSWORD)})), 'refused')
        link = manage_account_view_url(user)
        self.assertEqual(outcome_of(self.client.get(link)), 'refused')
        self.assertEqual(outcome_of(self.client.post(link, {'understood': '1'})), 'refused')
        self.assertEqual(mail.outbox, [])
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_a_superuser_is_refused_at_every_door(self):
        user = a_password_account('boss')
        user.is_superuser = True
        user.save()
        self.refuse_everywhere(user)

    def test_a_staff_account_is_refused_at_every_door(self):
        user = a_password_account('helper')
        user.is_staff = True
        user.save()
        self.refuse_everywhere(user)

    def test_the_flag_is_read_from_a_fresh_row(self):
        user = a_password_account('late')
        self.client.force_login(user)
        link = manage_account_view_url(user)
        User.objects.filter(pk=user.pk).update(is_superuser=True)
        self.assertEqual(outcome_of(self.client.post(link, {'understood': '1'})), 'refused')
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_the_danger_zone_is_hidden_from_visitors_and_superusers(self):
        visitor = Client().get('/manageaccount/').content.decode('utf-8')
        self.assertNotIn('delete_account', visitor)
        user = a_password_account('boss')
        user.is_superuser = True
        user.save()
        self.client.force_login(user)
        admin_page = self.client.get('/manageaccount/').content.decode('utf-8')
        self.assertNotIn('delete_account', admin_page)
        ordinary = a_password_account('plain', 'plain@test.local')
        self.client.force_login(ordinary)
        self.assertIn('delete_account/', self.client.get('/manageaccount/').content.decode('utf-8'))


class TheSessionAndTheLinkStayTogether(_AnAccount):

    def test_an_old_password_hash_is_upgraded_without_ending_the_link_or_the_session(self):
        from django.contrib.auth.hashers import get_hasher
        hasher = get_hasher('pbkdf2_sha256')
        self.user.password = hasher.encode(_prehash_password(PASSWORD), 'oldsalt', iterations=1000)
        self.user.save()
        self.client.force_login(self.user)
        response = self.type_the_password()
        self.assertIn('/confirm_account_deletion/', response['Location'])
        self.user.refresh_from_db()
        self.assertGreater(int(self.user.password.split('$')[1]), 1000)
        page = self.client.get(response['Location'])
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.wsgi_request.user.is_authenticated)

    def test_a_password_link_works_only_in_the_session_that_proved_it(self):
        link = self.type_the_password()['Location']
        for visitor in (Client(), self._signed_in_as(a_password_account('neighbour', 'n@test.local'))):
            self.assertEqual(outcome_of(visitor.get(link)), 'invalid')
            self.assertEqual(outcome_of(visitor.post(link, {'understood': '1'})), 'invalid')
        self.assertTrue(self.still_there())
        self.assertEqual(self.client.post(link, {'understood': '1'}).status_code, 302)
        self.assertFalse(self.still_there())

    def test_a_password_link_dies_with_the_session(self):
        link = self.type_the_password()['Location']
        self.client.logout()
        self.assertEqual(outcome_of(self.client.post(link, {'understood': '1'})), 'invalid')
        self.assertTrue(self.still_there())

    def test_a_mailed_link_needs_no_session(self):
        self.ask_for_the_link()
        link = mailed_link()
        self.assertEqual(Client().get(link).status_code, 200)

    def _signed_in_as(self, user):
        client = Client()
        client.force_login(user)
        return client


class TheDayAfterAnAddressChange(_AnAccount):

    def test_the_address_and_its_hold_are_saved_together(self):
        self.client.post('/saveaccount/', {'alias': 'Holder', 'email': 'new@test.local'})
        link = mailed_link(route='confirm_email_change')
        mail.outbox = []
        real = manage_account_view.note_hit

        def refuse_the_hold(key, window):
            if key.startswith('account-deletion-hold:'):
                raise DatabaseError('locked')
            return real(key, window)

        self.client.raise_request_exception = False
        with mock.patch('chardata.manage_account_view.note_hit', side_effect=refuse_the_hold):
            self.assertEqual(self.client.post(link).status_code, 500)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, ADDRESS)
        self.assertEqual(hits(manage_account_view._applied_key(self.user),
                              manage_account_view.EMAIL_CHANGE_MAX_AGE), 0)
        self.assertEqual(mail.outbox, [])

    def test_an_applied_change_without_a_hold_row_still_waits_a_day(self):
        manage_account_view.note_hit(manage_account_view._applied_key(self.user),
                                     manage_account_view.EMAIL_CHANGE_MAX_AGE)
        self.assertEqual(hits(manage_account_view._deletion_hold_key(self.user),
                              manage_account_view.ACCOUNT_DELETION_HOLD), 0)
        self.assertEqual(manage_account_view._deletion_refusal(self.user), 'too_soon')


class TheConfirmPageIsNeverStored(_AnAccount):

    def test_the_page_a_signed_out_visitor_opens_forbids_storage(self):
        self.ask_for_the_link()
        page = Client().get(mailed_link())
        self.assertEqual(page.status_code, 200)
        self.assertIn('no-store', page['Cache-Control'])
