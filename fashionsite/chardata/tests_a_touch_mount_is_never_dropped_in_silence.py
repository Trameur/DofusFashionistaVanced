# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch mount the encyclopedia page can't answer for stays in mounts.json instead of being dropped."""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
from unittest import mock

import requests
from django.test import SimpleTestCase

from chardata.tests import itemscraper_module

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _page(*titles):
    return ''.join('<div class="ak-title">\n                    %s'
                   '                            </div>' % title for title in titles)


EBONY = _page('Generation:                                 '
              '<span class="ak-title-info">3</span>',
              '80  Agility', '100  Vitality')
ALMOND = _page('100  Vitality', '80  Strength')

CATALOGUE = {
    '3': {'en': 'Ebony Dragoturkey', 'fr': 'Dragodinde Ebène'},
    '9': {'en': 'Almond Dragoturkey', 'fr': 'Dragodinde Amande'},
    '75': {'en': 'Unpublished Dragoturkey'},
}


def _response(status, text=''):
    resp = requests.Response()
    resp.status_code = status
    resp._content = text.encode('utf-8')
    resp.encoding = 'utf-8'
    resp.url = 'https://www.dofus-touch.com/en/mmorpg/encyclopedia/mounts/'
    return resp


class _Session:
    """Answers each mount id with its list of responses or errors, in turn."""

    def __init__(self, answers):
        self.answers = {mid: list(seq) for mid, seq in answers.items()}
        self.calls = []

    def get(self, url, timeout=None):
        mid = url.rsplit('/', 1)[1]
        self.calls.append(mid)
        answer = self.answers[mid].pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _is_notice():
    """update_data_touch's own test for a line that goes to Warnings/items to review."""
    spec = importlib.util.spec_from_file_location(
        'update_data_touch_for_tests', os.path.join(REPO_ROOT, 'update_data_touch.py'))
    module = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(module)
    return module._is_notice


class ATouchMountIsNeverDroppedInSilenceTests(SimpleTestCase):

    def setUp(self):
        self.mounts = itemscraper_module('download_touch_mounts')

    def _run(self, answers, previous=None, *args):
        """(exit code, printed lines, mounts.json afterwards or None, session)."""
        session = _Session(answers)
        catalogue = {mid: CATALOGUE[mid] for mid in answers}
        printed = io.StringIO()
        with tempfile.TemporaryDirectory() as dest, \
                mock.patch.object(self.mounts, 'resolve_data_url', return_value='proxy'), \
                mock.patch.object(self.mounts, 'fetch_mount_catalogue',
                                  return_value=(catalogue, {})), \
                mock.patch.object(self.mounts, 'make_session', return_value=session), \
                mock.patch.object(self.mounts, 'time'):
            path = os.path.join(dest, 'mounts.json')
            if previous is not None:
                with open(path, 'w', encoding='utf-8') as fh:
                    json.dump(previous, fh)
            with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
                code = self.mounts.main(['--dest', dest, '--delay', '0', *args])
            written = None
            if os.path.exists(path):
                with open(path, encoding='utf-8') as fh:
                    written = json.load(fh)
        return code, printed.getvalue().splitlines(), written, session

    def test_a_page_ankama_does_not_publish_is_one_line_that_is_not_a_warning(self):
        code, lines, written, session = self._run(
            {'3': [_response(200, EBONY)], '75': [_response(404)]})
        self.assertEqual(0, code)
        self.assertEqual([3], [m['ankama_id'] for m in written])
        self.assertEqual([[80, 80, 'Agility'], [100, 100, 'Vitality']],
                         written[0]['stats'])
        self.assertEqual(1, session.calls.count('75'))
        about_75 = [line for line in lines if '75' in line]
        self.assertEqual(1, len(about_75), lines)
        self.assertIn('not published by Ankama', about_75[0])
        is_notice = _is_notice()
        self.assertEqual([], [line for line in lines if is_notice(line)])

    def test_a_page_that_errors_is_retried(self):
        code, _, written, session = self._run(
            {'3': [_response(503), requests.exceptions.Timeout('read timed out'),
                   _response(200, EBONY)]})
        self.assertEqual(0, code)
        self.assertEqual(3, session.calls.count('3'))
        self.assertEqual([3], [m['ankama_id'] for m in written])

    def test_a_page_that_keeps_erroring_writes_nothing_and_fails(self):
        previous = [{'ankama_id': 3, 'name_en': 'Ebony Dragoturkey', 'stats': []},
                    {'ankama_id': 9, 'name_en': 'Almond Dragoturkey', 'stats': []}]
        code, lines, written, session = self._run(
            {'3': [_response(200, EBONY)], '9': [_response(429)] * 3}, previous)
        self.assertEqual(1, code)
        self.assertEqual(previous, written)
        self.assertEqual(3, session.calls.count('9'))
        self.assertIn('nothing written.', lines)
        is_notice = _is_notice()
        self.assertTrue(any(is_notice(line) for line in lines if '9' in line), lines)

    def test_a_mount_the_file_holds_is_not_lost(self):
        previous = [{'ankama_id': 3, 'name_en': 'Ebony Dragoturkey', 'stats': []},
                    {'ankama_id': 9, 'name_en': 'Almond Dragoturkey', 'stats': []}]
        code, lines, written, _ = self._run(
            {'3': [_response(200, EBONY)], '9': [_response(404)]}, previous)
        self.assertEqual(1, code)
        self.assertEqual(previous, written)
        self.assertTrue(any('Almond Dragoturkey (9)' in line for line in lines), lines)
        self.assertTrue(any(line.startswith('nothing written.') for line in lines), lines)

    def test_allow_shrink_writes_the_smaller_file(self):
        previous = [{'ankama_id': 3, 'name_en': 'Ebony Dragoturkey', 'stats': []},
                    {'ankama_id': 9, 'name_en': 'Almond Dragoturkey', 'stats': []}]
        code, _, written, _ = self._run(
            {'3': [_response(200, EBONY)], '9': [_response(404)]}, previous,
            '--allow-shrink')
        self.assertEqual(0, code)
        self.assertEqual([3], [m['ankama_id'] for m in written])

    def test_a_new_mount_is_welcome(self):
        previous = [{'ankama_id': 3, 'name_en': 'Ebony Dragoturkey', 'stats': []}]
        code, _, written, _ = self._run(
            {'3': [_response(200, EBONY)], '9': [_response(200, ALMOND)]}, previous)
        self.assertEqual(0, code)
        self.assertEqual([3, 9], [m['ankama_id'] for m in written])
