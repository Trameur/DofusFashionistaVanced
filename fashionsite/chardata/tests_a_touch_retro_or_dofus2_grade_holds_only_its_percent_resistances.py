# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch, Retro or Dofus 2 grade holds its five percent resistances only: one at 100 reads immune and takes 0, nothing else is said missing, Retro names its roll approximation."""
import math
from unittest import mock

from django.core.cache import caches
from django.test import SimpleTestCase

from chardata import spells_view, targets
from chardata.spell_combo import HpShare, best_turn, castable_spells, row_values
from chardata.spells_view import _RETRO_ROLLS_NOTE, _burst_total
from chardata.targets import ELEMENTS, FIRE, PERCENT_COLUMNS, Target, read_target
from fashionistapulp.combat.rules import load_rules
from fashionistapulp.dofus_constants import calculate_damage, percent_resist_cap
from fashionistapulp.structure import get_structure, set_current_game_version

FIRE_IMMUNE = {'touch': 'm83.1', 'retro': 'm83.1', 'dofus2': 'm194.1'}
STATS = {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30, 'cridam': 25,
         'ch': 45, 'ap': 11, 'hp': 3900}


def _stats(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in STATS.items():
        if key in stats:
            stats[key] = value
    return stats


def _one_element_spells(version, stats, char_class):
    """{element: [castable]} of the spells with one plain face hitting in one element only."""
    found = {}
    for castable in castable_spells(char_class, 200, version):
        faces = castable.plain_alternatives or []
        if len(faces) != 1 or not castable.cost or getattr(castable, 'late_by_effect', None):
            continue
        rows = [row for row in faces[0] if not isinstance(row, HpShare)]
        elements = {damage.element for damage in calculate_damage(
            rows, stats, False, castable.is_spell) if not damage.heals}
        if len(elements) == 1:
            found.setdefault(next(iter(elements)), []).append(castable)
    return found


class AGradeOfTouchRetroOrDofus2Tests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _combo(self, version, char_class, target):
        spells = castable_spells(char_class, 200, version)
        char = mock.Mock(char_class=char_class, level=200)
        solution = mock.Mock(item_list=[])
        solution.get_stats_total.return_value = _stats(version)
        with mock.patch('chardata.spell_combo.castable_spells', return_value=spells), \
                mock.patch('chardata.spell_combo.buffs_in_force', return_value={}), \
                mock.patch('chardata.spell_combo.stacks_in_force', return_value={}), \
                mock.patch('chardata.temporix_mode.solution_uses_temporix', return_value=False), \
                mock.patch.object(spells_view, 'worn_spell_modifiers', return_value={}), \
                mock.patch.object(spells_view, '_weapon_castable', return_value=None):
            return spells, spells_view._best_combo(char, solution, version, target=target,
                                                   note_without_buffs=False)

    def test_a_grade_at_a_hundred_reads_immune_uncapped_and_its_element_takes_nothing(self):
        for version, token in FIRE_IMMUNE.items():
            set_current_game_version(version)
            stats = _stats(version)
            target, refused = read_target(version, token)
            with self.subTest(version=version):
                self.assertEqual('', refused)
                self.assertEqual(version, target.version)
                self.assertGreaterEqual(target.percent_of(FIRE), 100)
                self.assertGreater(target.percent_of(FIRE), percent_resist_cap(version))
                self.assertIn(FIRE, target.immune_elements())
                spells, combo = self._combo(version, 'Cra', target)
                fire = [row for row in combo['target']['resistances']
                        if row['element'] == FIRE][0]
                self.assertTrue(fire['immune'])
                self.assertGreaterEqual(fire['percent'], 100)
                _total, order = best_turn(stats, spells, 11, standing={}, game_version=version,
                                          caster_level=200, target=target)
                self.assertEqual(_burst_total(stats, spells, order, {}, version, target),
                                 combo['total'])
                by_element = _one_element_spells(version, stats, 'Cra')
                self.assertTrue(by_element.get(FIRE))
                for castable in by_element[FIRE]:
                    self.assertGreater(best_turn(stats, [castable], castable.cost,
                                                 game_version=version, caster_level=200)[0], 0)
                    self.assertEqual(0, best_turn(stats, [castable], castable.cost,
                                                  game_version=version, caster_level=200,
                                                  target=target)[0])
                others = [castable for element, castables in by_element.items()
                          if element != FIRE and not target.percent_of(element) >= 100
                          for castable in castables]
                self.assertTrue(others)
                for castable in others:
                    self.assertGreater(best_turn(stats, [castable], castable.cost,
                                                 game_version=version, caster_level=200,
                                                 target=target)[0], 0)

    def test_nothing_but_the_tolerance_the_summons_and_on_retro_the_rolls_is_noted(self):
        for version, token in FIRE_IMMUNE.items():
            set_current_game_version(version)
            target, _refused = read_target(version, token)
            _spells, combo = self._combo(version, 'Iop', target)
            rules = load_rules(version)
            notes = combo['not_counted']
            with self.subTest(version=version):
                self.assertEqual([], list(target.unknown))
                self.assertIsNone(target.flat)
                self.assertIsNone(target.crit_flat)
                self.assertIsNone(target.push_flat)
                self.assertEqual([None] * len(ELEMENTS),
                                 [row['flat'] for row in combo['target']['resistances']])
                self.assertIsNone(combo['target']['critical_resistance'])
                self.assertIsNone(combo['target']['pushback_resistance'])
                self.assertEqual(list(rules.applied_order()),
                                 [stage['stage'] for stage in combo['stages']['counted']])
                self.assertTrue(rules.tolerance_per_hit)
                self.assertIn(str(rules.tolerance_per_hit), combo['stages']['note'])
                expected = ([str(_RETRO_ROLLS_NOTE)] if version == 'retro' else []) + [
                    str(spells_view._SUMMONS_NOTE)]
                self.assertEqual(expected, notes)
                self.assertEqual(version == 'retro', bool(combo['crit_failure_note']))

    def test_the_retro_roll_note_is_translated_in_every_language(self):
        from django.utils import translation
        seen = set()
        for language in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(language):
                seen.add(str(_RETRO_ROLLS_NOTE))
        self.assertEqual(5, len(seen))

    def test_a_missing_percent_hp_or_level_reads_unknown_not_zero(self):
        for version, token in FIRE_IMMUNE.items():
            set_current_game_version(version)
            _letter, monster_id, grade = ('m',) + tuple(int(x) for x in token[1:].split('.'))
            row, names = targets._grade_row(version, monster_id, grade)
            blank = dict(row, level=None, life_points=None, **{PERCENT_COLUMNS[0]: None})
            with mock.patch.object(targets, '_grade_row', return_value=(blank, names)):
                target, _refused = read_target(version, token)
            with self.subTest(version=version):
                self.assertEqual({'level', 'life_points', PERCENT_COLUMNS[0]},
                                 set(target.unknown))
                self.assertIsNone(target.percent[0])

    def test_dofus2_floors_every_roll_after_its_percent_and_not_the_mean(self):
        set_current_game_version('dofus2')
        stats = _stats('dofus2')
        target = Target(version='dofus2', kind='monster', ref=('m', 1, 1), level=200, hp=10000,
                        percent=(33,) * len(ELEMENTS), is_player=False, label='a monster')
        seen = 0
        for castable in castable_spells('Cra', 200, 'dofus2'):
            for row in (castable.plain_alternatives or [[]])[0]:
                if isinstance(row, HpShare) or int(row.max_dam) - int(row.min_dam) < 4:
                    continue
                damage = calculate_damage([row], stats, False, castable.is_spell)
                if not damage or damage[0].heals:
                    continue
                low, high = damage[0].min_dam, damage[0].max_dam
                span = int(row.max_dam) - int(row.min_dam)
                rolls = [low + (high - low) * step / span for step in range(span + 1)]
                floored = sum(math.floor(roll * 67 / 100.0) for roll in rolls) / len(rolls)
                two_ends = ((low + high) / 2.0) * 0.67
                value = row_values([row], stats, False, castable.is_spell, 1.0, target)[1]
                if abs(floored - two_ends) < 0.1:
                    continue
                seen += 1
                self.assertAlmostEqual(floored, value, places=6)
                self.assertGreater(abs(value - two_ends), 0.05)
        self.assertGreater(seen, 0)
