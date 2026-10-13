# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The read-only /setup/ preview shows the weights and minimums of the build the wizard door creates."""
import json
from functools import lru_cache
from itertools import product
from unittest import mock
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, RequestFactory, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from chardata import setup_preview
from chardata.create_project_view import create_project
from chardata.models import Char
from chardata.presets import FOCUS_COLUMNS, FOCUS_LIMIT, PRIORITIES, play_modes, setup_boxes
from chardata.smart_build import inert_aspects
from chardata.tests_every_preset_keeps_its_weights_and_minimums import (
    VERSIONS, _version_path, load_fixture)
from chardata.version_compat import class_exists_in_version, filter_classes_for_version
from chardata.weights_minimums import _caps, page_state
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.structure import get_current_game_version, set_current_game_version
from fashionistapulp.temporix import version_has_temporix

MAX_BODY_BYTES = 6 * 1024
STATE_KEYS = {'weights', 'minimums', 'ranges', 'members'}
LEVELS = (50, 120, 170, 200)
BOX_SETS = (frozenset(), frozenset({'str'}), frozenset({'int', 'crit'}),
            frozenset({'cha', 'res', 'pp'}), frozenset({'agi', 'dam', 'heal'}))


def form_fields(char_class, level, aspects, priority=None, play_mode=None, temporix=None):
    fields = [('project', ''), ('charname', ''), ('class', char_class), ('level', str(level)),
              ('wizard', 'wizard')]
    fields += [('check_%s' % aspect, 'on') for aspect in sorted(aspects)]
    if priority is not None:
        fields.append(('priority', priority))
    if play_mode is not None:
        fields.append(('play_mode', play_mode))
    if temporix is not None:
        fields.append(('temporix', 'on' if temporix else 'off'))
    return fields


def preview_url(version, fields):
    return '%s?%s' % (_version_path(version, '/setuppreview/'), urlencode(fields))


def classes_of(version):
    return filter_classes_for_version(CHARACTER_CLASSES, version)


@lru_cache(maxsize=1)
def golden_wizard_cases():
    cases = {}
    for name, record in load_fixture('setup').items():
        parts = name.split(' ')
        if len(parts) < 5 or parts[3] != 'wizard':
            continue
        cases.setdefault(parts[0], []).append(
            (name, parts[1], int(parts[2]), record['aspects'], 'temporix' in parts[5:]))
    return cases


def as_json(value):
    return json.loads(json.dumps(value))


class _FreshPreview(object):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        setup_preview._preview_body.cache_clear()


class _DoorBuilds(_FreshPreview):

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('setup-preview', 'preview@test.local',
                                             'pw-setup-preview-17')

    def door_build(self, version, fields):
        set_current_game_version(version)
        request = RequestFactory().post('/', dict(fields))
        request.user = self.owner
        request.game_version = version
        response = create_project(request)
        self.assertEqual(302, response.status_code)
        return Char.objects.order_by('-id').first()

    def problems(self, version, name, fields, char_class, level, aspects, priority=None,
                 play_mode=None, temporix=False):
        built = self.door_build(version, fields)
        set_current_game_version(version)
        stored = Char.objects.get(pk=built.pk)
        expected = as_json(page_state(stored))
        expected_caps = as_json(_caps(stored))
        found = []
        kwargs = {key: value for key, value in (('priority', priority),
                                                ('play_mode', play_mode)) if value is not None}
        preview = as_json(setup_preview.preview_state(
            version, char_class, level, frozenset(aspects), temporix=temporix, **kwargs))
        response = self.client.get(preview_url(version, fields))
        if response.status_code != 200:
            return ['%s answered %d' % (name, response.status_code)]
        served = response.json()
        if len(response.content) >= MAX_BODY_BYTES:
            found.append('%s: %d bytes' % (name, len(response.content)))
        for source, state in (('function', preview), ('view', served)):
            if as_json(state.get('caps')) != expected_caps:
                found.append('%s: %s caps differ' % (name, source))
            for key in sorted(expected):
                if state.get(key) != expected[key]:
                    found.append('%s: %s differs on %s' % (name, source, key))
        return found


