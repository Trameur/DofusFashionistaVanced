# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Locking a slot whose saved piece carries a Dracorune locks the rune too, and every other lock leaves the options alone."""

import pickle
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import translation

from chardata import fashion_action
from chardata.char_blobs import read_char_blob
from chardata.dracorune_fixtures import (OPTIONS, SmallModel, element_key, element_move, eligible_items,
                                         runes, structure)
from chardata.lock_forbid import get_inclusions_dict, set_item_included, the_build_can_wear
from chardata.models import Char
from chardata.options import get_options, set_options
from fashionistapulp import dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import ModelInput
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

WEARER = SimpleNamespace(char_class='Iop', level=200, gender=0, char_name='locks')
NOTE = 'Locked pieces keep their Dracorune, even above this number.'


def lines_of(item):
    lines = {}
    for stat_id, value in item.stats:
        key = structure().get_stat_by_id(stat_id).key
        lines[key] = lines.get(key, 0) + value
    return lines


def key_of(options):
    return ModelInput(200, {}, {}, {}, [], {}, options, 'Iop', 0).cache_key()


class _Locks(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('beta')
        self.owner = User.objects.create_user('rune-locks', 'rl@x.test', 'pw-42-solid')
        self.client.force_login(self.owner)
        self.source, self.target = element_move()
        self.key = element_key(self.source, self.target)
        self.hat, self.other_hat = self.pieces('Hat', 2)
        self.cloak, = self.pieces('Cloak', 1)

    def pieces(self, type_name, count):
        found = []
        for item in eligible_items(type_name):
            if (lines_of(item).get(self.source, 0) > 1 and item.level <= 200
                    and structure().get_item_by_name(item.name).id == item.id
                    and self.key in dict(dracorunes.variants(list(lines_of(item).items()), runes()))
                    and the_build_can_wear(WEARER, item)):
                found.append(item)
            if len(found) == count:
                return found
        self.fail('no %s takes the rune' % type_name)

    def char(self, version='beta', options=None, worn=None, runes_on=None):
        minimal = ModelResultMinimal(
            dict(worn or {}),
            {'options': dict(OPTIONS), 'char_level': 200,
             'base_stats_by_attr': {name: 0 for name, _key in STATS_NAMES}}, None)
        if runes_on:
            minimal.dracorunes = dict(runes_on)
        return Char.objects.create(
            name='Locks', char_name='locks', char_class='Iop', char_build='build', level=200,
            minimum_stats=pickle.dumps({}), minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(options or {}),
            inclusions=pickle.dumps({}), exclusions=pickle.dumps([]),
            minimal_solution=pickle.dumps(minimal),
            owner=self.owner, link_shared=False, game_version=version)

    def lock(self, char, slot, item, locked=True, version='beta'):
        prefix = '' if version == 'dofus3' else '/' + version
        return self.client.post('%s/setitemlocked/%d/' % (prefix, char.id), {
            'slot': slot, 'equip': item.name, 'locked': 'true' if locked else 'false'})

    def blob(self, char):
        return read_char_blob(Char.objects.get(id=char.id).options, {}, 'options')

    def solver_options(self, char):
        with mock.patch.object(fashion_action, 'get_char_or_raise',
                               return_value=Char.objects.get(id=char.id)):
            return fashion_action.get_options(None, char.id)


class LockingADraconizedSlotTests(_Locks):

    def draconized(self, options=None):
        return self.char(options=options, worn={'hat': self.hat.id, 'cloak': self.cloak.id},
                         runes_on={'hat': (self.hat.id, self.key)})

    def test_locking_a_draconized_piece_stores_its_rune(self):
        char = self.draconized()
        self.assertEqual(200, self.lock(char, 'hat', self.hat).status_code)
        self.assertEqual({'hat': self.key}, self.blob(char)['dracorune_locks'])
        self.assertEqual(self.hat.id, get_inclusions_dict(Char.objects.get(id=char.id))['hat'])

    def test_unlocking_the_slot_removes_the_entry(self):
        char = self.draconized()
        self.lock(char, 'hat', self.hat)
        self.lock(char, 'hat', self.hat, locked=False)
        self.assertNotIn('dracorune_locks', self.blob(char))

    def test_locking_a_plain_piece_stores_nothing(self):
        char = self.draconized()
        before = char.options
        self.assertEqual(200, self.lock(char, 'cloak', self.cloak).status_code)
        self.assertEqual(before, Char.objects.get(id=char.id).options)

    def test_locking_another_piece_in_the_slot_drops_the_entry(self):
        char = self.draconized()
        self.lock(char, 'hat', self.hat)
        self.lock(char, 'hat', self.other_hat)
        self.assertNotIn('dracorune_locks', self.blob(char))
        self.assertEqual(self.other_hat.id, get_inclusions_dict(Char.objects.get(id=char.id))['hat'])

    def test_a_rune_of_another_slot_is_kept_while_its_own_lock_stays(self):
        char = self.char(worn={'hat': self.hat.id, 'cloak': self.cloak.id},
                         runes_on={'hat': (self.hat.id, self.key), 'cloak': (self.cloak.id, self.key)})
        self.lock(char, 'hat', self.hat)
        self.lock(char, 'cloak', self.cloak)
        self.lock(char, 'hat', self.hat, locked=False)
        self.assertEqual({'cloak': self.key}, self.blob(char)['dracorune_locks'])

    def test_a_lock_on_a_piece_other_than_the_one_with_the_rune_stores_nothing(self):
        char = self.draconized()
        before = char.options
        self.lock(char, 'hat', self.other_hat)
        self.assertEqual(before, Char.objects.get(id=char.id).options)

    def test_the_solver_gets_the_rune_and_a_count_that_includes_it(self):
        char = self.draconized({'dracorunes': 0})
        self.lock(char, 'hat', self.hat)
        options = self.solver_options(char)
        self.assertEqual({'hat': self.key}, options['dracorune_locks'])
        self.assertEqual(1, options['dracorunes'])

    def test_a_count_above_the_locked_runes_is_left_as_it_is(self):
        char = self.draconized({'dracorunes': 3})
        self.lock(char, 'hat', self.hat)
        self.assertEqual(3, self.solver_options(char)['dracorunes'])
        self.assertNotIn('dracorune_locked', get_options(Char.objects.get(id=char.id)))

    def test_the_cache_key_changes_with_the_locked_rune(self):
        char = self.draconized({'dracorunes': 2})
        plain = self.solver_options(char)
        self.lock(char, 'hat', self.hat)
        locked = self.solver_options(char)
        self.assertNotEqual(key_of(plain), key_of(locked))
        self.assertNotEqual(hash(ModelInput(200, {}, {}, {}, [], {}, plain, 'Iop', 0)),
                            hash(ModelInput(200, {}, {}, {}, [], {}, locked, 'Iop', 0)))
        self.lock(char, 'hat', self.hat, locked=False)
        self.assertEqual(key_of(plain), key_of(self.solver_options(char)))


class TheNextSolveKeepsTheLockedRuneTests(_Locks):

    def solve(self, char):
        options = self.solver_options(char)
        locked = get_inclusions_dict(Char.objects.get(id=char.id))
        base = {name: 0 for name, _key in STATS_NAMES}
        model = SmallModel([self.hat, self.cloak])
        model.setup(ModelInput(200, base, {}, locked, [], {self.source: 1}, options, 'Iop', 0))
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        return model.get_result_minimal()

    def test_the_locked_piece_comes_back_with_its_rune_even_when_the_rune_costs(self):
        char = self.char(options={'dracorunes': 0}, worn={'hat': self.hat.id},
                         runes_on={'hat': (self.hat.id, self.key)})
        self.lock(char, 'hat', self.hat)
        result = self.solve(char)
        self.assertEqual(self.hat.id, result.item_per_slot['hat'])
        self.assertEqual({'hat': (self.hat.id, self.key)}, result.dracorunes)

    def test_once_unlocked_the_rune_is_not_forced_any_more(self):
        char = self.char(options={'dracorunes': 0}, worn={'hat': self.hat.id},
                         runes_on={'hat': (self.hat.id, self.key)})
        self.lock(char, 'hat', self.hat)
        self.lock(char, 'hat', self.hat, locked=False)
        self.assertFalse(self.solve(char).dracorunes)


class LockingThroughTheLockPageTests(_Locks):

    def post(self, char, **slots):
        return self.client.post('/beta/inclusionspost/%d/' % char.id, slots)

    def test_locking_a_draconized_piece_there_stores_its_rune(self):
        char = self.char(worn={'hat': self.hat.id}, runes_on={'hat': (self.hat.id, self.key)})
        self.assertEqual(200, self.post(char, hat=self.hat.id).status_code)
        self.assertEqual({'hat': self.key}, self.blob(char)['dracorune_locks'])

    def test_locking_a_plain_piece_there_stores_nothing(self):
        char = self.char(worn={'hat': self.hat.id, 'cloak': self.cloak.id},
                         runes_on={'hat': (self.hat.id, self.key)})
        before = char.options
        self.post(char, cloak=self.cloak.id)
        self.assertEqual(before, Char.objects.get(id=char.id).options)

    def test_clearing_the_slot_there_removes_the_entry(self):
        char = self.char(worn={'hat': self.hat.id}, runes_on={'hat': (self.hat.id, self.key)})
        self.post(char, hat=self.hat.id)
        self.post(char, hat='')
        self.assertNotIn('dracorune_locks', self.blob(char))


class ACopyToAnotherVersionLeavesTheLocksBehindTests(_Locks):

    def test_the_copy_holds_no_rune_lock(self):
        from django.test import RequestFactory
        from chardata.version_copy import copy_build
        char = self.char(options={'dracorunes': 1}, worn={'hat': self.hat.id},
                         runes_on={'hat': (self.hat.id, self.key)})
        self.lock(char, 'hat', self.hat)
        self.assertIn('dracorune_locks', self.blob(char))
        request = RequestFactory().post('/copy/')
        request.user = self.owner
        request.session = self.client.session
        copied, _missing = copy_build(request, Char.objects.get(id=char.id), 'dofus3')
        self.assertIsNotNone(copied)
        options = read_char_blob(Char.objects.get(id=copied.id).options, {}, 'options')
        self.assertNotIn('dracorune_locks', options)


class AStaleEntryIsDroppedTests(_Locks):

    def test_saving_the_options_drops_an_entry_whose_piece_cannot_take_that_rune(self):
        without = next(item for item in eligible_items('Hat')
                       if self.source not in lines_of(item) and the_build_can_wear(WEARER, item))
        char = self.char(options={'dracorune_locks': {'hat': self.key}},
                         worn={'hat': self.hat.id})
        char.inclusions = pickle.dumps({'hat': without.id})
        char.save()
        set_options(char, {'dracorunes': 1})
        self.assertNotIn('dracorune_locks', self.blob(char))

    def test_saving_the_options_drops_an_entry_whose_variant_is_gone(self):
        char = self.char(options={'dracorune_locks': {'hat': 'element:no>such'}})
        char.inclusions = pickle.dumps({'hat': self.hat.id})
        char.save()
        set_options(char, {'dracorunes': 1})
        self.assertNotIn('dracorune_locks', self.blob(char))

    def test_saving_the_options_keeps_a_good_entry(self):
        char = self.char(options={'dracorune_locks': {'hat': self.key}})
        char.inclusions = pickle.dumps({'hat': self.hat.id})
        char.save()
        set_options(char, {'dracorunes': 1})
        self.assertEqual({'hat': self.key}, self.blob(char)['dracorune_locks'])

    def test_a_stale_entry_reaches_neither_the_solver_nor_the_count(self):
        char = self.char(options={'dracorune_locks': {'hat': self.key}})
        options = self.solver_options(char)
        self.assertNotIn('dracorune_locks', options)
        self.assertNotIn('dracorunes', options)


class TheOptionsPageNoteTests(_Locks):

    def page(self, char):
        with translation.override('en'):
            return self.client.get('/beta/options/%d/' % char.id, follow=True).content.decode('utf-8')

    def locked_build(self, count):
        char = self.char(options={'dracorunes': count},
                         worn={'hat': self.hat.id}, runes_on={'hat': (self.hat.id, self.key)})
        self.lock(char, 'hat', self.hat)
        return char

    def test_the_note_shows_when_the_locked_runes_raise_the_count(self):
        char = self.locked_build(0)
        self.assertEqual(0, get_options(Char.objects.get(id=char.id))['dracorunes'])
        self.assertEqual(1, self.solver_options(char)['dracorunes'])
        self.assertIn(NOTE, self.page(char))

    def test_the_note_is_absent_when_the_count_already_covers_them(self):
        self.assertNotIn(NOTE, self.page(self.locked_build(2)))

    def test_saving_the_options_page_keeps_the_count_the_player_chose(self):
        char = self.locked_build(0)
        self.client.post('/beta/optionspost/%d/' % char.id, {'dracorunes': '0'})
        self.lock(char, 'hat', self.hat, locked=False)
        self.assertEqual(0, self.blob(char)['dracorunes'])
        self.assertNotIn(NOTE, self.page(char))
        self.assertNotIn('dracorunes', self.solver_options(char))

    def test_saving_the_options_back_as_read_leaves_nothing_behind_once_unlocked(self):
        char = self.locked_build(0)
        fresh = Char.objects.get(id=char.id)
        set_options(fresh, get_options(fresh))
        self.lock(char, 'hat', self.hat, locked=False)
        blob = self.blob(char)
        self.assertEqual(0, blob['dracorunes'])
        self.assertNotIn('dracorune_locked', blob)
        self.assertNotIn(NOTE, self.page(char))

    def test_the_note_is_absent_without_a_lock(self):
        self.assertNotIn(NOTE, self.page(self.char(options={'dracorunes': 1})))


class NoRetrofitTests(_Locks):

    def test_an_existing_build_keeps_its_options_through_every_lock_and_unlock(self):
        char = self.char(options={'dracorunes': 2, 'ap_exo': True},
                         worn={'hat': self.hat.id, 'cloak': self.cloak.id})
        before = Char.objects.get(id=char.id).options
        self.lock(char, 'cloak', self.cloak)
        self.lock(char, 'cloak', self.cloak, locked=False)
        self.assertEqual(before, Char.objects.get(id=char.id).options)
        self.assertNotIn('dracorune_locks', get_options(Char.objects.get(id=char.id)))

    def test_the_solver_options_of_a_build_without_locks_are_the_old_ones(self):
        char = self.char(options={'dracorunes': 2})
        options = self.solver_options(char)
        self.assertEqual(2, options['dracorunes'])
        self.assertNotIn('dracorune_locks', options)

    def test_the_runes_part_of_a_cache_key_without_locks_is_the_old_one(self):
        found = ModelInput(200, {}, {}, {}, [], {}, {'dofus': True, 'dracorunes': 2},
                           'Iop', 0)._dracorune_key()
        self.assertEqual({'dofus': True}, found[0])
        self.assertEqual(3, len(found[1]))
        self.assertEqual(['dracorunes', 2], found[1][:2])

    def test_an_empty_lock_dict_leaves_the_runes_part_of_the_cache_key_alone(self):
        plain = ModelInput(200, {}, {}, {}, [], {}, {'dracorunes': 2}, 'Iop', 0)
        empty = ModelInput(200, {}, {}, {}, [], {}, {'dracorunes': 2, 'dracorune_locks': {}},
                           'Iop', 0)
        self.assertEqual(plain._dracorune_key(), empty._dracorune_key())
        self.assertEqual(plain.cache_key(), empty.cache_key())

    def test_an_empty_lock_dict_is_not_passed_to_the_solver(self):
        char = self.char(options={'dracorunes': 2, 'dracorune_locks': {}})
        self.assertNotIn('dracorune_locks', self.solver_options(char))

    def test_a_version_without_a_runes_file_never_writes_the_key(self):
        set_current_game_version('dofus3')
        live = get_structure('dofus3')
        hat = next(item for item in live.get_available_items_list()
                   if live.get_type_name_by_id(item.type) == 'Hat'
                   and item.level <= 200 and the_build_can_wear(WEARER, item)
                   and live.get_item_by_name(item.name).id == item.id)
        char = self.char('dofus3', worn={'hat': hat.id}, runes_on={'hat': (hat.id, self.key)})
        before = char.options
        self.assertEqual(200, self.lock(char, 'hat', hat, version='dofus3').status_code)
        self.assertEqual(before, Char.objects.get(id=char.id).options)
        char.refresh_from_db()
        self.assertTrue(set_item_included(char, hat.id, 'hat', False))
        self.assertEqual(before, Char.objects.get(id=char.id).options)
        self.assertNotIn('dracorunes', self.solver_options(char))

    def test_a_forged_entry_on_a_version_without_a_file_is_not_passed_on(self):
        set_current_game_version('dofus3')
        char = self.char('dofus3', options={'dracorune_locks': {'hat': self.key}})
        options = self.solver_options(char)
        self.assertNotIn('dracorune_locks', options)
        self.assertNotIn('dracorunes', options)
