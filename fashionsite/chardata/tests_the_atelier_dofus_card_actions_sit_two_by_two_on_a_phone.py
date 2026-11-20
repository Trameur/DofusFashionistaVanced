# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a phone, the four actions of a Dofus or trophy card sit two by two, so each one stays wide enough to press."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, stylesheet

PARTS = stylesheet('modern-solution-parts.css')
ROW = 'html.fm-modern .solution-item-expand-header .solution-item-icons'
CARD = 'html.fm-modern .solution-item-section:not(.fm-sol-doll) .solution-item-expand-header .solution-item-icons'
PHONE = '(max-width:600px)'
NARROW = '(max-width:760px)'


def pixels(value):
    return float(value.split()[0].replace('px', ''))


class TheDofusCardActionsTests(SimpleTestCase):

    def test_the_actions_sit_two_by_two_on_a_phone(self):
        self.assertEqual('row', declared(PARTS, CARD, 'grid-auto-flow', PHONE)[0])
        self.assertEqual('repeat(2,minmax(0,44px))', declared(PARTS, CARD, 'grid-template-columns', PHONE)[0])

    def test_the_gap_between_the_two_rows_gives_back_what_the_margins_pull_in(self):
        margin = declared(PARTS, ROW.replace('-icons', '-button'), 'margin', NARROW)[0]
        self.assertLess(pixels(margin), 0)
        self.assertEqual('44px', declared(PARTS, ROW + ' > .solution-item-button', 'height', NARROW)[0])
        self.assertEqual(-2 * pixels(margin), pixels(declared(PARTS, CARD, 'row-gap', PHONE)[0]))

    def test_a_wider_screen_keeps_the_single_row(self):
        self.assertIsNone(declared(PARTS, CARD, 'grid-template-columns'))
        self.assertIsNone(declared(PARTS, CARD, 'grid-template-columns', NARROW))
        self.assertEqual('column', declared(PARTS, ROW, 'grid-auto-flow', NARROW)[0])
