# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build that allows no rune, or sits on a version without a runes file, keeps its options and its cache key."""

import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from chardata import fashion_action
from chardata.models import Char
from fashionistapulp import dracorunes
from fashionistapulp.model import ModelInput
from fashionistapulp.structure import set_current_game_version

PINNED_DIGESTS = {'dofus3': -5977905965642940188, 'beta': 3996759981717353406}
OPTIONS = {'ap_exo': True, 'range_exo': False, 'mp_exo': True, 'dofus': True,
           'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
           'prysmaradite': True, 'shields': True, 'trophies': True}
BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 100, 'Intelligence': 0, 'Chance': 0,
        'Agility': 0}
NO_RUNE = (0, -1, -3, True, False, None, '2', 2.0, [2])
NOT_SET = object()


def pinned_input(runes_allowed=NOT_SET):
    options = dict(OPTIONS)
    if runes_allowed is not NOT_SET:
        options['dracorunes'] = runes_allowed
    return ModelInput(200, dict(BASE),
                      {'AP': 11, 'MP': 6, 'adv_mins': {'Power + Strength': 300}},
                      {'Ring': 12345}, [678, 91011],
                      {'str': 1, 'pow': 1, 'earthdam': 4, 'vit': 1},
                      options, 'Iop', 995, ['Shield'], {},
                      crit_hinges=((40, 1),))


def no_runes_file(version, folder=None):
    return None


class TheCacheKeyOfABuildWithoutRunesTests(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_a_build_that_never_set_the_option_keeps_its_digest(self):
        for version, digest in PINNED_DIGESTS.items():
            set_current_game_version(version)
            with self.subTest(version=version):
                self.assertEqual(digest, pinned_input().cache_key())

    def test_no_rune_allowed_keeps_the_digest_and_the_hash(self):
        for version, digest in PINNED_DIGESTS.items():
            set_current_game_version(version)
            for runes_allowed in NO_RUNE:
                with self.subTest(version=version, runes_allowed=runes_allowed):
                    model_input = pinned_input(runes_allowed)
                    self.assertEqual(digest, model_input.cache_key())
                    self.assertEqual(hash(pinned_input()), hash(model_input))

    def test_runes_on_a_version_without_a_runes_file_keep_the_digest_and_the_hash(self):
        with mock.patch.object(dracorunes, 'load_runes', no_runes_file):
            for version, digest in PINNED_DIGESTS.items():
                set_current_game_version(version)
                with self.subTest(version=version):
                    model_input = pinned_input(2)
                    self.assertEqual(digest, model_input.cache_key())
                    self.assertEqual(hash(pinned_input()), hash(model_input))

    def test_the_real_versions_without_a_runes_file_keep_the_digest(self):
        for version, digest in PINNED_DIGESTS.items():
            if dracorunes.load_runes(version) is not None:
                continue
            set_current_game_version(version)
            with self.subTest(version=version):
                self.assertEqual(digest, pinned_input(2).cache_key())

    def test_runes_allowed_on_a_version_with_a_runes_file_change_the_key(self):
        set_current_game_version('beta')
        self.assertIsNotNone(dracorunes.load_runes('beta'))
        self.assertNotEqual(PINNED_DIGESTS['beta'], pinned_input(2).cache_key())
        self.assertNotEqual(hash(pinned_input()), hash(pinned_input(2)))
        self.assertNotEqual(pinned_input(1).cache_key(), pinned_input(2).cache_key())

    def test_reading_the_key_leaves_the_options_as_they_were(self):
        set_current_game_version('beta')
        for runes_allowed in (0, 2):
            model_input = pinned_input(runes_allowed)
            model_input.cache_key()
            hash(model_input)
            self.assertEqual(dict(OPTIONS, dracorunes=runes_allowed), model_input.options)

    def test_an_input_pickled_before_runes_still_gives_its_digest(self):
        set_current_game_version('dofus3')
        model_input = pinned_input()
        for name in ('modifier_values', 'modifier_overlaps', 'item_terms', 'gap'):
            model_input.__dict__.pop(name, None)
        restored = pickle.loads(pickle.dumps(model_input))
        self.assertEqual(PINNED_DIGESTS['dofus3'], restored.cache_key())


class TheModelOptionsOfABuildWithoutRunesTests(TestCase):

    BEFORE = {'ap_exo': False, 'range_exo': False, 'mp_exo': False, 'dofus': True,
              'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
              'prysmaradite': False, 'shields': True, 'trophies': True}

    def setUp(self):
        self.owner = User.objects.create_user('runes-off', 'r@x.test', 'pw-42-solid')

    def model_options(self, options, version):
        char = Char.objects.create(
            name='Runes', char_name='runes', char_class='Iop', char_build='build', level=200,
            minimum_stats=pickle.dumps({}), minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(options),
            inclusions=pickle.dumps({}), exclusions=pickle.dumps([]),
            owner=self.owner, link_shared=False, game_version=version)
        with mock.patch.object(fashion_action, 'get_char_or_raise', return_value=char):
            return fashion_action.get_options(None, char.id)

    def test_a_build_that_never_set_the_option_gets_the_options_of_before(self):
        for version in PINNED_DIGESTS:
            with self.subTest(version=version):
                self.assertEqual(self.BEFORE, self.model_options({}, version))

    def test_no_rune_allowed_adds_nothing(self):
        for version in PINNED_DIGESTS:
            for runes_allowed in NO_RUNE:
                with self.subTest(version=version, runes_allowed=runes_allowed):
                    self.assertEqual(self.BEFORE,
                                     self.model_options({'dracorunes': runes_allowed}, version))

    def test_runes_on_a_version_without_a_runes_file_add_nothing(self):
        with mock.patch.object(dracorunes, 'load_runes', no_runes_file):
            for version in PINNED_DIGESTS:
                with self.subTest(version=version):
                    self.assertEqual(self.BEFORE,
                                     self.model_options({'dracorunes': 2}, version))
