# -*- coding: utf-8 -*-
"""A power Dracorune blocks the element stats, power, damage and neutral damage."""
from django.test import SimpleTestCase

from fashionistapulp import dracorunes
from fashionistapulp.transcendence_terms import (ELEMENT_BLOCKED,
                                                 POWER_BLOCKED,
                                                 RESISTANCE_BLOCKED,
                                                 dracorune_kind,
                                                 rune_allowed_on)


class APowerDraconizedCopyBlocksTheDamageStatsTests(SimpleTestCase):

    def test_pow_dam_and_neutdam_are_refused(self):
        for stat in (dracorunes.POWER_LINE, dracorunes.DAMAGE_LINE, 'neutdam'):
            with self.subTest(stat=stat):
                self.assertFalse(rune_allowed_on('power', stat))

    def test_the_element_stats_and_their_damages_are_refused(self):
        for source, damage in dracorunes.ELEMENT_PAIRS:
            for stat in (source, damage):
                with self.subTest(stat=stat):
                    self.assertFalse(rune_allowed_on('power', stat))
                    self.assertFalse(rune_allowed_on('element', stat))

    def test_free_stats_stay_allowed(self):
        for stat in ('vit', 'ap', 'init', 'cridam', 'fireres'):
            with self.subTest(stat=stat):
                self.assertTrue(rune_allowed_on('power', stat))

    def test_resistances_are_blocked_by_the_resistance_kind_only(self):
        self.assertFalse(rune_allowed_on('resistance', 'fireres'))
        self.assertFalse(rune_allowed_on('resistance', 'airresper'))
        self.assertTrue(rune_allowed_on('element', 'fireres'))
        self.assertTrue(rune_allowed_on('power', 'fireres'))
        self.assertEqual(len(RESISTANCE_BLOCKED), 10)

    def test_no_dracorune_blocks_nothing(self):
        for stat in POWER_BLOCKED | RESISTANCE_BLOCKED:
            self.assertTrue(rune_allowed_on(None, stat))

    def test_the_power_set_is_the_element_set_plus_three(self):
        self.assertEqual(POWER_BLOCKED - ELEMENT_BLOCKED,
                         {'pow', 'dam', 'neutdam'})

    def test_the_kind_is_the_text_before_the_colon(self):
        self.assertEqual(dracorune_kind('element:str>int'), 'element')
        self.assertEqual(dracorune_kind('resistance:neutral>fire'),
                         'resistance')
        self.assertEqual(dracorune_kind('power'), 'power')