class ThePreviewEqualsTheBuildOfEveryGoldenSetupCaseTests(_DoorBuilds, TestCase):

    def check_version(self, version):
        cases = golden_wizard_cases()[version]
        self.assertGreater(len(cases), 100)
        found = []
        for name, char_class, level, aspects, temporix in cases:
            fields = form_fields(char_class, level, aspects, temporix=True if temporix else None)
            found += self.problems(version, name, fields, char_class, level, aspects,
                                   temporix=temporix)
        self.assertEqual([], found[:20])

    def test_dofus3(self):
        self.check_version('dofus3')

    def test_beta(self):
        self.check_version('beta')

    def test_dofus2(self):
        self.check_version('dofus2')

    def test_touch(self):
        self.check_version('touch')

    def test_retro(self):
        self.check_version('retro')

    def test_every_version_of_the_fixture_is_walked(self):
        self.assertEqual(set(VERSIONS), set(golden_wizard_cases()))


class ThePreviewEqualsTheBuildOfEveryPriorityAndModeTests(_DoorBuilds, TestCase):

    def check_version(self, version):
        classes = classes_of(version)
        pairs = list(product([priority.key for priority in PRIORITIES],
                             [key for key, _label in play_modes(version)]))
        found = []
        for index, (priority, play_mode) in enumerate(pairs):
            for shift in range(3):
                step = index + shift
                char_class = classes[(index * 3 + shift) % len(classes)]
                level = LEVELS[step % len(LEVELS)]
                aspects = BOX_SETS[step % len(BOX_SETS)]
                fields = form_fields(char_class, level, aspects, priority, play_mode)
                name = '%s %s %d %s %s %s' % (version, char_class, level, priority, play_mode,
                                              '+'.join(sorted(aspects)) or 'none')
                found += self.problems(version, name, fields, char_class, level, aspects,
                                       priority, play_mode)
        self.assertEqual([], found[:20])
        self.assertGreaterEqual(len(pairs), 16)

    def test_dofus3(self):
        self.check_version('dofus3')

    def test_beta(self):
        self.check_version('beta')

    def test_dofus2(self):
        self.check_version('dofus2')

    def test_touch(self):
        self.check_version('touch')

    def test_retro(self):
        self.check_version('retro')


class TheTemporixSwitchMovesOnlyTheCapsTests(_DoorBuilds, TestCase):

    def test_the_caps_match_the_build_the_door_creates_with_the_switch_on_and_off(self):
        for temporix in (True, False):
            with self.subTest(temporix=temporix):
                fields = form_fields('Iop', 200, {'int'}, temporix=temporix)
                self.assertEqual(
                    [], self.problems('touch', 'touch temporix %s' % temporix, fields, 'Iop',
                                      200, {'int'}, temporix=temporix))

    def test_the_switch_changes_the_caps_and_leaves_the_weights_and_minimums(self):
        on = self.client.get(preview_url('touch', form_fields('Iop', 200, {'int'}, temporix=True))).json()
        off = self.client.get(preview_url('touch', form_fields('Iop', 200, {'int'}, temporix=False))).json()
        self.assertNotEqual(on['caps'], off['caps'])
        for key in STATE_KEYS:
            self.assertEqual(on[key], off[key], key)

    def test_a_missing_switch_reads_as_off(self):
        bare = self.client.get(preview_url('touch', form_fields('Iop', 200, {'int'}))).json()
        off = self.client.get(preview_url('touch', form_fields('Iop', 200, {'int'}, temporix=False))).json()
        self.assertEqual(off, bare)


