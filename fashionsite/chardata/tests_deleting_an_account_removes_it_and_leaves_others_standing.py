# -*- coding: utf-8 -*-
"""A deleted account leaves no row that points at it, no readable build and no usable link, and takes nobody else's work with it."""
from unittest import mock

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.core import mail
from django.db import DatabaseError
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from chardata import manage_account_view
from chardata.account_deletion import destroy_account, forget_the_names
from chardata.account_deletion_fixtures import (ADDRESS, a_build, a_password_account,
                                                fill_every_relation, mailed_link,
                                                outcome_of)
from chardata.encoded_char_id import encode_char_id
from chardata.login_view import (_generate_token_for_user, _prehash_password,
                                 note_login_failure, note_reset_mail_sent)
from chardata.models import (BuildComment, Char, CommentReport, PageHit, RateCounter,
                             UserFollow)

A_READER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')


class _Deleting(TestCase):

    def setUp(self):
        mail.outbox = []
        self.user = a_password_account()
        self.other = a_password_account('neighbour', 'neighbour@test.local')
        self.shared, self.live, self.gone = fill_every_relation(self.user, self.other)
        self.client.force_login(self.user)

    def link(self, user=None):
        return reverse(
            'confirm_account_deletion',
            args=(manage_account_view._deletion_token(user or self.user),))

    def delete_through_the_page(self, client=None):
        return (client or self.client).post(self.link(), {'understood': '1'})


class EveryRowGoes(_Deleting):

    def test_no_relation_of_user_keeps_a_row(self):
        pk = self.user.pk
        relations = [relation for relation in User._meta.related_objects]
        for relation in relations:
            model, field = relation.related_model, relation.field.name
            self.assertTrue(model.objects.filter(**{field: pk}).exists(),
                            '%s.%s is not covered by the test rows' % (model.__name__, field))
        through = (User.groups.through, User.user_permissions.through)
        for table in through:
            self.assertTrue(table.objects.filter(user_id=pk).exists())
        self.delete_through_the_page()
        for table in through:
            self.assertFalse(table.objects.filter(user_id=pk).exists())
        for relation in relations:
            model, field = relation.related_model, relation.field.name
            self.assertFalse(model.objects.filter(**{field: pk}).exists(),
                             '%s.%s still points at the account' % (model.__name__, field))

    def test_soft_deleted_builds_go_too(self):
        ids = [self.shared.pk, self.live.pk, self.gone.pk]
        self.delete_through_the_page()
        self.assertFalse(Char.objects.filter(pk__in=ids).exists())

    def test_a_build_leaves_none_of_its_children(self):
        from chardata.models import (BuildTag, CharBaseStats, ItemInSharedBuild,
                                     SolutionGeneration)
        ids = [self.shared.pk, self.live.pk, self.gone.pk]
        for model in (BuildTag, CharBaseStats, ItemInSharedBuild, SolutionGeneration):
            self.assertEqual(model.objects.filter(char_id__in=ids).count(), 3, model.__name__)
        self.delete_through_the_page()
        for model in (BuildTag, CharBaseStats, ItemInSharedBuild, SolutionGeneration):
            self.assertFalse(model.objects.filter(char_id__in=ids).exists(), model.__name__)

    def test_admin_log_rows_about_the_user_are_gone(self):
        self.assertEqual(LogEntry.objects.filter(object_repr=self.user.username).count(), 2)
        self.assertTrue(LogEntry.objects.filter(user=self.user).exists())
        self.delete_through_the_page()
        self.assertFalse(LogEntry.objects.filter(object_repr=self.user.username).exists())
        self.assertFalse(LogEntry.objects.filter(user_id=self.user.pk).exists())

    def test_a_row_about_another_account_stays_in_the_admin_log(self):
        from django.contrib.contenttypes.models import ContentType
        kept = LogEntry.objects.create(
            user=self.other, content_type=ContentType.objects.get_for_model(User),
            object_id=str(self.other.pk), object_repr=self.other.username, action_flag=1)
        self.delete_through_the_page()
        self.assertTrue(LogEntry.objects.filter(pk=kept.pk).exists())

    def test_a_detached_row_holds_no_name(self):
        destroy_account(self.user.pk)
        names = Char.objects.filter(pk__in=[self.shared.pk, self.live.pk, self.gone.pk])
        self.assertEqual(names.count(), 3)
        for build in names:
            self.assertEqual((build.name, build.char_name), ('', ''))
            self.assertIsNone(build.owner_id)
            self.assertTrue(build.deleted)
            self.assertFalse(build.link_shared)


