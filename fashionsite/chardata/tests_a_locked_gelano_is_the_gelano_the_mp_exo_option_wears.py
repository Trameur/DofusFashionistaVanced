# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Gelano locked, unlocked or forbidden from its card, or saved locked, is the Gelano row the MP exo option wears."""
import json
import pickle
import re

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.coaching_view import create_build
from chardata.lock_forbid import get_all_exclusions_ids, get_inclusions_dict
from chardata.min_stats import set_min_stats
from chardata.options import get_options, set_options
from chardata.solution import get_solution
from chardata.stats_weights import set_stats_weights
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import (GELANO_DEPLOYED_IDS, get_structure,
                                       set_current_game_version)
from chardata.solver_guard import pulp_solver_required

_WEIGHTS = {'ap': 1000, 'mp': 800, 'vit': 1}

_OLD_EXO_GELANO_ID = next(old for old, name in GELANO_DEPLOYED_IDS['dofus3'].items()
                          if name == 'Gelano (#1)')

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'range_exo': False, 'dofus': True, 'trophies': True,
            'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
            'prysmaradite': False, 'dofuses': {}, 'dofusnotforchar': set()}


def _page_object(page, name):
    found = re.search(r'var %s = (\{.*?\})\s*\n' % name, page)
    return json.loads(found.group(1)) if found else None


