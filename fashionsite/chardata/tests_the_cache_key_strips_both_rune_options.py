# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The cache key and hash carry the Dracorune and transcendence options only when they are on and backed by a runes file."""

import os
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import model as model_module, transcendence
from fashionistapulp.model import ModelInput
from fashionistapulp.structure import set_current_game_version

OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False, 'dofus': True,
           'trophies': True, 'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
           'prysmaradite': False, 'shields': True}
PINNED = {'dofus3': -2991674296762793853, 'beta': -1446696439977293434,
          'dofus2': 3223225811400985701, 'retro': -202701968795513239,
          'touch': 6158392160761255377}
THREE = ('dofus3', 'beta', 'dofus2')


def key_input(**extra):
    return ModelInput(200, {'Vitality': 0, 'Strength': 0, 'AP': 7, 'MP': 3},
                      {'AP': 11, 'adv_mins': {'Power + Strength': 300}}, {}, [],
                      {'str': 1, 'vit': 1}, dict(OPTIONS, **extra), 'Iop', 995, [], {},
                      crit_hinges=((40, 1),))


def keys(**extra):
    built = key_input(**extra)
    return built.cache_key(), hash(built)


class TheCacheKeyStripsBothRuneOptionsTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.addCleanup(transcendence.clear_cache)
        transcendence.clear_cache()

    def on(self, version):
        set_current_game_version(version)

    def test_a_build_without_either_option_keeps_its_key_of_before(self):
        for version, pinned in PINNED.items():
            with self.subTest(version=version):
                self.on(version)
                self.assertEqual(pinned, key_input().cache_key())

    def test_an_off_transcendence_value_is_the_option_left_out(self):
        for version in PINNED:
            self.on(version)
            for value in (0, False, None, True, -1, '2', 2.0):
                with self.subTest(version=version, value=value):
                    self.assertEqual(keys(), keys(transcendence=value))

    def test_an_off_transcendence_value_keeps_the_dracorune_key(self):
        self.on('beta')
        for value in (0, False):
            with self.subTest(value=value):
                self.assertEqual(keys(dracorunes=2), keys(dracorunes=2, transcendence=value))
                locks = {'dracorune_locks': {'hat': 'element:str>int'}}
                self.assertEqual(keys(dracorunes=2, **locks),
                                 keys(dracorunes=2, transcendence=value, **locks))

    def test_an_off_dracorune_value_keeps_the_transcendence_key(self):
        self.on('beta')
        self.assertEqual(keys(transcendence=2), keys(transcendence=2, dracorunes=0))
        self.assertNotEqual(keys(), keys(transcendence=2, dracorunes=0))

    def test_the_count_changes_the_key_on_the_three_versions(self):
        for version in THREE:
            self.on(version)
            found = [keys(transcendence=count) for count in (0, 2, 3)]
            with self.subTest(version=version):
                for first in range(3):
                    for second in range(first + 1, 3):
                        self.assertNotEqual(found[first][0], found[second][0])
                        self.assertNotEqual(found[first][1], found[second][1])

    def test_both_options_on_differ_from_each_alone(self):
        self.on('beta')
        both = keys(dracorunes=2, transcendence=2)
        for other in (keys(), keys(dracorunes=2), keys(transcendence=2)):
            self.assertNotEqual(both[0], other[0])
            self.assertNotEqual(both[1], other[1])

    def test_the_order_of_the_options_does_not_change_the_key(self):
        self.on('beta')
        self.assertEqual(keys(dracorunes=2, transcendence=3), keys(transcendence=3, dracorunes=2))

    def test_outside_the_three_versions_the_option_changes_nothing(self):
        self.on('beta')
        runes = [dict(rune) for rune in transcendence.load_runes('beta')]
        for version in ('retro', 'touch'):
            self.on(version)
            with mock.patch.object(transcendence, 'load_runes', lambda *args, **kwargs: runes):
                with self.subTest(version=version):
                    self.assertEqual(PINNED[version], key_input(transcendence=2).cache_key())
                    self.assertEqual(keys()[1], keys(transcendence=2)[1])

    def test_a_version_without_runes_ignores_the_option(self):
        self.on('beta')
        with mock.patch.object(transcendence, 'load_runes', lambda *args, **kwargs: []):
            self.assertEqual(PINNED['beta'], key_input(transcendence=2).cache_key())

    def test_an_unreadable_rune_file_counts_as_none(self):
        self.on('beta')
        broken = (('cut short', b'{"runes": [{"id": 1'), ('empty', b'[]'),
                  ('not utf-8', bytes([0x81, 0xff, 0xfe])))
        for label, content in broken:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as folder:
                with open(os.path.join(folder, 'beta.json'), 'wb') as handle:
                    handle.write(content)
                transcendence.clear_cache()
                with mock.patch.object(transcendence, 'DEFAULT_FOLDER', folder):
                    with self.assertLogs('fashionistapulp.model', 'ERROR'):
                        self.assertEqual(PINNED['beta'], key_input(transcendence=2).cache_key())
                transcendence.clear_cache()

    def test_a_change_in_the_runes_changes_the_key(self):
        self.on('beta')
        runes = [dict(rune) for rune in transcendence.load_runes('beta')]
        runes[0]['bonus'] += 1
        with mock.patch.object(transcendence, 'load_runes', lambda *args, **kwargs: runes):
            changed = keys(transcendence=2)
        self.assertNotEqual(keys(transcendence=2)[0], changed[0])
        self.assertNotEqual(keys(transcendence=2)[1], changed[1])

    def test_the_option_on_key_carries_the_revision(self):
        self.on('beta')
        part = key_input(transcendence=2)._rune_keys()[1][-1]
        self.assertEqual(model_module.TRANSCENDENCE_KEY_REVISION, part[-1])
        self.assertEqual(['transcendence', 2], [part[0], part[1]])
        first = keys(transcendence=2)
        with mock.patch.object(model_module, 'TRANSCENDENCE_KEY_REVISION',
                               model_module.TRANSCENDENCE_KEY_REVISION + 1):
            second = keys(transcendence=2)
            self.assertEqual(PINNED['beta'], key_input().cache_key())
            self.assertEqual(PINNED['beta'], key_input(transcendence=0).cache_key())
        self.assertNotEqual(first[0], second[0])
        self.assertNotEqual(first[1], second[1])

    def test_the_revision_leaves_the_dracorune_key_alone(self):
        self.on('beta')
        before = keys(dracorunes=2)
        with mock.patch.object(model_module, 'TRANSCENDENCE_KEY_REVISION',
                               model_module.TRANSCENDENCE_KEY_REVISION + 1):
            self.assertEqual(before, keys(dracorunes=2))
