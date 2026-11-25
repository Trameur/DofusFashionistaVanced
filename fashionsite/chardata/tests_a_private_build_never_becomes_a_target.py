# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build the viewer may not open answers like a missing one: same status, same body, same rows read, none of its stats."""
import json
import logging
import re
from unittest import mock

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.backends.db import SessionStore
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from chardata import spells_view
from chardata.encoded_char_id import encode_char_id
from chardata.models import Char
from chardata.targets import read_target

SECRET = 'Secret-Sadida-name'
SECRET_RESIST = 47


def _char(owner, name, game_version='dofus3', **fields):
    return Char.objects.create(
        name=name, char_name=name, char_class='Iop', char_build='b', level=200,
        minimum_stats=b'', minimum_crits=b'', stats_weight=b'', options=b'',
        inclusions=b'', exclusions=b'', owner=owner, link_shared=fields.pop('link_shared', False),
        game_version=game_version, **fields)


def _solution():
    solution = mock.Mock(item_list=[])
    stats = {key: SECRET_RESIST for key in ('earthresper', 'fireresper', 'waterresper',
                                            'airresper', 'neutresper')}
    stats['hp'] = 4321
    solution.get_stats_total.return_value = stats
    return solution


def _shape(queries):
    return [re.sub(r'\d+', 'N', query['sql']) for query in queries]


class APrivateBuildIsNeverATargetTests(TestCase):

    def setUp(self):
        self.viewer = User.objects.create_user('viewer', 'v@x.test', 'pw-42-solid')
        self.stranger = User.objects.create_user('stranger', 's@x.test', 'pw-42-solid')
        self.own = _char(self.viewer, 'Own-build')
        self.own_deleted = _char(self.viewer, 'Own-deleted', deleted=True)
        self.own_dofus2 = _char(self.viewer, 'Own-dofus2', game_version='dofus2')
        self.private = _char(self.stranger, SECRET)
        self.shared = _char(self.stranger, 'Shared-build', link_shared=True)
        self.shared_deleted = _char(self.stranger, 'Shared-deleted', link_shared=True,
                                    deleted=True)
        self.shared_dofus2 = _char(self.stranger, 'Shared-dofus2', game_version='dofus2',
                                   link_shared=True)
        self.missing = Char.objects.order_by('-pk').first().pk + 1000
        patch = mock.patch('chardata.solution.get_solution', side_effect=lambda char: _solution())
        patch.start()
        self.addCleanup(patch.stop)

    def _request(self, user):
        request = RequestFactory().post('/best_combo/1/')
        request.user = user
        request.session = SessionStore()
        request.game_version = 'dofus3'
        return request

    def refusals(self):
        return {
            'another player private build': 'b%d' % self.private.pk,
            'a deleted build': 'b%d' % self.own_deleted.pk,
            'another version build': 'b%d' % self.own_dofus2.pk,
            'a missing build': 'b%d' % self.missing,
            'a private build by link': 'bs%s' % encode_char_id(self.private.pk),
            'a deleted shared build by link': 'bs%s' % encode_char_id(self.shared_deleted.pk),
            'another version shared build by link': 'bs%s' % encode_char_id(
                self.shared_dofus2.pk),
            'a missing build by link': 'bs%s' % encode_char_id(self.missing),
            'a link with a bad signature': 'bsAAAAAAAA',
            'a malformed token': 'b12.1',
            'a bare b': 'b',
            'a zero id': 'b0',
        }

    def test_the_viewers_own_build_and_a_shared_one_are_targets(self):
        for user, value in ((self.viewer, 'b%d' % self.own.pk),
                            (self.stranger, 'b%d' % self.private.pk),
                            (self.viewer, 'bs%s' % encode_char_id(self.shared.pk))):
            target, refused = read_target('dofus3', value, request=self._request(user))
            with self.subTest(value=value):
                self.assertEqual('', refused)
                self.assertEqual('build', target.kind)
                self.assertEqual(value, target.token())

    def test_every_refusal_is_the_same_word(self):
        for user in (self.viewer, AnonymousUser()):
            for case, value in self.refusals().items():
                target, refused = read_target('dofus3', value, request=self._request(user))
                with self.subTest(case=case, anonymous=user.is_anonymous):
                    self.assertIsNone(target)
                    self.assertEqual('build', refused)

    def test_a_refusal_reads_the_same_rows_whether_the_build_exists_or_not(self):
        for user in (self.viewer, AnonymousUser()):
            request = self._request(user)
            with CaptureQueriesContext(connection) as missing:
                read_target('dofus3', 'b%d' % self.missing, request=request)
            with CaptureQueriesContext(connection) as missing_link:
                read_target('dofus3', 'bs%s' % encode_char_id(self.missing), request=request)
            for case, value in self.refusals().items():
                if 'malformed' in case or 'bare' in case or 'zero' in case or 'signature' in case:
                    continue
                request = self._request(user)
                with CaptureQueriesContext(connection) as seen:
                    read_target('dofus3', value, request=request)
                expected = missing_link if value.startswith('bs') else missing
                with self.subTest(case=case, anonymous=user.is_anonymous):
                    self.assertEqual(_shape(expected.captured_queries),
                                     _shape(seen.captured_queries))

    def test_the_page_answers_every_refusal_with_one_body_and_no_stat(self):
        self.client.force_login(self.viewer)
        bodies = {}
        records = []
        handler = logging.Handler()
        handler.emit = records.append
        logging.getLogger().addHandler(handler)
        self.addCleanup(logging.getLogger().removeHandler, handler)
        with mock.patch.object(spells_view, 'get_solution', return_value=_solution()), \
                mock.patch.object(spells_view, '_best_combo', return_value={'total': 7}):
            for case, value in self.refusals().items():
                response = self.client.post('/best_combo/%d/' % self.own.pk,
                                            {'target': value, 'pushback': 'false'})
                with self.subTest(case=case):
                    self.assertEqual(200, response.status_code)
                    body = response.content.decode('utf-8')
                    self.assertNotIn(SECRET, body)
                    self.assertNotIn(str(SECRET_RESIST), body)
                    bodies[case] = json.loads(body)
        self.assertEqual(1, len({json.dumps(body, sort_keys=True) for body in bodies.values()}))
        self.assertEqual('build', next(iter(bodies.values()))['target_refused'])
        self.assertNotIn('their_turn', next(iter(bodies.values())))
        for record in records:
            self.assertNotIn(SECRET, record.getMessage())


