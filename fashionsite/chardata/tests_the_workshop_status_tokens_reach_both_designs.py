# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The workshop status tokens resolve in the classic design too.

modern.css only defines --fm-* under html.fm-modern, so the classic design
never sees them. The workshop's own --ws-* tokens must be declared straight
on html.fm-light / html.fm-dark instead, never under html.fm-modern, or a
classic-design reader gets an undefined colour on every status.
"""

import os
import re

from django.test import SimpleTestCase

_CSS_PATH = os.path.join(
    os.path.dirname(__file__), 'static', 'chardata', 'workshop.css')

_TOKENS = (
    '--ws-done', '--ws-part', '--ws-none',
    '--ws-done-line', '--ws-part-line', '--ws-none-line',
    '--ws-done-bg', '--ws-part-bg', '--ws-none-bg',
)


def _block(source, selector):
    match = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', source)
    return match.group(1) if match else ''


class TheStatusTokensReachBothDesignsTests(SimpleTestCase):

    def setUp(self):
        with open(_CSS_PATH, encoding='utf-8') as handle:
            raw = handle.read()
        # Strip comments first: prose mentioning "fm-modern" must not be
        # mistaken for a selector by the checks below.
        self.source = re.sub(r'/\*.*?\*/', '', raw, flags=re.S)

    def test_every_token_is_declared_on_fm_light(self):
        block = _block(self.source, 'html.fm-light')
        missing = [t for t in _TOKENS if t + ':' not in block]
        self.assertEqual([], missing, 'missing on html.fm-light: %s' % missing)

    def test_every_token_is_declared_on_fm_dark(self):
        block = _block(self.source, 'html.fm-dark')
        missing = [t for t in _TOKENS if t + ':' not in block]
        self.assertEqual([], missing, 'missing on html.fm-dark: %s' % missing)

    def test_no_token_is_declared_only_under_the_modern_design(self):
        for token in _TOKENS:
            with self.subTest(token=token):
                for match in re.finditer(
                        r'([^{}]+)\{[^{}]*%s\s*:' % re.escape(token), self.source):
                    selector = match.group(1).strip()
                    self.assertNotIn(
                        'fm-modern', selector,
                        '%s is declared under %r, a classic-design reader '
                        'would never see it' % (token, selector))
