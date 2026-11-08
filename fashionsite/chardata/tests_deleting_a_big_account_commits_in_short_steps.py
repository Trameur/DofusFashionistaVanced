# -*- coding: utf-8 -*-
"""The account goes in one short step whatever its builds weigh, and the builds go after it in bounded batches."""
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from chardata import manage_account_view
from chardata.account_deletion import destroy_account, purge_detached_builds
from chardata.account_deletion_fixtures import (a_build, a_password_account,
                                                fill_every_relation)
from chardata.models import BuildTag, Char, SolutionGeneration


def _queries_to_delete_an_account_with(builds):
    user = a_password_account('owner%d' % builds, 'owner%d@test.local' % builds)
    other = a_password_account('friend%d' % builds, 'friend%d@test.local' % builds)
    fill_every_relation(user, other)
    for number in range(builds):
        build = a_build(user, 'Extra%d' % number, shared=bool(number % 2))
        BuildTag.objects.create(char=build, name='t', display_name='T')
        SolutionGeneration.objects.create(char=build, minimal_solution=b'x')
    owned = Char.objects.filter(owner=user).count()
    detached_before = Char.objects.filter(owner=None, deleted=True).count()
    with CaptureQueriesContext(connection) as queries:
        destroy_account(user.pk)
    detached = Char.objects.filter(owner=None, deleted=True).count() - detached_before
    deletes_of_builds = [query['sql'] for query in queries.captured_queries
                         if query['sql'].startswith('DELETE FROM "chardata_char"')]
    return len(queries), deletes_of_builds, owned, detached


class TheAccountStep(TestCase):

    def test_the_account_transaction_query_count_does_not_grow_with_the_builds(self):
        few, few_deletes, few_owned, few_detached = _queries_to_delete_an_account_with(2)
        many, many_deletes, many_owned, many_detached = _queries_to_delete_an_account_with(40)
        self.assertEqual(few, many)
        self.assertEqual((few_deletes, many_deletes), ([], []))
        self.assertEqual((few_detached, many_detached), (few_owned, many_owned))
        self.assertGreater(many_owned, few_owned)

    def test_the_account_step_deletes_no_build(self):
        user = a_password_account()
        other = a_password_account('neighbour', 'neighbour@test.local')
        shared, live, gone = fill_every_relation(user, other)
        before = Char.objects.filter(owner=user).count()
        destroy_account(user.pk)
        self.assertEqual(Char.objects.filter(pk__in=[shared.pk, live.pk, gone.pk]).count(), before)

    def test_the_account_is_gone_before_the_first_batch(self):
        user = a_password_account()
        other = a_password_account('neighbour', 'neighbour@test.local')
        shared, live, gone = fill_every_relation(user, other)
        seen = {}

        def look(build_ids, **kwargs):
            seen['account'] = User.objects.filter(pk=user.pk).exists()
            seen['detached'] = Char.objects.filter(
                pk__in=build_ids, owner=None, deleted=True, link_shared=False).count()
            return purge_detached_builds(build_ids, **kwargs)

        self.client.force_login(user)
        link = reverse('confirm_account_deletion',
                       args=(manage_account_view._deletion_token(user),))
        with mock.patch('chardata.manage_account_view.purge_detached_builds', side_effect=look):
            self.client.post(link, {'understood': '1'})
        self.assertEqual(seen, {'account': False, 'detached': 3})
        self.assertFalse(Char.objects.filter(pk__in=[shared.pk, live.pk, gone.pk]).exists())


