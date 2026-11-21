# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The setup page puts cards 1 and 2 in the left column and 3, 4 and 5 in the right one."""
import os
import re

from django.test import SimpleTestCase

SCRIPT = os.path.join(os.path.dirname(__file__), 'static', 'chardata', 'setup.js')


class SetupCardOrderTests(SimpleTestCase):
    def placements(self):
        with open(SCRIPT, encoding='utf-8') as handle:
            source = handle.read()
        return {name: (column, int(order)) for column, name, order in re.findall(r'place\((col[AB]), (\w+), (\d+)\);', source)}

    def test_left_column_holds_the_first_two_cards_in_order(self):
        cards = self.placements()
        self.assertEqual(cards['register'], ('colA', 1))
        self.assertEqual(cards['recipes'], ('colA', 2))

    def test_right_column_holds_cards_three_to_five_in_order(self):
        cards = self.placements()
        right = sorted((order, name) for name, (column, order) in cards.items() if column == 'colB')
        self.assertEqual([name for order, name in right][:3], ['cardElement', 'cardStyle', 'more'])