class OthersStayStanding(_Deleting):

    def test_another_players_copy_survives(self):
        copy = a_build(self.other, self.shared.name)
        self.delete_through_the_page()
        copy.refresh_from_db()
        self.assertEqual(copy.owner_id, self.other.pk)
        self.assertFalse(copy.deleted)

    def test_another_players_build_and_comment_survive(self):
        theirs = a_build(self.other, 'Apart', shared=True)
        comment = BuildComment.objects.create(user=self.other, build=theirs, content='kept')
        self.delete_through_the_page()
        self.assertTrue(Char.objects.filter(pk=theirs.pk).exists())
        self.assertTrue(BuildComment.objects.filter(pk=comment.pk).exists())

    def test_his_comment_on_another_build_goes_with_its_reports(self):
        comment = BuildComment.objects.get(user=self.user)
        self.assertTrue(CommentReport.objects.filter(comment=comment).exists())
        build_id = comment.build_id
        self.delete_through_the_page()
        self.assertFalse(BuildComment.objects.filter(pk=comment.pk).exists())
        self.assertFalse(CommentReport.objects.filter(comment_id=comment.pk).exists())
        self.assertTrue(Char.objects.filter(pk=build_id).exists())

    def test_followers_keep_their_accounts_and_lose_the_edge(self):
        self.delete_through_the_page()
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertFalse(UserFollow.objects.filter(follower_id=self.other.pk).exists())
        self.assertFalse(UserFollow.objects.filter(followed_id=self.other.pk).exists())

    def test_a_session_of_another_account_stays_signed_in(self):
        neighbour = Client()
        neighbour.force_login(self.other)
        self.delete_through_the_page(neighbour)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        page = neighbour.get('/manageaccount/')
        self.assertEqual(page.wsgi_request.user.pk, self.other.pk)


class NoDoorReadsItAnymore(_Deleting):

    def test_his_shared_build_answers_404_on_every_door(self):
        code = encode_char_id(self.shared.pk)
        name = self.shared.char_name
        self.assertEqual(Client().get('/s/%s/%s/' % (name, code),
                                      HTTP_USER_AGENT=A_READER).status_code, 200)
        self.assertEqual(Client().get('/user/%s/' % self.user.username).status_code, 200)
        self.delete_through_the_page()
        self.assertEqual(Client().get('/s/%s/%s/' % (name, code),
                                      HTTP_USER_AGENT=A_READER).status_code, 404)
        self.assertEqual(Client().get('/user/%s/' % self.user.username).status_code, 404)
        self.assertEqual(Client().get('/user/%s/' % 'Holder').status_code, 404)

    def test_a_row_left_flagged_answers_404_too(self):
        code = encode_char_id(self.shared.pk)
        name = self.shared.char_name
        destroy_account(self.user.pk)
        self.assertTrue(Char.objects.filter(pk=self.shared.pk).exists())
        self.assertEqual(Client().get('/s/%s/%s/' % (name, code),
                                      HTTP_USER_AGENT=A_READER).status_code, 404)


