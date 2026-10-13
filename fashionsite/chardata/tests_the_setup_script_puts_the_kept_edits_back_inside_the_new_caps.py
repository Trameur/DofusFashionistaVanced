# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""When the player keeps the edits over a new preset the /setup/ script puts each edited value back, a minimum held at the new cap, and leaves untouched rows and aggregates alone."""
import io
import json
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_page_draws_the_live_weights_panel import SCRIPT
from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script


def restored(case, edit, cap):
    return run_script(case, 'return setupRestoredValues(%s, %s);' % (
        json.dumps(edit), 'undefined' if cap is None else json.dumps(cap)))


def edit(weight=None, minimum=None, aggregate=False):
    return {'weight': weight is not None, 'min': minimum is not None, 'aggregate': aggregate,
            'now': {'weight': weight, 'min': minimum}}


class TheKeptValuesComeBackTests(SimpleTestCase):

    def test_an_edited_weight_comes_back_as_typed(self):
        self.assertEqual({'weight': '9'}, restored(self, edit(weight='9'), None))

    def test_an_edited_minimum_comes_back_as_typed_under_the_cap(self):
        self.assertEqual({'min': '5'}, restored(self, edit(minimum='5'), '6'))

    def test_a_minimum_above_the_new_cap_comes_back_at_the_cap(self):
        self.assertEqual({'min': '12'}, restored(self, edit(minimum='14'), '12'))

    def test_a_minimum_at_the_cap_comes_back_as_typed(self):
        self.assertEqual({'min': '12'}, restored(self, edit(minimum='12'), '12'))

    def test_a_row_with_no_cap_keeps_any_minimum(self):
        self.assertEqual({'min': '14'}, restored(self, edit(minimum='14'), None))

    def test_a_cleared_minimum_stays_cleared_whatever_the_cap(self):
        self.assertEqual({'min': ''}, restored(self, edit(minimum=''), '6'))

    def test_a_weight_and_a_minimum_edited_together_come_back_together(self):
        self.assertEqual({'weight': '3', 'min': '6'},
                         restored(self, edit(weight='3', minimum='9'), '6'))

    def test_the_cap_never_touches_a_weight(self):
        self.assertEqual({'weight': '99999'}, restored(self, edit(weight='99999'), '6'))

    def test_a_row_nobody_edited_comes_back_with_nothing(self):
        self.assertEqual({}, restored(self, None, '6'))

    def test_an_aggregate_row_comes_back_with_nothing_its_members_carry_the_edit(self):
        self.assertEqual({}, restored(self, edit(weight='7', minimum='5', aggregate=True), '6'))

    def test_a_row_whose_edit_is_neither_a_weight_nor_a_minimum_comes_back_with_nothing(self):
        self.assertEqual({}, restored(self, {'weight': False, 'min': False, 'aggregate': False,
                                             'now': {'weight': '1', 'min': '1'}}, '6'))


class TheScriptRestoresThroughThatFunctionTests(SimpleTestCase):

    def test_the_row_loop_asks_the_function_and_writes_what_it_answers(self):
        source = io.open(SCRIPT, encoding='utf-8').read()
        match = re.search(r'function restoreEdits\(edits\) \{(.*?)\n    \}\n', source, re.S)
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn("setupRestoredValues(edits[$(this).attr('data-key')], $min.attr('max'))", body)
        self.assertIn('values.weight !== undefined', body)
        self.assertIn('values.min !== undefined', body)
        self.assertIn('api.refresh();', body)
