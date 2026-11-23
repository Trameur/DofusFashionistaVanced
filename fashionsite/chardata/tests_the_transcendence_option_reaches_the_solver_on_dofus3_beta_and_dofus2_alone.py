# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The transcendence count reaches the solver's model options on dofus3, beta and dofus2 only, next to the Dracorune count when both are set."""
import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata import fashion_action
from chardata.coaching_view import create_build
from chardata.fashion_action import transcendence_model_option
from chardata.models import Char
from fashionistapulp.structure import set_current_game_version
from fashionistapulp.transcendence_terms import TRANSCENDENCE_VERSIONS


class TheSolverReceivesTheTranscendenceCountTests(SimpleTestCase):

    def test_the_count_is_passed_on_the_versions_that_offer_it(self):
        for version in TRANSCENDENCE_VERSIONS:
            with self.subTest(version=version):
                self.assertEqual({'transcendence': 3},
                                 transcendence_model_option({'transcendence': 3}, version))

    def test_nothing_is_passed_on_the_other_versions(self):
        for version in ('touch', 'retro', 'wakfu'):
            with self.subTest(version=version):
                self.assertEqual({}, transcendence_model_option({'transcendence': 3}, version))

    def test_nothing_is_passed_at_zero_or_without_the_key_or_with_junk(self):
        for options in ({}, {'transcendence': 0}, {'transcendence': -2}, {'transcendence': 'x'},
                        {'transcendence': True}):
            with self.subTest(options=options):
                self.assertEqual({}, transcendence_model_option(options, 'dofus3'))


class TheRealGetOptionsPathCarriesTheCountTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('transsolver', 'transsolver@test.local', 'pw-1234')

    def solver_options(self, version, stored):
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, 'Iop', 200, {'str'}, version)
        char.options = pickle.dumps(stored)
        char.save()
        with mock.patch.object(fashion_action, 'get_char_or_raise',
                               return_value=Char.objects.get(id=char.id)):
            return fashion_action.get_options(None, char.id)

    def test_get_options_carries_the_count_on_the_versions_that_offer_it(self):
        for version in TRANSCENDENCE_VERSIONS:
            with self.subTest(version=version):
                options = self.solver_options(version, {'transcendence': 3})
                self.assertEqual(3, options['transcendence'])

    def test_get_options_carries_no_count_on_touch_and_retro(self):
        for version in ('touch', 'retro'):
            with self.subTest(version=version):
                options = self.solver_options(version, {'transcendence': 3})
                self.assertNotIn('transcendence', options)

    def test_get_options_gives_the_model_both_counts_on_the_beta(self):
        options = self.solver_options('beta', {'transcendence': 2, 'dracorunes': 4})
        self.assertEqual(2, options['transcendence'])
        self.assertEqual(4, options['dracorunes'])
