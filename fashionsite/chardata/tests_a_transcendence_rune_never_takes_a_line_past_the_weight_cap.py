# -*- coding: utf-8 -*-
"""A rune fits only while its weight plus the line's weight stays within 101."""
from django.test import SimpleTestCase

from fashionistapulp.transcendence_terms import WEIGHT_CAP, rune_fits


class TheWeightCapIsExactTests(SimpleTestCase):

    def test_the_cap_is_101(self):
        self.assertEqual(WEIGHT_CAP, 101)

    def test_a_line_exactly_at_the_cap_fits(self):
        rune = {'weight': 40, 'density': 1}
        self.assertTrue(rune_fits(rune, 61))
        self.assertFalse(rune_fits(rune, 62))

    def test_a_float_density_does_not_drift_past_the_cap(self):
        rune = {'weight': 40, 'density': 0.2}
        self.assertTrue(rune_fits(rune, 305))
        self.assertFalse(rune_fits(rune, 306))
        self.assertTrue(rune_fits({'weight': 41, 'density': 0.1}, 600))
        self.assertFalse(rune_fits({'weight': 41, 'density': 0.1}, 601))

    def test_a_negative_or_missing_line_counts_as_zero(self):
        rune = {'weight': 80, 'density': 100}
        self.assertTrue(rune_fits(rune, -5))
        self.assertTrue(rune_fits(rune, 0))
        self.assertTrue(rune_fits(rune, None))

    def test_a_rune_heavier_than_the_cap_never_fits(self):
        self.assertFalse(rune_fits({'weight': 102, 'density': 1}, 0))


class TheShippedFilesKeepTheCapExactTests(SimpleTestCase):

    def test_every_dofus2_vit_and_init_rune_fits_at_the_exact_boundary(self):
        from fashionistapulp import transcendence
        import json
        import os
        path = os.path.join(transcendence.DEFAULT_FOLDER, 'dofus2.json')
        with open(path, encoding='utf-8') as handle:
            runes = json.load(handle)['runes']
        checked = 0
        for rune in runes:
            if rune['stat_key'] not in ('vit', 'init'):
                continue
            line = int((WEIGHT_CAP - rune['weight']) / rune['density'] + 0.5)
            self.assertTrue(rune_fits(rune, line), rune['id'])
            self.assertFalse(rune_fits(rune, line + 1), rune['id'])
            checked += 1
        self.assertGreater(checked, 0)
