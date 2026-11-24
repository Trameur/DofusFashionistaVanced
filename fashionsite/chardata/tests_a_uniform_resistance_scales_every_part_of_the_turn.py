# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a target whose every resistance is p, each value of the turn is its raw value times (100 - p) / 100, a push excepted."""
import re

from django.core.cache import caches
from django.test import SimpleTestCase

from chardata.spell_combo import (best_turn, castable_spells, combat_ap, conditional_extras,
                                  delayed_damage, final_multiplier,
                                  get_damage_spells_for_version, late_taken_back)
from chardata.spells_view import _burst_total, _without_buffs_note
from chardata.targets import Target
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta')
PERCENTS = (50, -100)
STATS = {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30, 'cridam': 25,
         'ch': 45, 'ap': 11, 'mp': 5, 'hp': 3900, 'heals': 20}


def _stats(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in STATS.items():
        if key in stats:
            stats[key] = value
    return stats


def _uniform(version, percent):
    return Target(version=version, kind='monster', ref=('m', 1, 1), level=200, hp=10000,
                  percent=(percent,) * 5, is_player=False, label='a monster')


def _classes(version):
    return sorted(name for name in get_damage_spells_for_version(version) if name != 'default')


def _numbers(text):
    return [int(digits) for digits in re.findall(r'\d+', text)]


class AUniformResistanceScalesTheTurnTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _near(self, expected, found, delta=None):
        self.assertAlmostEqual(expected, found,
                               delta=delta or 1e-6 * max(1.0, abs(expected)))

    def test_the_turn_its_late_damage_its_extras_and_its_burst_total_scale_with_the_resistance(self):
        notes = 0
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            ap = combat_ap(stats['ap'], version)
            for char_class in _classes(version):
                spells = castable_spells(char_class, 200, version)
                for percent in PERCENTS:
                    target = _uniform(version, percent)
                    scale = (100 - percent) / 100.0
                    with self.subTest(version=version, char_class=char_class, percent=percent):
                        notes += self._check(stats, spells, ap, version, target, scale)
        self.assertGreater(notes, 0)

    def _check(self, stats, spells, ap, version, target, scale):
        raw_total, raw_order = best_turn(stats, spells, ap, game_version=version,
                                         caster_level=200)
        total, order = best_turn(stats, spells, ap, game_version=version, caster_level=200,
                                 target=target)
        self.assertEqual([name for name, _damage in raw_order],
                         [name for name, _damage in order])
        self._near(raw_total * scale, total)
        for crit in (False, True):
            self._near(best_turn(stats, spells, ap, crit=crit, game_version=version,
                                 caster_level=200)[0] * scale,
                       best_turn(stats, spells, ap, crit=crit, game_version=version,
                                 caster_level=200, target=target)[0])
        raw_late = delayed_damage(stats, spells, raw_order, game_version=version)
        late = delayed_damage(stats, spells, raw_order, game_version=version, target=target)
        self.assertEqual(set(raw_late), set(late))
        for name, damage in raw_late.items():
            self._near(damage * scale, late[name])
        for crit in (False, True):
            raw_extras = conditional_extras(stats, spells, raw_order, crit=crit,
                                            game_version=version, caster_level=200)
            extras = conditional_extras(stats, spells, raw_order, crit=crit,
                                        game_version=version, caster_level=200, target=target)
            self.assertEqual(len(raw_extras), len(extras))
            for (name, trigger, damage), (_name, _trigger, found) in zip(raw_extras, extras):
                self._near(damage if trigger.startswith('pushback into') else damage * scale,
                           found)
        raw_burst = _burst_total(stats, spells, raw_order, {}, version)
        self._near(raw_burst * scale, _burst_total(stats, spells, order, {}, version, target), 1)
        raw_note = _without_buffs_note(stats, spells, raw_order, ap, {}, version, False, 200,
                                       raw_burst)
        note = _without_buffs_note(stats, spells, order, ap, {}, version, False, 200,
                                   raw_burst * scale, target)
        self.assertEqual(bool(raw_note), bool(note))
        if raw_note:
            for raw_number, number in zip(_numbers(raw_note), _numbers(note)):
                self.assertLessEqual(abs(raw_number * scale - number), 1)
            return 1
        return 0

    def _castables(self, version, wanted):
        return [castable for char_class in _classes(version)
                for castable in castable_spells(char_class, 200, version) if wanted(castable)]

    def test_a_spell_armed_by_its_own_cast_adds_its_later_cast_on_the_target_scale(self):
        found = 0
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            target = _uniform(version, 50)
            for castable in self._castables(version, lambda spell: any(
                    trigger == 'cast_two_turns_later'
                    for _row, trigger in getattr(spell, 'waiting_plain', None) or ())):
                order = [(castable.name, 0.0)]
                raw = conditional_extras(stats, [castable], order, game_version=version,
                                         caster_level=200)
                on = conditional_extras(stats, [castable], order, game_version=version,
                                        caster_level=200, target=target)
                found += 1
                with self.subTest(version=version, spell=castable.name):
                    self.assertEqual([('cast_two_turns_later', damage > 0) for _n, _t, damage in raw],
                                     [(trigger, damage > 0) for _n, trigger, damage in on])
                    self.assertTrue(raw)
                    for (_n, _t, damage), (_name, _trigger, found_damage) in zip(raw, on):
                        self._near(damage * 0.5, found_damage)
        self.assertGreater(found, 0)

    def test_a_growing_spell_takes_back_its_late_damage_on_the_target_scale(self):
        found = 0
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            multiplier = final_multiplier(stats)
            target = _uniform(version, 50)
            for castable in self._castables(version, lambda spell: getattr(
                    spell, 'recasts', None) and getattr(spell, 'late_by_effect', None)):
                for crit in (False, True):
                    raw = late_taken_back(castable, 1, stats, multiplier, crit, version)
                    on = late_taken_back(castable, 1, stats, multiplier, crit, version, target)
                    found += 1
                    with self.subTest(version=version, spell=castable.name, crit=crit):
                        self.assertGreater(raw, 0)
                        self._near(raw * 0.5, on)
                order = [(castable.name, 0.0)] * 2
                raw_late = delayed_damage(stats, [castable], order, game_version=version)
                late = delayed_damage(stats, [castable], order, game_version=version,
                                      target=target)
                with self.subTest(version=version, spell=castable.name, kind='later'):
                    self._near(raw_late[castable.name] * 0.5, late[castable.name])
        self.assertGreater(found, 0)
