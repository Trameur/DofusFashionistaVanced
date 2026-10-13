# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""While the /setup/ question is open, putting every edited value back and leaving the box applies the held preset and closes the question."""
import io
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_page_draws_the_live_weights_panel import SCRIPT
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script

GATE = """
    var log = [];
    var world = {edited: 2};
    var gate = setupEditGate({
        hasBaseline: function() { return true; },
        edited: function() { return world.edited; },
        same: function() { return false; },
        apply: function(state, keep) { log.push(['apply', state, keep]); },
        ask: function(on) { log.push(['ask', on]); }
    });
    function seen() { var out = log; log = []; return out; }
"""


class TheLastUndoneEditSettlesTheQuestionTests(SimpleTestCase):

    def run_gate(self, body):
        return run_script(self, GATE + body)

    def test_with_every_edit_undone_the_held_preset_is_applied_and_the_question_closes(self):
        self.assertEqual({'log': [['ask', False], ['apply', 'B', False]], 'holding': False},
                         self.run_gate("""
            gate.arrive('B'); seen();
            world.edited = 0; gate.cleaned();
            return {log: seen(), holding: gate.holding()};"""))

    def test_with_one_edit_left_the_question_stays_open(self):
        self.assertEqual({'log': [], 'holding': True},
                         self.run_gate("""
            gate.arrive('B'); seen();
            world.edited = 1; gate.cleaned();
            return {log: seen(), holding: gate.holding()};"""))

    def test_with_no_question_open_nothing_happens(self):
        self.assertEqual([], self.run_gate("world.edited = 0; gate.cleaned(); return seen();"))

    def test_the_question_cannot_be_settled_twice(self):
        self.assertEqual([['ask', False], ['apply', 'B', False]],
                         self.run_gate("""
            gate.arrive('B'); seen();
            world.edited = 0; gate.cleaned(); gate.cleaned();
            return seen();"""))

    def test_the_latest_preset_is_the_one_applied(self):
        self.assertEqual([['ask', False], ['apply', 'C', False]],
                         self.run_gate("""
            gate.arrive('B'); gate.arrive('C'); seen();
            world.edited = 0; gate.cleaned();
            return seen();"""))

    def test_a_new_edit_after_the_settle_asks_again_on_the_next_click(self):
        self.assertEqual([['ask', True]],
                         self.run_gate("""
            gate.arrive('B'); world.edited = 0; gate.cleaned(); seen();
            world.edited = 1; gate.arrive('C');
            return seen();"""))


def panel_bindings(source):
    found = re.findall(r"\$block\.on\('([a-z ]+)', '\.wm-input', function\(\) \{(.*?)\}\);",
                       source, re.S)
    return {events: [line.strip() for line in body.strip().splitlines()] for events, body in found}


class TheScriptSettlesTheQuestionOnlyWhenAValueIsCommittedTests(SimpleTestCase):

    def setUp(self):
        self.source = io.open(SCRIPT, encoding='utf-8').read()
        self.bound = panel_bindings(self.source)

    def test_a_committed_value_marks_the_edits_then_lets_the_gate_settle(self):
        self.assertEqual(['markEdits();'], self.bound['change input'])
        self.assertEqual(['gate.cleaned();'], self.bound['change'])

    def test_a_value_typed_partway_never_reaches_the_gate(self):
        self.assertEqual(1, self.source.count('gate.cleaned()'))
        for events, lines in self.bound.items():
            if 'input' in events.split():
                with self.subTest(events=events):
                    self.assertNotIn('gate.cleaned();', lines)

    def test_the_edit_marks_still_follow_every_keystroke(self):
        marking = [events for events, lines in self.bound.items() if 'markEdits();' in lines]
        self.assertEqual(['change input'], marking)
