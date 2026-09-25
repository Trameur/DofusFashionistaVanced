# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The workshop print stylesheet hides site chrome and every control.

A printed workshop is a paper checklist: no toolbar, no buttons, no sidebar,
no ads, and it must read in black on white regardless of the reader's theme
or design, since --ws-* and --fm-* tokens are unavailable or invisible on
paper.
"""

import os
import re

from django.test import SimpleTestCase

_CSS_PATH = os.path.join(
    os.path.dirname(__file__), 'static', 'chardata', 'workshop.css')

_HIDDEN_CONTROL_SELECTORS = (
    '.ws-toolbar', '.ws-meta-actions', '.ws-card-bulk', '.ws-row-ctl',
    '.ws-shopping-actions', '.ws-hide-gathered', '.ws-progress', '.ws-mult',
    '.ws-remove', '.ws-source-wrap',
)

_HIDDEN_CHROME_SELECTORS = (
    '.skip-link', '.banner', '.char-overlay', '.header-controls',
    '.mobile-nav-toggle', '#main-sidebar', '.footer', '.fm-ad',
)


def _extract_media_print_block(source):
    match = re.search(r'@media\s+print\s*\{', source)
    if not match:
        return None
    depth = 1
    i = match.end()
    start = i
    while i < len(source) and depth:
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
        i += 1
    return source[start:i - 1]


class TheWorkshopPrintStylesheetTests(SimpleTestCase):

    def setUp(self):
        with open(_CSS_PATH, encoding='utf-8') as handle:
            raw = handle.read()
        self.source = re.sub(r'/\*.*?\*/', '', raw, flags=re.S)
        self.block = _extract_media_print_block(self.source)

    def test_an_at_media_print_block_exists(self):
        self.assertIsNotNone(self.block, 'no @media print block in workshop.css')

    def test_every_interactive_control_is_hidden(self):
        missing = [s for s in _HIDDEN_CONTROL_SELECTORS if s not in self.block]
        self.assertEqual([], missing, 'not hidden for print: %s' % missing)

    def test_every_chrome_selector_is_hidden(self):
        missing = [s for s in _HIDDEN_CHROME_SELECTORS if s not in self.block]
        self.assertEqual([], missing, 'not hidden for print: %s' % missing)

    def test_hidden_selectors_use_display_none_important(self):
        rule = re.search(
            r'([^{}]*\.ws-toolbar[^{}]*)\{([^}]*)\}', self.block)
        self.assertIsNotNone(rule)
        self.assertIn('display: none !important', rule.group(2))

    def test_text_and_background_are_forced_black_on_white(self):
        self.assertIn('color: #000 !important', self.block)
        self.assertIn('background: #fff !important', self.block)

    def test_a_missing_resource_gets_a_checklist_box(self):
        self.assertIn('::before', self.block)
        self.assertIn('data-state', self.block)
        self.assertIn('border: 1.4px solid #000', self.block)

    def test_cards_keep_a_visible_border_once_backgrounds_are_stripped(self):
        rule = re.search(r'\.ws-card\s*\{([^}]*)\}', self.block)
        self.assertIsNotNone(rule)
        self.assertIn('border: 1px solid #000', rule.group(1))
