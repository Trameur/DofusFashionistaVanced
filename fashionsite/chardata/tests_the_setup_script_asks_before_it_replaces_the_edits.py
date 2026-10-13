# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A click on a /setup/ box asks to keep or recompute the edits only when there are edits, and the page draws the question as two buttons."""
import io
import re

from django.test import SimpleTestCase, TestCase

from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import SCRIPT, setup_page
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script

GATE = """
    var log = [];
    var world = {baseline: true, edited: 0, same: false};
    var gate = setupEditGate({
        hasBaseline: function() { return world.baseline; },
        edited: function() { return world.edited; },
        same: function(state) { return world.same; },
        apply: function(state, keep) { log.push(['apply', state, keep]); },
        ask: function(on) { log.push(['ask', on]); }
    });
    function seen() { var out = log; log = []; return out; }
"""


class TheScriptAsksOnlyWhenThereAreEditsTests(SimpleTestCase):

    def run_gate(self, body):
        return run_script(self, GATE + body)

    def test_with_no_edit_the_new_preset_is_applied_without_a_question(self):
        self.assertEqual({'log': [['ask', False], ['apply', 'A', False]], 'holding': False},
                         self.run_gate("gate.arrive('A'); return {log: seen(), holding: gate.holding()};"))

    def test_the_first_preview_is_applied_without_a_question_even_if_fields_hold_values(self):
        self.assertEqual({'log': [['ask', False], ['apply', 'A', False]], 'holding': False},
                         self.run_gate("world.baseline = false; world.edited = 3; gate.arrive('A');"
                                       " return {log: seen(), holding: gate.holding()};"))

    def test_with_an_edit_a_different_preset_is_held_and_the_question_is_asked(self):
        self.assertEqual({'log': [['ask', True]], 'holding': True},
                         self.run_gate("world.edited = 1; gate.arrive('B');"
                                       " return {log: seen(), holding: gate.holding()};"))

    def test_with_an_edit_a_preset_equal_to_the_one_on_screen_asks_nothing(self):
        self.assertEqual({'log': [['ask', False]], 'holding': False},
                         self.run_gate("world.edited = 2; world.same = true; gate.arrive('B');"
                                       " return {log: seen(), holding: gate.holding()};"))

    def test_the_question_appears_on_the_first_click_after_an_edit_and_not_before(self):
        self.assertEqual({'first': [['ask', False], ['apply', 'A', False]],
                          'second': [['ask', True]]},
                         self.run_gate("""
            gate.arrive('A'); var first = seen();
            world.edited = 1; gate.arrive('B');
            return {first: first, second: seen()};"""))

    def test_keeping_applies_the_held_preset_and_the_edits_are_kept(self):
        self.assertEqual({'log': [['ask', True], ['ask', False], ['apply', 'B', True]],
                          'holding': False},
                         self.run_gate("world.edited = 1; gate.arrive('B'); gate.keep();"
                                       " return {log: seen(), holding: gate.holding()};"))

    def test_recomputing_applies_the_held_preset_and_drops_the_edits(self):
        self.assertEqual({'log': [['ask', True], ['ask', False], ['apply', 'B', False]],
                          'holding': False},
                         self.run_gate("world.edited = 1; gate.arrive('B'); gate.recompute();"
                                       " return {log: seen(), holding: gate.holding()};"))

    def test_while_the_question_is_open_the_latest_preset_is_the_one_applied(self):
        self.assertEqual([['ask', True], ['ask', True], ['ask', False], ['apply', 'C', True]],
                         self.run_gate("world.edited = 1; gate.arrive('B'); gate.arrive('C');"
                                       " gate.keep(); return seen();"))

    def test_an_answer_with_no_question_open_applies_nothing(self):
        self.assertEqual([['ask', False], ['ask', False]],
                         self.run_gate("gate.keep(); gate.recompute(); return seen();"))

    def test_nothing_is_ever_replaced_without_an_answer(self):
        self.assertEqual([], self.run_gate("""
            world.edited = 4;
            gate.arrive('B'); gate.arrive('C'); gate.arrive('D');
            return seen().filter(function(entry) { return entry[0] === 'apply'; });"""))


class TheQuestionTheScriptAsksIsDrawnByThePageTests(TestCase):

    def test_the_page_draws_the_question_hidden_with_one_button_per_answer(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                group = page.find('div', id='setup-preview-keep')
                self.assertEqual(1, len(group))
                attrs, ancestors = group[0]
                self.assertIn('hidden', attrs)
                self.assertEqual('group', attrs['role'])
                self.assertEqual('setup-preview-keep-question', attrs['aria-labelledby'])
                self.assertTrue(page.inside(ancestors, 'aside', 'setup-preview'))
                self.assertFalse(page.inside(ancestors, 'form', 'main_form'))
                question = page.find('p', id='setup-preview-keep-question')
                self.assertEqual('alert', question[0][0]['role'])
                for answer in ('setup-preview-keep-yes', 'setup-preview-keep-no'):
                    button = page.find('button', id=answer)
                    self.assertEqual(1, len(button), answer)
                    self.assertEqual('button', button[0][0]['type'])
                    self.assertNotIn('name', button[0][0])
                    self.assertTrue(page.inside(button[0][1], 'div', 'setup-preview-keep'))

    def test_the_bar_that_counts_the_edits_has_a_hidden_way_back(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                self.assertNotIn('hidden', page.find('div', id='setup-preview-edits')[0][0])
                reset = page.find('button', id='setup-preview-reset')
                self.assertEqual(1, len(reset))
                self.assertIn('hidden', reset[0][0])
                self.assertEqual('button', reset[0][0]['type'])
                self.assertIn('aria-live', page.find('p', id='setup-preview-edited')[0][0])

    def test_the_script_never_asks_with_a_browser_dialog(self):
        source = io.open(SCRIPT, encoding='utf-8').read()
        self.assertIsNone(re.search(r'\b(confirm|alert|prompt)\s*\(', source))
