# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build saved without some weights gets them from the engine on its next read, never from the weight table."""
import pickle
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata.smart_build import get_standard_weights
from chardata.stats_weights import STATS_TO_FILL_DEFAULT, get_stats_weights
from chardata.weight_table import SCENARIO_ASPECTS, cell_table, override_weight_table
from fashionistapulp.structure import get_current_game_version, set_current_game_version

VERSION = 'dofus3'
CELL = ('Iop', ('str',), 'glasscannon')
MISSING = ('perspedam', 'perweadam')


class ALegacyBuildFillsItsMissingWeightsFromTheEngineTests(SimpleTestCase):

    def setUp(self):
        previous = get_current_game_version()
        set_current_game_version(VERSION)
        self.addCleanup(set_current_game_version, previous)

    def test_the_filled_weights_are_the_engine_weights_on_a_tuned_cell(self):
        char_class, played, scenario = CELL
        aspects = set(played) | SCENARIO_ASPECTS[scenario]
        char = SimpleNamespace(char_class=char_class, level=200, game_version=VERSION, aspects=pickle.dumps(aspects),
                               minimum_stats=None, stats_weight=None, id=1)
        engine = get_standard_weights(char, table=False)
        char.stats_weight = pickle.dumps({key: value for key, value in engine.items() if key not in MISSING})
        self.assertTrue(set(MISSING) <= STATS_TO_FILL_DEFAULT)
        with override_weight_table(VERSION, cell_table(*CELL, {key: 50.0 for key in MISSING})):
            tuned = get_standard_weights(char)
            filled = get_stats_weights(char, persist=False)
        for key in MISSING:
            with self.subTest(stat=key):
                self.assertNotEqual(engine[key], tuned[key])
                self.assertEqual(engine[key], filled[key])
