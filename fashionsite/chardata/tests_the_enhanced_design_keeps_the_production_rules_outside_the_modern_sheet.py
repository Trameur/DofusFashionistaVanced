# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The 16 production selectors keyed on the new design class outside modern.css (18 rule occurrences, since each admin_tools.css selector appears in two rules) each have an enhanced classic twin in the same rule, so the enhanced design keeps them."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import stylesheet

PRODUCTION_SELECTORS = {
    'setup.css': (
        'html.fm-modern .setup-preview',
        'html.fm-modern .setup-doors input.setup-primary',
        'html.fm-modern .setup-doors input.setup-secondary',
        'html.fm-modern .setup-preview button.button-thin-foreground',
        'html.fm-modern:not(.fm-dark) .setup-doors input.setup-secondary',
        'html.fm-modern:not(.fm-dark) .setup-preview button.button-thin-foreground',
        'html.fm-modern .setup-doors input.setup-secondary:hover',
        'html.fm-modern .setup-recipes',
        'html.fm-modern .setup-chip',
        'html.fm-modern .setup-action',
        'html.fm-modern .setup-chip[aria-pressed="true"]',
        'html.fm-modern .setup-more',
        'html.fm-modern .setup-more .setup-more-box',
    ),
    'admin_tools.css': (
        'html.fm-modern.fm-light .admin-tools',
        'html.fm-modern.fm-dark .admin-tools',
    ),
    'workshop.css': (
        'html.fm-modern .ws-num',
    ),
}


def twin(selector):
    return selector.replace('html.fm-modern', 'html.fm-enhanced', 1)


class EveryProductionSelectorHasAnEnhancedTwinTests(SimpleTestCase):

    def test_the_frozen_list_holds_the_eighteen_production_rule_occurrences(self):
        rules = {name: stylesheet(name) for name in PRODUCTION_SELECTORS}
        count = sum(1 for name, wanted in PRODUCTION_SELECTORS.items() for rule in rules[name]
                    for selector in rule['selectors'] if selector in wanted)
        self.assertEqual(18, count)

    def test_each_production_selector_shares_its_rule_with_its_twin(self):
        for name, wanted in PRODUCTION_SELECTORS.items():
            rules = stylesheet(name)
            for selector in wanted:
                with self.subTest(sheet=name, selector=selector):
                    holding = [rule for rule in rules if selector in rule['selectors']]
                    self.assertTrue(holding)
                    for rule in holding:
                        self.assertIn(twin(selector), rule['selectors'])

    def test_no_twin_stands_in_a_rule_without_its_production_selector(self):
        for name, wanted in PRODUCTION_SELECTORS.items():
            for rule in stylesheet(name):
                for selector in rule['selectors']:
                    if selector.startswith('html.fm-enhanced'):
                        with self.subTest(sheet=name, selector=selector):
                            original = selector.replace('html.fm-enhanced', 'html.fm-modern', 1)
                            self.assertIn(original, wanted)
                            self.assertIn(original, rule['selectors'])
