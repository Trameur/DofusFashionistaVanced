# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Retro piece recorded above its catalogue Strength holds an over, so no exo is counted on it."""

from django.test import SimpleTestCase

from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_WEIGHTS = {'vit': 1, 'str': 3, 'pow': 2, 'ap': 1000, 'mp': 80, 'range': 10}
_OPTIONS = {'ap_exo': 8, 'mp_exo': 0, 'range_exo': 0, 'dofus': True,
            'trophies': True, 'dragoturkey': True, 'seemyool': True,
            'rhineetle': True, 'prysmaradite': False, 'dofuses': {},
            'dofusnotforchar': set()}


class AnOveredPieceTakesNoExoTests(SimpleTestCase):

    minimal = None

    def setUp(self):
        set_current_game_version('retro')
        structure = get_structure('retro')
        str_id = structure.get_stat_by_key('str').id
        hat = next(item for item
                   in structure.get_unique_items_by_type_and_level('Hat', 200)
                   if item.forgeable and not item.removed
                   and dict(item.stats).get(str_id, 0) > 0)
        overrides = {hat.id: {str_id: dict(hat.stats)[str_id] + 30}}
        cls = type(self)
        if cls.minimal is None:
            model = Model(stat_overrides=overrides)
            model.setup(ModelInput(200, dict(_BASE), {}, {'hat': hat.id}, set(),
                                   dict(_WEIGHTS), dict(_OPTIONS), 'Iop', 995))
            model.run(1)
            cls.minimal = model.get_result_minimal()
        self.result = model_result_from_minimal(self.minimal, overrides)
        self.result.get_stats_gear()
        worn = [item for item in self.result.item_list if item.item_added]
        self.hat = next(item for item in worn if item.slot == 'hat')
        self.assertEqual(hat.id, self.hat.id)
        self.free = [item for item in worn if item is not self.hat
                     and structure.get_item_by_id(item.id).forgeable]

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_the_overed_piece_holds_no_exo(self):
        self.assertTrue(self.hat.holds_an_over())
        self.assertIsNone(self.hat.assumed_exo)

    def test_the_solver_leaves_the_overed_piece_out_of_the_count(self):
        self.assertEqual(len(self.free), sum(self.minimal.exo_assumed.values()))
        self.assertEqual(self.minimal.exo_assumed, self.result.exo_points)
