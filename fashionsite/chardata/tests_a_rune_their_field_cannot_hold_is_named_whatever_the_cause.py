# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A rune with no usable position, or one that touches a total their field already refuses, is named as staying, never dropped."""

from django.test import SimpleTestCase

from chardata import dofusbook_export, dofusbook_export_view


class TheRunesTheFieldRefusesAreNamedTests(SimpleTestCase):

    def setUp(self):
        positions = dofusbook_export.index_by_stat_key()
        self.free = positions['init']
        self.base = positions['cha']

    def carry(self, runes, totals):
        return dofusbook_export_view._carry_runes(runes, totals, {}, 200)

    def test_a_rune_with_no_position_is_named_and_adds_nothing(self):
        forge, _refused, left = self.carry([('Lost (hat)', None)], {self.free: 10})
        self.assertEqual(['Lost (hat)'], left)
        self.assertEqual({self.free: 10}, forge)

    def test_a_rune_on_a_total_already_refused_is_named(self):
        forge, refused, left = self.carry([('Stuck (hat)', {self.base: 5})], {self.base: -3})
        self.assertEqual(['Stuck (hat)'], left)
        self.assertEqual([self.base], refused)
        self.assertNotIn(self.base, forge)

    def test_a_rune_that_fits_travels_and_is_not_named(self):
        forge, refused, left = self.carry([('Fine (hat)', {self.free: 3})], {self.free: 10})
        self.assertEqual([], left)
        self.assertEqual([], refused)
        self.assertEqual({self.free: 13}, forge)

    def test_the_one_that_crosses_the_line_is_named_beside_the_one_that_fits(self):
        _forge, _refused, left = self.carry(
            [('Fine (hat)', {self.free: 3}), ('Over (hat)', {self.base: -5})], {self.base: 2})
        self.assertEqual(['Over (hat)'], left)
