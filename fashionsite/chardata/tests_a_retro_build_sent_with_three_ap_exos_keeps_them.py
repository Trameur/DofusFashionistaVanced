# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Retro build sent with three AP exos keeps them: the validator, the import and the export agree."""

import html.parser
import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from chardata import fashionista_build
from chardata.models import Char
from chardata.options import get_options
from fashionistapulp.exo_options import forgeable_slot_count
from fashionistapulp.structure import get_structure, set_current_game_version

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

VALIDATE = '/api/v1/import/validate/'


class _Inputs(html.parser.HTMLParser):

    def __init__(self):
        super().__init__()
        self.hidden = {}
        self.actions = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('type') == 'hidden':
            self.hidden.setdefault(attrs.get('name'), []).append(attrs.get('value'))
        if tag == 'form':
            self.actions.append(attrs.get('action') or '')


def _sent(ap):
    payload = fashionista_build.example_payload('retro')
    payload['exos'] = {'ap': ap, 'mp': 0, 'range': 0}
    return payload


class ARetroBuildSentWithThreeApExosKeepsThemTests(TestCase):

    def setUp(self):
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')
        cache.clear()
        self.addCleanup(cache.clear)
        self.slots = forgeable_slot_count(get_structure('retro'))

    def _check(self, payload, lang='en', status=200):
        answer = self.client.post(VALIDATE + '?lang=' + lang, json.dumps(payload),
                                  content_type='application/json')
        self.assertEqual(status, answer.status_code)
        return answer.json()

    def test_the_validator_answers_with_the_count(self):
        self.assertLess(3, self.slots)
        data = self._check(_sent(3))
        self.assertTrue(data['valid'], data['errors'])
        self.assertEqual({'ap': 3, 'mp': 0, 'range': 0}, data['exos'])
        self.assertEqual([], data['warnings'])

    def test_true_still_reads_as_one_piece(self):
        data = self._check(dict(_sent(0), exos={'ap': True, 'mp': False}))
        self.assertEqual({'ap': 1, 'mp': 0, 'range': 0}, data['exos'])

    def test_more_than_the_forgeable_pieces_is_lowered_with_a_warning(self):
        data = self._check(_sent(12))
        self.assertTrue(data['valid'], data['errors'])
        self.assertEqual(self.slots, data['exos']['ap'])
        warning = next(w for w in data['warnings'] if w['code'] == 'exo_count_capped')
        self.assertEqual(('exos.ap', self.slots), (warning['path'], warning['slots']))
        self.assertIn('lowered to %d.' % self.slots, warning['message'])
        french = self._check(_sent(12), lang='fr')['warnings'][0]['message']
        self.assertIn('ramené à %d.' % self.slots, french)

    def test_a_count_is_refused_where_each_exo_is_one_point_for_the_build(self):
        payload = fashionista_build.example_payload('dofus3')
        payload['exos'] = {'ap': 2}
        data = self._check(payload, status=400)
        self.assertEqual(['bad_exos'], [error['code'] for error in data['errors']])

    def test_a_negative_count_is_refused(self):
        data = self._check(_sent(-1), status=400)
        self.assertEqual(['bad_exos'], [error['code'] for error in data['errors']])

    def test_the_build_brought_in_keeps_three_and_sends_three_back(self):
        owner = User.objects.create_user('retro-exos', 're@test.local', 'pw-42-solid')
        self.client.force_login(owner)
        payload = _sent(3)
        preview = self.client.get('/retro/import/build/',
                                  {'data': fashionista_build.encode_link_data(payload)},
                                  HTTP_ACCEPT_LANGUAGE='en', HTTP_USER_AGENT=BROWSER)
        self.assertEqual(200, preview.status_code)
        self.assertContains(preview, 'The exos of the build become its exo options: AP (3).')
        parsed = _Inputs()
        parsed.feed(preview.content.decode('utf-8'))
        action = next(a for a in parsed.actions if a.endswith('/import/text/'))
        fields = {'text': parsed.hidden['text'][-1], 'confirm': '1',
                  'char_class': 'Cra', 'level': str(payload['level'])}
        if parsed.hidden.get('count_token'):
            fields['count_token'] = parsed.hidden['count_token'][0]
        done = self.client.post(action, fields, HTTP_USER_AGENT=BROWSER)
        self.assertEqual(302, done.status_code)
        char = Char.objects.order_by('-id').first()
        self.assertEqual('retro', char.game_version)
        options = get_options(char)
        self.assertEqual((3, 0, 0),
                         (options['ap_exo'], options['mp_exo'], options['range_exo']))
        self.assertIs(int, type(options['ap_exo']))
        exported = self.client.get('/retro/export/fashionista/%d/' % char.id)
        self.assertEqual(200, exported.status_code)
        self.assertEqual({'ap': 3, 'mp': 0, 'range': 0}, exported.json()['exos'])
