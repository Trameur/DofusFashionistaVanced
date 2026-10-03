# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Retro asks how many pieces carry each exo and drops "Only Gelano"; the other versions keep their radios."""
import re

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.coaching_view import create_build
from fashionistapulp.exo_options import forgeable_slot_count
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_WEIGHTS = {'vit': 1, 'str': 3, 'pow': 2, 'ap': 1000, 'mp': 800, 'range': 100}
_OPTIONS = {'ap_exo': True, 'mp_exo': 'gelano', 'range_exo': False, 'dofus': True,
            'trophies': True, 'dragoturkey': True, 'seemyool': True,
            'rhineetle': True, 'prysmaradite': False, 'dofuses': {},
            'dofusnotforchar': set()}


def _exo_inputs(page, option):
    return re.findall(r'<input\b[^>]*\bname="%s"[^>]*>' % option, page)


class TheExoFieldsFollowTheVersionTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('gelanopage', 'gp@test.local', 'pw-1234')
        self.client.force_login(self.owner)

    def _pages(self, version):
        set_current_game_version(version)
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, 'Iop', 200, {'str'}, version)
        prefix = '' if version == 'dofus3' else '/%s' % version
        pages = {}
        for page in ('options', 'wizard'):
            response = self.client.get('%s/%s/%d/' % (prefix, page, char.id))
            self.assertEqual(200, response.status_code)
            pages[page] = response.content.decode('utf-8')
        return pages

    def test_retro_asks_a_number_of_pieces_and_offers_no_gelano(self):
        slots = forgeable_slot_count(get_structure('retro'))
        for page, body in self._pages('retro').items():
            with self.subTest(page=page):
                self.assertNotIn('value="gelano"', body)
                options = ('ap_exo', 'mp_exo', 'range_exo') if page == 'options' else ('ap_exo', 'mp_exo')
                for option in options:
                    fields = _exo_inputs(body, option)
                    self.assertEqual(1, len(fields), option)
                    self.assertIn('type="number"', fields[0])
                    self.assertIn('min="0"', fields[0])
                    self.assertIn('max="%d"' % slots, fields[0])
                self.assertIn('%d pieces at most' % slots, body)

    def test_dofus3_keeps_the_yes_no_radios_and_only_gelano(self):
        for page, body in self._pages('dofus3').items():
            with self.subTest(page=page):
                self.assertIn('value="gelano"', body)
                self.assertIn('Only Gelano', body)
                for option in ('ap_exo', 'mp_exo'):
                    fields = _exo_inputs(body, option)
                    self.assertTrue(fields)
                    self.assertTrue(all('type="radio"' in field for field in fields), option)
                self.assertNotIn('pieces at most', body)


class AnOldRetroGelanoBuildStillWearsTheGelanoTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')
        self.structure = get_structure('retro')

    def test_the_gelano_option_still_lets_gelano_1_be_worn(self):
        gelano = self.structure.get_item_by_name('Gelano (#1)')
        model = Model()
        model.setup(ModelInput(200, dict(_BASE), {}, {'ring1': gelano.id}, set(),
                               dict(_WEIGHTS), dict(_OPTIONS), 'Iop', 995))
        model.run(1)
        minimal = model.get_result_minimal()
        result = model_result_from_minimal(minimal)
        worn = [item.id for item in result.item_list if item.item_added]
        self.assertIn(gelano.id, worn)
        self.assertEqual(0, minimal.exo_assumed['mp'])
