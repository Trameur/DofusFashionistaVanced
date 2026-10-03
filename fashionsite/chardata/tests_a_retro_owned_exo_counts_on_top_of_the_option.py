# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Retro an exo recorded on a worn piece adds to the exos the option asks for, and always counts."""

from django.test import SimpleTestCase

from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'mp_exo': 0, 'range_exo': 0, 'dofus': True, 'trophies': True,
            'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
            'prysmaradite': False, 'dofuses': {}, 'dofusnotforchar': set()}


class AnOwnedExoAddsToTheOptionTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('retro')
        self.structure = get_structure('retro')
        self.ap_id = self.structure.get_stat_by_key('ap').id
        self.hat = next(item for item
                        in self.structure.get_unique_items_by_type_and_level('Hat', 200)
                        if item.forgeable and not item.removed
                        and self.ap_id not in dict(item.stats))
        self.overrides = {self.hat.id: {self.ap_id: 1}}

    def tearDown(self):
        set_current_game_version('dofus3')

    def _solve(self, ap_weight, ap_exo):
        model = Model(stat_overrides=self.overrides)
        weights = {'vit': 1, 'str': 3, 'pow': 2, 'ap': ap_weight, 'mp': 80}
        model.setup(ModelInput(200, dict(_BASE), {}, {'hat': self.hat.id}, set(),
                               weights, dict(_OPTIONS, ap_exo=ap_exo), 'Iop', 995))
        model.run(1)
        minimal = model.get_result_minimal()
        exo_ap = model.problem.get_result()['exo_%d' % self.ap_id]
        return minimal, model_result_from_minimal(minimal, self.overrides), exo_ap

    def test_the_option_puts_its_exo_on_another_piece(self):
        minimal, result, exo_ap = self._solve(1000, 1)
        self.assertEqual(2, round(exo_ap))
        self.assertEqual({'ap': 1, 'mp': 0, 'range': 0}, minimal.exo_assumed)
        worn = [item for item in result.item_list if item.item_added]
        hat = next(item for item in worn if item.slot == 'hat')
        self.assertEqual(self.hat.id, hat.id)
        self.assertIn('ap', hat.exo_overrides)
        self.assertIsNone(hat.assumed_exo)
        self.assertEqual(1, len([item for item in worn if item.assumed_exo == 'ap']))
        pieces = sum(item.stats.get('ap', 0) for item in worn)
        sets = sum(item_set.get_bonus().get('ap', 0) for item_set in result.sets)
        self.assertEqual(pieces + sets + 2, result.get_stats_gear()['ap'])

    def test_the_owned_exo_counts_even_when_ap_is_unwanted(self):
        minimal, result, exo_ap = self._solve(-1000, 0)
        self.assertEqual(1, round(exo_ap))
        self.assertEqual({'ap': 0, 'mp': 0, 'range': 0}, minimal.exo_assumed)
        result.get_stats_gear()
        self.assertEqual(1, result.exo_points['ap'])
