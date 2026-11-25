# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a character target the panel total is the burst total of its order, in panel order, and no summon-only spell is cast."""
from unittest import mock

from django.core.cache import caches
from django.test import SimpleTestCase

from chardata import spells_view
from chardata.spell_combo import (best_turn, castable_spells, combat_ap,
                                  get_damage_spells_for_version, summon_only_spells)
from chardata.spells_view import _burst_total
from chardata.targets import build_target
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
CASTER = {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30, 'cridam': 25,
          'ch': 45, 'ap': 11, 'hp': 3900, 'perspedam': 15, 'perweadam': 10, 'final': 6}
DEFENDER = {'earthresper': 28, 'fireresper': 61, 'waterresper': -10, 'airresper': 12,
            'neutresper': 35, 'earthres': 20, 'fireres': 9, 'waterres': 31, 'airres': 4,
            'neutres': 15, 'crires': 22, 'pshres': 40, 'hp': 4700}


def _stats(version, values):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in values.items():
        if key in stats:
            stats[key] = value
    return stats


def _defender(version):
    char = mock.Mock(pk=9, char_class='Sacrieur', level=200)
    char.name = 'the defender'
    solution = mock.Mock()
    solution.get_stats_total.return_value = _stats(version, DEFENDER)
    return build_target(char, solution, version, 'b9')


def _classes(version):
    return sorted(name for name in get_damage_spells_for_version(version) if name != 'default')


class ThePanelTotalOnACharacterTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _combo(self, version, char_class, spells, target):
        char = mock.Mock(char_class=char_class, level=200)
        solution = mock.Mock(item_list=[])
        solution.get_stats_total.return_value = _stats(version, CASTER)
        with mock.patch('chardata.spell_combo.castable_spells', return_value=spells), \
                mock.patch('chardata.spell_combo.buffs_in_force', return_value={}), \
                mock.patch('chardata.spell_combo.stacks_in_force', return_value={}), \
                mock.patch('chardata.temporix_mode.solution_uses_temporix', return_value=False), \
                mock.patch.object(spells_view, 'worn_spell_modifiers', return_value={}), \
                mock.patch.object(spells_view, '_weapon_castable', return_value=None):
            return spells_view._best_combo(char, solution, version, target=target,
                                           note_without_buffs=False)

    def test_the_payload_total_is_the_burst_total_of_its_order_on_a_build(self):
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version, CASTER)
            ap = combat_ap(stats['ap'], version)
            summons = set(summon_only_spells(version))
            target = _defender(version)
            for char_class in _classes(version):
                spells = castable_spells(char_class, 200, version)
                combo = self._combo(version, char_class, spells, target)
                _total, order = best_turn(stats, spells, ap, standing={},
                                          game_version=version, caster_level=200,
                                          target=target)
                with self.subTest(version=version, char_class=char_class):
                    self.assertEqual(_burst_total(stats, spells, order, {}, version, target),
                                     combo['total'])
                    self.assertEqual(combo['total'], sum(cast['damage']
                                                         for cast in combo['casts']))
                    self.assertEqual('b9', combo['target']['token'])
                    self.assertEqual('build', combo['target']['kind'])
                    by_name = {spell.name: spell for spell in spells}
                    self.assertFalse([name for name, _damage in order
                                      if getattr(by_name[name], 'spell_id', None) in summons])