class ThePurge(TestCase):

    def setUp(self):
        self.user = a_password_account()
        self.ids = [a_build(self.user, 'Build%d' % number, shared=True).pk
                    for number in range(7)]
        destroy_account(self.user.pk)

    def test_the_purge_stops_at_its_limit_and_the_rest_stays_hidden_and_detached(self):
        ticks = iter(range(0, 1000, 6))
        removed = purge_detached_builds(self.ids, batch_size=2, budget=10,
                                        clock=lambda: next(ticks))
        self.assertEqual(removed, 2)
        left = Char.objects.filter(pk__in=self.ids)
        self.assertEqual(left.count(), 5)
        for build in left:
            self.assertIsNone(build.owner_id)
            self.assertTrue(build.deleted)
            self.assertFalse(build.link_shared)
            self.assertEqual((build.name, build.char_name), ('', ''))

    def test_a_purge_with_room_deletes_every_batch(self):
        removed = purge_detached_builds(self.ids, batch_size=2, budget=10 ** 6)
        self.assertEqual(removed, 7)
        self.assertFalse(Char.objects.filter(pk__in=self.ids).exists())

    def test_the_purge_touches_only_builds_that_are_still_detached(self):
        keeper = a_build(a_password_account('keeper', 'keeper@test.local'), 'Kept')
        purge_detached_builds(self.ids + [keeper.pk])
        self.assertTrue(Char.objects.filter(pk=keeper.pk).exists())

    def test_the_purge_never_touches_a_build_that_is_not_detached_and_flagged(self):
        owner = a_password_account('keeper', 'keeper@test.local')
        old_flagged = a_build(None, 'OldFlagged', deleted=True)
        anonymous_live = a_build(None, 'Anonymous')
        owned_flagged = a_build(owner, 'OwnedFlagged', deleted=True)
        owned_live = a_build(owner, 'OwnedLive')
        guarded = [anonymous_live.pk, owned_flagged.pk, owned_live.pk]
        removed = purge_detached_builds(self.ids + guarded)
        self.assertEqual(removed, 7)
        self.assertEqual(Char.objects.filter(pk__in=guarded).count(), 3)
        self.assertTrue(Char.objects.filter(pk=old_flagged.pk).exists())

    def test_an_early_stop_logs_how_many_builds_are_left_and_which(self):
        ticks = iter(range(0, 1000, 6))
        with self.assertLogs('chardata.account_deletion', level='ERROR') as logged:
            purge_detached_builds(self.ids, batch_size=2, budget=10, clock=lambda: next(ticks))
        text = '\n'.join(logged.output)
        self.assertIn('5 detached builds were not purged', text)
        self.assertIn(str(self.ids[-1]), text)

    def test_a_complete_purge_logs_nothing(self):
        with self.assertNoLogs('chardata.account_deletion', level='ERROR'):
            purge_detached_builds(self.ids)

    def test_a_refusing_database_stops_the_purge_and_logs_no_row(self):
        from django.db import DatabaseError
        with mock.patch('chardata.account_deletion.Char.objects') as objects:
            objects.filter.return_value.delete.side_effect = DatabaseError('deadlock')
            with self.assertLogs('chardata.account_deletion', level='ERROR') as logged:
                removed = purge_detached_builds(self.ids, batch_size=2)
        self.assertEqual(removed, 0)
        self.assertIn('DatabaseError', logged.records[0].getMessage())
        self.assertNotIn('deadlock', ''.join(logged.output))


class TheCommand(TestCase):

    def setUp(self):
        self.user = a_password_account()
        self.detached = [a_build(self.user, 'Old%d' % number).pk for number in range(5)]
        destroy_account(self.user.pk)
        owner = a_password_account('keeper', 'keeper@test.local')
        self.live = a_build(owner, 'Live')
        self.soft = a_build(owner, 'Soft', deleted=True)
        self.anonymous = a_build(None, 'Anonymous')
        self.old = a_build(None, 'OldFlagged', deleted=True)

    def run_it(self, *arguments):
        out = StringIO()
        call_command('purge_detached_builds', *arguments, stdout=out)
        return out.getvalue()

    def test_without_its_go_flag_it_prints_a_count_and_deletes_nothing(self):
        printed = self.run_it()
        self.assertIn('6 detached builds would be deleted', printed)
        self.assertEqual(Char.objects.filter(pk__in=self.detached).count(), 5)

    def test_with_its_go_flag_it_deletes_only_the_detached_builds(self):
        printed = self.run_it('--go')
        self.assertIn('Deleted 6', printed)
        self.assertFalse(Char.objects.filter(pk__in=self.detached).exists())
        self.assertFalse(Char.objects.filter(pk=self.old.pk).exists())
        for kept in (self.live, self.soft, self.anonymous):
            self.assertTrue(Char.objects.filter(pk=kept.pk).exists())

    def test_the_blanked_selector_reaches_only_what_an_account_deletion_left(self):
        printed = self.run_it('--blanked', '--go')
        self.assertIn('1 other detached builds are left alone', printed)
        self.assertIn('Deleted 5', printed)
        self.assertFalse(Char.objects.filter(pk__in=self.detached).exists())
        self.assertTrue(Char.objects.filter(pk=self.old.pk).exists())

    def test_the_ids_selector_reaches_only_those_builds(self):
        self.run_it('--ids', '%d,%d' % (self.detached[0], self.old.pk), '--go')
        self.assertFalse(Char.objects.filter(pk__in=[self.detached[0], self.old.pk]).exists())
        self.assertEqual(Char.objects.filter(pk__in=self.detached[1:]).count(), 4)

    def test_the_dry_run_with_a_selector_deletes_nothing(self):
        printed = self.run_it('--blanked')
        self.assertIn('5 detached builds would be deleted', printed)
        self.assertEqual(Char.objects.filter(pk__in=self.detached).count(), 5)
