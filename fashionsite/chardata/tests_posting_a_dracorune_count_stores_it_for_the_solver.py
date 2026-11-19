# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The count posted from the options page or the setup page is stored, clamped to the slots, and reaches the solver options."""
import pickle
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata import fashion_action
from chardata.coaching_view import create_build
from chardata.models import Char
from chardata.options import get_available_options, get_options
from chardata.setup_options import GROUP_FIELD, apply_option_groups, more_options_context
from fashionistapulp.structure import set_current_game_version


class PostingADracoruneCountTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('dracopost', 'dracopost@test.local', 'pw-1234')
        self.client.force_login(self.owner)
        set_current_game_version('beta')
        self.slots = get_available_options()['dracorune_slots']

    def build(self, version='beta'):
        set_current_game_version(version)
        request = RequestFactory().post('/')
        request.user = self.owner
        return create_build(request, 'Iop', 200, {'str'}, version)

    def stored(self, char):
        return get_options(Char.objects.get(id=char.id)).get('dracorunes')

    def solver_options(self, char):
        with mock.patch.object(fashion_action, 'get_char_or_raise',
                               return_value=Char.objects.get(id=char.id)):
            return fashion_action.get_options(None, char.id)

    def post(self, char, count, version='beta'):
        return self.client.post('/%s/optionspost/%d/' % (version, char.id), {'dracorunes': count})

    def test_a_posted_count_is_stored_and_the_solver_gets_it(self):
        char = self.build()
        self.post(char, '3')
        self.assertEqual(3, self.stored(char))
        self.assertEqual(3, self.solver_options(char)['dracorunes'])

    def test_the_reply_carries_the_stored_count(self):
        char = self.build()
        self.assertEqual(2, self.post(char, '2').json()['dracorunes'])

    def test_a_count_above_the_slots_is_clamped_to_them(self):
        char = self.build()
        self.post(char, str(self.slots + 50))
        self.assertEqual(self.slots, self.stored(char))

    def test_garbage_and_negative_counts_become_zero(self):
        char = self.build()
        for value in ('abc', '-3', '', '2.5', ' '):
            with self.subTest(value=value):
                self.post(char, '4')
                self.post(char, value)
                self.assertEqual(0, self.stored(char))
                self.assertNotIn('dracorunes', self.solver_options(char))

    def test_a_version_without_runes_ignores_the_field(self):
        char = self.build('dofus3')
        self.client.post('/optionspost/%d/' % char.id, {'dracorunes': '3'})
        self.assertIsNone(self.stored(char))
        self.assertNotIn('dracorunes', self.solver_options(char))

    def test_the_setup_group_stores_the_count_for_a_new_build(self):
        char = self.build()
        request = RequestFactory().post('/beta/setup/', {GROUP_FIELD: 'dracorunes',
                                                         'dracorunes': str(self.slots + 5)})
        request.user = self.owner
        apply_option_groups(request, char)
        self.assertEqual(self.slots, self.stored(char))

    def raw(self, char):
        return pickle.loads(Char.objects.get(id=char.id).options)

    def test_the_blob_itself_holds_the_clamped_count(self):
        char = self.build()
        self.post(char, str(self.slots + 50))
        self.assertEqual(self.slots, self.raw(char)['dracorunes'])
        self.post(char, '-3')
        self.assertEqual(0, self.raw(char)['dracorunes'])

    def test_the_setup_group_of_a_version_without_runes_stores_nothing(self):
        char = self.build('dofus3')
        before = Char.objects.get(id=char.id).options
        request = RequestFactory().post('/setup/', {GROUP_FIELD: 'dracorunes', 'dracorunes': '3'})
        request.user = self.owner
        apply_option_groups(request, char)
        self.assertEqual(before, Char.objects.get(id=char.id).options)

    def test_the_setup_section_offers_the_option_on_the_beta_alone(self):
        for version, offered in (('beta', True), ('dofus3', False)):
            with self.subTest(version=version):
                char = self.build(version)
                request = RequestFactory().get('/')
                request.user = self.owner
                more = more_options_context(request, char, version)
                self.assertEqual(offered, 'dracorunes' in more['defaults'])
                self.assertEqual(offered, any(name == 'dracorunes' for name, _keys in more['table']['groups']))
