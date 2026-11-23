# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""In an opened Atelier tile the stat edit row puts the label on a full row of its own, so a label never breaks inside a word."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, stylesheet

PARTS = stylesheet('modern-solution-parts.css')
ROW = 'html.fm-modern .solution-item-section .expand-container.fm-open .sol-stat-edit-row'
LABEL = ROW + ' > span:not(.save-feedback)'
BUTTON = ROW + ' > button'
INPUT = ROW + ' > input'
PHONE = '(max-width:759px)'


def pixels(value):
    return float(value.replace('px', ''))


class TheEditRowTests(SimpleTestCase):

    def test_the_label_takes_the_whole_first_row(self):
        self.assertEqual('0 0 100%', declared(PARTS, LABEL, 'flex')[0])
        self.assertEqual('-1', declared(PARTS, LABEL, 'order')[0])

    def test_the_label_never_hyphenates_or_breaks_inside_a_word(self):
        self.assertNotEqual('auto', declared(PARTS, LABEL, 'hyphens')[0])
        self.assertEqual('normal', declared(PARTS, LABEL, 'overflow-wrap')[0])

    def test_the_cross_button_goes_to_the_right_of_the_next_row(self):
        self.assertEqual('auto', declared(PARTS, BUTTON, 'margin-left')[0])
        self.assertEqual('3', declared(PARTS, BUTTON, 'order')[0])

    def test_the_cross_button_is_44_pixels_on_a_phone_and_only_there(self):
        self.assertEqual(44, pixels(declared(PARTS, BUTTON, 'min-width', PHONE)[0]))
        self.assertEqual(44, pixels(declared(PARTS, BUTTON, 'min-height', PHONE)[0]))
        self.assertIsNone(declared(PARTS, BUTTON, 'min-width'))

    def test_the_input_keeps_its_own_full_row_after_the_button(self):
        self.assertEqual('4', declared(PARTS, INPUT, 'order')[0])
        self.assertEqual('0 0 100%', declared(PARTS, INPUT, 'flex')[0])
