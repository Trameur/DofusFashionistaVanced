# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Measures the gallery filter checkboxes in the stylesheet: 20 px boxes in rows at least 44 px high on a phone, nothing new on a desktop."""
from django.test import SimpleTestCase

from .tests_the_setup_stylesheet_support import declared, matching, stylesheet

PHONE = '(max-width:760px)'
BOX = 'html.fm-modern .filters-section .build-boxes-section input[type="checkbox"]'
LABEL_BOX = 'html.fm-modern .filters-section label.filter-label input[type="checkbox"]'
ROW = 'html.fm-modern .build-boxes-section label'


class TheGalleryFilterBoxesAreBigEnoughToTapTests(SimpleTestCase):
    """The filter checkboxes of the public build gallery stay tappable on a phone."""

    def setUp(self):
        self.rules = stylesheet('modern.css')

    def test_the_phone_box_is_twenty_pixels(self):
        """Width and height are both 20 px under the phone query."""
        for box in (BOX, LABEL_BOX):
            self.assertEqual(declared(self.rules, box, 'width', PHONE)[0], '20px')
            self.assertEqual(declared(self.rules, box, 'height', PHONE)[0], '20px')

    def test_the_phone_row_stays_at_least_forty_four_pixels_high(self):
        """The label around the box is the tap target and keeps its 44 px minimum."""
        self.assertEqual(declared(self.rules, ROW, 'min-height', PHONE)[0], '44px')

    def test_no_desktop_rule_sizes_the_box(self):
        """The box selector appears only inside the phone query."""
        for box in (BOX, LABEL_BOX):
            self.assertEqual(matching(self.rules, box, None), [])
            self.assertEqual(len(matching(self.rules, box, PHONE)), 1)

    def test_the_split_sheet_carries_the_same_rule(self):
        """The generated sheet the pages load holds the phone rule too."""
        self.assertEqual(declared(stylesheet('modern-rest.css'), BOX, 'width', PHONE)[0], '20px')
