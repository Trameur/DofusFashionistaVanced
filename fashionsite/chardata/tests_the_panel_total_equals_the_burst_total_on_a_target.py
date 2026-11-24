# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a target the panel total is the burst total of its order, a poison meets its own element and stays out, a summon-only spell is absent."""
from unittest import mock

from django.core.cache import caches
from django.test import SimpleTestCase

from chardata import spells_view
from chardata.spell_combo import (HpShare, best_turn, castable_spells, combat_ap,
                                  delayed_damage, get_damage_spells_for_version,
                                  summon_only_spells)
from chardata.spells_view import _burst_total
from chardata.targets import ELEMENTS, Target
from fashionistapulp.combat.rules import load_rules
from fashionistapulp.dofus_constants import calculate_damage
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
STATS = {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30, 'cridam': 25,
         'ch': 45, 'ap': 11, 'hp': 3900}
PERCENTS = ((-30, 15, 15, 100, 0), (17, 16, 29, 25, 14), (100, 100, 100, 100, 100))


def _stats(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in STATS.items():
        if key in stats:
            stats[key] = value
    return stats


def _target(version, percent):
    return Target(version=version, kind='monster', ref=('m', 1, 1), level=200, hp=10000,
                  percent=tuple(percent), is_player=False, label='a monster')


def _classes(version):
    return sorted(name for name in get_damage_spells_for_version(version) if name != 'default')


class ThePanelTotalOnATargetTests(SimpleTestCase):

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

    def test_the_payload_total_is_the_burst_total_of_its_order_on_the_target(self):
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            ap = combat_ap(stats['ap'], version)
            summons = set(summon_only_spells(version))
            for char_class in _classes(version):
                spells = castable_spells(char_class, 200, version)
                for percent in PERCENTS:
                    target = _target(version, percent)
                    combo = self._combo(version, char_class, spells, target)
                    _total, order = best_turn(stats, spells, ap, standing={},
                                              game_version=version, caster_level=200,
                                              target=target)
                    with self.subTest(version=version, char_class=char_class, percent=percent):
                        self.assertEqual(_burst_total(stats, spells, order, {}, version, target),
                                         combo['total'])
                        self.assertEqual(target.token(), combo['target']['token'])
                        by_name = {spell.name: spell for spell in spells}
                        self.assertFalse([name for name, _damage in order
                                          if getattr(by_name[name], 'spell_id', None)
                                          in summons])

    def test_a_poison_meets_its_own_element_and_stays_out_of_the_total(self):
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            tolerance = load_rules(version).tolerance_per_hit
            checked = 0
            for char_class in _classes(version):
                for castable in castable_spells(char_class, 200, version):
                    late = getattr(castable, 'late_by_effect', None) or {}
                    faces = castable.plain_alternatives or []
                    if not late or len(faces) != 1 or getattr(castable, 'crit_rate', 0):
                        continue
                    rows = [row for row in faces[0] if id(row) in late
                            and not isinstance(row, HpShare)]
                    found = {damage.element for damage in calculate_damage(
                        rows, stats, False, castable.is_spell)}
                    if len(found) != 1:
                        continue
                    element = next(iter(found))
                    order = [(castable.name, 0.0)]
                    raw = delayed_damage(stats, [castable], order, game_version=version)
                    if not raw.get(castable.name):
                        continue
                    weak = _target(version, [-50 if other == element else 100
                                             for other in ELEMENTS])
                    immune = _target(version, [100 if other == element else -50
                                               for other in ELEMENTS])
                    on_weak = delayed_damage(stats, [castable], order, game_version=version,
                                             target=weak)
                    on_immune = delayed_damage(stats, [castable], order, game_version=version,
                                               target=immune)
                    checked += 1
                    with self.subTest(version=version, spell=castable.name):
                        self.assertLessEqual(abs(on_weak[castable.name]
                                                 - raw[castable.name] * 3 / 2),
                                             tolerance * len(rows))
                        self.assertFalse(on_immune.get(castable.name))
                        turn, cast_order = best_turn(stats, [castable], castable.cost,
                                                     game_version=version, caster_level=200,
                                                     target=weak)
                        self.assertEqual(int(round(turn - on_weak[castable.name])),
                                         _burst_total(stats, [castable], cast_order, None,
                                                      version, weak))
            self.assertTrue(checked)
