# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Only the owner writes a build's weapon element, by POST with CSRF, and the build's cache moves on."""
import pickle
import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase

from chardata.models import Char, CharBaseStats
from chardata.util import _char_cache_epoch_key
from fashionistapulp import weapon_forge
from fashionistapulp.dofus_constants import STATS_NAMES, WATER
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

_KUKRI_KURA = 8932
_MINERS_PICK = 497
_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': set()}


def _url(char, version='dofus3'):
    prefix = '' if version == 'dofus3' else '/%s' % version
    return '%s/setweaponforge/%d/' % (prefix, char.id)


class TheWeaponForgeEndpointTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('forger', 'forger@test.local', 'pw-42-solid')
        self.other = User.objects.create_user('stranger', 'stranger@test.local', 'pw-42-solid')

    def _char(self, version='dofus3', ankama_id=_KUKRI_KURA, level=200, **fields):
        set_current_game_version(version)
        weapon = get_structure(version).get_item_by_ankama_id(ankama_id)
        entry = {'char_class': 'Iop', 'char_level': level, 'origin': 'generated',
                 'options': dict(_OPTIONS), 'base_stats_by_attr': dict(_BASE),
                 'locked_equips': {}}
        char = Char.objects.create(
            name='Forged', char_name='Forged', char_class='Iop', char_build='', level=level,
            minimum_stats=b'', minimum_crits=b'', stats_weight=pickle.dumps({}),
            options=pickle.dumps(dict(_OPTIONS)), inclusions=b'', exclusions=b'',
            owner=self.owner, link_shared=False, game_version=version,
            minimal_solution=pickle.dumps(ModelResultMinimal({'weapon': weapon.id}, entry, {})),
            **fields)
        for stat, _key in STATS_NAMES:
            CharBaseStats.objects.create(char=char, stat=stat, total_value=0, scrolled_value=0)
        set_current_game_version('dofus3')
        return char

    def _stored(self, char):
        return Char.objects.get(pk=char.pk).weapon_forge

    def test_the_owner_writes_each_kind_and_the_cache_moves_on(self):
        char = self._char()
        self.client.force_login(self.owner)
        steps = (({'damage': 'water:strong'}, {'damage': (WATER, 'strong')}),
                 ({'heal': 'none'}, {'damage': (WATER, 'strong'), 'heal': None}),
                 ({'damage': 'fire:weak'}, {'damage': ('fire', 'weak'), 'heal': None}),
                 ({'heal': ''}, {'damage': ('fire', 'weak')}),
                 ({'damage': ''}, {}))
        for posted, expected in steps:
            with self.subTest(posted=posted):
                before = cache.get(_char_cache_epoch_key(char.id))
                response = self.client.post(_url(char), posted)
                self.assertEqual(200, response.status_code)
                self.assertEqual(weapon_forge.write_choice(expected), self._stored(char))
                self.assertNotEqual(before, cache.get(_char_cache_epoch_key(char.id)))
        self.assertEqual('', self._stored(char))

    def test_a_write_does_not_move_the_build_date(self):
        char = self._char()
        before = Char.objects.get(pk=char.pk).modified_time
        self.client.force_login(self.owner)
        self.client.post(_url(char), {'damage': 'water:strong'})
        self.assertEqual(before, Char.objects.get(pk=char.pk).modified_time)

    def test_someone_else_or_a_visitor_is_refused(self):
        char = self._char()
        self.client.force_login(self.other)
        self.assertEqual(403, self.client.post(_url(char), {'damage': 'water:strong'}).status_code)
        self.client.logout()
        self.assertEqual(403, self.client.post(_url(char), {'damage': 'water:strong'}).status_code)
        self.assertEqual('', self._stored(char))

    def test_a_get_writes_nothing(self):
        char = self._char()
        self.client.force_login(self.owner)
        self.assertEqual(405, self.client.get(_url(char), {'damage': 'water:strong'}).status_code)
        self.assertEqual('', self._stored(char))

    def test_a_post_without_the_csrf_token_is_refused(self):
        char = self._char()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(403, client.post(_url(char), {'damage': 'water:strong'}).status_code)
        self.assertEqual('', self._stored(char))

    def test_what_the_version_does_not_sell_is_refused(self):
        dofus2 = self._char('dofus2')
        retro = self._char('retro')
        dofus3 = self._char()
        self.client.force_login(self.owner)
        for char, version, posted in ((dofus3, 'dofus3', {'damage': 'fire:medium'}),
                                      (dofus3, 'dofus3', {'damage': 'neut:strong'}),
                                      (dofus3, 'dofus3', {'damage': 'fire:strong',
                                                          'heal': 'lava:strong'}),
                                      (dofus2, 'dofus2', {'heal': 'fire:strong'}),
                                      (retro, 'retro', {'damage': 'fire:weak'}),
                                      (retro, 'retro', {'steal': 'none'})):
            with self.subTest(version=version, posted=posted):
                response = self.client.post(_url(char, version), posted)
                self.assertEqual(400, response.status_code)
                self.assertEqual('', self._stored(char))

    def test_a_build_of_another_version_is_not_found_here(self):
        char = self._char('dofus2')
        self.client.force_login(self.owner)
        self.assertEqual(404, self.client.post(_url(char), {'damage': 'fire:strong'}).status_code)
        self.assertEqual('', self._stored(char))

    def test_a_level_one_build_writes_its_choice(self):
        char = self._char('touch', _MINERS_PICK, level=1)
        self.client.force_login(self.owner)
        response = self.client.post(_url(char, 'touch'), {'damage': 'water:weak'})
        self.assertEqual(200, response.status_code)
        self.assertEqual(weapon_forge.write_choice({'damage': (WATER, 'weak')}),
                         self._stored(char))


class TheBuildPageShowsTheControlToItsOwnerTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        self.owner = User.objects.create_user('forger', 'forger@test.local', 'pw-42-solid')

    def test_the_stored_choice_is_selected_on_the_build_page(self):
        set_current_game_version('dofus3')
        weapon = get_structure('dofus3').get_item_by_ankama_id(_KUKRI_KURA)
        entry = {'char_class': 'Iop', 'char_level': 200, 'origin': 'generated',
                 'options': dict(_OPTIONS, dofusnotforchar=[]),
                 'base_stats_by_attr': dict(_BASE), 'locked_equips': {}}
        char = Char.objects.create(
            name='Forged', char_name='Forged', char_class='Iop', char_build='', level=200,
            minimum_stats=b'', minimum_crits=b'', stats_weight=pickle.dumps({}),
            options=pickle.dumps(dict(_OPTIONS)), inclusions=b'', exclusions=b'',
            owner=self.owner, link_shared=False, game_version='dofus3',
            minimal_solution=pickle.dumps(ModelResultMinimal({'weapon': weapon.id}, entry, {})),
            weapon_forge=weapon_forge.write_choice({'damage': (WATER, 'weak')}))
        for stat, _key in STATS_NAMES:
            CharBaseStats.objects.create(char=char, stat=stat, total_value=0, scrolled_value=0)
        self.client.force_login(self.owner)
        page = self.client.get('/solution/%d/' % char.id,
                               HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertIn('weapon-forge-damage', page)
        selected = re.findall(r'<option[^>]*\bselected\b[^>]*>', page)
        self.assertTrue(any(re.search(r'value="?water:weak"?', option) for option in selected))
        self.assertIn('/setweaponforge/', page)
        name = weapon_forge.item_name('dofus3', 'damage', WATER, 'weak', 'en')
        self.assertIn('%s: Water, 10%%' % name, page)
