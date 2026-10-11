# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every door of the setup page maps to one weight scenario, or to none, and only the listed doors map to one."""
from itertools import combinations

from django.test import SimpleTestCase

from chardata.presets import FOCUS_COLUMNS, PLAY_MODES, PRIORITIES, STYLE_BY_KEY, solved_aspects, with_mode_boxes
from chardata.weight_table import (BANDS, SCENARIO_ASPECTS, SCENARIOS, cell_table, level_band, override_weight_table,
                                   table_cell, weight_scenario)
from fashionistapulp.dofus_constants import MAIN_STATS

VERSION = 'dofus3'
OTHER_VERSIONS = ('beta', 'touch', 'retro', 'dofus2')
NO_MODE_BOXES = ('general', 'pvm_solo')
FOCUS_BOXES = tuple(box for column in FOCUS_COLUMNS for box in column)
ELEMENT_CHOICES = ([()] + [(element,) for element in MAIN_STATS] + list(combinations(MAIN_STATS, 2))
                   + [('omni',), tuple(MAIN_STATS)])
UNMAPPED_BOXES = ('pvp', 'duel', 'crit', 'noncrit', 'heal', 'wis', 'pp', 'pods', 'dam', 'trap', 'summon', 'pushback',
                  'aprape', 'mprape')
# The three rows of the table of doors: (style, priority) pairs, with the default mode and no focus box
LISTED_DOORS = {'plain': [(None, 'balanced')],
                'glasscannon': [('solo_pvm', 'balanced'), ('solo_pvm', 'damage'), (None, 'damage')],
                'tank': [('group_pvm', 'balanced'), ('group_pvm', 'defense'), (None, 'defense')]}


def _door(elements, style, priority, mode, focus):
    """The aspects the weights of a door are solved from."""
    boxes = set(elements) | (STYLE_BY_KEY[style].aspects if style else set()) | set(focus)
    return solved_aspects(with_mode_boxes(boxes, mode), priority)


def _doors():
    modes = [mode.key for mode in PLAY_MODES]
    focuses = [()] + [(box,) for box in FOCUS_BOXES] + list(combinations(FOCUS_BOXES, 2))
    for elements in ELEMENT_CHOICES:
        for style in [None] + list(STYLE_BY_KEY):
            for priority in [priority.key for priority in PRIORITIES]:
                for mode in modes:
                    for focus in focuses:
                        yield elements, style, priority, mode, focus


class TheListedDoorsMapToTheirScenarioTests(SimpleTestCase):

    def test_each_listed_door_maps_to_its_scenario_for_every_element_choice(self):
        for scenario, doors in LISTED_DOORS.items():
            for style, priority in doors:
                for mode in NO_MODE_BOXES:
                    for elements in ELEMENT_CHOICES:
                        with self.subTest(scenario=scenario, style=style, priority=priority, mode=mode,
                                          elements=elements):
                            aspects = _door(elements, style, priority, mode, ())
                            self.assertEqual(scenario, weight_scenario(aspects, VERSION))

    def test_the_scenarios_are_the_three_rows(self):
        self.assertEqual(set(LISTED_DOORS), set(SCENARIOS))
        self.assertEqual({'plain': set(), 'glasscannon': {'glasscannon'}, 'tank': {'vit', 'res'}},
                         {name: set(aspects) for name, aspects in SCENARIO_ASPECTS.items()})

    def test_element_boxes_omni_and_balanced_do_not_change_the_scenario(self):
        for elements in ELEMENT_CHOICES:
            for extra in ((), ('balanced',)):
                with self.subTest(elements=elements, extra=extra):
                    self.assertEqual('plain', weight_scenario(set(elements) | set(extra), VERSION))


