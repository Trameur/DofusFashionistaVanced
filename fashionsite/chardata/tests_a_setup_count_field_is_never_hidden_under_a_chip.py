# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The /setup/ More options count fields (Dracorunes, exos per piece) stay visible number boxes: no stylesheet turns their label into a chip that hides the box."""
import glob
import os
import re

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, stylesheet

COUNT_LABEL = 'setup-more-count'
HIDDEN = {'opacity': '0', 'visibility': 'hidden', 'display': 'none'}
CHOICE_ONLY = re.compile(r'input\[type=["\']?(radio|checkbox)["\']?\]|:checked')


def hides(rule):
    return any(rule['declarations'].get(prop, (None,))[0] == value for prop, value in HIDDEN.items())


def reaches_a_count_box(selector):
    """A selector that ends on the input of a More options field label and does not leave the count labels out."""
    if 'advanced-options-field' not in selector and 'setup-more' not in selector:
        return False
    tail = selector.rsplit(' ', 1)[-1]
    if not tail.startswith('input') or CHOICE_ONLY.search(tail):
        return False
    return 'label' in selector and ':not(.%s)' % COUNT_LABEL not in selector


class ASetupCountFieldIsNeverHiddenUnderAChipTests(SimpleTestCase):

    def test_no_stylesheet_hides_the_box_of_a_count_label(self):
        found = []
        for path in sorted(glob.glob(os.path.join(STATIC, '*.css'))):
            name = os.path.basename(path)
            for rule in stylesheet(name):
                if hides(rule):
                    found += ['%s: %s' % (name, selector) for selector in rule['selectors']
                              if reaches_a_count_box(selector)]
        self.assertEqual([], found)

    def test_the_old_chip_rule_is_caught(self):
        self.assertTrue(reaches_a_count_box(
            'html.fm-modern .setup-atelier.setup-new .fm-setup-card .advanced-options-field > label > input'))
        self.assertFalse(reaches_a_count_box(
            'html.fm-modern .setup-atelier.setup-new .fm-setup-card .advanced-options-field > label:not(.setup-more-count) > input'))

    def test_the_dracorune_row_draws_its_box_inside_a_count_label(self):
        page = render_to_string('chardata/dracorune_option.html', {'slots': 8, 'value': 2, 'as_row': True})
        self.assertRegex(page, r'<label class="%s"><span>[^<]+</span><input [^>]*type="number" [^>]*name="dracorunes" '
                               r'min="0" max="8"[^>]*value="2"' % COUNT_LABEL)