class AnAnonymousVisitorOpensNoOwnerlessBuildTests(TestCase):

    def setUp(self):
        self.mine = _char(None, 'Visitor-project')
        self.ownerless = _char(None, SECRET)
        self.mine_deleted = _char(None, 'Visitor-deleted', deleted=True)
        self.root = User.objects.create_superuser('root', 'r@x.test', 'pw-42-solid')
        self.stranger = User.objects.create_user('other', 'o@x.test', 'pw-42-solid')
        self.stranger_deleted = _char(self.stranger, 'Other-deleted', deleted=True)
        self.missing = Char.objects.order_by('-pk').first().pk + 1000
        patch = mock.patch('chardata.solution.get_solution', side_effect=lambda char: _solution())
        patch.start()
        self.addCleanup(patch.stop)

    def _request(self, user, session=None):
        request = RequestFactory().post('/best_combo/1/')
        request.user = user
        request.session = SessionStore()
        for key, value in (session or {}).items():
            request.session[key] = value
        request.game_version = 'dofus3'
        return request

    def _visitor(self, legacy=False):
        if legacy:
            return self._request(AnonymousUser(), {'char_id': self.mine.pk})
        return self._request(AnonymousUser(), {'char_ids': {'dofus3': self.mine.pk}})

    def test_a_visitor_with_a_project_cannot_target_another_ownerless_build(self):
        for legacy in (False, True):
            target, refused = read_target('dofus3', 'b%d' % self.ownerless.pk,
                                          request=self._visitor(legacy))
            with self.subTest(legacy=legacy):
                self.assertEqual((None, 'build'), (target, refused))

    def test_a_visitor_opens_only_the_project_the_session_holds(self):
        target, refused = read_target('dofus3', 'b%d' % self.mine.pk, request=self._visitor())
        self.assertEqual(('build', ''), (target.kind, refused))

    def test_ownership_never_matches_a_missing_owner_with_a_missing_user(self):
        from chardata.util import char_belongs_to_user
        self.assertFalse(char_belongs_to_user(self._request(AnonymousUser()), self.ownerless))
        self.assertFalse(char_belongs_to_user(self._visitor(), self.ownerless))
        self.assertTrue(char_belongs_to_user(self._visitor(), self.mine))

    def test_a_deleted_build_is_refused_to_its_anonymous_owner_and_to_a_superuser(self):
        cases = ((self._visitor(), self.mine_deleted),
                 (self._request(self.root), self.stranger_deleted))
        for request, char in cases:
            target, refused = read_target('dofus3', 'b%d' % char.pk, request=request)
            with self.subTest(char=char.name):
                self.assertEqual((None, 'build'), (target, refused))

    def test_a_visitor_with_a_project_reads_the_same_rows_for_an_existing_build_or_a_missing_one(self):
        for value, missing in (('b%d' % self.ownerless.pk, 'b%d' % self.missing),
                               ('bs%s' % encode_char_id(self.ownerless.pk),
                                'bs%s' % encode_char_id(self.missing))):
            for legacy in (False, True):
                with CaptureQueriesContext(connection) as expected:
                    read_target('dofus3', missing, request=self._visitor(legacy))
                with CaptureQueriesContext(connection) as seen:
                    read_target('dofus3', value, request=self._visitor(legacy))
                with self.subTest(value=value, legacy=legacy):
                    self.assertEqual(_shape(expected.captured_queries),
                                     _shape(seen.captured_queries))
