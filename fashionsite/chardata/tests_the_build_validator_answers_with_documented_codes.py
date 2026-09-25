# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The fashionista-build validator answers with the documented codes, open CORS, a preflight and a rate limit; the JSON Schema agrees with it."""

import copy
import json
import unittest
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from chardata import fashionista_build, fashionista_build_view
from chardata.models import RateCounter
from fashionistapulp.structure import get_structure

URL = '/api/v1/import/validate/'
SCHEMA = '/api/v1/import/schema/1/'

#: Every stat key version 1 of the format was published with
STAT_KEYS_V1 = (
    'agi', 'airdam', 'airres', 'airresper', 'ap', 'apred', 'apres', 'cf', 'ch', 'cha',
    'cridam', 'crires', 'dam', 'dodge', 'earthdam', 'earthres', 'earthresper', 'firedam',
    'fireres', 'fireresper', 'heals', 'hp', 'init', 'int', 'lock', 'mp', 'mpred', 'mpres',
    'neutdam', 'neutres', 'neutresper', 'permedam', 'perrandam', 'perspedam', 'perweadam',
    'pod', 'pow', 'pp', 'pshdam', 'pshres', 'pvpairres', 'pvpairresper', 'pvpearthres',
    'pvpearthresper', 'pvpfireres', 'pvpfireresper', 'pvpneutres', 'pvpneutresper',
    'pvpwaterres', 'pvpwaterresper', 'range', 'ref', 'respermee', 'resperran', 'resperwea',
    'str', 'summon', 'trapdam', 'trapdamper', 'vit', 'waterdam', 'waterres', 'waterresper',
    'wis',
)


def _good(game='dofus3'):
    return fashionista_build.example_payload(game)


def _cloak():
    """The example's cloak, which the warning test marks as no longer in the game."""
    return get_structure('dofus3').get_item_by_ankama_id(_good()['items'][1])


def _only_in_retro():
    retro, dofus3 = get_structure('retro'), get_structure('dofus3')
    return next(item.ankama_id for item in retro.get_items_list()
                if item.ankama_id and item.id < 10_000_000
                and dofus3.get_item_by_ankama_id(item.ankama_id) is None)


def _third_ring(payload):
    structure = get_structure(payload['game'])
    taken = {entry for entry in payload['items'] if not isinstance(entry, dict)}
    return next(item.ankama_id for item in structure.get_items_list()
                if structure.get_type_name_by_id(item.type) == 'Ring'
                and item.ankama_id not in taken and not item.removed
                and structure.get_item_by_ankama_id(item.ankama_id) is item)


def _with(**changes):
    payload = _good()
    payload.update(changes)
    return payload


def _ring(game, with_set):
    structure = get_structure(game)
    return next(item for item in structure.get_items_list()
                if structure.get_type_name_by_id(item.type) == 'Ring'
                and not item.removed and item.ankama_id
                and (item.set is not None) == with_set
                and structure.get_item_by_ankama_id(item.ankama_id) is item)


def _error_cases():
    """{code: body} for every error a body can cause."""
    good = _good()
    return {
        'not_json': '{"format": ',
        'not_an_object': '[1, 2, 3]',
        'too_large': json.dumps(dict(good, name='x' * fashionista_build.MAX_JSON)),
        'wrong_format': json.dumps(_with(format='dofusbook')),
        'unsupported_version': json.dumps(_with(version=2)),
        'unknown_game': json.dumps(_with(game='wakfu')),
        'bad_items': json.dumps(_with(items=[{'id': 'abc'}])),
        'too_many_items': json.dumps(_with(items=[44] * (fashionista_build.MAX_ITEMS + 1))),
        'bad_stats': json.dumps(_with(items=[{'id': 44, 'stats': [{'key': 'vit', 'value': 'x'}]}])),
        'bad_level': json.dumps(_with(level=201)),
        'bad_characteristics': json.dumps(_with(characteristics={'vitalite': 10})),
        'bad_exos': json.dumps(_with(exos={'ap': 'yes'})),
        'no_known_item': json.dumps(_with(items=[987654321])),
        'wrong_game': json.dumps(_with(items=[_only_in_retro()])),
    }