class ThePreviewWritesNothingTests(_DoorBuilds, TestCase):

    def requests(self):
        yield preview_url('dofus3', form_fields('Iop', 200, {'str', 'crit'}))
        yield preview_url('retro', form_fields('Cra', 100, {'agi'}, 'damage', 'group_pvp'))
        yield preview_url('touch', form_fields('Xelor', 200, {'cha'}, temporix=True))
        yield preview_url('beta', form_fields('Iop', 0, {'str'}))

    def test_no_char_is_created_and_no_statement_writes(self):
        before = Char.objects.count()
        with CaptureQueriesContext(connection) as captured:
            for url in self.requests():
                self.client.get(url)
            setup_preview.preview_state('dofus3', 'Iop', 200, frozenset({'str'}), 'damage',
                                        'koli_1v1')
        statements = [query['sql'] for query in captured]
        self.assertEqual(before, Char.objects.count())
        self.assertEqual([], [sql for sql in statements
                              if sql.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))])
        self.assertEqual([], statements)

    def test_the_game_version_the_caller_had_is_still_current_afterwards(self):
        set_current_game_version('retro')
        setup_preview.preview_state('touch', 'Iop', 200, frozenset({'int'}), temporix=True)
        self.assertEqual('retro', get_current_game_version())

    def test_the_game_version_is_restored_when_the_preview_fails(self):
        set_current_game_version('retro')
        with mock.patch.object(setup_preview, 'get_standard_weights', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                setup_preview.preview_state('touch', 'Iop', 200, frozenset({'int'}))
        self.assertEqual('retro', get_current_game_version())


class ThePreviewAnswerHasTheShapeTheBlockReadsTests(_FreshPreview, SimpleTestCase):

    def get(self, version, fields):
        return self.client.get(preview_url(version, fields))

    def test_a_valid_request_answers_json_with_the_page_state_keys_and_the_caps(self):
        response = self.get('dofus3', form_fields('Iop', 200, {'str', 'glasscannon'}))
        self.assertEqual(200, response.status_code)
        self.assertEqual('application/json', response['Content-Type'])
        state = response.json()
        self.assertEqual(STATE_KEYS | {'caps'}, set(state))
        self.assertTrue(all(isinstance(value, (int, float))
                            for value in state['weights'].values()))
        for part in ('weights', 'minimums', 'caps'):
            self.assertIn('ap', state[part], part)

    def test_a_priority_changes_the_weights(self):
        balanced = self.get('dofus3', form_fields('Iop', 200, {'str'})).json()
        damage = self.get('dofus3', form_fields('Iop', 200, {'str'}, 'damage')).json()
        self.assertNotEqual(balanced['weights'], damage['weights'])

    def test_the_answer_is_cacheable_for_ten_minutes(self):
        response = self.get('dofus3', form_fields('Iop', 200, {'str'}))
        self.assertIn('max-age=600', response['Cache-Control'])

    def test_form_fields_the_preview_does_not_read_are_ignored(self):
        bare = self.get('dofus3', [('class', 'Iop'), ('level', '200'), ('check_str', 'on')])
        form = self.get('dofus3', form_fields('Iop', 200, {'str'}) + [
            ('publish', 'on'), ('lock_item', ''), ('csrfmiddlewaretoken', 'x'),
            ('check_balanced', 'on')])
        self.assertEqual(bare.content, form.content)

    def test_an_unticked_box_reads_as_no_box(self):
        bare = self.get('dofus3', [('class', 'Iop'), ('level', '200')])
        off = self.get('dofus3', [('class', 'Iop'), ('level', '200'), ('check_str', 'off')])
        self.assertEqual(bare.content, off.content)

    def test_the_order_of_the_boxes_does_not_matter(self):
        first = self.get('dofus3', [('class', 'Iop'), ('level', '200'),
                                    ('check_str', 'on'), ('check_crit', 'on')])
        second = self.get('dofus3', [('check_crit', 'on'), ('check_str', 'on'),
                                     ('level', '200'), ('class', 'Iop')])
        self.assertEqual(first.content, second.content)

    def test_the_first_and_the_last_level_are_accepted(self):
        for level in (1, 200):
            with self.subTest(level=level):
                self.assertEqual(200, self.get('dofus3', form_fields('Iop', level, {'str'}))
                                 .status_code)


class EveryVersionNamespaceAnswersThePreviewTests(_FreshPreview, SimpleTestCase):

    def test_each_version_answers_200_for_its_own_first_class(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                response = Client().get(preview_url(version, form_fields(
                    classes_of(version)[0], 200, {'str'})))
                self.assertEqual(200, response.status_code)
                self.assertEqual(STATE_KEYS | {'caps'}, set(response.json()))

    def test_the_route_is_named_in_every_namespace(self):
        self.assertEqual('/setuppreview/', reverse('setup_preview'))
        for version in VERSIONS:
            if version != 'dofus3':
                with self.subTest(version=version):
                    self.assertEqual('/%s/setuppreview/' % version,
                                     reverse('%s:setup_preview' % version))

    def test_a_language_prefix_reaches_the_same_view(self):
        response = Client().get('/fr/touch/setuppreview/?%s' % urlencode(
            form_fields('Iop', 200, {'str'})))
        self.assertEqual(200, response.status_code)

    def test_a_version_answers_for_a_class_only_when_it_has_the_class(self):
        for version in VERSIONS:
            missing = [name for name in CHARACTER_CLASSES
                       if not class_exists_in_version(name, version)]
            for name in missing:
                with self.subTest(version=version, char_class=name):
                    self.assertEqual(400, Client().get(preview_url(
                        version, form_fields(name, 200, {'str'}))).status_code)
        self.assertTrue(any(not class_exists_in_version(name, version)
                            for version in VERSIONS for name in CHARACTER_CLASSES))


class AnInvalidPreviewRequestAnswers400Tests(_FreshPreview, SimpleTestCase):

    def refused(self, version, pairs, field):
        response = Client().get(preview_url(version, pairs))
        self.assertEqual(400, response.status_code, pairs)
        self.assertEqual({'error': 'invalid', 'field': field}, response.json(), pairs)

    def test_a_missing_or_unknown_class(self):
        self.refused('dofus3', [('level', '200')], 'class')
        self.refused('dofus3', [('class', 'NoSuchClass'), ('level', '200')], 'class')
        self.refused('dofus3', [('class', 'iop'), ('level', '200')], 'class')
        self.refused('dofus3', [('class', ''), ('level', '200')], 'class')

    def test_a_class_given_twice(self):
        self.refused('dofus3', [('class', 'Iop'), ('class', 'Cra'), ('level', '200')], 'class')

    def test_a_level_outside_one_to_the_cap_or_not_a_number(self):
        for level in ('0', '201', '999', '1000', '-5', '+5', 'abc', '', '1.5', '2e2', ' 200',
                      '20 0', '\u0662\u0660\u0660', '\u00b2'):
            with self.subTest(level=level):
                self.refused('dofus3', [('class', 'Iop'), ('level', level)], 'level')
        self.refused('dofus3', [('class', 'Iop')], 'level')

    def test_a_box_the_form_does_not_offer(self):
        self.refused('dofus3', [('class', 'Iop'), ('level', '200'), ('check_nope', 'on')],
                     'check_nope')
        self.refused('dofus3', [('class', 'Iop'), ('level', '200'), ('check_', 'on')], 'check_')
        self.refused('dofus3', [('class', 'Iop'), ('level', '200'), ('check_Str', 'on')],
                     'check_Str')

    def test_a_box_set_to_anything_but_on_or_off(self):
        for value in ('yes', '1', 'true', 'ON', ''):
            with self.subTest(value=value):
                self.refused('dofus3', [('class', 'Iop'), ('level', '200'),
                                        ('check_str', value)], 'check_str')

    def test_an_inert_box_of_the_version(self):
        walked = 0
        for version in VERSIONS:
            for aspect in inert_aspects(version):
                walked += 1
                with self.subTest(version=version, aspect=aspect):
                    self.refused(version, form_fields(classes_of(version)[0], 200, {aspect}),
                                 'check_%s' % aspect)
        self.assertGreater(walked, 0)

    def test_more_focus_boxes_than_the_limit(self):
        for version in VERSIONS:
            offered = setup_boxes(version) - set(inert_aspects(version))
            focus = [box for column in FOCUS_COLUMNS for box in column
                     if box in offered and box != 'balanced']
            with self.subTest(version=version):
                char_class = classes_of(version)[0]
                self.refused(version, form_fields(char_class, 200, focus[:FOCUS_LIMIT + 1]),
                             'focus')
                response = Client().get(preview_url(
                    version, form_fields(char_class, 200, focus[:FOCUS_LIMIT])))
                self.assertEqual(200, response.status_code)

    def test_an_unknown_priority_or_mode(self):
        base = [('class', 'Iop'), ('level', '200')]
        self.refused('dofus3', base + [('priority', 'everything')], 'priority')
        self.refused('dofus3', base + [('priority', '')], 'priority')
        self.refused('dofus3', base + [('play_mode', 'koli_9v9')], 'play_mode')
        self.refused('dofus3', base + [('play_mode', '')], 'play_mode')
        self.refused('dofus3', base + [('priority', 'damage'), ('priority', 'defense')],
                     'priority')

    def test_a_mode_another_version_offers(self):
        base = [('class', 'Iop'), ('level', '200')]
        self.refused('dofus3', base + [('play_mode', 'group_pvp')], 'play_mode')
        self.refused('retro', base + [('play_mode', 'koli_3v3')], 'play_mode')
        self.refused('touch', base + [('play_mode', 'koli_2v2')], 'play_mode')

    def test_a_temporix_switch_on_a_version_without_it_or_with_a_bad_value(self):
        base = [('class', 'Iop'), ('level', '200')]
        for version in VERSIONS:
            if not version_has_temporix(version):
                with self.subTest(version=version):
                    self.refused(version, base + [('temporix', 'on')], 'temporix')
        self.refused('touch', base + [('temporix', 'maybe')], 'temporix')

    def test_only_a_get_or_a_head_is_answered(self):
        url = preview_url('dofus3', form_fields('Iop', 200, {'str'}))
        self.assertEqual(405, Client().post(url).status_code)
        self.assertEqual(200, Client().head(url).status_code)


class ThePreviewIsKeptPerProcessTests(_FreshPreview, SimpleTestCase):

    def hits(self):
        return setup_preview._preview_body.cache_info().hits

    def misses(self):
        return setup_preview._preview_body.cache_info().misses

    def test_the_cache_holds_512_entries(self):
        self.assertEqual(512, setup_preview._preview_body.cache_info().maxsize)

    def test_the_same_request_twice_computes_once_and_answers_the_same_bytes(self):
        url = preview_url('dofus3', form_fields('Iop', 200, {'str'}))
        first = Client().get(url)
        self.assertEqual((0, 1), (self.hits(), self.misses()))
        second = Client().get(url)
        self.assertEqual((1, 1), (self.hits(), self.misses()))
        self.assertEqual(first.content, second.content)

    def test_every_parameter_is_part_of_the_key(self):
        base = dict(char_class='Iop', level=200, aspects={'str'}, priority=None,
                    play_mode=None)
        variants = [dict(), dict(char_class='Cra'), dict(level=199), dict(aspects={'int'}),
                    dict(priority='damage'), dict(play_mode='koli_1v1')]
        for changes in variants:
            merged = dict(base, **changes)
            Client().get(preview_url('dofus3', form_fields(
                merged['char_class'], merged['level'], merged['aspects'],
                merged['priority'], merged['play_mode'])))
        self.assertEqual((0, len(variants)), (self.hits(), self.misses()))

    def test_the_game_version_is_part_of_the_key(self):
        fields = form_fields('Iop', 200, {'str'})
        Client().get(preview_url('dofus3', fields))
        Client().get(preview_url('beta', fields))
        self.assertEqual((0, 2), (self.hits(), self.misses()))

    def test_the_temporix_switch_is_part_of_the_key(self):
        Client().get(preview_url('touch', form_fields('Iop', 200, {'str'}, temporix=True)))
        Client().get(preview_url('touch', form_fields('Iop', 200, {'str'}, temporix=False)))
        self.assertEqual((0, 2), (self.hits(), self.misses()))

    def test_the_data_version_is_part_of_the_key(self):
        url = preview_url('dofus3', form_fields('Iop', 200, {'str'}))
        Client().get(url)
        with mock.patch.object(setup_preview, 'current_data_version', return_value='9.9.9.9'):
            Client().get(url)
        self.assertEqual((0, 2), (self.hits(), self.misses()))

    def test_a_refused_request_computes_nothing(self):
        Client().get(preview_url('dofus3', form_fields('Iop', 201, {'str'})))
        self.assertEqual((0, 0), (self.hits(), self.misses()))
