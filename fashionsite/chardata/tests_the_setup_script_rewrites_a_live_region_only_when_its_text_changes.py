# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ script writes the text of a live region only when the text changes, so a screen reader hears each message once and not at every keystroke."""
import io
import re

from django.test import SimpleTestCase, TestCase

from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import SCRIPT, setup_page
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script
from fashionistapulp.structure import set_current_game_version

REGION = """
    function region(text) {
        return {shown: text, writes: [],
                text: function(value) {
                    if (arguments.length === 0) { return this.shown; }
                    this.shown = value; this.writes.push(value); return this;
                }};
    }
"""


class AWriteHappensOnlyOnAChangeTests(SimpleTestCase):

    def run_region(self, body):
        return run_script(self, REGION + body)

    def test_the_same_text_is_not_written_again(self):
        self.assertEqual({'answers': [True, False, False], 'writes': ['You edited 2 values.']},
                         self.run_region("""
            var node = region('');
            var answers = [setupWriteLive(node, 'You edited 2 values.'),
                           setupWriteLive(node, 'You edited 2 values.'),
                           setupWriteLive(node, 'You edited 2 values.')];
            return {answers: answers, writes: node.writes};"""))

    def test_a_new_text_is_written_once(self):
        self.assertEqual({'answers': [True, True, False], 'writes': ['one', 'two']},
                         self.run_region("""
            var node = region('');
            var answers = [setupWriteLive(node, 'one'), setupWriteLive(node, 'two'),
                           setupWriteLive(node, 'two')];
            return {answers: answers, writes: node.writes};"""))

    def test_emptying_an_empty_region_writes_nothing(self):
        self.assertEqual({'answer': False, 'writes': []},
                         self.run_region("""
            var node = region('');
            return {answer: setupWriteLive(node, ''), writes: node.writes};"""))

    def test_emptying_a_region_that_speaks_writes_the_empty_text_once(self):
        self.assertEqual({'answers': [True, False], 'writes': ['']},
                         self.run_region("""
            var node = region('You edited 1 value.');
            var answers = [setupWriteLive(node, ''), setupWriteLive(node, '')];
            return {answers: answers, writes: node.writes};"""))

    def test_forty_keystrokes_that_keep_the_count_at_two_write_the_text_once(self):
        self.assertEqual(1, self.run_region("""
            var node = region('');
            for (var i = 0; i < 40; i++) {
                setupWriteLive(node, setupPreviewEdits(2));
            }
            return node.writes.length;"""))


class EveryLiveRegionOfTheScriptIsWrittenThroughItTests(SimpleTestCase):

    def test_no_live_region_is_written_with_a_bare_text_call(self):
        source = io.open(SCRIPT, encoding='utf-8').read()
        for node in ('$edited', '$changes', '$guard'):
            with self.subTest(node=node):
                self.assertNotIn('%s.text(' % node, source)
                self.assertIn('setupWriteLive(%s, ' % node, source)


class TheRegionsTheScriptWritesAreTheLiveOnesOfThePageTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_three_regions_are_aria_live_paragraphs_in_the_panel(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                for element_id in ('setup-preview-edited', 'setup-preview-changes',
                                   'setup-preview-guard'):
                    found = page.find('p', id=element_id)
                    self.assertEqual(1, len(found), element_id)
                    self.assertEqual('polite', found[0][0]['aria-live'], element_id)
                    self.assertTrue(page.inside(found[0][1], 'aside', 'setup-preview'))

    def test_the_script_looks_each_region_up_by_the_id_the_page_gives_it(self):
        source = io.open(SCRIPT, encoding='utf-8').read()
        for name, element_id in (('$edited', 'setup-preview-edited'),
                                 ('$changes', 'setup-preview-changes'),
                                 ('$guard', 'setup-preview-guard')):
            self.assertIsNotNone(re.search(r"var %s = \$\('#%s'\);" % (re.escape(name), element_id),
                                           source), name)
