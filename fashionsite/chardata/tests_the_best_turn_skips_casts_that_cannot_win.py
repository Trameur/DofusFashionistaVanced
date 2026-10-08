# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The best turn skips the casts that cannot beat the best one found and still gives the full search's answer."""
import copy
import sys
from unittest import mock

from django.test import SimpleTestCase

import chardata.spell_combo as spell_combo
from chardata.spell_combo import castable_spells, get_damage_spells_for_version
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.structure import get_structure, set_current_game_version


def _stats(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update({'str': 400, 'int': 400, 'cha': 400, 'agi': 900, 'pow': 100,
                  'dam': 40, 'ch': 30, 'cridam': 20, 'hp': 4000})
    return stats


def _searched(*args, **kwargs):
    """(turn, {search function: calls}) of one uncached best_turn."""
    calls = {'search': 0, 'bounded': 0}

    def counted(frame, event, _arg):
        if event == 'call' and frame.f_code.co_name in calls:
            calls[frame.f_code.co_name] += 1

    sys.setprofile(counted)
    try:
        turn = spell_combo._search_best_turn(*args, **kwargs)
    finally:
        sys.setprofile(None)
    return turn, calls


def _classes(version):
    known = set(get_damage_spells_for_version(version))
    return [char_class for char_class in filter_classes_for_version(CHARACTER_CLASSES, version)
            if char_class in known]


class TheTurnSearchStaysSmallTests(SimpleTestCase):

    def test_a_twelve_ap_turn_visits_a_fraction_of_its_casts(self):
        set_current_game_version('dofus3')
        stats = _stats('dofus3')
        for char_class in ('Cra', 'Huppermage'):
            with self.subTest(char_class=char_class):
                (total, order), calls = _searched(
                    stats, castable_spells(char_class, 200, 'dofus3'), 12,
                    game_version='dofus3', caster_level=200)
                self.assertTrue(order)
                self.assertGreater(total, 0)
                self.assertGreater(calls['bounded'], 0)
                self.assertEqual(0, calls['search'])
                self.assertLess(calls['bounded'], 150000)


class TheBoundGivesTheFullSearchAnswerTests(SimpleTestCase):

    def _both(self, *args, **kwargs):
        turn, calls = _searched(*args, **kwargs)
        with mock.patch.object(spell_combo, 'CEILING_SCORES', 0):
            full = spell_combo._search_best_turn(*args, **kwargs)
        self.assertEqual(repr(full), repr(turn))
        return calls['bounded'] > 0

    def test_every_class_gets_the_same_turn_with_or_without_the_bound(self):
        bounded = 0
        for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
            set_current_game_version(version)
            stats = _stats(version)
            for char_class in _classes(version):
                spells = castable_spells(char_class, 200, version)
                for ap, extra in ((7, {}), (9, {'crit': True}), (9, {'pushback': True})):
                    with self.subTest(version=version, char_class=char_class, ap=ap, **extra):
                        bounded += self._both(stats, spells, ap, game_version=version,
                                              caster_level=200, **extra)
        self.assertGreater(bounded, 100)

    def test_two_casts_worth_the_same_keep_the_first_one(self):
        set_current_game_version('dofus3')
        stats = _stats('dofus3')
        for char_class in ('Cra', 'Iop', 'Sram'):
            spells = castable_spells(char_class, 200, 'dofus3')
            for position, spell in enumerate(spells):
                if spell.alternatives and spell.limit != 1:
                    break
            twin = copy.copy(spell)
            twin.name = spell.name + ' twin'
            for ordered in (spells[:position] + [twin] + spells[position:],
                            spells[:position + 1] + [twin] + spells[position + 1:]):
                with self.subTest(char_class=char_class, first=ordered[position].name):
                    self.assertTrue(self._both(stats, ordered, 9, game_version='dofus3',
                                               caster_level=200))

    def test_a_negative_standing_stack_takes_the_full_search(self):
        set_current_game_version('dofus3')
        spells = castable_spells('Huppermage', 200, 'dofus3')
        standing = {spell.name: -2 for spell in spells if spell.buffs}
        self.assertTrue(standing)
        _turn, calls = _searched(_stats('dofus3'), spells, 9, standing=standing,
                                 game_version='dofus3', caster_level=200)
        self.assertEqual(0, calls['bounded'])
        self.assertGreater(calls['search'], 0)
