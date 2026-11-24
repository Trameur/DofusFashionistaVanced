# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every in-game reading of a version replays through its record within the record's tolerance per hit."""
import json
import os

from django.test import SimpleTestCase

from chardata.spell_combo import (HpShare, castable_spells, final_multiplier, landed_index,
                                  row_value)
from chardata.targets import TARGET_VERSIONS, _monster_index, read_target
from fashionistapulp.combat.rules import load_rules
from fashionistapulp.dofus_constants import calculate_damage
from fashionistapulp.structure import get_structure, set_current_game_version

READINGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'combat_readings')
KEYS = {'id', 'client_tag', 'date', 'source', 'case', 'attacker', 'spell_id', 'spell_level',
        'row', 'critical', 'distance', 'target', 'observed'}


def readings(version):
    with open(os.path.join(READINGS, '%s.json' % version), encoding='utf-8') as handle:
        return json.load(handle)


def replayed(entry, version):
    """The mean hit the shipped row value gives for one reading, on the face the caster lands."""
    attacker = entry['attacker']
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update(attacker['stats'])
    castable = next(spell for spell in castable_spells(
        attacker['class'], attacker['level'], version)
        if getattr(spell, 'spell_id', None) == entry['spell_id'])
    critical = entry['critical']
    faces = (castable.crit_alternatives if critical and castable.crit
             else castable.plain_alternatives)
    multiplier = final_multiplier(stats)
    landed = landed_index(castable, [
        row_value([row for row in rows if not isinstance(row, HpShare)], stats, critical,
                  castable.is_spell, multiplier) for rows in faces])
    target = read_target(version, 'm%d.%d' % (entry['target']['monster_id'],
                                             entry['target']['grade']))[0]
    return row_value([faces[landed][entry['row']]], stats, critical, castable.is_spell,
                     multiplier, target)


def off_by(entry, version):
    return abs(replayed(entry, version)
               - (entry['observed']['min'] + entry['observed']['max']) / 2.0)


class TheReadingsReplayTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_each_version_has_its_own_readings_file_in_the_format(self):
        for version in TARGET_VERSIONS:
            entries = readings(version)
            with self.subTest(version=version):
                self.assertIsInstance(entries, list)
                for entry in entries:
                    self.assertEqual(KEYS, set(entry))
                    self.assertTrue(entry['id'].startswith(version + '-'))
                self.assertEqual(len(entries), len({entry['id'] for entry in entries}))

    def test_every_reading_replays_within_the_tolerance(self):
        for version in TARGET_VERSIONS:
            set_current_game_version(version)
            tolerance = load_rules(version).tolerance_per_hit
            for entry in readings(version):
                with self.subTest(version=version, reading=entry['id']):
                    self.assertLessEqual(off_by(entry, version), tolerance)

    def test_a_reading_off_by_more_than_the_tolerance_is_caught(self):
        version = 'dofus3'
        set_current_game_version(version)
        tolerance = load_rules(version).tolerance_per_hit
        castable = next(spell for spell in castable_spells('Cra', 200, version)
                        if spell.plain_alternatives and spell.plain_alternatives[0]
                        and calculate_damage(spell.plain_alternatives[0][:1], {
                            stat.key: 0 for stat in get_structure(version).get_stats_list()},
                            False, spell.is_spell))
        entry = {'attacker': {'class': 'Cra', 'level': 200, 'stats': {'str': 100, 'agi': 100,
                                                                      'int': 100, 'cha': 100}},
                 'spell_id': castable.spell_id, 'row': 0, 'critical': False}
        monster_id, _names, grades = _monster_index(version)[0][0]
        entry['target'] = {'monster_id': monster_id, 'grade': grades[0][0]}
        value = replayed(entry, version)
        entry['observed'] = {'min': value, 'max': value}
        self.assertLessEqual(off_by(entry, version), tolerance)
        entry['observed'] = {'min': value + tolerance + 1, 'max': value + tolerance + 1}
        self.assertGreater(off_by(entry, version), tolerance)
