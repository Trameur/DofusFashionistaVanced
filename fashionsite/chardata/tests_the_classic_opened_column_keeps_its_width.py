# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""In the classic designs an opened item card stays inside its table column, so Expand All does not widen the column."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, is_classic_only, stylesheet

SOLUTION = stylesheet('solution.css')
OPENED = 'html:not(.fm-modern, .fm-enhanced) .solution-item-section-column .solution-item-expand-content'


class TheClassicOpenedColumnTests(SimpleTestCase):

    def test_the_opened_content_adds_nothing_to_the_column_width(self):
        self.assertEqual('0', declared(SOLUTION, OPENED, 'width')[0])
        self.assertEqual('100%', declared(SOLUTION, OPENED, 'min-width')[0])

    def test_the_rule_skips_both_the_atelier_and_the_enhanced_design(self):
        self.assertTrue(is_classic_only(OPENED))
        sized = [selector for rule in SOLUTION for selector in rule['selectors']
                 if selector.endswith('.solution-item-expand-content') and 'min-width' in rule['declarations']
                 and 'width' in rule['declarations']]
        self.assertEqual([OPENED], sized)
