# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A turn on a target is cached under a key naming the target's values and its record, never uncached."""
from unittest import mock

from django.core.cache import caches
from django.test import SimpleTestCase

import chardata.spell_combo as spell_combo
from chardata.spell_combo import _turn_key, best_turn, castable_spells
from chardata.targets import ELEMENTS, Target
from fashionistapulp.combat import rules as combat_rules
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta')


def _stats(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    for key, value in {'str': 450, 'agi': 480, 'int': 470, 'cha': 460, 'pow': 90, 'dam': 30,
                       'cridam': 25, 'ch': 45, 'hp': 3900}.items():
        if key in stats:
            stats[key] = value
    return stats


def _target(version, percent, label='a monster'):
    return Target(version=version, kind='monster', ref=('m', 1, 1), level=200, hp=10000,
                  percent=percent, is_player=False, label=label)


class TheTargetCacheKeyTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _key(self, version, target):
        return _turn_key(_stats(version), castable_spells('Cra', 200, version), 11, False,
                         None, version, False, 200, target)

    def _turn(self, version, target):
        """(turn, searches) of one best_turn on the target."""
        with mock.patch.object(spell_combo, '_search_best_turn',
                               wraps=spell_combo._search_best_turn) as searched:
            turn = best_turn(_stats(version), castable_spells('Cra', 200, version), 11,
                             game_version=version, caster_level=200, target=target)
        return turn, searched.call_count

    def test_a_target_key_is_made_and_differs_from_the_raw_key(self):
        for version in VERSIONS:
            set_current_game_version(version)
            on = self._key(version, _target(version, (0,) * len(ELEMENTS)))
            with self.subTest(version=version):
                self.assertIsNotNone(on)
                self.assertNotEqual(self._key(version, None), on)

    def test_one_resistance_apart_gives_two_keys_and_the_name_gives_none(self):
        for version in VERSIONS:
            set_current_game_version(version)
            base = (10, 20, 30, 40, 50)
            for index in range(len(ELEMENTS)):
                raised = tuple(value + (index == place) for place, value in enumerate(base))
                with self.subTest(version=version, element=ELEMENTS[index]):
                    self.assertNotEqual(self._key(version, _target(version, base)),
                                        self._key(version, _target(version, raised)))
            self.assertEqual(self._key(version, _target(version, base, 'one name')),
                             self._key(version, _target(version, base, 'another name')))

    def test_a_record_revision_enters_the_key(self):
        version = 'dofus3'
        set_current_game_version(version)
        target = _target(version, (10, 20, 30, 40, 50))
        before = self._key(version, target)
        record = combat_rules.read_record(combat_rules.record_path(version))
        record['revision'] += 1
        with mock.patch.dict(combat_rules._LOADED,
                             {version: combat_rules.RuleSet(record)}):
            self.assertNotEqual(before, self._key(version, target))

    def test_a_then_b_then_a_reads_a_from_the_cache(self):
        for version in VERSIONS:
            set_current_game_version(version)
            caches['best_turn'].clear()
            weak_earth = _target(version, (-50, 50, 50, 50, 50))
            weak_air = _target(version, (50, 50, 50, -50, 50))
            first, searches = self._turn(version, weak_earth)
            with self.subTest(version=version):
                self.assertEqual(1, searches)
                other, searches = self._turn(version, weak_air)
                self.assertEqual(1, searches)
                self.assertNotEqual(repr(first), repr(other))
                again, searches = self._turn(version, weak_earth)
                self.assertEqual(0, searches)
                self.assertEqual(repr(first), repr(again))

    def test_a_target_never_makes_the_key_fail(self):
        for version in VERSIONS:
            set_current_game_version(version)
            target = _target(version, (None, 20, -30, 100, 150))
            with mock.patch.object(spell_combo, '_turn_key',
                                   wraps=spell_combo._turn_key) as keyed:
                best_turn(_stats(version), castable_spells('Cra', 200, version), 11,
                          game_version=version, caster_level=200, target=target)
            with self.subTest(version=version):
                self.assertEqual(1, keyed.call_count)
                self.assertIsNotNone(self._key(version, target))
                self.assertIsNotNone(caches['best_turn'].get(self._key(version, target)))
