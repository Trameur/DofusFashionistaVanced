# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A posted transcendence count is held between zero and the slot count, and a junk value stores zero or nothing."""

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.models import Char
from chardata.options import get_available_options
from fashionistapulp.structure import set_current_game_version


class APostedTranscendenceCountIsClampedTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('transclamp', 'transclamp@test.local', 'pw-1234')
        self.client.force_login(self.owner)
        request = RequestFactory().post('/')
        request.user = self.owner
        self.char = create_build(request, 'Iop', 200, {'str'}, 'dofus3')
        self.slots = get_available_options()['transcendence_slots']

    def stored(self):
        return read_char_blob(Char.objects.get(id=self.char.id).options, {}, 'options')

    def post(self, value):
        self.client.post('/optionspost/%d/' % self.char.id,
                         {'ap_exo': 'no', 'mp_exo': 'no', 'transcendence': value})

    def test_a_count_above_the_slots_stores_the_slot_count(self):
        self.post(str(self.slots + 20))
        self.assertEqual(self.slots, self.stored()['transcendence'])

    def test_a_count_inside_the_range_is_stored_as_posted(self):
        self.post('3')
        self.assertEqual(3, self.stored()['transcendence'])

    def test_a_negative_count_on_a_new_build_stores_nothing(self):
        self.post('-4')
        self.assertNotIn('transcendence', self.stored())

    def test_junk_on_a_new_build_stores_nothing(self):
        self.post('abc')
        self.assertNotIn('transcendence', self.stored())

    def test_a_negative_or_junk_count_on_a_build_that_had_runes_stores_zero(self):
        for value in ('-4', 'abc', ''):
            with self.subTest(value=value):
                self.post('2')
                self.post(value)
                self.assertEqual(0, self.stored()['transcendence'])

    def test_a_version_that_does_not_offer_it_ignores_the_post(self):
        set_current_game_version('retro')
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, 'Iop', 200, {'str'}, 'retro')
        self.client.post('/retro/optionspost/%d/' % char.id,
                         {'ap_exo': 'no', 'mp_exo': 'no', 'transcendence': '3'})
        blob = Char.objects.get(id=char.id).options
        self.assertNotIn('transcendence', read_char_blob(blob, {}, 'options'))
