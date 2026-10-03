# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Retro build saved with the AP and MP exos on gets the same score, AP and MP as with one exo per stat."""

from unittest import mock

import pulp
from django.test import SimpleTestCase

from fashionistapulp.game_versions import get_game_version
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.modelresult import model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_WEIGHTS = {'vit': 1, 'str': 3, 'pow': 2, 'ap': 100, 'mp': 80, 'range': 10}
_OPTIONS = {'range_exo': False, 'dofus': True, 'trophies': True,
            'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
            'prysmaradite': False, 'dofuses': {}, 'dofusnotforchar': set()}


def _solve(level, exos, per_item):
    with mock.patch.object(get_game_version('retro'), 'exo_per_item', per_item):
        model = Model()
        model.setup(ModelInput(level, dict(_BASE), {}, {}, set(), dict(_WEIGHTS),
                               dict(_OPTIONS, **exos), 'Iop', (level - 1) * 5))
        model.run(1)
        result = model_result_from_minimal(model.get_result_minimal())
        total = result.get_stats_total()
        # Several sets can tie on the score, so the pieces are not compared
        return pulp.value(model.problem.pulp_lp.objective), total['ap'], total['mp']


class AnOldRetroBuildSolvesAsBeforeTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('retro')
        # The catalogue reads the forgeable pieces once, with the real flag
        get_structure('retro')

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_the_options_saved_as_yes_give_what_one_exo_per_stat_gave(self):
        for level in (200, 60):
            with self.subTest(level=level):
                before = _solve(level, {'ap_exo': True, 'mp_exo': True}, False)
                self.assertEqual(before, _solve(level, {'ap_exo': True, 'mp_exo': True}, True))
                self.assertEqual(before, _solve(level, {'ap_exo': 1, 'mp_exo': 1}, True))