class _AGelanoBuild(TestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        structure = get_structure('dofus3')
        self.exo_gelano = structure.get_item_by_name('Gelano (#1)')
        self.plain_gelano = structure.get_item_by_name('Gelano (#2)')
        self.owner = User.objects.create_user('gelanolock', 'gl@test.local', 'pw-gel-lock-1')
        request = RequestFactory().post('/')
        request.user = self.owner
        self.char = create_build(request, 'Feca', 60, {'cha'}, 'dofus3')
        set_min_stats(self.char, {})
        set_stats_weights(self.char, dict(_WEIGHTS))
        self.client.force_login(self.owner)

    def _mp_exo(self, value):
        options = get_options(self.char)
        options['ap_exo'] = False
        options['mp_exo'] = value
        set_options(self.char, options)

    def _save_lock(self, slot, item_id):
        self.char.inclusions = pickle.dumps({slot: item_id})
        self.char.save()

    def _save_forbid(self, item_id):
        self.char.exclusions = pickle.dumps(get_all_exclusions_ids(self.char) + [item_id])
        self.char.save()

    def _solve(self):
        response = self.client.get('/fashion/%d/' % self.char.pk)
        self.assertEqual(302, response.status_code)
        self.assertNotIn('/infeasible/', response.url,
                         'the solve of the build was sent to the failure page')
        self.char.refresh_from_db()

    def _worn_gelanos(self):
        rows = (self.exo_gelano.id, self.plain_gelano.id)
        return {item.slot: item.id for item in get_solution(self.char).item_list
                if item.item_added and item.id in rows}

    def _cards(self):
        page = self.client.get('/solution/%d/' % self.char.pk).content.decode('utf-8')
        return _page_object(page, 'itemNames'), _page_object(page, 'itemIds')

    def _wearing_the_exo_gelano(self):
        self._solve()
        worn = self._worn_gelanos()
        self.assertEqual([self.exo_gelano.id], list(worn.values()),
                         'the build does not wear the AP + MP Gelano, nothing below is measured')
        slot = next(iter(worn))
        names, ids = self._cards()
        self.assertEqual(self.exo_gelano.id, ids[slot])
        return slot, names[slot]

    def _post(self, route, data):
        response = self.client.post('/%s/%d/' % (route, self.char.pk), data)
        self.assertEqual(200, response.status_code, response.content)


@pulp_solver_required
class TheCardOfTheExoGelanoTests(_AGelanoBuild):

    def test_locking_the_card_keeps_the_ap_and_mp_gelano_on(self):
        self._mp_exo('gelano')
        slot, equip = self._wearing_the_exo_gelano()

        self._post('setitemlocked', {'slot': slot, 'equip': equip, 'locked': 'true'})
        self._solve()

        self.assertEqual({slot: self.exo_gelano.id}, self._worn_gelanos())

    def test_forbidding_the_card_takes_off_every_gelano_row(self):
        self._mp_exo('gelano')
        slot, equip = self._wearing_the_exo_gelano()

        self._post('setitemforbidden', {'slot': slot, 'equip': equip, 'forbidden': 'true'})
        self._solve()

        self.assertEqual({}, self._worn_gelanos())

    def test_forbidding_the_card_of_an_old_exo_gelano_lock_takes_the_lock_off(self):
        self._mp_exo('gelano')
        self._save_lock('ring1', _OLD_EXO_GELANO_ID)
        slot, equip = self._wearing_the_exo_gelano()

        self._post('setitemforbidden', {'slot': slot, 'equip': equip, 'forbidden': 'true'})
        self._solve()

        self.assertEqual({}, self._worn_gelanos())


@pulp_solver_required
class ABuildSavedWithAGelanoLockedTests(_AGelanoBuild):

    def test_the_plain_gelano_locked_under_the_gelano_exo_wears_the_ap_and_mp_gelano(self):
        self._mp_exo('gelano')
        self._save_lock('ring1', self.plain_gelano.id)

        self._solve()

        self.assertEqual({'ring1': self.exo_gelano.id}, self._worn_gelanos())

    def test_the_ap_and_mp_gelano_locked_without_the_gelano_exo_wears_the_plain_gelano(self):
        for mp_exo in (False, True):
            with self.subTest(mp_exo=mp_exo):
                self._mp_exo(mp_exo)
                self._save_lock('ring1', _OLD_EXO_GELANO_ID)

                self._solve()

                self.assertEqual({'ring1': self.plain_gelano.id}, self._worn_gelanos())


class TheCardUndoesAnOldGelanoRowTests(_AGelanoBuild):

    def test_unlocking_the_card_frees_a_slot_locked_on_the_old_exo_gelano_id(self):
        self._mp_exo('gelano')
        self._save_lock('ring1', _OLD_EXO_GELANO_ID)

        self._post('setitemlocked', {'slot': 'ring1', 'equip': self.exo_gelano.or_name,
                                     'locked': 'false'})

        self.char.refresh_from_db()
        self.assertIn(get_inclusions_dict(self.char).get('ring1', ''), ('', None))

    def test_locking_the_card_lifts_a_forbid_held_on_the_other_gelano_row(self):
        self._mp_exo('gelano')
        self._save_forbid(_OLD_EXO_GELANO_ID)

        self._post('setitemlocked', {'slot': 'ring1', 'equip': self.exo_gelano.or_name,
                                     'locked': 'true'})

        self.char.refresh_from_db()
        rows = {self.exo_gelano.id, self.plain_gelano.id}
        self.assertEqual(set(), rows.intersection(get_all_exclusions_ids(self.char)))


@pulp_solver_required
class EveryDofusVersionReadsAGelanoLockTheSameWayTests(SimpleTestCase):

    VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def _worn(self, version, locked, mp_exo):
        set_current_game_version(version)
        structure = get_structure(version)
        model = Model()
        options = dict(_OPTIONS, mp_exo=mp_exo)
        model.setup(ModelInput(60, dict(_BASE), {}, locked, set(), dict(_WEIGHTS),
                               options, 'Feca', 0))
        model.run(1)
        self.assertEqual('Optimal', model.get_solved_status(),
                         'a Gelano lock made the %s build infeasible' % version)
        result = model_result_from_minimal(model.get_result_minimal())
        rows = {structure.get_item_by_name('Gelano (#1)').id,
                structure.get_item_by_name('Gelano (#2)').id}
        return {item.slot: item.id for item in result.item_list
                if item.item_added and item.id in rows}

    def test_either_row_locked_wears_the_row_the_option_picks(self):
        for version in self.VERSIONS:
            structure = get_structure(version)
            exo = structure.get_item_by_name('Gelano (#1)').id
            plain = structure.get_item_by_name('Gelano (#2)').id
            for locked, mp_exo, wanted in ((plain, 'gelano', exo), (exo, 'gelano', exo),
                                           (exo, False, plain), (plain, False, plain)):
                with self.subTest(version=version, locked=locked, mp_exo=mp_exo):
                    self.assertEqual({'ring1': wanted},
                                     self._worn(version, {'ring1': locked}, mp_exo))

    def test_both_rings_locked_on_a_gelano_wear_one_gelano(self):
        for version in self.VERSIONS:
            structure = get_structure(version)
            exo = structure.get_item_by_name('Gelano (#1)').id
            plain = structure.get_item_by_name('Gelano (#2)').id
            with self.subTest(version=version):
                worn = self._worn(version, {'ring1': plain, 'ring2': exo}, 'gelano')
                self.assertEqual([exo], list(worn.values()))