def _warning_cases():
    """{code: payload} for every warning a readable payload can carry."""
    good = _good()
    hat = good['items'][0]
    return {
        'unknown_item': _with(items=good['items'] + [987654321]),
        'item_from_another_game': _with(items=good['items'] + [_only_in_retro()]),
        'slot_full': _with(items=good['items'] + [_third_ring(good)]),
        'removed_item': _with(),
        'item_above_level': _with(level=1),
        'unknown_stat': _with(items=[dict(hat, stats=[{'key': 'nope', 'value': 3}])]
                              + good['items'][1:]),
        'already_placed': _with(items=good['items'] + [good['items'][2]]),
        'duplicate_stat': _with(items=[dict(hat, stats=hat['stats'] * 2)]
                                + good['items'][1:]),
        'stat_out_of_range': _with(items=[dict(hat, stats=[dict(hat['stats'][0], value=9999)])]
                                   + good['items'][1:]),
        'unknown_class': _with(**{'class': 'Wizard'}),
        'class_not_in_game': dict(_good('retro'), **{'class': 'Forgelance'}),
        'scroll_capped': _with(scrolls=dict(good['scrolls'], agility=400)),
        'exos_not_in_game': dict(_good('retro'), exos={'ap': True}),
        'name_truncated': _with(name='x' * 80),
        'name_ignored': _with(name=12),
        'source_ignored': _with(source='not a domain'),
        'back_url_ignored': _with(back_url='http://example.org/'),
        'unknown_field': _with(colour='blue'),
    }


