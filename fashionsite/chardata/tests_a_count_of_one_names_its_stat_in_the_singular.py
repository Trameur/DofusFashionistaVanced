# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A counted stat reads in the singular when the count is exactly one."""

from unittest import mock

from django.test import SimpleTestCase
from django.utils import translation

from chardata import encyclopedia_view
from chardata.solution_result import AttributeLine
from chardata.translation_util import stat_label_for_count

SINGULAR = {
    'fr': {'Summon': 'Invocation', 'Heals': 'Soin', 'Earth Damage': 'Dommage Terre'},
    'es': {'Summon': 'Invocación', 'Heals': 'Cura', 'Fire Damage': 'Daño Fuego'},
    'pt': {'Summon': 'Invocação', 'Heals': 'Cura', 'Water Damage': 'Dano Água'},
    'de': {'Summon': 'Beschwörung', 'Heals': 'Heilung'},
    'en': {'Summon': 'Summon', 'Heals': 'Heal'},
}
PLURAL_FR = {'Summon': 'Invocations', 'Heals': 'Soins', 'Earth Damage': 'Dommages Terre'}


class ACountOfOneNamesItsStatInTheSingularTests(SimpleTestCase):

    def test_a_count_of_one_uses_the_singular_in_every_language(self):
        for language, names in SINGULAR.items():
            for name, expected in names.items():
                with self.subTest(language=language, name=name), \
                        translation.override(language):
                    self.assertEqual(expected, stat_label_for_count(name, 1))

    def test_other_counts_keep_the_plural_name(self):
        with translation.override('fr'):
            for name, expected in PLURAL_FR.items():
                for count in (0, 2, 5, -2):
                    with self.subTest(name=name, count=count):
                        self.assertEqual(expected, stat_label_for_count(name, count))

    def test_a_stat_that_is_not_counted_is_left_alone(self):
        with translation.override('fr'):
            self.assertEqual('PA', stat_label_for_count('AP', 1))

    def test_the_build_card_line_says_one_invocation(self):
        with translation.override('fr'):
            self.assertEqual('1 Invocation', AttributeLine('summon', 1, 'Summon').text)
            self.assertEqual('2 Invocations', AttributeLine('summon', 2, 'Summon').text)

    def test_a_malus_of_one_reads_in_the_singular(self):
        with translation.override('fr'):
            self.assertEqual('Invocation', stat_label_for_count('Summon', -1))
            self.assertEqual('-1 Invocation', AttributeLine('summon', -1, 'Summon').text)

    def test_the_encyclopedia_keeps_the_plural_for_a_rolled_range(self):
        with mock.patch.object(encyclopedia_view, 'get_stat_range', return_value=None):
            fixed = encyclopedia_view._stat_count(None, 1, 1.0)
        with mock.patch.object(encyclopedia_view, 'get_stat_range', return_value=(1, 2)):
            ranged = encyclopedia_view._stat_count(None, 1, 1.0)
        self.assertEqual(1, fixed)
        self.assertEqual(0, ranged)
        self.assertEqual('Invocation', encyclopedia_view._counted_stat('Summon', 'fr', None, fixed))
        self.assertEqual('Invocations', encyclopedia_view._counted_stat('Summon', 'fr', None, ranged))
