# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Retro solution saved before the exo count keeps its exo total until the next solve: the owned exos worn fill the option first."""
import pickle

from django.test import SimpleTestCase

from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': True, 'mp_exo': False, 'range_exo': False, 'dofus': True,
            'trophies': True, 'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
            'prysmaradite': False, 'dofuses': {}, 'dofusnotforchar': set()}


class ARetroSolutionSavedBeforeTheCountKeepsItsExoTotalTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')
        structure = get_structure('retro')
        self.ap_id = structure.get_stat_by_key('ap').id
        self.hat, self.cloak = (
            next(item for item in structure.get_unique_items_by_type_and_level(type_name, 200)
                 if item.forgeable and not item.removed and self.ap_id not in dict(item.stats))
            for type_name in ('Hat', 'Cloak'))
        self.owned_ap_exo = {self.hat.id: {self.ap_id: 1}}

    def _minimal(self, saved_before_the_count):
        minimal = ModelResultMinimal({'hat': self.hat.id, 'cloak': self.cloak.id},
                                     {'options': dict(_OPTIONS), 'char_level': 200,
                                      'base_stats_by_attr': dict(_BASE)}, None)
        if saved_before_the_count:
            del minimal.exo_option_tops_owned
        return pickle.loads(pickle.dumps(minimal))

    @staticmethod
    def _ap_exos(result):
        result.get_stats_gear()
        forged = [item.slot for item in result.item_list
                  if item.item_added and item.assumed_exo == 'ap']
        return result.exo_points['ap'], forged

    def test_an_owned_ap_exo_fills_the_option_of_an_old_solution(self):
        result = model_result_from_minimal(self._minimal(True), self.owned_ap_exo)
        self.assertEqual((1, []), self._ap_exos(result))

    def test_an_old_solution_with_no_owned_exo_still_forges_one(self):
        result = model_result_from_minimal(self._minimal(True), None)
        points, forged = self._ap_exos(result)
        self.assertEqual(1, points)
        self.assertEqual(1, len(forged))

    def test_a_solution_saved_now_forges_the_option_on_top_of_the_owned_exo(self):
        result = model_result_from_minimal(self._minimal(False), self.owned_ap_exo)
        self.assertEqual((2, ['cloak']), self._ap_exos(result))

    def test_an_item_swap_on_an_old_solution_keeps_its_total(self):
        result = model_result_from_minimal(self._minimal(True), self.owned_ap_exo)
        saved = pickle.loads(pickle.dumps(ModelResultMinimal.from_model_result(result)))
        again = model_result_from_minimal(saved, self.owned_ap_exo)
        self.assertEqual((1, []), self._ap_exos(again))
