# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The payload of a turn on a target carries the raw total of the raw turn and the share of the target's HP that its own total takes."""
from unittest import mock

from django.core.cache import caches
from django.test import SimpleTestCase

from chardata import spells_view
from chardata.spell_combo import best_turn, castable_spells, combat_ap
from chardata.spells_view import _burst_total
from chardata.targets import Target
from fashionistapulp.structure import get_structure, set_current_game_version

STATS = {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30, 'cridam': 25,
         'ch': 45, 'ap': 11, 'hp': 3900}
PERCENT = (17, 16, 29, 25, 14)
HP = 7000


def _stats(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in STATS.items():
        if key in stats:
            stats[key] = value
    return stats


class ThePayloadOfATargetTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _combo(self, version, char_class, spells, target):
        char = mock.Mock(char_class=char_class, level=200)
        solution = mock.Mock(item_list=[])
        solution.get_stats_total.return_value = _stats(version)
        with mock.patch('chardata.spell_combo.castable_spells', return_value=spells), \
                mock.patch('chardata.spell_combo.buffs_in_force', return_value={}), \
                mock.patch('chardata.spell_combo.stacks_in_force', return_value={}), \
                mock.patch('chardata.temporix_mode.solution_uses_temporix', return_value=False), \
                mock.patch.object(spells_view, 'worn_spell_modifiers', return_value={}), \
                mock.patch.object(spells_view, '_weapon_castable', return_value=None):
            return spells_view._best_combo(char, solution, version, target=target,
                                           note_without_buffs=False)

    def test_the_raw_total_is_the_panel_total_without_a_target_and_the_share_reads_the_target_total(self):
        for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
            set_current_game_version(version)
            stats = _stats(version)
            ap = combat_ap(stats['ap'], version)
            target = Target(version=version, kind='monster', ref=('m', 1, 1), level=200, hp=HP,
                            percent=PERCENT, is_player=False, label='a monster')
            for char_class in ('Cra', 'Iop', 'Sadida', 'Sram', 'Xelor'):
                spells = castable_spells(char_class, 200, version)
                _total, raw_order = best_turn(stats, spells, ap, standing={},
                                              game_version=version, caster_level=200)
                combo = self._combo(version, char_class, spells, target)
                with self.subTest(version=version, char_class=char_class):
                    self.assertNotEqual(combo['total'], combo['raw_total'])
                    self.assertEqual(_burst_total(stats, spells, raw_order, {}, version),
                                     combo['raw_total'])
                    self.assertEqual(int(round(100.0 * combo['total'] / HP)),
                                     combo['target']['hp_share'])
                    self.assertNotEqual(int(round(100.0 * combo['raw_total'] / HP)),
                                        combo['target']['hp_share'])
