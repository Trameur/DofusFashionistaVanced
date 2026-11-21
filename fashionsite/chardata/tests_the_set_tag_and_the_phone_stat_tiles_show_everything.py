# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A set tag on a closed card shows its whole name and count on up to two lines, and the phone stat tiles form a balanced grid with no lone tile."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, matching, stylesheet

PARTS = stylesheet('modern-solution-parts.css')
TAG = 'html.fm-modern .solution-item-name-div .fm-set-tag'
NAME = TAG + ' .fm-set-tag-name'
NUMS = 'html.fm-modern .fm-sol-nums'
TILE = 'html.fm-modern .fm-sol-nums .fm-sol-num'
PHONE = '(max-width:759px)'
SMALL = '(max-width:520px)'


class ASetTagShowsItsWholeNameTests(SimpleTestCase):

    def test_the_name_wraps_between_words_and_the_count_stays_whole(self):
        self.assertEqual(('nowrap', True), declared(PARTS, TAG, 'white-space'))
        self.assertEqual(('normal', True), declared(PARTS, NAME, 'white-space'))

    def test_no_ellipsis_and_no_clipping_remain_on_the_name(self):
        self.assertEqual(('clip', False), declared(PARTS, NAME, 'text-overflow'))
        self.assertEqual(('visible', False), declared(PARTS, NAME, 'overflow'))
        for rule in PARTS:
            if '.fm-set-tag-name' in ' '.join(rule['selectors']):
                self.assertNotEqual('ellipsis', rule['declarations'].get('text-overflow', ('', 0))[0])

    def test_the_tag_follows_the_alignment_of_its_card(self):
        for prop in ('text-align', 'justify-content', 'margin'):
            self.assertIsNone(declared(PARTS, TAG, prop), prop)


class ThePhoneStatTilesFormABalancedGridTests(SimpleTestCase):

    def test_a_phone_lays_the_six_tiles_out_in_columns_of_equal_width(self):
        self.assertEqual(('grid', False), declared(PARTS, NUMS, 'display', PHONE))
        self.assertEqual(('100%', False), declared(PARTS, NUMS, 'width', PHONE))
        self.assertEqual(('repeat(3,minmax(0,1fr))', False), declared(PARTS, NUMS, 'grid-template-columns', PHONE))

    def test_a_small_phone_uses_two_columns_so_no_tile_is_alone(self):
        self.assertEqual(('repeat(2,minmax(0,1fr))', False), declared(PARTS, NUMS, 'grid-template-columns', SMALL))

    def test_a_tile_may_shrink_and_a_long_value_breaks_instead_of_overflowing(self):
        self.assertEqual(('0', False), declared(PARTS, TILE, 'min-width', PHONE))
        self.assertEqual(('anywhere', False), declared(PARTS, 'html.fm-modern .fm-sol-nums .fm-sol-num-v', 'overflow-wrap', PHONE))

    def test_the_laptop_layout_is_left_to_the_original_rule(self):
        self.assertFalse([rule for rule in matching(PARTS, NUMS) + matching(PARTS, TILE) if rule['media'] is None])
