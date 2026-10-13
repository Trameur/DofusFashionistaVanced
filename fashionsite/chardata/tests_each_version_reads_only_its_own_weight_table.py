# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A version reads the weight table of its own file, and the table of Dofus 3 never reaches another version."""
import os
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata.smart_build import _set_weights
from chardata.weight_table import (DIRECTORY, SCENARIO_ASPECTS, SCENARIOS, VERSIONS, cell_table, engine_ratios,
                                   load_weight_table, override_weight_table, table_cell)
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.game_versions import dofus_versions

OTHER_VERSIONS = ('beta', 'touch', 'retro', 'dofus2')
CLASSES = ('Iop', 'Cra', 'Xelor', 'Ecaflip', 'Osamodas')


def _char(version, char_class, level=200):
    return SimpleNamespace(char_class=char_class, level=level, game_version=version, minimum_stats=None)


def _full_table(char_class, played, scenario, version):
    """A cell whose every ratio is double the engine's."""
    ratios = {stat: 2 * ratio for stat, ratio in engine_ratios(char_class, played, scenario, version).items()}
    return cell_table(char_class, played, scenario, ratios)


class OnlyDofus3HasATableTests(SimpleTestCase):

    def test_the_tables_are_for_dofus_3_alone(self):
        self.assertEqual(('dofus3',), VERSIONS)

    def test_the_directory_holds_no_file_of_another_version(self):
        names = os.listdir(DIRECTORY) if os.path.isdir(DIRECTORY) else []
        self.assertLessEqual(set(names), {'dofus3.json'})

    def test_another_version_loads_an_empty_table(self):
        for version in OTHER_VERSIONS + ('', 'dofus3/../beta', '../dofus3', 'nope'):
            with self.subTest(version=version):
                self.assertEqual({}, load_weight_table(version))

    def test_every_playable_version_is_either_dofus_3_or_without_a_table(self):
        for version in dofus_versions():
            key = getattr(version, 'key', version)
            if key != 'dofus3':
                self.assertEqual({}, load_weight_table(key), key)


class ATableOfDofus3NeverReachesAnotherVersionTests(SimpleTestCase):

    def test_the_weights_of_every_other_version_ignore_it(self):
        for scenario in SCENARIOS:
            for char_class in CLASSES:
                table = _full_table(char_class, ('str',), scenario, 'dofus3')
                aspects = {'str'} | SCENARIO_ASPECTS[scenario]
                for version in OTHER_VERSIONS:
                    char = _char(version, char_class)
                    with self.subTest(version=version, char_class=char_class, scenario=scenario):
                        with override_weight_table('dofus3', table):
                            with_it = _set_weights(char, aspects, apply=False)
                        self.assertEqual(_set_weights(char, aspects, apply=False, table=False), with_it)

    def test_the_same_build_on_dofus_3_does_take_it(self):
        table = _full_table('Iop', ('str',), 'plain', 'dofus3')
        char = _char('dofus3', 'Iop')
        with override_weight_table('dofus3', table):
            with_it = _set_weights(char, {'str'}, apply=False)
        self.assertNotEqual(_set_weights(char, {'str'}, apply=False, table=False), with_it)

    def test_a_table_keyed_to_another_version_is_not_read_either(self):
        table = _full_table('Iop', ('str',), 'plain', 'dofus3')
        for version in OTHER_VERSIONS:
            char = _char(version, 'Iop')
            with self.subTest(version=version):
                with override_weight_table(version, table):
                    self.assertIsNone(table_cell('Iop', {'str'}, 200, version))
                    self.assertEqual(_set_weights(char, {'str'}, apply=False, table=False),
                                     _set_weights(char, {'str'}, apply=False))

    def test_an_override_of_one_version_leaves_the_others_on_their_own_file(self):
        with override_weight_table('beta', {'cells': {'Iop': {}}}):
            self.assertEqual(load_weight_table('dofus3'), load_weight_table('dofus3'))
            self.assertEqual({'cells': {'Iop': {}}}, load_weight_table('beta'))
        self.assertEqual({}, load_weight_table('beta'))

    def test_the_grid_classes_are_those_of_the_game(self):
        self.assertEqual(19, len(CHARACTER_CLASSES))
