# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Without a target, every hit value, turn key and payload field is the one the panel had before targets."""
import json
from unittest import mock

from django.test import SimpleTestCase

import chardata.spell_combo as spell_combo
from chardata import spells_view
from chardata.spell_combo import (_average, _turn_key, castable_spells, final_multiplier,
                                  get_damage_spells_for_version, row_value)
from fashionistapulp.dofus_constants import calculate_damage
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'touchbeta', 'retro')

FIELDS = {'ap_available', 'ap_used', 'buff_note', 'can_push', 'casts', 'conditional',
          'crit_failure_note', 'item_effects_note', 'later', 'later_total', 'melee_note',
          'pushback', 'rank_note', 'total', 'without_buffs_note'}


def _stats(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30,
                       'cridam': 25, 'ch': 45, 'ap': 11, 'mp': 5, 'hp': 3900,
                       'final': 5}.items():
        if key in stats:
            stats[key] = value
    return stats


def _classes(version):
    return sorted(name for name in get_damage_spells_for_version(version) if name != 'default')


def _in_version(test, version):
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


class ARowWithoutATargetTests(SimpleTestCase):

    def test_every_row_of_every_class_is_worth_the_mean_the_panel_always_took(self):
        for version in VERSIONS:
            _in_version(self, version)
            stats = _stats(version)
            multiplier = final_multiplier(stats)
            for char_class in _classes(version):
                for castable in castable_spells(char_class, 200, version):
                    for critical, faces in ((False, castable.plain_alternatives),
                                            (True, castable.crit_alternatives)):
                        for rows in faces or []:
                            rows = [row for row in rows
                                    if not isinstance(row, spell_combo.HpShare)]
                            with self.subTest(version=version, spell=castable.name,
                                              critical=critical):
                                self.assertEqual(
                                    _average(calculate_damage(rows, stats, critical,
                                                              castable.is_spell)) * multiplier,
                                    row_value(rows, stats, critical, castable.is_spell,
                                              multiplier))


class ATurnKeyWithoutATargetTests(SimpleTestCase):

    def test_no_target_part_enters_the_key_and_the_default_is_no_target(self):
        for version in VERSIONS:
            _in_version(self, version)
            stats = _stats(version)
            spells = castable_spells(_classes(version)[0], 200, version)
            added = []
            real_add = spell_combo._TurnKey.add

            def watched(key, part):
                added.append(part)
                return real_add(key, part)

            with mock.patch.object(spell_combo._TurnKey, 'add', watched):
                key = _turn_key(stats, spells, 11, False, None, version, False, 200)
            with self.subTest(version=version):
                self.assertEqual(key, _turn_key(stats, spells, 11, False, None, version, False,
                                                200, None))
                self.assertFalse([part for part in added
                                  if isinstance(part, tuple) and part and part[0] == 'target'])


class APayloadWithoutATargetTests(SimpleTestCase):

    def _combo(self, version, char_class, **kwargs):
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
            return spells_view._best_combo(char, solution, version, **kwargs)

    def test_the_payload_keeps_its_fields_and_equals_an_explicit_no_target(self):
        for version in VERSIONS:
            _in_version(self, version)
            char_class = _classes(version)[0]
            combo = self._combo(version, char_class)
            with self.subTest(version=version):
                self.assertIsNotNone(combo)
                self.assertEqual(FIELDS, set(combo))
                self.assertEqual(json.dumps(combo, sort_keys=True),
                                 json.dumps(self._combo(version, char_class, target=None),
                                            sort_keys=True))
