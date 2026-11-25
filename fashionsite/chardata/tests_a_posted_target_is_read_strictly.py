# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A posted target that does not read leaves the turn raw and says why; only a well formed grade of the page's version is used."""
import json
from unittest import mock

from django.test import RequestFactory, SimpleTestCase

from chardata import spells_view
from chardata.targets import _monster_index, read_target

REFUSALS = {'malformed', 'version', 'monster', 'grade', 'unreadable'}


def _known(version):
    monster_id, _names, grades = _monster_index(version)[0][0]
    return monster_id, grades[0][0], grades[-1][0]


class APostedTargetTests(SimpleTestCase):

    def _post(self, version, target=None, reader=None):
        data = {'pushback': 'false'}
        if target is not None:
            data['target'] = target
        request = RequestFactory().post('/best_combo/', data)
        request.game_version = version
        seen = []

        def combo(char, solution, game_version, *args, **kwargs):
            seen.append(kwargs.get('target'))
            return {'total': 1}

        patches = [mock.patch.object(spells_view, 'get_solution', return_value=object()),
                   mock.patch.object(spells_view, '_best_combo', combo)]
        if reader is not None:
            patches.append(mock.patch('chardata.targets.read_target', reader))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        response = spells_view._best_combo_response(request, mock.Mock())
        self.assertEqual(200, response.status_code)
        return json.loads(response.content), seen[0]

    def test_no_target_posts_the_raw_turn_with_no_refusal(self):
        payload, target = self._post('dofus3')
        self.assertIsNone(target)
        self.assertEqual({'best_combo': {'total': 1}}, payload)
        payload, target = self._post('dofus3', '')
        self.assertIsNone(target)
        self.assertNotIn('target_refused', payload)

    def test_a_known_grade_reaches_the_turn(self):
        for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
            monster_id, grade, _last = _known(version)
            payload, target = self._post(version, 'm%d.%d' % (monster_id, grade))
            with self.subTest(version=version):
                self.assertNotIn('target_refused', payload)
                self.assertEqual(('m', monster_id, grade), target.ref)
                self.assertEqual(version, target.version)

    def test_each_kind_of_bad_target_is_refused_with_its_reason(self):
        monster_id, grade, last = _known('dofus3')
        biggest = max(entry[0] for entry in _monster_index('dofus3')[0])
        cases = {
            'malformed': ['x', 'm', 'm0.1', 'm%d' % monster_id, 'm%d.0' % monster_id,
                          'm%d.%dx' % (monster_id, grade), ' m%d.%d' % (monster_id, grade),
                          'm-1.1', 'm1.1.1', 'M%d.%d' % (monster_id, grade),
                          'm%d.%d\n' % (monster_id, grade)],
            'build': ['b12.1'],
            'monster': ['m%d.1' % (biggest + 1)],
            'grade': ['m%d.%d' % (monster_id, last + 1)],
        }
        for reason, values in cases.items():
            for value in values:
                payload, target = self._post('dofus3', value)
                with self.subTest(value=value):
                    self.assertIsNone(target)
                    self.assertEqual(reason, payload['target_refused'])
                    self.assertTrue(payload['target_refused_note'])
                    self.assertEqual({'total': 1}, payload['best_combo'])

    def test_a_version_without_targets_refuses_a_well_formed_one(self):
        monster_id, grade, _last = _known('dofus3')
        for version in ('touchbeta', 'retrobeta', 'wakfu'):
            payload, target = self._post(version, 'm%d.%d' % (monster_id, grade))
            with self.subTest(version=version):
                self.assertIsNone(target)
                self.assertEqual('version', payload['target_refused'])

    def test_a_reader_that_fails_never_turns_into_an_error_page(self):
        def broken(version, value, language=None):
            raise OSError('the database is gone')

        payload, target = self._post('dofus3', 'm1.1', reader=broken)
        self.assertIsNone(target)
        self.assertEqual('unreadable', payload['target_refused'])
        self.assertIn(payload['target_refused'], REFUSALS)

    def test_a_turn_that_fails_on_a_target_is_shown_raw_with_a_refusal(self):
        monster_id, grade, _last = _known('dofus3')
        request = RequestFactory().post('/best_combo/', {'target': 'm%d.%d' % (monster_id, grade)})
        request.game_version = 'dofus3'
        calls = []

        def combo(char, solution, game_version, *args, **kwargs):
            calls.append(kwargs.get('target'))
            if kwargs.get('target') is not None:
                raise ValueError('a record that cannot be read')
            return {'total': 1}

        with mock.patch.object(spells_view, 'get_solution', return_value=object()),                 mock.patch.object(spells_view, '_best_combo', combo):
            response = spells_view._best_combo_response(request, mock.Mock())
        payload = json.loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual({'total': 1}, payload['best_combo'])
        self.assertEqual('unreadable', payload['target_refused'])
        self.assertEqual([calls[0], None], calls)
        self.assertIsNotNone(calls[0])

    def test_the_reader_and_the_view_agree_on_every_refusal(self):
        for value in ('x', 'm0.1'):
            self.assertEqual((None, 'malformed'), read_target('dofus3', value))
        self.assertEqual((None, 'malformed'), read_target('dofus3', ['m1.1']))