class TheNamesAreForgotten(_Deleting):

    def test_counters_holding_the_name_and_address_are_gone(self):
        request = RequestFactory().get('/', REMOTE_ADDR='203.0.113.9')
        request.user = self.user
        note_login_failure(request, self.user.username)
        note_reset_mail_sent(request, ADDRESS)
        for key, _ceiling in manage_account_view._email_change_keys(request, ADDRESS):
            manage_account_view.note_hit(key, 60)
        before = set(RateCounter.objects.values_list('key', flat=True))
        self.assertTrue([key for key in before if ADDRESS in key])
        self.assertTrue([key for key in before if 'holder' in key])
        self.delete_through_the_page()
        after = set(RateCounter.objects.values_list('key', flat=True))
        self.assertFalse([key for key in after if ADDRESS in key])
        self.assertFalse([key for key in after if key.startswith('login-fail-user:')])
        self.assertTrue([key for key in after if key.startswith('reset-mail-ip:')])

    def test_pagehit_rows_holding_the_name_are_gone_and_others_stay(self):
        today = timezone.localdate()
        gone = ['/user/holder/', '/email_confirmed/holder/yes/',
                '/email_confirmed/holder/no/', '/do_recover_password/holder/<id>/',
                '/confirm_email/holder/<id>/']
        kept = ['/user/neighbour/', '/', '/user/holder-two/', '/email_confirmed/neighbour/yes/']
        for path in gone + kept:
            PageHit.objects.create(day=today, path=path, count=1)
        forget_the_names('holder', 'Holder', ADDRESS)
        self.assertEqual(sorted(PageHit.objects.values_list('path', flat=True)), sorted(kept))

    def test_the_username_and_address_can_register_again(self):
        self.delete_through_the_page()
        with mock.patch('chardata.login_view.recaptcha_ok', return_value=True):
            response = Client().post('/register/', {
                'username': 'holder', 'email': ADDRESS,
                'password': _prehash_password('another-42-solid')})
        self.assertEqual(response.status_code, 302)
        reborn = User.objects.get(username='holder')
        self.assertNotEqual(reborn.pk, self.user.pk)
        self.assertEqual(reborn.email, ADDRESS)

    def test_an_old_confirmation_link_does_not_activate_the_new_holder(self):
        with mock.patch('chardata.login_view.recaptcha_ok', return_value=True):
            Client().post('/register/', {'username': 'newcomer', 'email': 'new@test.local',
                                         'password': _prehash_password('another-42-solid')})
        old_link = mailed_link(route='confirm_email/newcomer')
        old = User.objects.get(username='newcomer')
        destroy_account(old.pk)
        with mock.patch('chardata.login_view.recaptcha_ok', return_value=True):
            Client().post('/register/', {'username': 'newcomer', 'email': 'new2@test.local',
                                         'password': _prehash_password('another-42-solid')})
        new = User.objects.get(username='newcomer')
        self.assertFalse(new.is_active)
        response = Client().get(old_link)
        self.assertContains(response, 'invalid token')
        new.refresh_from_db()
        self.assertFalse(new.is_active)

    def test_the_confirmation_link_of_the_same_account_still_works(self):
        with mock.patch('chardata.login_view.recaptcha_ok', return_value=True):
            Client().post('/register/', {'username': 'newcomer', 'email': 'new@test.local',
                                         'password': _prehash_password('another-42-solid')})
        link = mailed_link(route='confirm_email/newcomer')
        user = User.objects.get(username='newcomer')
        self.assertIn(_generate_token_for_user(user), link)
        Client().get(link)
        user.refresh_from_db()
        self.assertTrue(user.is_active)


class TheSessionAndTheMail(_Deleting):

    def test_the_session_ends_and_the_result_page_is_signed_out(self):
        response = self.delete_through_the_page()
        self.assertEqual(outcome_of(response), 'deleted')
        self.assertNotIn('_auth_user_id', self.client.session)
        page = self.client.get(response['Location'])
        self.assertEqual(page.status_code, 200)
        self.assertFalse(page.context['user'].is_authenticated)

    def test_a_session_on_another_device_no_longer_signs_in(self):
        phone = Client()
        phone.force_login(self.user)
        self.delete_through_the_page()
        page = phone.get('/manageaccount/')
        self.assertTrue(page.wsgi_request.user.is_anonymous)

    def test_the_last_mail_goes_to_the_address(self):
        self.delete_through_the_page()
        self.assertEqual([message.to for message in mail.outbox], [[ADDRESS]])
        self.assertIn('Holder', mail.outbox[0].body)
        self.assertNotIn('/confirm_account_deletion/', mail.outbox[0].body)

    def test_a_failed_last_mail_still_deletes_and_logs_no_address(self):
        with mock.patch('chardata.manage_account_view.send_mail',
                        side_effect=OSError(ADDRESS)):
            with self.assertLogs('chardata.manage_account_view', level='ERROR') as logged:
                response = self.delete_through_the_page()
        self.assertEqual(outcome_of(response), 'deleted')
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertNotIn(ADDRESS, '\n'.join(logged.output))

    def test_a_second_post_of_the_link_answers_invalid(self):
        link = self.link()
        self.client.post(link, {'understood': '1'})
        again = self.client.post(link, {'understood': '1'})
        self.assertEqual(outcome_of(again), 'invalid')

    def test_a_database_failure_rolls_everything_back_and_says_so(self):
        names = {build.pk: build.name for build in (self.shared, self.live, self.gone)}
        comments = BuildComment.objects.count()
        with mock.patch.object(User, 'delete', side_effect=DatabaseError('locked')):
            with self.assertLogs('chardata.manage_account_view', level='ERROR'):
                response = self.delete_through_the_page()
        self.assertEqual(outcome_of(response), 'failed')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        for build in Char.objects.filter(pk__in=list(names)):
            self.assertEqual(build.owner_id, self.user.pk)
            self.assertEqual(build.name, names[build.pk])
        self.assertFalse(Char.objects.get(pk=self.shared.pk).deleted)
        self.assertTrue(Char.objects.get(pk=self.shared.pk).link_shared)
        self.assertEqual(BuildComment.objects.count(), comments)
        self.assertEqual(mail.outbox, [])


