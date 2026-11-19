# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Leaving the Dracorune count at zero writes nothing: the options blob and the solver options stay as they were."""
import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import fashion_action
from chardata.coaching_view import create_build
from chardata.models import Char
from chardata.setup_options import GROUP_FIELD, apply_option_groups
from fashionistapulp.structure import set_current_game_version


class AnUntouchedDracoruneOptionLeavesNoTraceTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('dracozero', 'dracozero@test.local', 'pw-1234')
        self.client.force_login(self.owner)
        set_current_game_version('beta')
        request = RequestFactory().post('/')
        request.user = self.owner
        self.char = create_build(request, 'Iop', 200, {'str'}, 'beta')

    def blob(self):
        return Char.objects.get(id=self.char.id).options

    def solver_options(self):
        with mock.patch.object(fashion_action, 'get_char_or_raise',
                               return_value=Char.objects.get(id=self.char.id)):
            return fashion_action.get_options(None, self.char.id)

    def post_options(self, extra):
        return self.client.post('/beta/optionspost/%d/' % self.char.id,
                                dict({'ap_exo': 'no', 'mp_exo': 'no'}, **extra))

    def setup_post(self, fields):
        request = RequestFactory().post('/beta/setup/', fields)
        request.user = self.owner
        apply_option_groups(request, self.char)

    def test_a_post_without_the_field_and_a_post_of_zero_write_the_same_blob(self):
        self.post_options({})
        without = self.blob()
        self.post_options({'dracorunes': '0'})
        self.assertEqual(without, self.blob())
        self.assertNotIn('dracorunes', pickle.loads(self.blob()))

    def test_the_solver_options_are_identical_with_the_field_at_zero(self):
        self.post_options({})
        without = self.solver_options()
        self.post_options({'dracorunes': '0'})
        self.assertEqual(without, self.solver_options())
        self.assertNotIn('dracorunes', without)

    def test_the_setup_page_leaves_the_blob_alone_when_the_group_is_not_posted(self):
        before = self.blob()
        self.setup_post({'dracorunes': '0'})
        self.assertEqual(before, self.blob())

    def test_the_setup_group_at_zero_stores_nothing(self):
        before = self.blob()
        self.setup_post({GROUP_FIELD: 'dracorunes', 'dracorunes': '0'})
        self.assertEqual(before, self.blob())

    def test_a_build_that_had_runes_can_go_back_to_zero(self):
        self.post_options({'dracorunes': '2'})
        self.post_options({'dracorunes': '0'})
        self.assertEqual(0, pickle.loads(self.blob())['dracorunes'])
        self.assertNotIn('dracorunes', self.solver_options())
