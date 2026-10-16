# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The forgemagie real mode rebuilds its rows on every change, so the template must hand the focus back to the input that was being edited."""
import os
import re

from django.test import SimpleTestCase

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, 'templates', 'chardata', 'forgemagie.html')


class RealModeFocusRestoreSource(SimpleTestCase):
    """Reads the inline script as text: it lives in the template, so a harness would have to retype it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(TEMPLATE, encoding='utf-8') as handle:
            source = handle.read()
        start = source.index('function renderSession()')
        cls.body = source[start:source.index('simSuggestionDiv.innerHTML', start)]

    def test_both_inputs_are_tagged_with_their_row_and_field(self):
        self.assertIn("nowInput.dataset.fmField = 'value'", self.body)
        self.assertIn("targetInput.dataset.fmField = 'target'", self.body)
        self.assertEqual(len(re.findall(r'\.dataset\.fmRow = rowIndex', self.body)), 2)

    def test_the_active_input_is_read_before_the_rows_are_emptied(self):
        read = self.body.index('document.activeElement')
        emptied = self.body.index("simRowsBody.innerHTML = ''")
        self.assertLess(read, emptied)
        self.assertIn('simRowsBody.contains(focusedField)', self.body)

    def test_focus_is_restored_after_the_rows_are_rebuilt(self):
        rebuilt = self.body.index('simRowsBody.appendChild(tr);')
        restored = self.body.index('refocused.focus()')
        self.assertLess(rebuilt, restored)
        self.assertIn('if (refocus)', self.body)

    def test_both_row_inputs_rebuild_after_the_focus_has_moved(self):
        self.assertEqual(self.body.count('setTimeout(renderSession, 0);'), 2)
