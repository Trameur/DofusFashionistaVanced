# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A positive whole number of runes reaches the solver; anything else counts as none."""

import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from chardata import fashion_action
from chardata.models import Char
from chardata.options import get_options
from fashionistapulp import dracorunes

INVALID = (-1, True, False, None, '2', 2.5, [2])


class TheRuneCountOfTheOptionsTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('runes-count', 'c@x.test', 'pw-42-solid')

    def build(self, options, version='beta'):
        return Char.objects.create(
            name='Runes', char_name='runes', char_class='Iop', char_build='build', level=200,
            minimum_stats=pickle.dumps({}), minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(options),
            inclusions=pickle.dumps({}), exclusions=pickle.dumps([]),
            owner=self.owner, link_shared=False, game_version=version)

    def model_options(self, char):
        with mock.patch.object(fashion_action, 'get_char_or_raise', return_value=char):
            return fashion_action.get_options(None, char.id)

    def test_the_solver_gets_the_count_on_a_version_with_a_runes_file(self):
        self.assertIsNotNone(dracorunes.load_runes('beta'))
        for count in (1, 3):
            with self.subTest(count=count):
                options = self.model_options(self.build({'dracorunes': count}))
                self.assertEqual(count, options['dracorunes'])

    def test_an_invalid_count_reaches_the_solver_as_none(self):
        for count in INVALID + (0,):
            with self.subTest(count=count):
                options = self.model_options(self.build({'dracorunes': count}))
                self.assertNotIn('dracorunes', options)

    def test_the_build_options_read_an_invalid_count_as_zero(self):
        for count in INVALID:
            with self.subTest(count=count):
                self.assertEqual(0, get_options(self.build({'dracorunes': count}))['dracorunes'])

    def test_the_build_options_keep_a_valid_count(self):
        self.assertEqual(4, get_options(self.build({'dracorunes': 4}))['dracorunes'])

    def test_the_build_options_of_a_build_that_never_set_it_have_no_count(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertNotIn('dracorunes', get_options(self.build({}, version)))
