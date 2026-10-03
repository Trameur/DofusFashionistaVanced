# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Retro options page and wizard save how many pieces carry each exo, kept between 0 and the forgeable slots."""
import json

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from chardata.coaching_view import create_build
from chardata.models import Char
from chardata.options import get_options
from fashionistapulp.exo_options import forgeable_slot_count
from fashionistapulp.structure import get_structure, set_current_game_version

_OPTIONS = ('ap_exo', 'mp_exo', 'range_exo')


class TheRetroPagesSaveAnExoCountTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('exocount', 'exocount@test.local', 'pw-1234')
        self.client.force_login(self.owner)

    def _char(self, version):
        set_current_game_version(version)
        request = RequestFactory().post('/')
        request.user = self.owner
        return create_build(request, 'Iop', 200, {'str'}, version)

    def _saved(self, char):
        options = get_options(Char.objects.get(id=char.id))
        return tuple(options.get(option) for option in _OPTIONS)

    def test_the_options_page_stores_the_count_clamped_to_the_slots(self):
        char = self._char('retro')
        slots = forgeable_slot_count(get_structure('retro'))
        self.client.post('/retro/optionspost/%d/' % char.id,
                         {'ap_exo': '3', 'mp_exo': '99', 'range_exo': '-2'})
        self.assertEqual((3, slots, 0), self._saved(char))

    def test_the_reply_the_page_redraws_from_carries_the_stored_count(self):
        char = self._char('retro')
        slots = forgeable_slot_count(get_structure('retro'))
        response = self.client.post('/retro/optionspost/%d/' % char.id,
                                    {'ap_exo': '99', 'mp_exo': '1.5', 'range_exo': '2'})
        reply = json.loads(response.content)
        self.assertEqual((slots, 0, 2), tuple(reply[option] for option in _OPTIONS))
        page = self.client.get('/retro/options/%d/' % char.id).content.decode('utf-8')
        self.assertIn('optionsInit(savedOptions)', page)

    def test_a_word_where_a_count_belongs_stores_none(self):
        char = self._char('retro')
        self.client.post('/retro/optionspost/%d/' % char.id,
                         {'ap_exo': 'gelano', 'mp_exo': '', 'range_exo': '2'})
        self.assertEqual((0, 0, 2), self._saved(char))

    def test_the_wizard_keeps_the_range_count_it_does_not_show(self):
        char = self._char('retro')
        self.client.post('/retro/optionspost/%d/' % char.id,
                         {'ap_exo': '1', 'mp_exo': '1', 'range_exo': '2'})
        self.client.post('/retro/wizardpost/%d/' % char.id, {'ap_exo': '2', 'mp_exo': '0'})
        self.assertEqual((2, 0, 2), self._saved(char))

    def test_dofus3_still_stores_yes_no_and_gelano(self):
        char = self._char('dofus3')
        self.client.post('/optionspost/%d/' % char.id,
                         {'ap_exo': 'yes', 'mp_exo': 'gelano', 'range_exo': 'no'})
        self.assertEqual((True, 'gelano', False), self._saved(char))
        self.client.post('/optionspost/%d/' % char.id,
                         {'ap_exo': '3', 'mp_exo': 'yes', 'range_exo': 'yes'})
        self.assertEqual((False, True, True), self._saved(char))
