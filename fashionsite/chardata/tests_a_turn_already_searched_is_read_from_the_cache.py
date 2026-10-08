# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A turn already searched is read from the cache; any change to what the search reads searches again."""
import copy
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.core.cache import cache, caches
from django.test import SimpleTestCase, TestCase, override_settings

import chardata.spell_combo as spell_combo
from chardata.spell_combo import (WeaponCastable, best_turn, castable_spells,
                                  get_damage_spells_for_version)
from fashionistapulp.dofus_constants import NEUTRAL, DamageDigest
from fashionistapulp.structure import get_structure, set_current_game_version

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')


def _stats(version):
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update({'str': 400, 'agi': 900, 'pow': 100, 'dam': 40, 'ch': 30, 'pshdam': 20,
                  'hp': 4000})
    return stats


def _weapon():
    return WeaponCastable(SimpleNamespace(
        name='Test bow', ap=3, uses_per_turn=2, element_maged=None, crit_chance=10,
        non_crit_hits={NEUTRAL: [DamageDigest(20, 30, NEUTRAL)]},
        crit_hits={NEUTRAL: [DamageDigest(25, 35, NEUTRAL)]}))


def _classes(version):
    return sorted(name for name in get_damage_spells_for_version(version) if name != 'default')


class _Watched(object):

    def __init__(self, target, read):
        object.__setattr__(self, '_target', target)
        object.__setattr__(self, '_read', read)

    def __getattr__(self, name):
        self._read.add(name)
        return getattr(self._target, name)


class TheTurnCacheTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        caches['best_turn'].clear()
        self.addCleanup(caches['best_turn'].clear)
        self.stats = _stats('dofus3')
        self.spells = castable_spells('Cra', 200, 'dofus3') + [_weapon()]

    def _turn(self, stats=None, spells=None, ap=9, **kwargs):
        """(turn, searches) of one best_turn."""
        kwargs.setdefault('game_version', 'dofus3')
        kwargs.setdefault('caster_level', 200)
        stats = self.stats if stats is None else stats
        spells = self.spells if spells is None else spells
        with mock.patch.object(spell_combo, '_search_best_turn',
                               wraps=spell_combo._search_best_turn) as searched:
            turn = best_turn(stats, spells, ap, **kwargs)
        self.assertEqual(repr(spell_combo._search_best_turn(stats, spells, ap, **kwargs)),
                         repr(turn))
        return turn, searched.call_count

    def _changed(self, position, **fields):
        changed = copy.copy(self.spells[position])
        for name, value in fields.items():
            setattr(changed, name, value)
        return self.spells[:position] + [changed] + self.spells[position + 1:]

    def test_the_same_turn_again_is_not_searched_again(self):
        turn, searches = self._turn()
        self.assertEqual(1, searches)
        self.assertTrue(turn[1])
        rebuilt = castable_spells('Cra', 200, 'dofus3') + [_weapon()]
        again, searches = self._turn(spells=rebuilt)
        self.assertEqual(0, searches)
        self.assertEqual(repr(turn), repr(again))

    def test_a_change_to_anything_the_search_reads_searches_again(self):
        self._turn()
        hitting = next(index for index, spell in enumerate(self.spells)
                       if spell.is_spell and spell.alternatives)
        spell = self.spells[hitting]
        first_hit = spell.alternatives[0][0]
        raised = copy.copy(first_hit)
        raised.min_dam += 1
        alternatives = [[raised] + spell.alternatives[0][1:]] + spell.alternatives[1:]
        scaled = copy.copy(spell.spell)
        scaled.buff_scaling = {'stats': {'agi': {'base': 1}}}
        changes = {
            'a stat': dict(stats=dict(self.stats, agi=self.stats['agi'] + 1)),
            'the AP': dict(ap=10),
            'critical hits': dict(crit=True),
            'pushback': dict(pushback=True),
            'the caster level': dict(caster_level=199),
            'a standing stack': dict(standing={spell.name: 1}),
            'the game version': dict(game_version='beta'),
            'the cast order': dict(spells=self.spells[::-1]),
            'a cost': dict(spells=self._changed(hitting, cost=spell.cost - 1)),
            'a hit row': dict(spells=self._changed(hitting, alternatives=alternatives,
                                                   plain_alternatives=alternatives)),
            'a delayed row': dict(spells=self._changed(
                hitting, late_by_effect={id(first_hit): 'turn'})),
            'a buff scaling': dict(spells=self._changed(hitting, spell=scaled)),
        }
        self.assertNotIn(id(first_hit), spell.late_by_effect)
        for change, kwargs in changes.items():
            with self.subTest(change=change):
                self.assertEqual(1, self._turn(**kwargs)[1])
                self.assertEqual(0, self._turn(**kwargs)[1])

    def test_a_turn_is_kept_apart_from_the_page_cache(self):
        self._turn()
        key = spell_combo._turn_key(self.stats, self.spells, 9, False, None, 'dofus3', False,
                                    200)
        self.assertIsNotNone(caches['best_turn'].get(key))
        self.assertIsNone(cache.get(key))

    def test_the_turn_cache_never_outlives_the_process(self):
        self.assertEqual('django.core.cache.backends.locmem.LocMemCache',
                         settings.CACHES['best_turn']['BACKEND'])

    def test_a_variant_pair_change_searches_again(self):
        self._turn()
        with mock.patch('chardata.spell_combo.variant_of', return_value=None):
            self.assertEqual(1, self._turn()[1])

    def test_the_game_version_in_force_is_in_the_key(self):
        self._turn()
        set_current_game_version('beta')
        self.addCleanup(set_current_game_version, 'dofus3')
        self.assertEqual(1, self._turn()[1])

    def test_a_new_data_version_searches_again(self):
        self._turn()
        versions = dict(settings.SITE_VERSIONS, dofus3=settings.SITE_VERSIONS['dofus3'] + '.1')
        with override_settings(SITE_VERSIONS=versions):
            self.assertEqual(1, self._turn()[1])
            self.assertEqual(0, self._turn()[1])
        self.assertEqual(0, self._turn()[1])

    def test_every_version_keys_its_casts(self):
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            for char_class in _classes(version):
                with self.subTest(version=version, char_class=char_class):
                    spells = castable_spells(char_class, 200, version) + [_weapon()]
                    self.assertIsNotNone(spell_combo._turn_key(
                        stats, spells, 7, False, None, version, False, 200))

    def test_a_cast_reads_only_the_buff_scaling_of_its_spell_and_nothing_of_its_weapon(self):
        read, weapon_read = set(), set()
        for version in VERSIONS:
            set_current_game_version(version)
            stats = _stats(version)
            for char_class in _classes(version):
                spells = castable_spells(char_class, 200, version)
                for castable in spells:
                    castable.spell = _Watched(castable.spell, read)
                weapon = _weapon()
                weapon.weapon = _Watched(weapon.weapon, weapon_read)
                for crit, pushback in ((False, True), (True, False)):
                    spell_combo._search_best_turn(stats, spells + [weapon], 7, crit=crit,
                                                  pushback=pushback, game_version=version,
                                                  caster_level=200)
        self.assertEqual({'buff_scaling'}, read)
        self.assertEqual(set(), weapon_read)


