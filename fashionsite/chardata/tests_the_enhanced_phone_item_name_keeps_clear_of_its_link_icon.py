# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a narrow screen the enhanced classic design pins the item link icon over the name's right padding, which must stay inside the name's cell."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, stylesheet

NARROW = '(max-width: 900px)'
NAME = 'html.fm-enhanced .solution-item-name-div'
LINK = 'html.fm-enhanced .solution-item-link-div'


class TheEnhancedPhoneItemNameKeepsClearOfItsLinkIconTests(SimpleTestCase):
    def setUp(self):
        self.rules = stylesheet('enhanced.css')

    def test_the_link_icon_sits_over_the_top_right_corner(self):
        self.assertEqual(('absolute', True), declared(self.rules, LINK, 'position', NARROW))
        self.assertEqual(('8px', False), declared(self.rules, LINK, 'right', NARROW))

    def test_the_name_reserves_room_for_the_icon(self):
        self.assertEqual(('26px', False), declared(self.rules, NAME, 'padding-right', NARROW))

    def test_the_reserved_room_counts_inside_the_name_width(self):
        self.assertEqual(('border-box', False), declared(self.rules, NAME, 'box-sizing', NARROW))
