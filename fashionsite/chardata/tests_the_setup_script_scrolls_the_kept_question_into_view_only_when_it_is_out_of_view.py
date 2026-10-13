# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ script scrolls the keep question into view once, only when it is fully out of view, with no smooth scroll under reduced motion and without moving the focus."""
import io
import json
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_page_draws_the_live_weights_panel import SCRIPT
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script

VIEWPORT = 800
PANEL = {'top': 100, 'bottom': 700}


def out_of_view(case, top, bottom, panel=None, viewport=VIEWPORT):
    return run_script(case, 'return setupOutOfView(%s, %s, %s);' % (
        json.dumps({'top': top, 'bottom': bottom}), json.dumps(panel or PANEL), viewport))


class TheQuestionIsOutOfViewOnlyWhenNoneOfItIsVisibleTests(SimpleTestCase):

    def test_a_group_inside_the_panel_is_in_view(self):
        self.assertFalse(out_of_view(self, 300, 400))

    def test_a_group_below_the_panel_edge_is_out_of_view(self):
        self.assertTrue(out_of_view(self, 720, 800))

    def test_a_group_above_the_panel_edge_is_out_of_view(self):
        self.assertTrue(out_of_view(self, 20, 90))

    def test_a_group_with_one_visible_line_is_in_view(self):
        self.assertFalse(out_of_view(self, 690, 760))
        self.assertFalse(out_of_view(self, 40, 101))

    def test_a_group_touching_the_edge_without_overlap_is_out_of_view(self):
        self.assertTrue(out_of_view(self, 700, 760))
        self.assertTrue(out_of_view(self, 40, 100))

    def test_a_group_inside_a_tall_panel_but_below_the_screen_is_out_of_view(self):
        self.assertTrue(out_of_view(self, 900, 980, {'top': 100, 'bottom': 1400}))

    def test_a_group_inside_a_tall_panel_and_inside_the_screen_is_in_view(self):
        self.assertFalse(out_of_view(self, 600, 680, {'top': 100, 'bottom': 1400}))

    def test_a_panel_scrolled_above_the_screen_shows_only_what_the_screen_shows(self):
        self.assertFalse(out_of_view(self, 20, 80, {'top': -300, 'bottom': 500}))
        self.assertTrue(out_of_view(self, -60, -10, {'top': -300, 'bottom': 500}))

    def test_a_group_under_the_screen_bottom_while_the_panel_runs_past_it_is_out_of_view(self):
        self.assertTrue(out_of_view(self, 800, 880, {'top': 200, 'bottom': 1200}))


class TheScrollOptionsTests(SimpleTestCase):

    def options(self, reduce_motion):
        return run_script(self, 'return setupScrollOptions(%s);' % json.dumps(reduce_motion))

    def test_the_scroll_moves_the_least_it_can(self):
        self.assertEqual('nearest', self.options(False)['block'])
        self.assertEqual('nearest', self.options(True)['block'])

    def test_the_scroll_is_smooth_when_the_player_has_not_asked_for_less_motion(self):
        self.assertEqual({'block': 'nearest', 'behavior': 'smooth'}, self.options(False))

    def test_the_scroll_is_instant_under_reduced_motion(self):
        self.assertEqual({'block': 'nearest', 'behavior': 'auto'}, self.options(True))


class TheScriptRevealsTheQuestionOnlyWhenItOpensTests(SimpleTestCase):

    def setUp(self):
        self.source = io.open(SCRIPT, encoding='utf-8').read()

    def body(self, name):
        match = re.search(r'function %s\([^)]*\) \{(.*?)\n    \}\n' % name, self.source, re.S)
        self.assertIsNotNone(match, name)
        return match.group(1)

    def test_the_reveal_runs_once_per_opening_and_never_on_the_other_calls(self):
        self.assertEqual(1, self.source.count('revealQuestionOnce();'))
        ask = self.body('ask')
        self.assertIn('if (opening) {\n            revealQuestionOnce();', ask)
        self.assertEqual(1, ask.count('revealQuestionOnce'))

    def test_the_reveal_waits_for_the_panel_to_be_open_and_the_question_to_be_out_of_view(self):
        reveal = self.body('revealQuestionOnce')
        self.assertIn("if (!$details.prop('open')) {\n            return;", reveal)
        self.assertIn('if (setupOutOfView(', reveal)

    def test_the_reveal_reads_the_reduced_motion_setting_and_scrolls_the_question_group(self):
        reveal = self.body('revealQuestionOnce')
        self.assertIn("window.matchMedia('(prefers-reduced-motion: reduce)').matches", reveal)
        self.assertIn('$keep.get(0).scrollIntoView(setupScrollOptions(still));', reveal)

    def test_the_reveal_never_moves_the_focus(self):
        for name in ('revealQuestionOnce', 'ask'):
            with self.subTest(function=name):
                body = self.body(name)
                self.assertNotIn('focus', body)
                self.assertNotIn('scrollTo', body)
                self.assertNotIn('.scrollTop', body)

    def test_the_badge_shows_the_question_while_it_is_open_and_comes_back_afterwards(self):
        ask = self.body('ask')
        self.assertIn("addClass('setup-asking')", ask)
        self.assertIn("removeClass('setup-asking')", ask)
        self.assertIn('badgeBeforeAsking = null;', ask)
