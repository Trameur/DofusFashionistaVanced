# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The item picker's weapon popup tests the element key, not its translated name, and names the potion."""
import os
import pickle
import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import translation
from django.utils.html import escape

from chardata.item_exchange import _get_weapon_info
from chardata.models import Char, CharBaseStats
from fashionistapulp import weapon_forge
from fashionistapulp.dofus_constants import NEUTRAL, STATS_NAMES, WATER
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

_KUKRI_KURA = 8932
_HUNTING_KNIFE = 1934
_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': []}
_POPUP = os.path.join(os.path.dirname(__file__), 'static', 'chardata', 'solution_popup.js')


class ThePopupReadsTheElementKeyTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('dofus3')
        self.structure = get_structure('dofus3')
        self.owner = User.objects.create_user('picker', 'picker@test.local', 'pw-42-solid')

    def _char(self, choice, level=200):
        weapon = self.structure.get_item_by_ankama_id(_KUKRI_KURA)
        entry = {'char_class': 'Iop', 'char_level': level, 'origin': 'generated',
                 'options': dict(_OPTIONS), 'base_stats_by_attr': dict(_BASE),
                 'locked_equips': {}}
        char = Char.objects.create(
            name='Picker', char_name='Picker', char_class='Iop', char_build='', level=level,
            minimum_stats=b'', minimum_crits=b'', stats_weight=pickle.dumps({}),
            options=pickle.dumps(dict(_OPTIONS)), inclusions=b'', exclusions=b'',
            owner=self.owner, link_shared=False, game_version='dofus3',
            minimal_solution=pickle.dumps(ModelResultMinimal({'weapon': weapon.id}, entry, {})),
            weapon_forge=weapon_forge.write_choice(choice))
        for stat, _key in STATS_NAMES:
            CharBaseStats.objects.create(char=char, stat=stat, total_value=0, scrolled_value=0)
        return char

    def test_a_turned_weapon_names_its_potion_in_the_page_language(self):
        for level, ankama_id in ((200, _KUKRI_KURA), (1, _HUNTING_KNIFE)):
            with self.subTest(level=level):
                char = self._char({'damage': (WATER, 'strong')}, level)
                with translation.override('fr'):
                    info = _get_weapon_info(
                        self.structure.get_item_by_ankama_id(ankama_id), char)
                self.assertEqual(WATER, info['element_key'])
                self.assertEqual('Eau', info['element'])
                self.assertEqual(escape(weapon_forge.item_name('dofus3', 'damage', WATER,
                                                               'strong', 'fr')),
                                 info['forge_item'])

    def test_a_neutral_weapon_has_the_neutral_key_whatever_the_language(self):
        char = self._char({'damage': None})
        for language, word in (('en', 'Neutral'), ('fr', 'Neutre')):
            with self.subTest(language=language):
                with translation.override(language):
                    info = _get_weapon_info(
                        self.structure.get_item_by_ankama_id(_KUKRI_KURA), char)
                self.assertEqual(NEUTRAL, info['element_key'])
                self.assertEqual(word, info['element'])
                self.assertIsNone(info['forge_item'])

    def test_the_script_tests_the_key_and_never_the_translated_name(self):
        with open(_POPUP, encoding='utf-8') as handle:
            script = handle.read()
        self.assertIn(".element_key != 'neut'", script)
        self.assertEqual([], re.findall(r"\]\.element\s*!=\s*'neut'", script))
        self.assertIn('%(item)s (%(element)s)', script)