class EveryOtherDoorMapsToNoScenarioTests(SimpleTestCase):

    def test_a_door_maps_only_when_its_other_aspects_are_exactly_a_scenario(self):
        wanted = {frozenset(aspects): name for name, aspects in SCENARIO_ASPECTS.items()}
        mapped = 0
        for elements, style, priority, mode, focus in _doors():
            aspects = _door(elements, style, priority, mode, focus)
            others = frozenset(aspects) - set(MAIN_STATS) - {'omni', 'balanced'}
            expected = wanted.get(others)
            if weight_scenario(aspects, VERSION) != expected:
                self.fail('%s maps to %s, not %s' % (sorted(aspects), weight_scenario(aspects, VERSION), expected))
            mapped += expected is not None
        self.assertGreater(mapped, 0)

    def test_the_boxes_of_other_presets_map_to_none_alone_and_with_any_scenario(self):
        for box in UNMAPPED_BOXES:
            for scenario in SCENARIOS:
                with self.subTest(box=box, scenario=scenario):
                    aspects = {'str'} | SCENARIO_ASPECTS[scenario] | {box}
                    self.assertIsNone(weight_scenario(aspects, VERSION))

    def test_glasscannon_together_with_vit_and_res_maps_to_none(self):
        self.assertIsNone(weight_scenario({'int', 'glasscannon', 'vit', 'res'}, VERSION))
        self.assertIsNone(weight_scenario({'int', 'vit'}, VERSION))
        self.assertIsNone(weight_scenario({'int', 'res'}, VERSION))

    def test_a_mule_maps_to_none(self):
        for boxes in ({'wis'}, {'pp'}, {'wis', 'pp'}, {'pods'}, {'wis', 'pp', 'pods'}):
            with self.subTest(boxes=sorted(boxes)):
                self.assertIsNone(weight_scenario(boxes, VERSION))

    def test_the_other_versions_map_to_none(self):
        for version in OTHER_VERSIONS + (None, ''):
            for scenario in SCENARIOS:
                with self.subTest(version=version, scenario=scenario):
                    self.assertIsNone(weight_scenario({'str'} | SCENARIO_ASPECTS[scenario], version))


class AScenarioFindsItsCellOnlyAtTheGridTests(SimpleTestCase):

    def _table(self):
        cells = {scenario: {'status': 'shipped', 'ratios': {'pow': {'value': 1.0, 'weak': False}}}
                 for scenario in SCENARIOS}
        return {'cells': {'Iop': {'str': {scenario: {BANDS[0]: cell} for scenario, cell in cells.items()},
                                  'str+int': {scenario: {BANDS[0]: cell} for scenario, cell in cells.items()}}}}

    def test_one_or_two_elements_at_level_200_find_the_cell(self):
        with override_weight_table(VERSION, self._table()):
            for aspects in ({'str'}, {'str', 'int'}, {'str', 'glasscannon'}, {'int', 'str', 'vit', 'res'}):
                with self.subTest(aspects=sorted(aspects)):
                    self.assertIsNotNone(table_cell('Iop', aspects, 200, VERSION))

    def test_no_element_three_elements_omni_and_the_levels_below_200_find_no_cell(self):
        with override_weight_table(VERSION, self._table()):
            for aspects, level in (({'glasscannon'}, 200), (set(), 200), ({'str', 'int', 'cha'}, 200),
                                   ({'omni'}, 200), ({'str'}, 199), ({'str'}, 100), ({'str'}, 1)):
                with self.subTest(aspects=sorted(aspects), level=level):
                    self.assertIsNone(table_cell('Iop', aspects, level, VERSION))

    def test_another_version_finds_no_cell_in_the_dofus3_table(self):
        with override_weight_table(VERSION, self._table()):
            for version in OTHER_VERSIONS:
                self.assertIsNone(table_cell('Iop', {'str'}, 200, version))

    def test_the_level_band_starts_at_the_grid_level(self):
        self.assertEqual(BANDS[0], level_band(200))
        self.assertEqual(BANDS[0], level_band(230))
        self.assertIsNone(level_band(199))
        self.assertIsNone(level_band(None))

    def test_a_one_cell_table_serves_that_cell_alone(self):
        table = cell_table('Iop', ('str',), 'plain', {'pow': 1.0})
        with override_weight_table(VERSION, table):
            self.assertIsNotNone(table_cell('Iop', {'str'}, 200, VERSION))
            self.assertIsNone(table_cell('Iop', {'int'}, 200, VERSION))
            self.assertIsNone(table_cell('Cra', {'str'}, 200, VERSION))
            self.assertIsNone(table_cell('Iop', {'str', 'glasscannon'}, 200, VERSION))
