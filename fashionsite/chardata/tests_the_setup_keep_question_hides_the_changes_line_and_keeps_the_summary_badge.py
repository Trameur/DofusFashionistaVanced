# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""While the /setup/ keep question is open the changes line is hidden by the stylesheet and the summary badge stays visible with the panel open."""
from django.test import TestCase

from chardata.tests_every_preset_keeps_its_weights_and_minimums import VERSIONS
from chardata.tests_the_setup_page_draws_the_live_weights_panel import setup_page
from chardata.tests_the_setup_stylesheet_support import declared, rule_order, stylesheet
from fashionistapulp.structure import set_current_game_version

SETUP = stylesheet('setup.css')
HIDE_CHANGES = '.setup-preview-keep:not([hidden]) ~ .setup-preview-changes'
BADGE_CLOSED_ONLY = 'details[open] > summary > .setup-badge'
BADGE_ASKING = 'details[open] > summary > .setup-badge.setup-asking'


class TheChangesLineIsHiddenWhileTheQuestionIsOpenTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_rule_hides_the_line_with_an_important_display_none(self):
        self.assertEqual(('none', True), declared(SETUP, HIDE_CHANGES, 'display'))

    def test_the_rule_reaches_the_line_because_the_question_precedes_it_among_the_same_siblings(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                keep = page.find('div', id='setup-preview-keep')
                changes = page.find('p', id='setup-preview-changes')
                self.assertEqual(1, len(keep))
                self.assertEqual(1, len(changes))
                self.assertEqual(keep[0][1], changes[0][1])
                ids = [attrs.get('id') for name, attrs, ancestors in page.elements
                       if ancestors == keep[0][1] and attrs.get('id') in (
                           'setup-preview-keep', 'setup-preview-changes')]
                self.assertEqual(['setup-preview-keep', 'setup-preview-changes'], ids)

    def test_the_line_is_not_hidden_by_any_other_rule_so_it_comes_back_when_the_question_closes(self):
        hiding = [rule['selectors'] for rule in SETUP
                  if rule['declarations'].get('display', ('', False))[0] == 'none'
                  and any('setup-preview-changes' in selector for selector in rule['selectors'])]
        self.assertEqual([[HIDE_CHANGES], ['.setup-preview-changes:empty']], hiding)


class TheSummaryBadgeStaysVisibleWhileTheQuestionIsOpenTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_an_open_panel_hides_the_badge_unless_it_carries_the_question(self):
        self.assertEqual(('none', False), declared(SETUP, BADGE_CLOSED_ONLY, 'display'))
        self.assertEqual(('inline-block', False), declared(SETUP, BADGE_ASKING, 'display'))

    def test_the_asking_rule_comes_after_the_hiding_rule(self):
        self.assertLess(rule_order(SETUP, BADGE_CLOSED_ONLY)[-1],
                        rule_order(SETUP, BADGE_ASKING)[0])

    def test_the_badge_is_the_summary_child_the_rules_select(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _html, page = setup_page(self.client, version)
                badge = page.find('span', id='setup-preview-badge')
                self.assertEqual(1, len(badge))
                self.assertEqual('setup-badge', badge[0][0]['class'])
                names = [name for name, _attrs in badge[0][1][-3:]]
                self.assertEqual(['aside', 'details', 'summary'], names)
