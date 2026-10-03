# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Asking more Retro exos than pieces can hold gives one exo per forgeable piece worn, no more."""

from django.test import SimpleTestCase

from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_WEIGHTS = {'vit': 1, 'str': 3, 'pow': 2, 'ap': 1000, 'mp': 800, 'range': 100}
_OPTIONS = {'ap_exo': 8, 'mp_exo': 8, 'range_exo': 8, 'dofus': True,
            'trophies': True, 'dragoturkey': True, 'seemyool': True,
            'rhineetle': True, 'prysmaradite': False, 'dofuses': {},
            'dofusnotforchar': set()}


class ExosStayWithinTheForgeablePiecesTests(SimpleTestCase):

    minimal = None

    def setUp(self):
        set_current_game_version('retro')
        structure = get_structure('retro')
        cls = type(self)
        if cls.minimal is None:
            model = Model()
            model.setup(ModelInput(200, dict(_BASE), {}, {}, set(), dict(_WEIGHTS),
                                   dict(_OPTIONS), 'Iop', 995))
            model.run(1)
            cls.minimal = model.get_result_minimal()
        self.result = model_result_from_minimal(self.minimal)
        self.result.get_stats_gear()
        self.worn = [item for item in self.result.item_list if item.item_added]
        self.forgeable = [item for item in self.worn
                          if structure.get_item_by_id(item.id).forgeable]

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_the_solver_counts_no_more_exos_than_forgeable_pieces_worn(self):
        self.assertTrue(self.forgeable)
        self.assertLessEqual(sum(self.minimal.exo_assumed.values()), len(self.forgeable))

    def test_every_counted_exo_sits_on_its_own_piece(self):
        holders = [item for item in self.worn if item.assumed_exo]
        self.assertEqual(sum(self.minimal.exo_assumed.values()), len(holders))
        self.assertEqual(self.minimal.exo_assumed, self.result.exo_points)
