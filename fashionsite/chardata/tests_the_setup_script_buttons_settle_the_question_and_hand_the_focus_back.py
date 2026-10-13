# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ panel buttons settle the open question or restore the preset and hand the focus back to the panel title, and a failed preview closes the question."""
import io
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_page_draws_the_live_weights_panel import SCRIPT
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script

WORLD = """
    var log = [];
    var edited = 1;
    var gate = setupEditGate({
        hasBaseline: function() { return true; },
        edited: function() { return edited; },
        same: function() { return false; },
        apply: function(state, keep) { log.push(['apply', state, keep]); },
        ask: function(on) { log.push(['ask', on]); }
    });
    var actions = setupPanelActions(gate, {
        focusSummary: function() { log.push(['focus']); },
        restorePreset: function() { log.push(['restore']); },
        clearTouched: function() { log.push(['clear']); },
        edits: function() { return {}; },
        edited: function() { return edited; },
        attach: function(fields) { log.push(['attach', fields]); },
        showQuestion: function() { log.push(['question']); },
        showNotice: function() { log.push(['notice']); }
    });
    function seen() { var out = log; log = []; return out; }
"""


class ThePanelButtonsTests(SimpleTestCase):

    def run_world(self, body):
        return run_script(self, WORLD + body)

    def test_keep_applies_the_held_preset_with_the_edits_and_focuses_the_title(self):
        self.assertEqual([['ask', True], ['ask', False], ['apply', 'B', True], ['focus']],
                         self.run_world("gate.arrive('B'); actions.keep(); return seen();"))

    def test_recompute_applies_the_held_preset_without_the_edits_and_focuses_the_title(self):
        self.assertEqual([['ask', True], ['ask', False], ['apply', 'B', False], ['focus']],
                         self.run_world("gate.arrive('B'); actions.recompute(); return seen();"))

    def test_back_to_the_preset_values_while_asking_recomputes_from_the_held_preset(self):
        self.assertEqual([['ask', True], ['ask', False], ['apply', 'B', False], ['focus']],
                         self.run_world("gate.arrive('B'); actions.reset(); return seen();"))

    def test_back_to_the_preset_values_with_no_question_restores_the_shown_preset(self):
        self.assertEqual([['restore'], ['focus']],
                         self.run_world("actions.reset(); return seen();"))

    def test_an_answer_with_no_question_open_applies_nothing_and_still_hands_the_focus_back(self):
        self.assertEqual([['ask', False], ['focus'], ['ask', False], ['focus']],
                         self.run_world("actions.keep(); actions.recompute(); return seen();"))

    def test_a_button_ignores_the_arguments_the_click_hands_it(self):
        self.assertEqual([['ask', True], ['ask', False], ['apply', 'B', True], ['focus']],
                         self.run_world("""
            gate.arrive('B');
            actions.keep({type: 'click'}, 7);
            return seen();"""))


class AFailedPreviewClosesTheQuestionTests(SimpleTestCase):

    def run_world(self, body):
        return run_script(self, WORLD + body)

    def test_the_held_preset_is_dropped_and_the_notice_is_shown(self):
        self.assertEqual({'log': [['ask', True], ['ask', False], ['notice']], 'holding': False},
                         self.run_world("""
            gate.arrive('B'); actions.failed();
            return {log: seen(), holding: gate.holding()};"""))

    def test_recompute_after_a_failure_applies_no_stale_preset(self):
        self.assertEqual([['ask', False], ['focus']],
                         self.run_world("""
            gate.arrive('B'); actions.failed(); seen();
            actions.recompute();
            return seen();"""))

    def test_keep_after_a_failure_applies_no_stale_preset(self):
        self.assertEqual([['ask', False], ['focus']],
                         self.run_world("""
            gate.arrive('B'); actions.failed(); seen();
            actions.keep();
            return seen();"""))

    def test_a_failure_with_no_question_open_only_shows_the_notice(self):
        self.assertEqual([['ask', False], ['notice']],
                         self.run_world("actions.failed(); return seen();"))

    def test_the_submit_after_a_failure_is_not_blocked_by_the_dropped_preset(self):
        self.assertEqual({'log': [['clear'], ['attach', []]], 'blocked': False},
                         self.run_world("""
            gate.arrive('B'); actions.failed(); seen();
            var event = {blocked: false, isDefaultPrevented: function() { return this.blocked; },
                         preventDefault: function() { this.blocked = true; }};
            actions.submit(event);
            return {log: seen(), blocked: event.blocked};"""))


class TheScriptWiresTheButtonsToTheActionsTests(SimpleTestCase):

    def setUp(self):
        self.source = io.open(SCRIPT, encoding='utf-8').read()

    def test_each_button_calls_its_action_and_nothing_else(self):
        for selector, action in (('#setup-preview-reset', 'reset'),
                                 ('#setup-preview-keep-yes', 'keep'),
                                 ('#setup-preview-keep-no', 'recompute')):
            with self.subTest(selector=selector):
                self.assertEqual(
                    [".on('click', actions.%s);" % action],
                    re.findall(r"\$\('%s'\)(\.on\('click'[^\n]*)" % re.escape(selector), self.source))

    def test_the_preview_loop_reports_a_failure_through_the_action(self):
        self.assertIn('failed: actions.failed', self.source)
        self.assertEqual(1, self.source.count('failed: actions.failed'))
