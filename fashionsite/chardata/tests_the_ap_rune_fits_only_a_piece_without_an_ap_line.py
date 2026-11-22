# -*- coding: utf-8 -*-
"""The Beta Gata Pa rune weighs 80 at density 100, so any positive AP line blocks it."""
from django.test import SimpleTestCase

from fashionistapulp.transcendence import load_runes
from fashionistapulp.transcendence_terms import (best_fitting, rune_fits,
                                                 runes_by_stat)


class TheApRuneFitsOnlyWithoutAnApLineTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gata = next(rune for rune in load_runes('beta')
                        if rune['id'] == 29679)

    def test_it_fits_at_line_zero_and_below(self):
        for line in (0, -1, -10, None):
            with self.subTest(line=line):
                self.assertTrue(rune_fits(self.gata, line))

    def test_it_does_not_fit_at_line_one(self):
        self.assertFalse(rune_fits(self.gata, 1))

    def test_the_best_fitting_ap_rune_follows_the_line(self):
        by_stat = runes_by_stat(load_runes('beta'))
        free = best_fitting(by_stat, {}, ['ap'])['ap']
        taken = best_fitting(by_stat, {'ap': 1}, ['ap'])['ap']
        self.assertEqual(free['id'], 29679)
        self.assertIsNone(taken)
