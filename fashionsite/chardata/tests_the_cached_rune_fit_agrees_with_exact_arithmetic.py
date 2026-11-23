# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The cached weight check and gains give what exact fractions give, for every rune of each file."""

from fractions import Fraction

from django.test import SimpleTestCase

from fashionistapulp.transcendence import load_runes
from fashionistapulp.transcendence_terms import (TRANSCENDENCE_VERSIONS, WEIGHT_CAP, _gain,
                                                 rune_fits)

LINES = (None, -30, 0, 0.1, 0.5, 1, 9.5, 10, 10.5, 15, 20, 20.5, 21, 21.0, 25, 30.5, 40.99,
         41, 61, 100, 0.30000000000000004, 0.3)


def _exact_fit(rune, line):
    used = (Fraction(str(rune['weight']))
            + max(Fraction(str(line or 0)), 0) * Fraction(str(rune['density'])))
    return used <= WEIGHT_CAP


class TheCachedRuneFitAgreesWithExactArithmeticTests(SimpleTestCase):

    def test_every_rune_and_line_fits_as_exact_fractions_say(self):
        for version in TRANSCENDENCE_VERSIONS:
            for rune in load_runes(version):
                for line in LINES:
                    with self.subTest(version=version, rune=rune['id'], line=line):
                        self.assertEqual(_exact_fit(rune, line), rune_fits(rune, line))

    def test_every_gain_is_the_exact_product_of_weight_and_bonus(self):
        for version in TRANSCENDENCE_VERSIONS:
            for rune in load_runes(version):
                for weight in (1, 0.05, 0.1, 3, Fraction(1, 3), 2.5):
                    with self.subTest(version=version, rune=rune['id'], weight=weight):
                        expected = Fraction(str(weight)) * Fraction(str(rune['bonus']))
                        self.assertEqual(expected, _gain(rune, {rune['stat_key']: weight}))
