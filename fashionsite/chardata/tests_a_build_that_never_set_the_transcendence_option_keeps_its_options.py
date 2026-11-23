# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Leaving the transcendence count at zero writes nothing: the options blob and the solver options stay as they were."""

from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import fashion_action
from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.models import Char
from fashionistapulp.structure import set_current_game_version


class AnUntouchedTranscendenceOptionLeavesNoTraceTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('transkeep', 'transkeep@test.local', 'pw-1234')
        self.client.force_login(self.owner)
        request = RequestFactory().post('/')
        request.user = self.owner
        self.char = create_build(request, 'Iop', 200, {'str'}, 'dofus3')

    def blob(self):
        return Char.objects.get(id=self.char.id).options

    def solver_options(self):
        with mock.patch.object(fashion_action, 'get_char_or_raise',
                               return_value=Char.objects.get(id=self.char.id)):
            return fashion_action.get_options(None, self.char.id)

    def post_options(self, extra):
        return self.client.post('/optionspost/%d/' % self.char.id,
                                dict({'ap_exo': 'no', 'mp_exo': 'no'}, **extra))

    def test_a_post_without_the_field_and_a_post_of_zero_write_the_same_blob(self):
        self.post_options({})
        without = self.blob()
        self.post_options({'transcendence': '0'})
        self.assertEqual(without, self.blob())
        self.assertNotIn('transcendence', read_char_blob(self.blob(), {}, 'options'))

    def test_the_model_options_carry_no_transcendence_key(self):
        self.post_options({})
        without = self.solver_options()
        self.post_options({'transcendence': '0'})
        self.assertEqual(without, self.solver_options())
        self.assertNotIn('transcendence', without)

    def test_a_build_that_had_runes_can_go_back_to_zero(self):
        self.post_options({'transcendence': '2'})
        self.post_options({'transcendence': '0'})
        self.assertEqual(0, read_char_blob(self.blob(), {}, 'options')['transcendence'])
        self.assertNotIn('transcendence', self.solver_options())