class _Validator(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _post(self, body, lang='en', **extra):
        if not isinstance(body, (str, bytes)):
            body = json.dumps(body)
        return self.client.post(URL + '?lang=' + lang, body,
                                content_type='application/json', **extra)


class AValidBuildIsReadBackTests(_Validator):

    def test_every_item_comes_back_found_and_named_in_the_asked_language(self):
        payload = _good()
        answer = self._post(payload, lang='fr')
        self.assertEqual(200, answer.status_code)
        data = answer.json()
        self.assertEqual((True, 'dofus3', 'Iop', 200), (data['valid'], data['game'],
                                                       data['class'], data['level']))
        structure = get_structure('dofus3')
        expected = [structure.get_item_name_in_language(structure.get_item_by_ankama_id(
            entry['id'] if isinstance(entry, dict) else entry), 'fr')
            for entry in payload['items']]
        self.assertEqual(expected, [piece['name'] for piece in data['items']])
        self.assertTrue(all(piece['found'] and piece['placed'] for piece in data['items']))
        self.assertEqual(payload['characteristics'], data['characteristics'])
        self.assertEqual(payload['scrolls'], data['scrolls'])
        self.assertEqual([], data['errors'])
        self.assertEqual([], data['warnings'])
        self.assertTrue(data['link'].startswith('https://dofusfashionista.gg/import/build/?data='))

    def test_the_link_it_hands_out_opens_the_same_build(self):
        data = self._post(_good('touch')).json()
        path = data['link'][len('https://dofusfashionista.gg'):]
        self.assertTrue(path.startswith('/touch/import/build/?data='))
        page = self.client.get(path, HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'Build received: Example build')


class EveryDocumentedCodeIsTheOneAnsweredTests(_Validator):

    def test_each_error_code_is_answered_for_its_cause(self):
        for code, body in _error_cases().items():
            with self.subTest(code=code):
                answer = self._post(body)
                self.assertEqual(413 if code == 'too_large' else 400, answer.status_code)
                data = answer.json()
                self.assertFalse(data['valid'])
                self.assertIn(code, [error['code'] for error in data['errors']])
                self.assertEqual('*', answer['Access-Control-Allow-Origin'])

    def test_each_warning_code_is_answered_and_the_build_stays_valid(self):
        cases = _warning_cases()
        with mock.patch.object(_cloak(), 'removed', True):
            for code, payload in cases.items():
                with self.subTest(code=code):
                    data = self._post(payload).json()
                    self.assertTrue(data['valid'], data['errors'])
                    self.assertIn(code, [warning['code'] for warning in data['warnings']])
        self.assertNotIn('removed_item', [warning['code'] for warning
                                          in self._post(_good()).json()['warnings']])

    def test_the_documented_codes_are_exactly_the_ones_the_cases_reach(self):
        documented = {code for code, _text in fashionista_build.ERRORS}
        # bad_encoding only comes from a link, the landing tests reach it
        reached = set(_error_cases()) | {'rate_limited', 'method_not_allowed', 'bad_encoding'}
        self.assertEqual(documented, reached)
        self.assertEqual({code for code, _text in fashionista_build.WARNINGS},
                         set(_warning_cases()))

    def test_a_message_comes_in_the_asked_language_with_its_path(self):
        data = self._post(_with(level=0), lang='fr').json()
        self.assertEqual([{'code': 'bad_level', 'path': 'level',
                           'message': 'Le niveau doit être un nombre entier de 1 à 200.'}],
                         data['errors'])
        data = self._post(_with(items=[987654321]), lang='de').json()
        self.assertEqual('Keiner dieser Gegenstände ist in unserem Katalog für dieses Spiel.',
                         data['errors'][0]['message'])
        self.assertEqual(['unknown_item'], [w['code'] for w in data['warnings']])
        self.assertEqual(987654321, data['warnings'][0]['id'])

    def test_an_id_from_another_game_names_the_games_it_belongs_to(self):
        retro_only = _only_in_retro()
        data = self._post(_with(items=_good()['items'] + [retro_only])).json()
        piece = data['items'][-1]
        self.assertEqual((retro_only, False), (piece['id'], piece['found']))
        self.assertIn('retro', piece['games'])


class APieceIsPlacedOnlyAsTheGameAllowsTests(_Validator):

    def _placed(self, game, items):
        payload = dict(_good(game), items=items)
        data = self._post(payload).json()
        self.assertTrue(data['valid'], data['errors'])
        return ([piece['placed'] for piece in data['items']],
                [w['code'] for w in data['warnings'] if w['code'] == 'already_placed'])

    def test_a_dofus3_set_ring_sent_twice_is_placed_once(self):
        ring = _ring('dofus3', with_set=True).ankama_id
        self.assertEqual(([True, False], ['already_placed']),
                         self._placed('dofus3', [ring, ring]))

    def test_a_retro_ring_sent_twice_is_placed_once(self):
        ring = _ring('retro', with_set=False).ankama_id
        self.assertEqual(([True, False], ['already_placed']),
                         self._placed('retro', [ring, ring]))

    def test_a_dofus3_ring_without_a_set_may_be_worn_twice(self):
        ring = _ring('dofus3', with_set=False).ankama_id
        self.assertEqual(([True, True], []), self._placed('dofus3', [ring, ring]))

    def test_a_dofus_sent_six_times_is_placed_once(self):
        structure = get_structure('dofus3')
        dofus = next(item.ankama_id for item in structure.get_items_list()
                     if structure.get_type_name_by_id(item.type) == 'Dofus'
                     and not item.removed and item.ankama_id
                     and structure.get_item_by_ankama_id(item.ankama_id) is item)
        placed, codes = self._placed('dofus3', [dofus] * 6)
        self.assertEqual([True] + [False] * 5, placed)
        self.assertEqual(['already_placed'] * 5, codes)


class TheAnswerSaysWhatWillApplyTests(_Validator):

    def test_a_build_sent_without_exos_is_answered_with_none(self):
        payload = _good()
        del payload['exos']
        data = self._post(payload).json()
        self.assertEqual({'ap': False, 'mp': False, 'range': False}, data['exos'])
        self.assertIsNone(self._post(dict(_good('retro'))).json()['exos'])

    def test_a_stat_sent_twice_keeps_its_last_line(self):
        hat = _good()['items'][0]
        key = hat['stats'][0]['key']
        payload = _with(items=[dict(hat, stats=[{'key': key, 'value': 1},
                                                {'key': key, 'value': hat['stats'][0]['value']}])]
                        + _good()['items'][1:])
        reading = fashionista_build.check(payload)
        structure = get_structure('dofus3')
        item = structure.get_item_by_ankama_id(hat['id'])
        self.assertEqual([{'key': key, 'value': hat['stats'][0]['value']}],
                         reading.build['rolls'][item.id])
        self.assertEqual([('duplicate_stat', 'items[0].stats[1]')],
                         [(w['code'], w['path']) for w in reading.warnings])

    def test_a_value_outside_the_rolls_names_the_range(self):
        hat = _good()['items'][0]
        payload = _with(items=[dict(hat, stats=[dict(hat['stats'][0], value=9999)])]
                        + _good()['items'][1:])
        warning = next(w for w in self._post(payload).json()['warnings']
                       if w['code'] == 'stat_out_of_range')
        from chardata.stat_range import get_stat_range
        structure = get_structure('dofus3')
        item = structure.get_item_by_ankama_id(hat['id'])
        stat = structure.get_stat_by_key(hat['stats'][0]['key'])
        self.assertEqual(('items[0].stats[0]', list(get_stat_range(item, stat.id))),
                         (warning['path'], [warning['low'], warning['high']]))

    def test_an_answer_full_of_unknown_fields_stays_small(self):
        payload = _good()
        for number in range(3000):
            payload['f%d' % number] = 0
        body = json.dumps(payload, separators=(',', ':'))
        self.assertLess(len(body), fashionista_build.MAX_JSON)
        answer = self._post(body)
        data = answer.json()
        self.assertEqual(fashionista_build.ISSUES_PER_CODE,
                         [w['code'] for w in data['warnings']].count('unknown_field'))
        self.assertEqual(3000 - fashionista_build.ISSUES_PER_CODE, data['warnings_omitted'])
        self.assertLess(len(answer.content), 20000)

    def test_a_form_field_named_data_is_read_like_the_body(self):
        answer = self.client.post(URL + '?lang=en', {'data': json.dumps(_good())})
        self.assertEqual(200, answer.status_code)
        self.assertTrue(answer.json()['valid'])


class TheFormatStaysReadableTests(_Validator):

    def test_the_version_refusal_names_every_version_that_can_be_read(self):
        from django.utils import translation
        with translation.override('en'):
            sentence = fashionista_build.message('unsupported_version')
        for version in fashionista_build.READABLE_VERSIONS:
            self.assertIn('version %d' % version, sentence)
        self.assertIn(fashionista_build.FORMAT_VERSION, fashionista_build.READABLE_VERSIONS)

    def test_every_stat_key_version_1_was_published_with_still_reads_in_every_game(self):
        from fashionistapulp.game_versions import version_keys
        for game in version_keys():
            structure = get_structure(game)
            with self.subTest(game=game):
                self.assertEqual([], [key for key in STAT_KEYS_V1
                                      if structure.get_stat_by_key(key) is None])

    def test_the_schema_reads_null_as_absent_like_the_checker(self):
        validator = self._validator()
        payload = dict(_good(), **{field: None for field in (
            'class', 'level', 'name', 'characteristics', 'scrolls', 'exos', 'source',
            'back_url')})
        self.assertEqual([], [error.message for error in validator.iter_errors(payload)])
        self.assertTrue(self._post(payload).json()['valid'])

    def _validator(self):
        try:
            import jsonschema
        except ImportError:
            raise unittest.SkipTest('jsonschema not installed')
        return jsonschema.Draft202012Validator(self.client.get(SCHEMA).json())


class CorsAndMethodsTests(_Validator):

    def test_a_preflight_is_answered_without_a_body_and_without_credentials(self):
        answer = self.client.options(URL, HTTP_ORIGIN='https://example.org',
                                     HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST')
        self.assertEqual(204, answer.status_code)
        self.assertEqual(b'', answer.content)
        self.assertEqual('*', answer['Access-Control-Allow-Origin'])
        self.assertIn('POST', answer['Access-Control-Allow-Methods'])
        self.assertIn('Content-Type', answer['Access-Control-Allow-Headers'])
        self.assertFalse(answer.has_header('Access-Control-Allow-Credentials'))

    def test_every_answer_carries_open_cors_and_no_credentials(self):
        for answer in (self._post(_good()), self._post('nope'),
                       self.client.get(URL)):
            with self.subTest(status=answer.status_code):
                self.assertEqual('*', answer['Access-Control-Allow-Origin'])
                self.assertFalse(answer.has_header('Access-Control-Allow-Credentials'))

    def test_a_get_says_how_to_call_it_and_another_method_is_refused_with_its_code(self):
        usage = self.client.get(URL)
        self.assertEqual(200, usage.status_code)
        self.assertEqual('https://dofusfashionista.gg' + SCHEMA, usage.json()['schema'])
        answer = self.client.put(URL, '{}', content_type='application/json')
        self.assertEqual(405, answer.status_code)
        self.assertEqual('GET, POST, OPTIONS', answer['Allow'])
        self.assertEqual(['method_not_allowed'], [e['code'] for e in answer.json()['errors']])
        self.assertEqual('*', answer['Access-Control-Allow-Origin'])

    def test_no_csrf_token_is_asked(self):
        from django.test import Client
        answer = Client(enforce_csrf_checks=True).post(
            URL, json.dumps(_good()), content_type='application/json')
        self.assertEqual(200, answer.status_code)


class TheRateLimitAppliesPerAddressTests(_Validator):

    def test_a_forwarded_for_header_the_caller_writes_does_not_reset_the_count(self):
        with mock.patch.object(fashionista_build_view, 'VALIDATE_PER_ADDRESS', 3):
            answers = [self._post(_good(), REMOTE_ADDR='203.0.113.7',
                                  HTTP_X_FORWARDED_FOR='198.51.100.%d' % number).status_code
                       for number in range(1, 8)]
        self.assertEqual([200, 200, 200, 429, 429, 429, 429], answers)
        self.assertEqual({'build-validate:203.0.113.7', 'build-validate-new',
                          'build-validate-all'},
                         set(RateCounter.objects.values_list('key', flat=True)))

    def test_the_address_cloudflare_or_nginx_saw_is_the_one_counted(self):
        with mock.patch.object(fashionista_build_view, 'VALIDATE_PER_ADDRESS', 1):
            self.assertEqual(200, self._post(_good(), REMOTE_ADDR='10.0.0.2',
                                             HTTP_X_REAL_IP='203.0.113.7').status_code)
            self.assertEqual(429, self._post(_good(), REMOTE_ADDR='10.0.0.2',
                                             HTTP_X_REAL_IP='203.0.113.7').status_code)
            self.assertEqual(200, self._post(_good(), REMOTE_ADDR='10.0.0.2',
                                             HTTP_X_REAL_IP='203.0.113.7',
                                             HTTP_CF_CONNECTING_IP='198.51.100.4').status_code)

    def test_ipv6_addresses_of_one_64_share_their_count(self):
        with mock.patch.object(fashionista_build_view, 'VALIDATE_PER_ADDRESS', 2):
            for address, status in (('2001:db8:1:2::1', 200), ('2001:db8:1:2::ffff', 200),
                                    ('2001:db8:1:2:aaaa::9', 429), ('2001:db8:1:3::1', 200)):
                with self.subTest(address=address):
                    self.assertEqual(status, self._post(_good(), REMOTE_ADDR=address).status_code)
        self.assertIn('build-validate:2001:db8:1:2::/64',
                      set(RateCounter.objects.values_list('key', flat=True)))

    def test_new_addresses_past_their_ceiling_are_refused_and_leave_no_row(self):
        with mock.patch.object(fashionista_build_view, 'VALIDATE_NEW_ADDRESSES', 2):
            answers = [self._post(_good(), REMOTE_ADDR='203.0.113.%d' % number).status_code
                       for number in range(1, 5)]
            self.assertEqual([200, 200, 429, 429], answers)
            self.assertEqual(200, self._post(_good(), REMOTE_ADDR='203.0.113.1').status_code)
        self.assertEqual(2, RateCounter.objects.filter(key__startswith='build-validate:').count())

    def test_every_check_counts_toward_one_ceiling_for_the_whole_site(self):
        with mock.patch.object(fashionista_build_view, 'VALIDATE_ALL', 3):
            answers = [self._post(_good(), REMOTE_ADDR='203.0.113.%d' % number).status_code
                       for number in range(1, 6)]
        self.assertEqual([200, 200, 200, 429, 429], answers)

    def test_past_the_limit_an_address_gets_429_and_another_does_not(self):
        with mock.patch.object(fashionista_build_view, 'VALIDATE_PER_ADDRESS', 3):
            for _ in range(2):
                self.assertEqual(200, self._post(_good(), REMOTE_ADDR='203.0.113.7').status_code)
            self.client.options(URL, REMOTE_ADDR='203.0.113.7')
            self.assertEqual(200, self._post(_good(), REMOTE_ADDR='203.0.113.7').status_code)
            refused = self._post(_good(), REMOTE_ADDR='203.0.113.7')
            self.assertEqual(429, refused.status_code)
            self.assertEqual(str(fashionista_build_view.VALIDATE_WINDOW), refused['Retry-After'])
            self.assertEqual(['rate_limited'], [e['code'] for e in refused.json()['errors']])
            self.assertEqual('*', refused['Access-Control-Allow-Origin'])
            self.assertEqual(200, self._post(_good(), REMOTE_ADDR='198.51.100.4').status_code)

    def test_a_body_past_the_limit_is_refused_before_it_is_read(self):
        answer = self.client.generic('POST', URL, b'{}', content_type='application/json',
                                     CONTENT_LENGTH=str(10 ** 9))
        self.assertEqual(413, answer.status_code)
        self.assertEqual(['too_large'], [e['code'] for e in answer.json()['errors']])


class TheSchemaIsServedAndAgreesWithTheValidatorTests(_Validator):

    def test_the_schema_is_served_with_open_cors_at_its_own_id(self):
        self.assertEqual(SCHEMA, fashionista_build.SCHEMA_PATH)
        answer = self.client.get(SCHEMA)
        self.assertEqual(200, answer.status_code)
        self.assertEqual('*', answer['Access-Control-Allow-Origin'])
        schema = answer.json()
        self.assertEqual('https://dofusfashionista.gg' + SCHEMA, schema['$id'])
        self.assertEqual({'const': 'fashionista-build'}, schema['properties']['format'])

    def test_a_version_that_cannot_be_read_has_no_schema(self):
        for path in ('/api/v1/import/schema/2/', '/api/v1/import/schema/0/'):
            with self.subTest(path=path):
                answer = self.client.get(path)
                self.assertEqual(404, answer.status_code)
                self.assertEqual('*', answer['Access-Control-Allow-Origin'])
        self.assertEqual(404, self.client.get('/api/v1/import/schema/' + '9' * 5000 + '/')
                         .status_code)

    def test_the_api_root_lists_the_new_endpoints_and_the_developer_page(self):
        root = self.client.get('/api/v1/').json()
        for endpoint in ('POST /api/v1/import/validate/?lang=en',
                         'GET ' + SCHEMA,
                         'GET /api/v1/shared-builds/<encoded_id>/fashionista-build/'):
            self.assertIn(endpoint, root['endpoints'])
        self.assertEqual('https://dofusfashionista.gg/developers/send-a-build/',
                         root['send_a_build'])

    def _validator(self):
        try:
            import jsonschema
        except ImportError:
            raise unittest.SkipTest('jsonschema not installed')
        schema = self.client.get(SCHEMA).json()
        jsonschema.Draft202012Validator.check_schema(schema)
        return jsonschema.Draft202012Validator(schema)

    def test_the_schema_accepts_every_example_and_every_warning_case(self):
        validator = self._validator()
        payloads = [_good(game) for game in ('dofus3', 'beta', 'dofus2', 'touch', 'retro')]
        # The schema wants text for name; the reader leaves a wrong one out and reads the rest
        payloads += [payload for code, payload in _warning_cases().items()
                     if code != 'name_ignored']
        for payload in payloads:
            with self.subTest(payload=str(payload)[:60]):
                self.assertEqual([], [error.message for error in validator.iter_errors(payload)])

    def test_the_schema_refuses_what_the_validator_refuses_for_its_shape(self):
        validator = self._validator()
        catalogue_only = {'no_known_item', 'wrong_game', 'too_large'}
        for code, body in _error_cases().items():
            if code in catalogue_only:
                continue
            with self.subTest(code=code):
                try:
                    payload = json.loads(body)
                except ValueError:
                    continue
                self.assertFalse(validator.is_valid(copy.deepcopy(payload)))
