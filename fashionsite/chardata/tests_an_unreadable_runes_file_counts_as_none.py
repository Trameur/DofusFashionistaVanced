# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A runes file that cannot be read means no runes file to the cache key, the build options and the model alike."""

import os
import shutil
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from chardata import fashion_action
from chardata.dracorune_fixtures import NOT_ASKED, SmallModel, piece, real_input
from fashionistapulp import dracorunes
from fashionistapulp.structure import set_current_game_version

VERSION = 'beta'
UNREADABLE = {
    'cut short': b'{"source_tag": "x", "runes": [',
    'not an object': b'[]',
    'not utf-8': b'{"source_tag": "\xff"}',
}


class AnUnreadableRunesFileCountsAsNoneTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version(VERSION)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.hat = piece('Hat', {'str': 40})

    def unreadable(self, content):
        with open(os.path.join(self.folder, '%s.json' % VERSION), 'wb') as handle:
            handle.write(content)
        return mock.patch.object(dracorunes, 'DEFAULT_FOLDER', self.folder)

    def test_the_key_is_the_key_without_runes(self):
        expected = (real_input(NOT_ASKED).cache_key(), hash(real_input(NOT_ASKED)))
        for label, content in UNREADABLE.items():
            with self.subTest(label), self.unreadable(content), \
                    self.assertLogs('fashionistapulp.model', 'ERROR'):
                self.assertEqual(expected, (real_input(2).cache_key(), hash(real_input(2))))

    def test_the_build_options_ask_for_no_rune(self):
        for label, content in UNREADABLE.items():
            with self.subTest(label), self.unreadable(content), \
                    self.assertLogs('fashionistapulp.model', 'ERROR'):
                self.assertEqual({}, fashion_action.dracorune_model_option({'dracorunes': 2},
                                                                          VERSION))

    def test_the_model_offers_no_rune(self):
        for label, content in UNREADABLE.items():
            with self.subTest(label), self.unreadable(content), \
                    self.assertLogs('fashionistapulp.model', 'ERROR'):
                self.assertEqual({}, SmallModel([self.hat]).dracorune_candidates)
