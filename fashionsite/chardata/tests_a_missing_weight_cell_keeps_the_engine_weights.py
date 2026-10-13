# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""No weight table, or a table without the build's cell, leaves the engine's weights as they are."""
import pickle
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata.smart_build import _set_weights, get_standard_weights
from chardata.weight_table import (SCENARIO_ASPECTS, SCENARIOS, cell_table, element_key, grid_element_sets,
                                   load_weight_table, override_weight_table, table_cell)
from fashionistapulp.dofus_constants import CHARACTER_CLASSES

VERSION = 'dofus3'
OTHER_CELL = ('Cra', ('agi',), 'plain')


def _char(char_class, level=200):
    return SimpleNamespace(char_class=char_class, level=level, game_version=VERSION, minimum_stats=None)


def _grid():
    for char_class in CHARACTER_CLASSES:
        for played in grid_element_sets():
            for scenario in SCENARIOS:
                yield char_class, played, scenario, set(played) | SCENARIO_ASPECTS[scenario]


class AnEmptyOrForeignTableChangesNothingTests(SimpleTestCase):

    def _assert_engine_everywhere(self, table, held=None):
        with override_weight_table(VERSION, table):
            for char_class, played, scenario, aspects in _grid():
                if (char_class, played, scenario) == held:
                    continue
                char = _char(char_class)
                with self.subTest(char_class=char_class, elements=element_key(played), scenario=scenario):
                    self.assertEqual(_set_weights(char, aspects, apply=False, table=False),
                                     _set_weights(char, aspects, apply=False))

    def test_no_table_gives_the_engine_weights_on_the_whole_grid(self):
        self._assert_engine_everywhere({})

    def test_a_table_without_the_cell_gives_the_engine_weights_everywhere_else(self):
        char_class, played, scenario = OTHER_CELL
        self._assert_engine_everywhere(cell_table(char_class, played, scenario, {'pow': 9.0}), OTHER_CELL)

    def test_a_cell_of_the_engine_status_gives_the_engine_weights(self):
        table = cell_table('Iop', ('str',), 'plain', {'pow': 9.0})
        table['cells']['Iop']['str']['plain']['200']['status'] = 'engine'
        self._assert_engine_everywhere(table)

    def test_the_standard_weights_follow_the_same_rule(self):
        char = SimpleNamespace(char_class='Iop', level=200, game_version=VERSION, aspects=pickle.dumps({'str'}),
                               minimum_stats=None)
        with override_weight_table(VERSION, {}):
            self.assertEqual(get_standard_weights(char, table=False), get_standard_weights(char))


class AMissingCellIsLoggedAsInformationTests(SimpleTestCase):

    def test_a_loaded_table_without_the_cell_logs_at_info_level_only(self):
        char_class, played, scenario = OTHER_CELL
        table = cell_table(char_class, played, scenario, {'pow': 9.0})
        with override_weight_table(VERSION, table):
            with self.assertLogs('chardata.weight_table', level='INFO') as logged:
                self.assertIsNone(table_cell('Iop', {'str'}, 200, VERSION))
        self.assertEqual(['INFO'], [record.levelname for record in logged.records])
        self.assertIn('Iop', logged.output[0])

    def test_a_version_without_a_table_logs_nothing(self):
        with override_weight_table(VERSION, {}):
            with self.assertNoLogs('chardata.weight_table', level='INFO'):
                self.assertIsNone(table_cell('Iop', {'str'}, 200, VERSION))

    def test_the_shipped_file_is_read_without_an_error_when_it_exists(self):
        self.assertIsInstance(load_weight_table(VERSION), dict)
