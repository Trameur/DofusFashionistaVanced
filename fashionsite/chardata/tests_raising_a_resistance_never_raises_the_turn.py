# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Raising any resistance of a target never raises a hit or the best turn; with none below 0 the turn never beats the raw one."""
import random

from django.core.cache import caches
from django.test import SimpleTestCase

from chardata.spell_combo import (HpShare, best_turn, castable_spells, final_multiplier,
                                  get_damage_spells_for_version, row_value)
from chardata.targets import ELEMENTS, Target
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
BUILDS = (('Cra', {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30,
                   'cridam': 25, 'ch': 45, 'hp': 3900}),
          ('Iop', {'str': 900, 'agi': 120, 'pow': 160, 'dam': 45, 'earthdam': 30,
                   'cridam': 40, 'ch': 35, 'hp': 4200}))


def _stats(version, wanted):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in wanted.items():
        if key in stats:
            stats[key] = value
    return stats


def _target(version, percent):
    return Target(version=version, kind='monster', ref=('m', 1, 1), level=200, hp=10000,
                  percent=tuple(percent), is_player=False, label='a monster')


class RaisingAResistanceTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.draw = random.Random(len(ELEMENTS))

    def _percents(self, low):
        return [self.draw.randint(low, 120) for _element in ELEMENTS]

    def test_no_row_gains_from_a_higher_resistance(self):
        for version in VERSIONS:
            set_current_game_version(version)
            for char_class, wanted in BUILDS:
                stats = _stats(version, wanted)
                multiplier = final_multiplier(stats)
                percent = self._percents(-60)
                for castable in castable_spells(char_class, 200, version):
                    for rows in castable.plain_alternatives or []:
                        for row in rows:
                            if isinstance(row, HpShare):
                                continue
                            before = row_value([row], stats, False, castable.is_spell,
                                               multiplier, _target(version, percent))
                            for index in range(len(ELEMENTS)):
                                raised = list(percent)
                                raised[index] += self.draw.randint(1, 60)
                                with self.subTest(version=version, spell=castable.name,
                                                  element=ELEMENTS[index]):
                                    self.assertLessEqual(
                                        row_value([row], stats, False, castable.is_spell,
                                                  multiplier, _target(version, raised)),
                                        before)

    def test_the_best_turn_never_gains_from_a_higher_resistance(self):
        for version in VERSIONS:
            set_current_game_version(version)
            for char_class, wanted in BUILDS:
                stats = _stats(version, wanted)
                spells = castable_spells(char_class, 200, version)
                for _draw in range(2):
                    percent = self._percents(-60)
                    total = best_turn(stats, spells, 11, game_version=version, caster_level=200,
                                      target=_target(version, percent))[0]
                    index = self.draw.randrange(len(ELEMENTS))
                    raised = list(percent)
                    raised[index] += self.draw.randint(1, 60)
                    with self.subTest(version=version, char_class=char_class, percent=percent,
                                      element=ELEMENTS[index]):
                        self.assertLessEqual(
                            best_turn(stats, spells, 11, game_version=version,
                                      caster_level=200, target=_target(version, raised))[0],
                            total + 1e-9)

    def test_with_no_resistance_below_zero_the_turn_never_beats_the_raw_one(self):
        for version in VERSIONS:
            set_current_game_version(version)
            for char_class, wanted in BUILDS:
                stats = _stats(version, wanted)
                spells = castable_spells(char_class, 200, version)
                raw = best_turn(stats, spells, 11, game_version=version, caster_level=200)[0]
                for _draw in range(2):
                    percent = self._percents(0)
                    with self.subTest(version=version, char_class=char_class, percent=percent):
                        self.assertLessEqual(
                            best_turn(stats, spells, 11, game_version=version,
                                      caster_level=200, target=_target(version, percent))[0],
                            raw + 1e-9)

    def test_a_target_with_no_resistance_never_beats_the_raw_turn_of_any_class(self):
        for version in VERSIONS:
            set_current_game_version(version)
            for char_class in sorted(name for name in get_damage_spells_for_version(version)
                                     if name != 'default'):
                for _label, wanted in BUILDS:
                    stats = _stats(version, wanted)
                    spells = castable_spells(char_class, 200, version)
                    raw = best_turn(stats, spells, 11, game_version=version,
                                    caster_level=200)[0]
                    with self.subTest(version=version, char_class=char_class):
                        self.assertLessEqual(
                            best_turn(stats, spells, 11, game_version=version, caster_level=200,
                                      target=_target(version, [0] * len(ELEMENTS)))[0],
                            raw + 1e-9)
