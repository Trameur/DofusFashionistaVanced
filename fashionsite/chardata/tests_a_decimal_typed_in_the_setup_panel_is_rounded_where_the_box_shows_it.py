# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A decimal or exponent typed in a /setup/ panel box becomes the whole number the build will store, and a value that is not a number is no edit."""
import json

from django.test import SimpleTestCase

from chardata.tests_the_setup_script_sends_the_form_and_shows_only_the_last_change import run_script
from chardata.tests_the_weights_page_boxes_change_only_what_was_typed import run_page_script

TYPED = (('2.5', '3'), ('2.49', '2'), ('-2.5', '-2'), ('-2.51', '-3'), ('1e2', '100'),
         ('1.5e2', '150'), ('12.5', '13'), ('7', '7'), ('-0.4', '0'))


class TheBoxShowsTheWholeNumberTests(SimpleTestCase):

    def settled(self, column, typed, preview=True, cap=None):
        return run_page_script(self, """
            previewMode = %s;
            resistPage([240, 240, 240, 240, 240], ['', '', '', '', ''], '53');
            var box = boxes.%s_vit;
            %s
            focus(box);
            type(box, %s);
            $(box).trigger('change');
            return box.value;""" % (json.dumps(preview), column,
                                    "box.max = '%s';" % cap if cap else '', json.dumps(typed)))

    def test_a_weight_typed_with_decimals_or_an_exponent_is_rounded_half_up(self):
        for typed, shown in TYPED:
            with self.subTest(typed=typed):
                self.assertEqual(shown, self.settled('weight', typed))

    def test_a_minimum_typed_with_decimals_or_an_exponent_is_rounded_half_up(self):
        for typed, shown in TYPED:
            with self.subTest(typed=typed):
                self.assertEqual(shown, self.settled('min', typed))

    def test_a_minimum_rounded_up_past_the_cap_is_cut_to_the_cap(self):
        self.assertEqual('53', self.settled('min', '52.6', cap='53'))
        self.assertEqual('53', self.settled('min', '53.6', cap='53'))
        self.assertEqual('52', self.settled('min', '52.4', cap='53'))

    def test_a_resist_group_typed_with_decimals_hands_each_member_the_whole_number(self):
        self.assertEqual(['3', '3', '3', '3', '3'], run_page_script(self, """
            previewMode = true;
            var keys = resistPage([240, 240, 240, 240, 240], ['', '', '', '', ''], '53');
            focus(boxes.weight_perres);
            type(boxes.weight_perres, '2.5');
            $(boxes.weight_perres).trigger('change');
            return values('weight', keys);"""))

    def test_an_emptied_minimum_stays_empty_and_an_emptied_weight_becomes_zero(self):
        self.assertEqual('', self.settled('min', ''))
        self.assertEqual('0', self.settled('weight', ''))

    def test_a_value_that_is_not_a_number_is_left_alone(self):
        self.assertEqual('abc', self.settled('weight', 'abc'))
        self.assertEqual('abc', self.settled('min', 'abc'))

    def test_the_weights_page_keeps_what_was_typed_for_its_own_validation(self):
        self.assertEqual('2.5', self.settled('weight', '2.5', preview=False))
        self.assertEqual('1e2', self.settled('min', '1e2', preview=False))


class AValueThatWillNotBeStoredIsNoEditTests(SimpleTestCase):

    def edits(self, was, now):
        return run_script(self, """
            var edits = setupEdits(%s, %s);
            return {edits: edits, fields: setupTouchedFields(edits)};""" % (json.dumps(was), json.dumps(now)))

    def row(self, weight=None, minimum=None):
        row = {}
        if weight is not None:
            row['weight'] = weight
        if minimum is not None:
            row['min'] = minimum
        return {'wis': row}

    def test_a_decimal_that_rounds_to_the_preset_value_is_no_edit(self):
        found = self.edits(self.row('10', '5'), self.row('10.4', '5.2'))
        self.assertEqual({}, found['edits'])
        self.assertEqual([], found['fields'])

    def test_a_decimal_that_rounds_to_another_value_is_one_edit_carrying_the_whole_number(self):
        found = self.edits(self.row('10', '5'), self.row('2.5', '1e2'))
        self.assertEqual([['min_wis', '100'], ['weight_wis', '3']], sorted(found['fields']))
        self.assertEqual({'weight': 3, 'min': 100}, {key: found['edits']['wis']['now'][key]
                                                       for key in ('weight', 'min')})

    def test_a_value_that_is_not_a_finite_number_is_no_edit(self):
        for typed in ('abc', 'NaN', 'Infinity', '-Infinity', '1e999'):
            with self.subTest(typed=typed):
                found = self.edits(self.row('10', '5'), self.row(typed, typed))
                self.assertEqual({}, found['edits'])
                self.assertEqual([], found['fields'])

    def test_an_emptied_weight_is_no_edit_and_an_emptied_minimum_is_the_edit_that_clears_it(self):
        for emptied in ('', '  '):
            with self.subTest(emptied=emptied):
                found = self.edits(self.row('10', '5'), self.row(emptied, emptied))
                self.assertEqual([['min_wis', emptied]], found['fields'])

    def test_an_empty_minimum_over_an_empty_preset_is_no_edit(self):
        self.assertEqual([], self.edits(self.row('10', ''), self.row('10', ''))['fields'])
