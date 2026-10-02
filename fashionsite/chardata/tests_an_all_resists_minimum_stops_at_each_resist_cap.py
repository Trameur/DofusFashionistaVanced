# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A minimum typed on the All % Resists row stops at each resist's cap, as one typed on a resist does."""
from django.test import SimpleTestCase

from chardata.tests_the_weights_page_boxes_change_only_what_was_typed import run_page_script


class AnAllResistsMinimumStopsAtEachCapTests(SimpleTestCase):

    def test_a_group_minimum_above_the_cap_lands_on_the_cap_and_flashes(self):
        self.assertEqual({'minimums': ['53', '53', '53', '53', '53'], 'group': '53',
                          'flashed': 5}, run_page_script(self, """
            var keys = resistPage([240, 240, 240, 240, 240], ['', '', '', '', ''], '53');
            focus(boxes.min_perres);
            type(boxes.min_perres, '60');
            press(boxes.min_perres);
            return {minimums: values('min', keys), group: boxes.min_perres.value,
                    flashed: keys.filter(function(k) {
                        return rows[k].classes['wm-cap-hit']; }).length};"""))

    def test_a_group_minimum_under_the_cap_reaches_every_resist(self):
        self.assertEqual(['20', '20', '20', '20', '20'], run_page_script(self, """
            var keys = resistPage([240, 240, 240, 240, 240], ['', '', '30', '', ''], '38');
            focus(boxes.min_perres);
            type(boxes.min_perres, '20');
            press(boxes.min_perres);
            return values('min', keys);"""))

    def test_a_resist_minimum_above_the_cap_lands_on_the_cap(self):
        self.assertEqual(['', '', '38', '', ''], run_page_script(self, """
            var keys = resistPage([240, 240, 240, 240, 240], ['', '', '', '', ''], '38');
            focus(boxes.min_fireresper);
            type(boxes.min_fireresper, '45');
            press(boxes.min_fireresper);
            return values('min', keys);"""))
