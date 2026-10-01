# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The default elements' reference set carries the HP the build page gives its level and Vitality."""
import re

from django.test import SimpleTestCase

from chardata import default_elements
from chardata.management.commands import store_default_elements as generator
from chardata.spell_combo import HpShare, best_turn, castable_spells, hp_share_hits_for_version
from chardata.util import character_own_stats
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES, STAT_KEY_TO_NAME, STATS_NAMES,
                                             max_scroll_for_version)
from fashionistapulp.game_versions import dofus_versions
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal
from fashionistapulp.structure import get_current_game_version, set_current_game_version

AP = 12
ELEMENT = 'str'
NO_EXO = {'ap_exo': False, 'range_exo': False, 'mp_exo': False}


def _gear(version, level):
    return default_elements.default_elements_table(version)['gear'][str(level)]


def _page_hp(version, char_class, level, vitality):
    """HP of an empty build scrolled to the version maximum, the rest of its Vitality spent in points."""
    set_current_game_version(version)
    scroll = max_scroll_for_version(version, level)
    minimal = ModelResultMinimal.generate_empty_solution({
        'char_level': level, 'options': dict(NO_EXO),
        'base_stats_by_attr': dict(character_own_stats(level, char_class, version))})
    spent = {name: 0 for name, _key in STATS_NAMES}
    spent[STAT_KEY_TO_NAME['vit']] = vitality - scroll
    minimal.update_base_stats(spent, {name: scroll for name, _key in STATS_NAMES})
    return model_result_from_minimal(minimal).get_stats_total()['hp']


class TheReferenceSetCarriesTheBuildPagesHpTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_its_vitality_is_the_scroll_and_the_gear_mean(self):
        for version in dofus_versions():
            for level in generator.LEVELS:
                gear = _gear(version, level)
                with self.subTest(version=version, level=level):
                    stats = generator.reference_stats(version, 'Iop', ELEMENT, gear, AP, level)
                    self.assertEqual(max_scroll_for_version(version, level) + gear['vit'],
                                     stats['vit'])

    def test_the_eight_pieces_carry_vitality_at_the_top_level(self):
        for version in dofus_versions():
            with self.subTest(version=version):
                self.assertGreater(_gear(version, generator.TOP_LEVEL)['vit'], 0)

    def test_its_hp_is_the_build_pages_for_every_class_and_level(self):
        checked = 0
        for version in dofus_versions():
            for char_class in filter_classes_for_version(CHARACTER_CLASSES, version):
                for level in generator.LEVELS:
                    with self.subTest(version=version, char_class=char_class, level=level):
                        stats = generator.reference_stats(version, char_class, ELEMENT,
                                                          _gear(version, level), AP, level)
                        self.assertEqual(_page_hp(version, char_class, level, stats['vit']),
                                         stats['hp'])
                        self.assertGreater(stats['hp'], stats['vit'])
                        checked += 1
        self.assertGreater(checked, 400)

    def test_the_reference_text_names_the_characteristics_the_set_scrolls(self):
        version = 'dofus3'
        scroll = max_scroll_for_version(version, generator.TOP_LEVEL)
        self.assertGreater(scroll, 0)
        stats = generator.reference_stats(version, 'Iop', ELEMENT,
                                          dict.fromkeys(generator.GEAR_KEYS, 0), AP)
        segment = generator.reference_text().split(': ', 1)[1].split(
            ' scrolled to the version maximum')[0]
        self.assertEqual({name for name, key in STATS_NAMES if stats[key] >= scroll},
                         set(re.split(', | and ', segment)))

    def test_build_hp_leaves_the_current_version_as_it_found_it(self):
        set_current_game_version('retro')
        generator.build_hp('dofus2', 'Iop', generator.TOP_LEVEL, 100)
        self.assertEqual('retro', get_current_game_version())

    def test_a_share_of_hp_counts_in_the_reference_turn(self):
        checked = 0
        for version in dofus_versions():
            set_current_game_version(version)
            gear = _gear(version, generator.TOP_LEVEL)
            for char_class in hp_share_hits_for_version(version):
                stats = generator.reference_stats(version, char_class, ELEMENT, gear, AP,
                                                  generator.TOP_LEVEL)
                without = dict(stats, hp=0)
                for spell in castable_spells(char_class, generator.TOP_LEVEL, version):
                    if not any(isinstance(row, HpShare) for alternative
                               in spell.plain_alternatives for row in alternative):
                        continue
                    with self.subTest(version=version, spell=spell.name):
                        self.assertGreater(
                            best_turn(stats, [spell], spell.cost, game_version=version,
                                      caster_level=generator.TOP_LEVEL)[0],
                            best_turn(without, [spell], spell.cost, game_version=version,
                                      caster_level=generator.TOP_LEVEL)[0])
                        checked += 1
        self.assertGreater(checked, 0)
