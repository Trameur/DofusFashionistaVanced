# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ script asks the preview route for what the form says and tells the player what the last click changed."""
import io
import json
import os
import shutil
import subprocess
import tempfile

from django.test import SimpleTestCase, TestCase

from chardata import setup_preview
from chardata.presets import (ELEMENT_BOXES, FOCUS_COLUMNS, GUARD_KIND, GUARD_PERCENTS,
                              play_modes, setup_boxes, stat_floors)
from chardata.smart_build import inert_aspects
from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS, _version_path
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.temporix import version_has_temporix

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, 'static', 'chardata', 'setup.js')

PRELUDE = r"""
var window = {};
var document = {};
var $ = function() { return {ready: function() {}}; };
function gettext(text) { return text; }
function ngettext(one, many, count) { return count === 1 ? one : many; }
function interpolate(format, values, named) {
    if (named) {
        return format.replace(/%\(\w+\)s/g, function(match) { return String(values[match.slice(2, -2)]); });
    }
    return format.replace(/%s/g, function() { return String(values.shift()); });
}
function flush() { return new Promise(function(done) { setImmediate(done); }); }
function fakeEnv() {
    var env = {next: null, loads: [], controllers: [], shows: [], failures: 0, settles: 0};
    env.query = function() { return env.next; };
    env.newController = function() {
        var controller = {aborted: false, signal: {}, abort: function() { this.aborted = true; }};
        env.controllers.push(controller);
        return controller;
    };
    env.load = function(query, signal) {
        return new Promise(function(resolve, reject) {
            env.loads.push({query: query, resolve: resolve, reject: reject, signal: signal});
        });
    };
    env.show = function(state, query) { env.shows.push([query, state]); };
    env.failed = function() { env.failures += 1; };
    env.settled = function() { env.settles += 1; };
    return env;
}
"""


def run_script(case, body):
    node = shutil.which('node')
    if node is None:
        case.skipTest('node is not installed')
    source = io.open(SCRIPT, encoding='utf-8').read()
    program = '\n'.join([PRELUDE, source, """
Promise.resolve((async function() {%s})()).then(function(result) {
    console.log(JSON.stringify(result));
}, function(error) { console.error(String(error && error.stack || error)); process.exit(1); });
""" % body])
    with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8', delete=False) as handle:
        handle.write(program)
        name = handle.name
    try:
        done = subprocess.run([node, name], capture_output=True, text=True, encoding='utf-8')
    finally:
        os.unlink(name)
    case.assertEqual(0, done.returncode, done.stderr[-800:])
    return json.loads(done.stdout)


