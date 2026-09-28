# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A worn seal changes its spell by the amount Ankama's item gives."""

import json
import os
import pickle

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from chardata.models import Char
from chardata.solution import get_solution
from chardata.spell_modifiers import modified_cast, worn_spell_modifiers
from chardata.spell_reference import reference_by_spell_id
from chardata.tests_a_touch_build_saved_before_the_seals_still_loads import (
    _OPTIONS, sixteen_slot_minimal)
from fashionistapulp.structure import get_structure, set_current_game_version

_RAW_ITEMS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper', 'touch_raw', 'Items_fr.json')

_POWER_SEAL = 19017
_COOLDOWN_EFFECT = 286


class TheIopPowerSealTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('touch')
        structure = get_structure('touch')
        with open(_RAW_ITEMS, encoding='utf-8') as handle:
            raw = json.load(handle)[str(_POWER_SEAL)]
        (effect,) = [effect for effect in raw['possibleEffects']
                     if effect['effectId'] == _COOLDOWN_EFFECT]
        self.spell_id = effect['diceNum']
        self.shortened_by = effect['value']
        self.seal = structure.get_item_by_ankama_id(_POWER_SEAL)
        minimal = sixteen_slot_minimal(structure)
        minimal.item_per_slot['emblem1'] = self.seal.id
        self.owner = User.objects.create_user('power-seal', 'ps@test.local',
                                              'pw-42-solid')
        self.client.force_login(self.owner)
        self.char = Char.objects.create(
            name='Power seal', char_name='', char_class='Iop', char_build='',
            level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(dict(_OPTIONS)),
            inclusions=b'', exclusions=b'', owner=self.owner, link_shared=False,
            game_version='touch', minimal_solution=pickle.dumps(minimal))

    def test_it_shortens_the_power_cooldown_by_the_raw_value(self):
        modifiers = worn_spell_modifiers(get_solution(self.char), 'touch')
        self.assertIn(self.spell_id, modifiers)
        cooldowns = reference_by_spell_id('touch', 'Iop')[self.spell_id]['cooldown']
        for rank, cooldown in enumerate(cooldowns, start=1):
            with self.subTest(rank=rank):
                _cost, _per_turn, _per_target, after = modified_cast(
                    None, None, None, cooldown, modifiers[self.spell_id])
                self.assertEqual(max(0, cooldown - self.shortened_by), after)

    def test_the_spells_page_names_the_seal_on_its_spell(self):
        page = self.client.get('/touch/spells/%d/' % self.char.id)
        self.assertEqual(200, page.status_code)
        self.assertIn('%s: ' % self.seal.name, page.content.decode('utf-8'))

    def test_the_item_card_says_which_class_and_spell_rank(self):
        page = self.client.get('/fr/touch/solution/%d/' % self.char.id)
        self.assertEqual(200, page.status_code)
        html = page.content.decode('utf-8')
        spell = reference_by_spell_id('touch', 'Iop')[self.spell_id]
        self.assertIn('Classe : Iop', html)
        self.assertIn('Le sort %s doit être niveau 6' % spell['name']['fr'],
                      html)