class AWornBuildTests(TestCase):

    def test_a_worn_build_turn_is_searched_once(self):
        from django.contrib.auth.models import User
        from chardata.models import Char
        from chardata.solution import get_solution
        from chardata.spell_modifiers import item_spell_modifiers, worn_spell_modifiers
        from chardata.spells_view import _best_combo, _weapon_castable
        self.client.force_login(User.objects.create_user('author', 'a@x.test', 'pw'))
        set_current_game_version('dofus3')
        structure = get_structure('dofus3')
        cra_spells = {spell.spell_id for spell in castable_spells('Cra', 200, 'dofus3')}
        names = []
        for type_name in ('Weapon', 'Hat', 'Cloak', 'Belt', 'Boots', 'Amulet'):
            items = [item for item in structure.types[200][type_name]
                     if not item.removed and item.ankama_id]
            item = next((item for item in items
                         if any(spell_id in cra_spells for spell_id, _kind, _amount
                                in item_spell_modifiers('dofus3', item.ankama_id))), items[0])
            names.append(structure.get_item_name_in_language(item, 'en'))
        self.client.post('/import/text/', {'text': '\n'.join(names), 'confirm': '1',
                                           'char_class': 'Cra', 'level': '200'})
        char = Char.objects.order_by('-id').first()
        searches = []
        for _view in range(2):
            solution = get_solution(char)
            self.assertTrue(worn_spell_modifiers(solution, 'dofus3'))
            self.assertIsNotNone(_weapon_castable(solution))
            with mock.patch.object(spell_combo, '_search_best_turn',
                                   wraps=spell_combo._search_best_turn) as searched:
                self.assertTrue(_best_combo(char, solution, 'dofus3', note_without_buffs=False))
            searches.append(searched.call_count)
        self.assertEqual([1, 0], searches)
