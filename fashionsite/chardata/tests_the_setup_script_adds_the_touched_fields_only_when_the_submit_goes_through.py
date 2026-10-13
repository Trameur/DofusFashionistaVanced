# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ submit handler adds the touched fields to the form only when the submit is not blocked, and blocks it only while edits wait for an answer."""
import io
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_page_draws_the_live_weights_panel import SCRIPT
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script

WORLD = """
    var log = [];
    var baseline = {ap: {weight: '50', min: '11'}, str: {weight: '3', min: ''}};
    var current = JSON.parse(JSON.stringify(baseline));
    function edits() { return setupEdits(baseline, current); }
    var gate = setupEditGate({
        hasBaseline: function() { return true; },
        edited: function() { return setupTouchedFields(edits()).length; },
        same: function() { return false; },
        apply: function(state, keep) { log.push(['apply', state, keep]); },
        ask: function(on) { log.push(['ask', on]); }
    });
    var actions = setupPanelActions(gate, {
        focusSummary: function() { log.push(['focus']); },
        restorePreset: function() { log.push(['restore']); },
        clearTouched: function() { log.push(['clear']); },
        edits: edits,
        edited: function() { return setupTouchedFields(edits()).length; },
        attach: function(fields) { log.push(['attach', fields]); },
        showQuestion: function() { log.push(['question']); },
        showNotice: function() { log.push(['notice']); }
    });
    function submit(alreadyBlocked) {
        var event = {blocked: !!alreadyBlocked,
            isDefaultPrevented: function() { return this.blocked; },
            preventDefault: function() { this.blocked = true; }};
        actions.submit(event);
        var seen = log;
        log = [];
        return {log: seen, blocked: event.blocked};
    }
"""


class TheSubmitHandlerAddsTheFieldsOnlyWhenTheFormGoesThroughTests(SimpleTestCase):

    def run_world(self, body):
        return run_script(self, WORLD + body)

    def test_a_form_with_no_edit_goes_through_and_adds_no_field(self):
        self.assertEqual({'log': [['clear'], ['attach', []]], 'blocked': False},
                         self.run_world("return submit();"))

    def test_a_form_with_edits_goes_through_and_adds_one_field_per_edit(self):
        self.assertEqual({'log': [['clear'], ['attach', [['weight_ap', '60'], ['min_ap', '12'],
                                                          ['weight_str', '0']]]],
                          'blocked': False},
                         self.run_world("""
            current.ap.weight = '60'; current.ap.min = '12'; current.str.weight = '0';
            return submit();"""))

    def test_a_submit_another_handler_already_blocked_adds_nothing(self):
        self.assertEqual({'log': [['clear']], 'blocked': True},
                         self.run_world("current.ap.weight = '60'; return submit(true);"))

    def test_edits_waiting_for_an_answer_block_the_submit_and_show_the_question(self):
        self.assertEqual({'log': [['clear'], ['question']], 'blocked': True},
                         self.run_world("""
            current.ap.weight = '60';
            gate.arrive('B'); log = [];
            return submit();"""))

    def test_nothing_is_added_while_the_question_is_open(self):
        self.assertEqual([], self.run_world("""
            current.ap.weight = '60';
            gate.arrive('B'); log = [];
            return submit().log.filter(function(entry) { return entry[0] === 'attach'; });"""))

    def test_every_submit_first_clears_the_fields_a_blocked_submit_left_behind(self):
        self.assertEqual(['clear', 'clear', 'clear'],
                         self.run_world("""
            var first = [];
            current.ap.weight = '60';
            first.push(submit().log[0][0]);
            first.push(submit(true).log[0][0]);
            gate.arrive('B'); log = [];
            first.push(submit().log[0][0]);
            return first;"""))

    def test_after_the_player_answers_the_submit_goes_through_with_the_fields(self):
        self.assertEqual({'log': [['clear'], ['attach', [['weight_ap', '60']]]], 'blocked': False},
                         self.run_world("""
            current.ap.weight = '60';
            gate.arrive('B'); gate.keep(); log = [];
            return submit();"""))

    def test_edits_all_put_back_while_the_question_is_open_no_longer_block_the_submit(self):
        self.assertEqual({'log': [['clear'], ['attach', []]], 'blocked': False},
                         self.run_world("""
            current.ap.weight = '60';
            gate.arrive('B'); log = [];
            current.ap.weight = '50';
            return submit();"""))


class TheScriptBindsTheSubmitHandlerOnceTests(SimpleTestCase):

    def test_the_form_submit_is_bound_to_the_panel_action_and_nothing_else(self):
        source = io.open(SCRIPT, encoding='utf-8').read()
        self.assertEqual(["$form.on('submit', actions.submit);"],
                         re.findall(r"\$form\.on\('submit'[^\n]*", source))
