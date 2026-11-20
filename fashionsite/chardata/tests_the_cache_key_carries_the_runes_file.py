# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Another runes file gives a build that allows runes another cache key, and a build that allows none the same one."""

import json
import os
import shutil
import tempfile
from copy import deepcopy
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp import dracorunes
from fashionistapulp.structure import set_current_game_version

from chardata.dracorune_fixtures import NOT_ASKED, real_input

VERSION = 'beta'


def other_tag(runes):
    runes['source_tag'] = '%s.other' % runes.get('source_tag')


def other_keep(runes):
    rune = next(rune for rune in runes['runes'] if rune['kind'] == 'power')
    rune['keep'] = rune['keep'] / 2


class TheCacheKeyReadsTheRunesFileTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version(VERSION)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        with open(os.path.join(dracorunes.DEFAULT_FOLDER, '%s.json' % VERSION),
                  encoding='utf-8') as handle:
            self.runes = json.load(handle)

    def keys(self, runes, runes_allowed, indent=1):
        with open(os.path.join(self.folder, '%s.json' % VERSION), 'w',
                  encoding='utf-8') as handle:
            json.dump(runes, handle, indent=indent)
        with mock.patch.object(dracorunes, 'DEFAULT_FOLDER', self.folder):
            model_input = real_input(runes_allowed)
            return model_input.cache_key(), hash(model_input)

    def changed(self, change):
        runes = deepcopy(self.runes)
        change(runes)
        self.assertNotEqual(self.runes, runes)
        return runes

    def assert_both_differ(self, keys, others):
        self.assertNotEqual(keys[0], others[0])
        self.assertNotEqual(keys[1], others[1])

    def test_the_power_rune_has_a_keep_rate_to_change(self):
        self.assertTrue(any(rune['kind'] == 'power' and rune.get('keep')
                            for rune in self.runes['runes']))

    def test_another_source_tag_gives_another_key(self):
        for runes_allowed in (1, 2):
            with self.subTest(runes_allowed=runes_allowed):
                self.assert_both_differ(self.keys(self.runes, runes_allowed),
                                        self.keys(self.changed(other_tag), runes_allowed))

    def test_another_keep_rate_gives_another_key(self):
        for runes_allowed in (1, 2):
            with self.subTest(runes_allowed=runes_allowed):
                self.assert_both_differ(self.keys(self.runes, runes_allowed),
                                        self.keys(self.changed(other_keep), runes_allowed))

    def test_the_same_file_written_otherwise_gives_the_same_key(self):
        self.assertEqual(self.keys(self.runes, 2, indent=1),
                         self.keys(self.runes, 2, indent=None))

    def test_no_rune_allowed_gives_the_same_key_whatever_the_file(self):
        for runes_allowed in (NOT_ASKED, 0):
            with self.subTest(runes_allowed=runes_allowed):
                expected = self.keys(self.runes, NOT_ASKED)
                for change in (other_tag, other_keep):
                    self.assertEqual(expected, self.keys(self.changed(change), runes_allowed))
