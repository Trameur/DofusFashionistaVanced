# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build target enters the turn cache key by the values the damage reads: editing the build changes the key, editing it back restores it."""
import inspect
from unittest import mock

from django.core.cache import caches
from django.test import SimpleTestCase

from chardata.spell_combo import _turn_key, best_turn, castable_spells
from chardata.targets import ELEMENTS, build_target
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
FIRST = {'earthresper': 20, 'fireresper': 10, 'earthres': 12, 'crires': 5, 'hp': 3000}
EDITED = dict(FIRST, earthresper=31)


def _stats(version, values=None):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update(values or {'str': 600, 'pow': 80, 'dam': 20, 'ap': 11})
    return stats


def _target(version, values, name='the same build'):
    char = mock.Mock(pk=42, char_class='Iop', level=200)
    char.name = name
    solution = mock.Mock()
    solution.get_stats_total.return_value = _stats(version, values)
    return build_target(char, solution, version, 'b42')


class ABuildTargetCacheKeyTests(SimpleTestCase):

    def setUp(self):
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.addCleanup(set_current_game_version, 'dofus3')

    def _key(self, version, target):
        stats = _stats(version)
        spells = castable_spells('Iop', 200, version)
        return _turn_key(stats, spells, 11, False, None, version, False, 200, target)

    def test_a_then_b_then_a_gives_two_keys_and_the_first_comes_back(self):
        for version in VERSIONS:
            set_current_game_version(version)
            first = self._key(version, _target(version, FIRST))
            edited = self._key(version, _target(version, EDITED))
            back = self._key(version, _target(version, FIRST))
            with self.subTest(version=version):
                self.assertNotEqual(first, edited)
                self.assertEqual(first, back)

    def test_the_key_reads_values_not_the_name_or_the_link(self):
        version = 'dofus3'
        set_current_game_version(version)
        target = _target(version, FIRST)
        renamed = _target(version, FIRST, name='renamed')
        self.assertEqual(self._key(version, target), self._key(version, renamed))
        parts = target.key_parts()
        self.assertIn(tuple(FIRST.get('%sresper' % element, 0) for element in ELEMENTS), parts)
        self.assertIn(tuple(FIRST.get('%sres' % element, 0) for element in ELEMENTS), parts)
        self.assertNotIn('b42', parts)
        self.assertNotIn('the same build', parts)
        for part in parts:
            self.assertIn(type(part), (str, int, bool, tuple, type(None)))

    def test_the_edited_build_is_searched_again_and_the_first_is_read_back(self):
        version = 'dofus3'
        set_current_game_version(version)
        stats = _stats(version)
        spells = castable_spells('Iop', 200, version)
        searches = []
        import chardata.spell_combo as spell_combo
        real = spell_combo._search_best_turn

        def counted(*args, **kwargs):
            searches.append(inspect.signature(real).bind(*args, **kwargs).arguments['target'].key_parts())
            return real(*args, **kwargs)

        with mock.patch.object(spell_combo, '_search_best_turn', counted):
            for values in (FIRST, EDITED, FIRST):
                best_turn(stats, spells, 11, game_version=version, caster_level=200,
                          target=_target(version, values))
        self.assertEqual(2, len(searches))
        self.assertNotEqual(searches[0], searches[1])