class TheResultPageTellsOnlyWhatHappened(_Deleting):

    def test_the_page_opened_by_hand_does_not_claim_a_deletion(self):
        page = self.client.get('/account_deletion/deleted/')
        self.assertEqual(page.context['outcome'], 'invalid')
        self.assertNotIn('are deleted', page.content.decode())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_the_page_after_a_deletion_says_so_and_that_the_session_ended(self):
        response = self.delete_through_the_page()
        page = self.client.get(response['Location'])
        self.assertEqual(page.context['outcome'], 'deleted')
        self.assertIn('signed out', page.content.decode())

    def test_another_account_left_signed_in_is_not_told_it_was_signed_out(self):
        neighbour = Client()
        neighbour.force_login(self.other)
        response = self.delete_through_the_page(neighbour)
        text = neighbour.get(response['Location']).content.decode()
        self.assertIn('are deleted', text)
        self.assertNotIn('signed out', text)


class TheAfterCommitStepsDoNotBlockEachOther(_Deleting):

    def test_a_last_mail_that_fails_in_any_way_still_lets_the_purge_run(self):
        with mock.patch('chardata.manage_account_view.send_mail',
                        side_effect=RuntimeError(ADDRESS)):
            with self.assertLogs('chardata.manage_account_view', level='ERROR') as logged:
                response = self.delete_through_the_page()
        self.assertEqual(outcome_of(response), 'deleted')
        self.assertFalse(Char.objects.filter(pk__in=[self.shared.pk, self.live.pk, self.gone.pk]).exists())
        self.assertNotIn(ADDRESS, '\n'.join(logged.output))

    def test_the_last_mail_has_a_short_timeout(self):
        from django.core.mail import get_connection
        with mock.patch('chardata.manage_account_view.get_connection',
                        wraps=get_connection) as opened:
            self.delete_through_the_page()
        opened.assert_called_once_with(timeout=manage_account_view.DELETION_MAIL_TIMEOUT)


class OldAndAnonymousRowsSurvive(_Deleting):

    def test_builds_of_nobody_and_of_others_are_untouched_by_a_full_deletion(self):
        old_flagged = a_build(None, 'OldFlagged', deleted=True)
        anonymous = a_build(None, 'Anonymous')
        theirs_gone = a_build(self.other, 'TheirsGone', deleted=True)
        before = {build.pk: (build.name, build.char_name, build.deleted, build.owner_id)
                  for build in (old_flagged, anonymous, theirs_gone)}
        self.delete_through_the_page()
        for pk, expected in before.items():
            row = Char.objects.get(pk=pk)
            self.assertEqual((row.name, row.char_name, row.deleted, row.owner_id), expected)


