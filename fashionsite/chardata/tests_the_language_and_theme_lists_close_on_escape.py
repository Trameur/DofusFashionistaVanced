# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The language list and the theme list of the top bar close on Escape and give the focus back."""

import os
import re

from django.test import SimpleTestCase


class TheTopBarListsCloseOnEscapeTests(SimpleTestCase):

    def _escape_handler(self):
        path = os.path.join(os.path.dirname(__file__), 'templates', 'chardata', 'base.html')
        with open(path, encoding='utf-8') as handle:
            source = handle.read()
        match = re.search(r'document\.addEventListener\("keydown", function\(e\) \{\s*'
                          r'if \(e\.key !== "Escape"\) return;(.*?)\}, true\);', source, re.S)
        self.assertIsNotNone(match, 'no capture phase Escape listener for the lists')
        return match.group(1)

    def test_escape_closes_the_language_list_and_focuses_its_button(self):
        handler = self._escape_handler()
        self.assertIn('$("#blanket-language").is(":visible")', handler)
        self.assertIn('$("#blanket-language").click()', handler)
        self.assertIn('$("#flag").focus()', handler)

    def test_escape_closes_the_theme_list_and_focuses_its_button(self):
        handler = self._escape_handler()
        self.assertIn('$("#blanket-theme").is(":visible")', handler)
        self.assertIn('$("#blanket-theme").click()', handler)
        self.assertIn('$(".current-theme").first().focus()', handler)

    def test_escape_stops_before_the_phone_nav_closes_too(self):
        self.assertEqual(self._escape_handler().count('e.stopPropagation()'), 2)
