# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""When a preview fails while the /setup/ question is open, going back to the criteria that were held asks the question again."""
import io
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_page_draws_the_live_weights_panel import SCRIPT
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script

WORLD = """
    var log = [];
    var world = {edited: 0, baseline: null};
    var gate = setupEditGate({
        hasBaseline: function() { return world.baseline !== null; },
        edited: function() { return world.edited; },
        same: function(state) { return state === world.baseline; },
        apply: function(state, keep) { world.baseline = state; log.push(['apply', state, keep]); },
        ask: function(on) { log.push(['ask', on]); }
    });
    var actions = setupPanelActions(gate, {
        showNotice: function() { log.push(['notice']); },
        focusSummary: function() {}
    });
    var env = fakeEnv();
    env.show = function(state) { gate.arrive(state); };
    env.failed = actions.failed;
    var loop = setupPreviewLoop(env);
    async function choose(query, answer) {
        env.next = query;
        loop.refresh();
        var load = env.loads[env.loads.length - 1];
        if (answer === 'fail') {
            load.reject(new Error('down'));
        } else if (answer) {
            load.resolve(answer);
        }
        await flush();
    }
"""


class TheHeldCriteriaAreAskedAgainTests(SimpleTestCase):

    def run_world(self, body):
        return run_script(self, WORLD + body)

    def test_going_back_to_the_held_criteria_after_a_failure_asks_the_question_again(self):
        self.assertEqual({'log': [['ask', False], ['apply', 'stateA', False], ['ask', True],
                                  ['ask', False], ['notice'], ['ask', True]],
                          'loads': 3, 'holding': True}, self.run_world("""
            await choose('A', 'stateA');
            world.edited = 1;
            await choose('B', 'stateB');
            await choose('C', 'fail');
            await choose('B', null);
            return {log: log, loads: env.loads.length, holding: gate.holding()};"""))

    def test_the_held_preset_is_applied_when_the_player_then_asks_for_it(self):
        self.assertEqual([['ask', False], ['apply', 'stateB', False]], self.run_world("""
            await choose('A', 'stateA');
            world.edited = 1;
            await choose('B', 'stateB');
            await choose('C', 'fail');
            await choose('B', null);
            log.length = 0;
            actions.recompute();
            return log;"""))

    def test_going_back_to_the_shown_criteria_after_a_failure_asks_nothing(self):
        self.assertEqual({'log': [['ask', False]], 'loads': 2, 'holding': False}, self.run_world("""
            await choose('A', 'stateA');
            world.edited = 1;
            await choose('C', 'fail');
            log.length = 0;
            await choose('A', null);
            return {log: log, loads: env.loads.length, holding: gate.holding()};"""))

    def test_a_failure_does_not_lose_the_answers_already_fetched(self):
        self.assertEqual(3, self.run_world("""
            await choose('A', 'stateA');
            await choose('B', 'stateB');
            await choose('C', 'fail');
            await choose('A', null);
            await choose('B', null);
            return env.loads.length;"""))


class TheNoticeGoesWhenAPreviewComesBackTests(SimpleTestCase):

    def test_showing_a_preview_hides_the_failure_notice_even_when_the_panel_keeps_its_values(self):
        source = io.open(SCRIPT, encoding='utf-8').read()
        match = re.search(r'\n    function show\(state\) \{(.*?)\n    \}\n', source, re.S)
        self.assertIsNotNone(match)
        self.assertEqual(['gate.arrive(state);', "$notice.prop('hidden', true);"],
                         [line.strip() for line in match.group(1).strip().splitlines()])