class NothingTypedByTheOwnerIsLeftOnABuild(_Deleting):

    def test_the_tags_go_with_the_account_while_the_builds_wait_for_the_purge(self):
        from chardata.models import BuildTag
        theirs = BuildTag.objects.create(char=a_build(self.other, 'Elsewhere'),
                                         name='kept', display_name='Kept')
        BuildTag.objects.create(char=self.live, name='jean dupont', display_name='Jean Dupont')
        destroy_account(self.user.pk)
        self.assertEqual(BuildTag.objects.filter(char__in=[self.shared, self.live, self.gone]).count(), 0)
        self.assertTrue(Char.objects.filter(pk=self.live.pk).exists())
        self.assertTrue(BuildTag.objects.filter(pk=theirs.pk).exists())


class TheHitCounterKeepsRowsOfOthers(_Deleting):

    def test_an_alias_spelled_like_the_placeholder_wipes_nothing_else(self):
        today = timezone.localdate()
        for path in ('/user/<id>/', '/confirm_email/<id>/<id>/', '/about/'):
            PageHit.objects.create(day=today, path=path, count=1)
        forget_the_names('holder', '<id>', ADDRESS)
        self.assertEqual(PageHit.objects.count(), 3)


class AStaleSaveCannotBringAnAccountBack(TestCase):

    def test_a_password_change_that_loses_the_row_answers_invalid(self):
        from django.contrib.auth import authenticate as real
        user = a_password_account('walker', 'walker@test.local')

        def lose_the_row(**credentials):
            found = real(**credentials)
            User.objects.filter(pk=found.pk).delete()
            return found

        with mock.patch('chardata.login_view.authenticate', side_effect=lose_the_row):
            response = Client().post('/change_password/', {
                'username': 'walker', 'password': _prehash_password('pw-42-solid'),
                'newPassword': _prehash_password('another-42-solid')})
        self.assertEqual(response.content.decode(), 'invalid')
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_a_confirmation_that_loses_the_row_does_not_bring_it_back(self):
        user = a_password_account('walker', 'walker@test.local')
        User.objects.filter(pk=user.pk).update(is_active=False)
        token = _generate_token_for_user(user)

        def lose_the_row(first, second):
            User.objects.filter(pk=user.pk).delete()
            return True

        with mock.patch('chardata.login_view.constant_time_compare', side_effect=lose_the_row):
            Client().get('/confirm_email/walker/%s/' % token)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())

    def test_a_reset_that_loses_the_row_does_not_bring_it_back(self):
        user = a_password_account('walker', 'walker@test.local')

        def lose_the_row(*arguments):
            User.objects.filter(pk=user.pk).delete()
            return True

        with mock.patch('chardata.login_view._password_reset_token_is_valid',
                        side_effect=lose_the_row):
            response = Client().post('/do_recover_password/walker/token/', {
                'new_password': 'another-42-solid', 'confirm_password': 'another-42-solid'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())


class NoRelationOfABuildKeepsARowAfterThePurge(_Deleting):

    def test_every_relation_of_char_is_empty_for_his_builds(self):
        from chardata.models import BuildVote, BuildView
        ids = [self.shared.pk, self.live.pk, self.gone.pk]
        BuildView.objects.create(build=self.shared, ip_address='203.0.113.1')
        BuildVote.objects.create(user=self.other, build=self.shared, vote_type='like')
        BuildComment.objects.create(user=self.other, build=self.shared, content='nice')
        relations = [relation for relation in Char._meta.related_objects
                     if relation.one_to_many or relation.one_to_one]
        self.assertGreaterEqual(len(relations), 7)
        for relation in relations:
            self.assertTrue(relation.related_model.objects.filter(
                **{relation.field.name + '__in': ids}).exists(), relation.related_model.__name__)
        self.delete_through_the_page()
        for relation in relations:
            self.assertFalse(relation.related_model.objects.filter(
                **{relation.field.name + '__in': ids}).exists(), relation.related_model.__name__)


class AnAdministratorIsKeptByTheDeletionItself(TestCase):

    def test_destroy_account_called_directly_leaves_a_superuser_standing(self):
        admin = a_password_account('boss', 'boss@test.local')
        User.objects.filter(pk=admin.pk).update(is_superuser=True)
        build = a_build(admin)
        self.assertIsNone(destroy_account(admin.pk))
        self.assertTrue(User.objects.filter(pk=admin.pk).exists())
        self.assertEqual(Char.objects.get(pk=build.pk).owner_id, admin.pk)
