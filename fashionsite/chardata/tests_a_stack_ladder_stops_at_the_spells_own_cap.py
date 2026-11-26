# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell's Stack ladder stops at the cap its own level declares, not at the template's row count."""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version

FIT_OF_RAGE = 13156
SHRIVELLING = 13254
IMMOBILISING_ARROW = 32436
SHRILL_CHOIR = 25861
VERSIONS = ('dofus3', 'beta')


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _labels(spell):
    return [label for label, _rows in spell.aggregates]


def _ladder(max_stacks, declared_cap):
    non_crit = [['23-26', '43-46']]
    labels = _generator()._apply_stackable_damage(
        {'stackable_damage': {'per_stack': [20, 20], 'max_stacks': max_stacks}},
        [90, 157], non_crit, None, ['EARTH'], None, None, False, declared_cap)
    return [label for label, _rows in labels], non_crit


class TheShippedLaddersStopAtTheSpellsOwnCapTests(SimpleTestCase):

    def test_fit_of_rage_climbs_to_two_stacks_not_four(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                rage = _spell(version, FIT_OF_RAGE)
                self.assertEqual(rage.stacks, 2)
                self.assertEqual(_labels(rage), ['Stack 0', 'Stack 1', 'Stack 2'])
                self.assertEqual(len(rage.effects.non_crit_ranges), 3)

    def test_fit_of_rage_tops_out_at_forty_more_damage(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                top = _spell(version, FIT_OF_RAGE).effects.non_crit_ranges[-1]
                self.assertEqual([(top[0].min_dam, top[0].max_dam)], [(63, 66)])

    def test_shrivelling_climbs_to_three_stacks_not_four(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, SHRIVELLING)
                self.assertEqual(spell.stacks, 3)
                self.assertEqual(_labels(spell), ['Stack 0', 'Stack 1', 'Stack 2', 'Stack 3'])
                self.assertEqual(len(spell.effects.non_crit_ranges), 4)

    def test_a_ladder_that_already_matched_its_cap_keeps_every_row(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, IMMOBILISING_ARROW)
                self.assertEqual(spell.stacks, 4)
                self.assertEqual(_labels(spell), ['Stack %d' % count for count in range(5)])
                self.assertEqual(len(spell.effects.non_crit_ranges), 5)

    def test_a_multi_row_ladder_capped_by_its_declared_stack_keeps_its_rows(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                spell = _spell(version, SHRILL_CHOIR)
                self.assertEqual(spell.stacks, 3)
                self.assertEqual(len(spell.aggregates), 8)


class TheGeneratorCapsTheLadderTests(SimpleTestCase):

    def test_a_declared_cap_below_the_template_count_shortens_the_ladder(self):
        labels, non_crit = _ladder([4, 4], 2)
        self.assertEqual(labels, ['Stack 0', 'Stack 1', 'Stack 2'])
        self.assertEqual(non_crit[-1], ['63-66', '83-86'])

    def test_no_declared_cap_leaves_the_template_ladder(self):
        labels, _ = _ladder([4, 4], None)
        self.assertEqual(labels, ['Stack %d' % count for count in range(5)])

    def test_a_cap_of_one_is_not_a_ladder_cap(self):
        labels, _ = _ladder([4, 4], 1)
        self.assertEqual(len(labels), 5)

    def test_a_declared_cap_above_the_template_count_does_not_lengthen_it(self):
        labels, _ = _ladder([4, 4], 9)
        self.assertEqual(len(labels), 5)

    def test_the_cap_a_level_declares_is_read_from_the_spell(self):
        generator = _generator()
        spell = {'levels': [{'max_stack': 2}, {'max_stack': 2}]}
        self.assertEqual(generator._declared_stack_limit(spell), (2, True))
        self.assertEqual(generator._declared_stack_limit({'levels': [{'max_stack': -1}]}),
                         (None, False))
