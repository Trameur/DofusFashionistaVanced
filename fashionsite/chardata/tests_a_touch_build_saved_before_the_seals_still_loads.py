# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Touch build stored with sixteen slots loads, shows and solves as before, its seal slots empty."""

import pickle

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from chardata.char_blobs import read_char_blob
from chardata.models import Char
from chardata.solution import get_solution
from fashionistapulp.dofus_constants import SLOTS, STATS_NAMES, SLOT_NAME_TO_TYPE
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'shields': True}


def sixteen_slot_minimal(structure, char_class='Iop', level=200):
    """A minimal solution in the layout stored before the seal slots."""
    per_slot = {}
    taken = set()
    for slot in SLOTS:
        type_name = SLOT_NAME_TO_TYPE[slot]
        item = next(item for item in structure.types[level][type_name]
                    if not item.removed and item.id not in taken
                    and item.set is None)
        taken.add(item.id)
        per_slot[slot] = item.id
    model_input = {'char_class': char_class, 'char_level': level,
                   'origin': 'generated', 'options': dict(_OPTIONS),
                   'base_stats_by_attr': {name: 0 for name, _key in STATS_NAMES},
                   'locked_equips': {}}
    return ModelResultMinimal(per_slot, model_input, {})


class AStoredTouchBuildTests(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('touch')
        self.structure = get_structure('touch')
        self.minimal = sixteen_slot_minimal(self.structure)
        self.owner = User.objects.create_user('seal-less', 'sl@test.local',
                                              'pw-42-solid')
        self.client.force_login(self.owner)
        self.blob = pickle.dumps(self.minimal)
        self.char = Char.objects.create(
            name='Before the seals', char_name='', char_class='Iop',
            char_build='', level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(dict(_OPTIONS)),
            inclusions=b'', exclusions=b'', owner=self.owner, link_shared=False,
            game_version='touch', minimal_solution=self.blob)

    def test_the_stored_blob_still_has_its_sixteen_slots(self):
        stored = read_char_blob(self.char.minimal_solution, None,
                                'minimal_solution', self.char)
        self.assertEqual(sorted(SLOTS), sorted(stored.item_per_slot))

    def test_it_loads_with_both_seal_slots_empty(self):
        solution = get_solution(self.char)
        self.assertEqual(set(), solution.open_slots)
        seals = solution.items['Emblem']
        self.assertEqual(['emblem1', 'emblem2'],
                         sorted(item.slot for item in seals))
        self.assertFalse(any(item.item_added for item in seals))
        worn = sorted(item.id for item in solution.item_list if item.item_added)
        self.assertEqual(sorted(self.minimal.item_per_slot.values()), worn)

    def test_the_build_page_shows_two_empty_seal_boxes_and_rewrites_nothing(self):
        page = self.client.get('/touch/solution/%d/' % self.char.id)
        self.assertEqual(200, page.status_code)
        html = page.content.decode('utf-8')
        for slot in ('emblem1', 'emblem2'):
            with self.subTest(slot=slot):
                self.assertIn('id="item-container-%s"' % slot, html)
        self.assertIn('chardata/Emblem.png', html)
        self.char.refresh_from_db()
        self.assertEqual(self.blob, bytes(self.char.minimal_solution))

    def test_a_dofus3_build_page_has_no_seal_box(self):
        set_current_game_version('dofus3')
        minimal = sixteen_slot_minimal(get_structure('dofus3'))
        char = Char.objects.create(
            name='Dofus 3', char_name='', char_class='Iop', char_build='',
            level=200, minimum_stats=b'', minimum_crits=b'',
            stats_weight=pickle.dumps({}), options=pickle.dumps(dict(_OPTIONS)),
            inclusions=b'', exclusions=b'', owner=self.owner, link_shared=False,
            game_version='dofus3', minimal_solution=pickle.dumps(minimal))
        page = self.client.get('/solution/%d/' % char.id)
        self.assertEqual(200, page.status_code)
        self.assertNotIn('item-container-emblem', page.content.decode('utf-8'))


class AnUnlockedSealNeverChangesASolveTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('touch')
        self.structure = get_structure('touch')

    def _solve(self, forbidden=()):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100,
                     'Pods': 1000})
        model = Model()
        model.setup(ModelInput(200, base, {}, {}, list(forbidden),
                               {'vit': 1, 'str': 3, 'pow': 3, 'ap': 400,
                                'mp': 300},
                               dict(_OPTIONS), 'Iop', 995))
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        return model

    def test_the_solve_is_the_one_without_any_seal_in_the_catalogue(self):
        emblem = self.structure.get_type_id_by_name('Emblem')
        seals = [item.id for item in self.structure.get_items_list()
                 if item.type == emblem]
        with_seals = self._solve()
        pool = with_seals.get_candidate_pool()
        worn = with_seals.get_result_minimal().item_per_slot
        without = self._solve(forbidden=seals).get_result_minimal().item_per_slot
        self.assertNotIn('Emblem', pool)
        self.assertEqual(None, worn.get('emblem1'))
        self.assertEqual(None, worn.get('emblem2'))
        self.assertEqual(sorted(without.values()), sorted(worn.values()))
