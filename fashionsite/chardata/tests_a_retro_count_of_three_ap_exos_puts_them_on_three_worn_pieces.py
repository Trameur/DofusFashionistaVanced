# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Three AP exos asked on Retro land on three worn forgeable pieces and add three AP."""

from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import SLOT_NAME_TO_TYPE
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_WEIGHTS = {'vit': 1, 'str': 3, 'pow': 2, 'ap': 1000, 'mp': 80, 'range': 10}
_OPTIONS = {'ap_exo': 3, 'mp_exo': 0, 'range_exo': 0, 'dofus': True,
            'trophies': True, 'dragoturkey': True, 'seemyool': True,
            'rhineetle': True, 'prysmaradite': False, 'dofuses': {},
            'dofusnotforchar': set()}


class ThreeApExosTests(SimpleTestCase):

    minimal = None

    def setUp(self):
        set_current_game_version('retro')
        self.structure = get_structure('retro')
        cls = type(self)
        if cls.minimal is None:
            model = Model()
            model.setup(ModelInput(200, dict(_BASE), {}, {}, set(), dict(_WEIGHTS),
                                   dict(_OPTIONS), 'Iop', 995))
            model.run(1)
            cls.minimal = model.get_result_minimal()
        self.result = model_result_from_minimal(self.minimal)
        self.worn = [item for item in self.result.item_list if item.item_added]

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_the_solver_counts_three_exos_to_forge(self):
        self.assertEqual({'ap': 3, 'mp': 0, 'range': 0}, self.minimal.exo_assumed)

    def test_three_forgeable_pieces_each_take_one(self):
        holders = [item for item in self.worn if item.assumed_exo]
        self.assertEqual(['ap', 'ap', 'ap'], [item.assumed_exo for item in holders])
        for item in holders:
            self.assertTrue(self.structure.get_item_by_id(item.id).forgeable, item.name)
            self.assertNotIn(SLOT_NAME_TO_TYPE[item.slot], ('Dofus', 'Pet', 'Shield'))

    def test_the_gear_ap_is_the_pieces_the_sets_and_the_three_exos(self):
        pieces = sum(item.stats.get('ap', 0) for item in self.worn)
        sets = sum(item_set.get_bonus().get('ap', 0) for item_set in self.result.sets)
        self.assertEqual(pieces + sets + 3, self.result.get_stats_gear()['ap'])
        self.assertEqual({'ap': 3, 'mp': 0, 'range': 0}, self.result.exo_points)