class TheScriptIsValidTests(SimpleTestCase):

    def test_node_accepts_the_file(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('node is not installed')
        done = subprocess.run([node, '--check', SCRIPT], capture_output=True, text=True)
        self.assertEqual(0, done.returncode, done.stderr[-800:])


class TheQueryTheScriptBuildsTests(SimpleTestCase):

    def query(self, fields):
        return run_script(self, 'return setupPreviewQuery(%s);' % json.dumps(fields))

    def test_the_fields_come_out_sorted_so_one_choice_is_one_query(self):
        fields = {'className': 'Iop', 'level': '200', 'boxes': ['str', 'crit', 'int'],
                  'priority': 'balanced', 'playMode': 'general', 'temporix': None}
        self.assertEqual('class=Iop&level=200&check_crit=on&check_int=on&check_str=on'
                         '&priority=balanced&play_mode=general', self.query(fields))
        fields['boxes'] = ['int', 'str', 'crit']
        self.assertEqual('class=Iop&level=200&check_crit=on&check_int=on&check_str=on'
                         '&priority=balanced&play_mode=general', self.query(fields))

    def test_a_level_the_route_would_refuse_asks_nothing(self):
        for level in ('', '0', '201', '20.5', 'abc', '-5', '1000', ' 5'):
            with self.subTest(level=level):
                self.assertIsNone(self.query({'className': 'Iop', 'level': level}))
        for level in ('1', '200', '050'):
            with self.subTest(level=level):
                self.assertIsNotNone(self.query({'className': 'Iop', 'level': level}))

    def test_no_class_asks_nothing(self):
        self.assertIsNone(self.query({'className': None, 'level': '200'}))
        self.assertIsNone(self.query({'className': '', 'level': '200'}))

    def test_temporix_is_sent_only_where_the_form_has_the_box(self):
        base = {'className': 'Iop', 'level': '200'}
        self.assertNotIn('temporix', self.query(dict(base, temporix=None)))
        self.assertTrue(self.query(dict(base, temporix=True)).endswith('&temporix=on'))
        self.assertTrue(self.query(dict(base, temporix=False)).endswith('&temporix=off'))

    def test_a_value_is_escaped(self):
        self.assertEqual('class=A%20B%26C&level=5',
                         self.query({'className': 'A B&C', 'level': '5'}))


def offered_boxes(version):
    return setup_boxes(version) - set(inert_aspects(version))


class TheQueryTheScriptBuildsIsTheOneTheRouteAnswersTests(TestCase):

    def asked(self, version, fields):
        query = run_script(self, 'return setupPreviewQuery(%s);' % json.dumps(fields))
        return query, self.client.get('%s?%s' % (_version_path(version, '/setuppreview/'), query))

    def test_every_version_answers_the_query_with_the_state_of_its_function(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                char_class = sorted(filter_classes_for_version(CHARACTER_CLASSES, version))[0]
                mode = [key for key, _label in play_modes(version)][-1]
                temporix = True if version_has_temporix(version) else None
                offered = offered_boxes(version)
                aspects = [sorted(offered & set(ELEMENT_BOXES))[0],
                           sorted(offered & {a for column in FOCUS_COLUMNS for a in column})[0]]
                query, response = self.asked(version, {
                    'className': char_class, 'level': '170', 'boxes': aspects,
                    'priority': 'damage', 'playMode': mode, 'temporix': temporix})
                self.assertEqual(200, response.status_code, query)
                set_current_game_version('dofus3')
                expected = setup_preview.preview_state(
                    version, char_class, 170, frozenset(aspects), priority='damage',
                    play_mode=mode, temporix=bool(temporix))
                self.assertEqual(json.loads(json.dumps(expected)), response.json())
        set_current_game_version('dofus3')

    def test_every_box_the_page_draws_is_a_box_the_route_accepts(self):
        for version in VERSIONS:
            char_class = sorted(filter_classes_for_version(CHARACTER_CLASSES, version))[0]
            refused = []
            for aspect in sorted(offered_boxes(version)):
                _query, response = self.asked(version, {
                    'className': char_class, 'level': '200', 'boxes': [aspect]})
                if response.status_code != 200:
                    refused.append(aspect)
            self.assertEqual([], refused, version)
        set_current_game_version('dofus3')

    def test_the_switch_is_sent_only_on_the_version_that_has_it(self):
        for version in VERSIONS:
            char_class = sorted(filter_classes_for_version(CHARACTER_CLASSES, version))[0]
            for ticked in (True, False):
                _query, response = self.asked(version, {
                    'className': char_class, 'level': '200', 'temporix': ticked})
                self.assertEqual(200 if version_has_temporix(version) else 400,
                                 response.status_code, (version, ticked))
        set_current_game_version('dofus3')


class TheChangesTheScriptReportsTests(SimpleTestCase):

    def test_an_unchanged_row_is_not_reported(self):
        self.assertEqual({}, run_script(self, """
            return setupPreviewChanges({ap: {weight: '5', min: '11'}, mp: {weight: '2', min: ''}},
                                       {ap: {weight: '5', min: '11'}, mp: {weight: '2', min: ''}});"""))

    def test_a_weight_and_a_minimum_are_told_apart_with_their_old_values(self):
        self.assertEqual({'ap': {'weight': True, 'min': False, 'weightWas': '5', 'minWas': '11'},
                          'mp': {'weight': False, 'min': True, 'weightWas': '2', 'minWas': ''},
                          'vit': {'weight': True, 'min': True, 'weightWas': '1', 'minWas': ''}},
                         run_script(self, """
            return setupPreviewChanges(
                {ap: {weight: '5', min: '11'}, mp: {weight: '2', min: ''},
                 vit: {weight: '1', min: ''}},
                {ap: {weight: '6', min: '11'}, mp: {weight: '2', min: '6'},
                 vit: {weight: '9', min: '3'}});"""))

    def test_a_row_without_a_box_in_a_column_never_counts_for_that_column(self):
        self.assertEqual({}, run_script(self, """
            return setupPreviewChanges({chance: {weight: undefined, min: '4'}},
                                       {chance: {weight: undefined, min: '4'}});"""))
        self.assertEqual({'chance': {'weight': False, 'min': True, 'weightWas': None,
                                     'minWas': '4'}},
                         run_script(self, """
            var changes = setupPreviewChanges({chance: {min: '4'}}, {chance: {min: '5'}});
            changes.chance.weightWas = changes.chance.weightWas === undefined ? null : 1;
            return changes;"""))

    def test_a_row_the_first_state_did_not_have_is_ignored(self):
        self.assertEqual({}, run_script(self, """
            return setupPreviewChanges({}, {ap: {weight: '5', min: ''}});"""))
        self.assertEqual({}, run_script(self, """
            return setupPreviewChanges(null, {ap: {weight: '5', min: ''}});"""))


class TheSentencesTheScriptWritesTests(SimpleTestCase):

    def summary(self, names, total=None):
        return run_script(self, 'return setupPreviewSummary(%s, %d);' % (
            json.dumps(names), len(names) if total is None else total))

    def test_nothing_changed(self):
        self.assertEqual('Your last choice left the weights and minimums unchanged.',
                         self.summary([]))

    def test_one_name(self):
        self.assertEqual('Your last choice changed 1 characteristic: AP.', self.summary(['AP']))

    def test_three_names_are_all_listed(self):
        self.assertEqual('Your last choice changed 3 characteristics: AP, Damage, Range.',
                         self.summary(['AP', 'Damage', 'Range']))

    def test_more_than_three_names_end_with_a_count_of_the_others(self):
        self.assertEqual('Your last choice changed 4 characteristics: AP, Damage, Range and 1 more.',
                         self.summary(['AP', 'Damage', 'Range', 'MP']))
        names = ['AP', 'Damage', 'Range'] + ['x%d' % i for i in range(22)]
        self.assertEqual('Your last choice changed 25 characteristics: AP, Damage, Range and 22 more.',
                         self.summary(names))

    def test_the_badge_and_the_tooltip(self):
        self.assertEqual(['1 changed', '7 changed'], run_script(self, """
            return [setupPreviewBadge(1), setupPreviewBadge(7)];"""))
        self.assertEqual(['Weight was 5', 'Minimum was 11', 'There was no minimum',
                          'Weight was 1\nMinimum was 4'], run_script(self, """
            return [setupPreviewTitle({weight: true, weightWas: '5'}),
                    setupPreviewTitle({min: true, minWas: '11'}),
                    setupPreviewTitle({min: true, minWas: ''}),
                    setupPreviewTitle({weight: true, weightWas: '1', min: true, minWas: '4'})];"""))


class TheSafeguardLineTheScriptWritesTests(SimpleTestCase):

    def line(self, priority, percent):
        return run_script(self, 'return setupPreviewGuard(%s, %s, %s);' % (
            json.dumps(priority), json.dumps(percent), json.dumps(GUARD_KIND)))

    def test_a_damage_priority_names_effective_hp_and_the_share_kept(self):
        self.assertEqual(
            'Safeguard: effective HP, AP, MP, Range and the other stats the priority does not aim '
            'for keep at least 90% of their value in the balanced build. The exact values are '
            'computed at launch.', self.line('damage', '10'))

    def test_a_defense_or_heals_priority_names_the_damage_stats_instead(self):
        expected = ('Safeguard: damage stats, AP, MP, Range and the other stats the priority does '
                    'not aim for keep at least 85% of their value in the balanced build. The exact '
                    'values are computed at launch.')
        self.assertEqual(expected, self.line('defense', '15'))
        self.assertEqual(expected, self.line('heals', '15'))

    def test_no_priority_has_no_safeguard_line(self):
        self.assertIsNone(self.line('balanced', '10'))
        self.assertIsNone(self.line(None, '10'))

    def test_the_strictest_safeguard_is_still_told_because_it_keeps_everything(self):
        self.assertIn('keep at least 100% of their value', self.line('damage', '0'))

    def test_a_percent_the_form_does_not_hold_says_nothing(self):
        for percent in (None, '', 'abc', '-5', '101'):
            with self.subTest(percent=percent):
                self.assertIsNone(self.line('damage', percent))

    def test_a_kind_the_server_did_not_send_says_nothing(self):
        self.assertIsNone(run_script(self, "return setupPreviewGuard('damage', '10', {damage: 'other'});"))
        self.assertIsNone(run_script(self, "return setupPreviewGuard('damage', '10', null);"))

    def test_every_percent_the_form_offers_is_told_as_the_share_the_server_keeps(self):
        for percent in GUARD_PERCENTS:
            for priority, kind in GUARD_KIND.items():
                with self.subTest(percent=percent, priority=priority):
                    kept = stat_floors(kind, percent, {'mp': 100}, ['mp'])['mp']
                    self.assertIn('keep at least %d%% of their value' % kept,
                                  self.line(priority, str(percent)))


class TheRequestsTheScriptSendsTests(SimpleTestCase):

    def test_the_first_choice_is_asked_once_and_shown_when_it_arrives(self):
        self.assertEqual({'loads': ['q1'], 'shows': [['q1', {'v': 1}]], 'failures': 0},
                         run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            env.next = 'q1'; loop.refresh(); loop.refresh();
            env.loads[0].resolve({v: 1}); await flush();
            return {loads: env.loads.map(function(l) { return l.query; }), shows: env.shows,
                    failures: env.failures};"""))

    def test_a_choice_asked_before_is_not_asked_again(self):
        self.assertEqual({'loads': ['q1', 'q2'],
                          'shows': [['q1', {'v': 1}], ['q2', {'v': 2}], ['q1', {'v': 1}]]},
                         run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            env.next = 'q1'; loop.refresh(); env.loads[0].resolve({v: 1}); await flush();
            env.next = 'q2'; loop.refresh(); env.loads[1].resolve({v: 2}); await flush();
            env.next = 'q1'; loop.refresh(); await flush();
            return {loads: env.loads.map(function(l) { return l.query; }), shows: env.shows};"""))

    def test_the_choice_on_screen_asks_nothing_and_clears_the_notice(self):
        self.assertEqual({'loads': 1, 'settles': 2}, run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            env.next = 'q1'; loop.refresh(); env.loads[0].resolve({v: 1}); await flush();
            loop.refresh(); loop.refresh();
            return {loads: env.loads.length, settles: env.settles};"""))

    def test_an_invalid_form_asks_nothing(self):
        self.assertEqual({'loads': 0, 'shows': 0}, run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            env.next = null; loop.refresh();
            return {loads: env.loads.length, shows: env.shows.length};"""))

    def test_a_newer_choice_cancels_the_older_request_and_its_late_answer_is_ignored(self):
        self.assertEqual({'aborted': [True, False], 'shows': [['q2', {'v': 2}]]},
                         run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            env.next = 'q1'; loop.refresh();
            env.next = 'q2'; loop.refresh();
            env.loads[0].resolve({v: 1}); env.loads[1].resolve({v: 2}); await flush();
            return {aborted: env.controllers.map(function(c) { return c.aborted; }),
                    shows: env.shows};"""))

    def test_going_back_to_the_choice_on_screen_cancels_the_request_on_its_way(self):
        self.assertEqual({'aborted': [False, True], 'shows': [['q1', {'v': 1}]]},
                         run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            env.next = 'q1'; loop.refresh(); env.loads[0].resolve({v: 1}); await flush();
            env.next = 'q2'; loop.refresh();
            env.next = 'q1'; loop.refresh();
            env.loads[1].resolve({v: 2}); await flush();
            return {aborted: env.controllers.map(function(c) { return c.aborted; }),
                    shows: env.shows};"""))

    def test_a_failure_keeps_what_was_shown_and_the_next_choice_asks_again(self):
        self.assertEqual({'failures': 1, 'shows': [['q1', {'v': 1}], ['q3', {'v': 3}]],
                          'loads': ['q1', 'q2', 'q2', 'q3']}, run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            env.next = 'q1'; loop.refresh(); env.loads[0].resolve({v: 1}); await flush();
            env.next = 'q2'; loop.refresh(); env.loads[1].reject(new Error('status 500')); await flush();
            loop.refresh(); env.loads[2].reject({name: 'AbortError'}); await flush();
            env.next = 'q3'; loop.refresh(); env.loads[3].resolve({v: 3}); await flush();
            return {failures: env.failures, shows: env.shows,
                    loads: env.loads.map(function(l) { return l.query; })};"""))

    def test_an_aborted_request_is_not_a_failure(self):
        self.assertEqual(0, run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            env.next = 'q1'; loop.refresh(); env.loads[0].reject({name: 'AbortError'}); await flush();
            return env.failures;"""))

    def test_a_script_error_while_showing_is_a_failure_not_a_silent_half_update(self):
        self.assertEqual(1, run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            env.show = function() { throw new Error('boom'); };
            env.next = 'q1'; loop.refresh(); env.loads[0].resolve({v: 1}); await flush();
            return env.failures;"""))

    def test_the_memo_forgets_its_oldest_answer_first(self):
        self.assertEqual({'again': True, 'kept': False}, run_script(self, """
            var env = fakeEnv(); var loop = setupPreviewLoop(env);
            var total = SETUP_PREVIEW.memoLimit + 1;
            for (var i = 0; i < total; i++) {
                env.next = 'q' + i; loop.refresh(); env.loads[i].resolve({v: i}); await flush();
            }
            var before = env.loads.length;
            env.next = 'q0'; loop.refresh(); var again = env.loads.length > before;
            await flush();
            before = env.loads.length;
            env.next = 'q' + (total - 1); loop.refresh();
            return {again: again, kept: env.loads.length > before};"""))
