# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A table cell the hook cannot read, a value that is not finite or a malformed shape, gives the engine's weights."""
import pickle
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata.smart_build import _set_weights
from chardata.weight_table import SCENARIO_ASPECTS, cell_table, override_weight_table

VERSION = 'dofus3'
CELL = ('Iop', ('str',), 'glasscannon')


def _char():
    return SimpleNamespace(char_class=CELL[0], level=200, game_version=VERSION, minimum_stats=None)


def _aspects():
    return set(CELL[1]) | SCENARIO_ASPECTS[CELL[2]]


def _cell(table):
    char_class, played, scenario = CELL
    return table['cells'][char_class][played[0]][scenario]['200']


class AnUnreadableCellKeepsTheEngineWeightsTests(SimpleTestCase):

    def _weights(self, table):
        with override_weight_table(VERSION, table):
            return _set_weights(_char(), _aspects(), apply=False)

    def _engine(self):
        return _set_weights(_char(), _aspects(), apply=False, table=False)

    def test_a_readable_cell_moves_the_weight_it_reads(self):
        self.assertNotEqual(self._engine()['pow'], self._weights(cell_table(*CELL, {'pow': 9.0}))['pow'])

    def test_a_value_that_is_not_finite_keeps_the_engine_value(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value):
                self.assertEqual(self._engine(), self._weights(cell_table(*CELL, {'pow': value})))

    def test_a_ratio_entry_that_is_not_a_mapping_keeps_every_engine_value(self):
        table = cell_table(*CELL, {'pow': 9.0, 'vit': 3.0})
        _cell(table)['ratios']['vit'] = 'unreadable'
        with self.assertLogs('chardata.smart_build', 'ERROR'):
            self.assertEqual(self._engine(), self._weights(table))

    def test_a_table_that_is_not_a_mapping_keeps_the_engine_weights(self):
        with self.assertLogs('chardata.smart_build', 'ERROR'):
            self.assertEqual(self._engine(), self._weights(['not', 'a', 'table']))

    def test_the_standard_weights_of_a_build_follow_the_same_rule(self):
        from chardata.smart_build import get_standard_weights
        char = SimpleNamespace(char_class=CELL[0], level=200, game_version=VERSION, aspects=pickle.dumps(_aspects()),
                               minimum_stats=None)
        with override_weight_table(VERSION, cell_table(*CELL, {'pow': float('nan')})):
            self.assertEqual(get_standard_weights(char, table=False), get_standard_weights(char))
