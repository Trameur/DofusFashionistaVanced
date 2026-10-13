# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A weight table sets the weights of the stats it reads, and nothing else changes, floors and clamps included."""
from itertools import combinations
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.char_blobs import read_char_blob
from chardata.smart_build import MULE_STATS, VERSION_WEIGHT_TUNING, _set_weights
from chardata.stats_weights import MAX_STAT_WEIGHT, set_stats_weights
from chardata.weight_table import (SCENARIO_ASPECTS, SHARE_STATS, TABLE_STATS, apply_weight_table, cell_table,
                                   engine_weights, override_weight_table, unit_of)

VERSION = 'dofus3'
CELLS = (('Iop', ('str',), 'plain'), ('Cra', ('agi',), 'glasscannon'), ('Ecaflip', ('int', 'agi'), 'tank'),
         ('Xelor', ('int', 'agi'), 'glasscannon'), ('Sacrier', ('str', 'cha'), 'plain'),
         ('Eniripsa', ('int',), 'tank'))
UNREAD = ('ch', 'cridam', 'permedam', 'perrandam', 'ap_before_floor')


def _char(char_class, level=200):
    return SimpleNamespace(char_class=char_class, level=level, game_version=VERSION, minimum_stats=None)


def _unit(count, scenario):
    return unit_of(range(count), scenario)


def _weights(char_class, played, scenario, table):
    aspects = set(played) | SCENARIO_ASPECTS[scenario]
    with override_weight_table(VERSION, table):
        return _set_weights(_char(char_class), aspects, apply=False)


def _doubled(char_class, played, scenario):
    """The cell whose ratios put every read stat at twice the engine's weight, a duo's shares left equal."""
    engine = engine_weights(char_class, played, scenario, VERSION)
    unit = _unit(len(played), scenario)
    ratios = {stat: 2.0 * engine[stat] / unit for stat in TABLE_STATS}
    if len(played) == 2:
        ratios.update({element: 1.0 for element in played})
    return engine, ratios


class TheReadStatsTakeTheTableTests(SimpleTestCase):

    def test_every_read_stat_is_twice_the_engine_weight(self):
        for char_class, played, scenario in CELLS:
            engine, ratios = _doubled(char_class, played, scenario)
            table = _weights(char_class, played, scenario, cell_table(char_class, played, scenario, ratios))
            for stat in TABLE_STATS:
                with self.subTest(char_class=char_class, elements=played, scenario=scenario, stat=stat):
                    self.assertEqual(2 * engine[stat], table[stat])

    def test_every_other_weight_is_the_engine_weight(self):
        for char_class, played, scenario in CELLS:
            engine, ratios = _doubled(char_class, played, scenario)
            table = _weights(char_class, played, scenario, cell_table(char_class, played, scenario, ratios))
            self.assertEqual(set(engine), set(table))
            for stat in set(engine) - set(TABLE_STATS):
                with self.subTest(char_class=char_class, elements=played, scenario=scenario, stat=stat):
                    self.assertEqual(engine[stat], table[stat])

    def test_the_crit_and_final_damage_weights_and_the_ap_floor_mark_stay_the_engines(self):
        for char_class, played, scenario in CELLS:
            engine, ratios = _doubled(char_class, played, scenario)
            table = _weights(char_class, played, scenario, cell_table(char_class, played, scenario, ratios))
            for stat in UNREAD:
                with self.subTest(char_class=char_class, stat=stat):
                    self.assertEqual(engine.get(stat), table.get(stat))

    def test_a_ratio_for_an_unread_stat_does_nothing(self):
        for stat in UNREAD + ('wis', 'mp', 'range', 'init', 'lock', 'dodge', 'heals'):
            engine = engine_weights('Iop', ('str',), 'plain', VERSION)
            table = cell_table('Iop', ('str',), 'plain', {stat: 7.0})
            with self.subTest(stat=stat):
                self.assertEqual(engine, _weights('Iop', ('str',), 'plain', table))

    def test_a_weak_or_non_numeric_entry_does_nothing(self):
        engine = engine_weights('Iop', ('str',), 'plain', VERSION)
        for entry in ({'value': 9.0, 'weak': True}, {'value': None, 'weak': False}, {'value': 'x', 'weak': False},
                      {'value': True, 'weak': False}, {'weak': False}):
            table = cell_table('Iop', ('str',), 'plain', {'pow': 1.0})
            table['cells']['Iop']['str']['plain']['200']['ratios']['pow'] = entry
            with self.subTest(entry=entry):
                self.assertEqual(engine, _weights('Iop', ('str',), 'plain', table))

    def test_the_weight_of_a_stat_is_the_ratio_times_the_unit_rounded(self):
        for ratio in (0.4, 1.0, 1.37, 3.3):
            table = cell_table('Iop', ('str',), 'plain', {'pow': ratio})
            with self.subTest(ratio=ratio):
                weights = _weights('Iop', ('str',), 'plain', table)
                self.assertEqual(int(round(ratio * _unit(1, 'plain'))), weights['pow'])


class TheFloorsAreReappliedOnceTests(SimpleTestCase):

    def test_equal_shares_give_the_engine_weights_floors_included(self):
        for char_class, played in (('Cra', ('int', 'agi')), ('Iop', ('cha', 'str')), ('Xelor', ('agi', 'cha'))):
            engine = engine_weights(char_class, played, 'plain', VERSION)
            table = cell_table(char_class, played, 'plain', {element: 1.0 for element in played})
            with self.subTest(char_class=char_class, elements=played):
                self.assertEqual(engine, _weights(char_class, played, 'plain', table))

    def test_a_tiny_agility_share_is_lifted_to_the_dodge_and_lock_floor(self):
        engine = engine_weights('Cra', ('int', 'agi'), 'plain', VERSION)
        table = cell_table('Cra', ('int', 'agi'), 'plain', {'int': 1.999, 'agi': 0.001})
        weights = _weights('Cra', ('int', 'agi'), 'plain', table)
        self.assertAlmostEqual((engine['dodge'] + engine['lock']) / 10.0, weights['agi'], delta=1)
        self.assertGreater(weights['agi'], 0.001 * _unit(2, 'plain'))

    def test_a_tiny_chance_share_gets_the_prospecting_floor_and_the_prospecting_share_once(self):
        engine = engine_weights('Iop', ('str', 'cha'), 'plain', VERSION)
        table = cell_table('Iop', ('str', 'cha'), 'plain', {'str': 1.999, 'cha': 0.001})
        weights = _weights('Iop', ('str', 'cha'), 'plain', table)
        pp = engine['pp']
        self.assertAlmostEqual(max(0.001 * _unit(2, 'plain'), pp / 10.0) + 0.1 * pp, weights['cha'], delta=1)

    def test_a_characteristic_the_table_does_not_write_keeps_its_engine_floor(self):
        engine = engine_weights('Cra', ('agi',), 'plain', VERSION)
        table = cell_table('Cra', ('agi',), 'plain', {'pow': 1.0})
        self.assertEqual(engine['agi'], _weights('Cra', ('agi',), 'plain', table)['agi'])


class TheSitesOwnRulesStillRunAfterTheTableTests(SimpleTestCase):

    def test_a_zeroed_stat_stays_zero(self):
        tuning = dict(VERSION_WEIGHT_TUNING.get(VERSION, {}), zero_stats=('perspedam', 'pow'))
        engine, ratios = _doubled('Iop', ('str',), 'plain')
        with mock.patch.dict(VERSION_WEIGHT_TUNING, {VERSION: tuning}):
            weights = _weights('Iop', ('str',), 'plain', cell_table('Iop', ('str',), 'plain', ratios))
        self.assertEqual(0, weights['perspedam'])
        self.assertEqual(0, weights['pow'])
        self.assertEqual(2 * engine['dam'], weights['dam'])

    def test_apply_weight_table_reports_only_the_keys_it_wrote(self):
        engine, ratios = _doubled('Cra', ('int', 'agi'), 'plain')
        w = dict(engine)
        char = _char('Cra')
        with override_weight_table(VERSION, cell_table('Cra', ('int', 'agi'), 'plain', ratios)):
            written = apply_weight_table(w, char, {'int', 'agi'}, _unit(2, 'plain'),
                                         {'zero_stats': ('perweadam',)})
        self.assertEqual(set(TABLE_STATS) - {'perweadam'} | set(SHARE_STATS) & {'int', 'agi'}, set(written))
        self.assertEqual(engine['perweadam'], w['perweadam'])

    def test_a_mule_is_never_touched(self):
        everything = {stat: 5.0 for stat in TABLE_STATS + SHARE_STATS}
        for count in (1, 2, 3):
            for boxes in combinations(sorted(MULE_STATS), count):
                aspects = set(boxes)
                char = _char('Iop')
                table = {'cells': {'Iop': {key: {scenario: {'200': {'status': 'shipped', 'ratios': {
                    stat: {'value': value, 'weak': False} for stat, value in everything.items()}}}
                    for scenario in SCENARIO_ASPECTS} for key in ('str', 'int', 'str+int')}}}
                with self.subTest(boxes=boxes):
                    with override_weight_table(VERSION, table):
                        self.assertEqual(_set_weights(char, aspects, apply=False, table=False),
                                         _set_weights(char, aspects, apply=False))

    def test_the_clamp_of_the_site_applies_to_the_stored_weights(self):
        engine, ratios = _doubled('Ecaflip', ('int', 'agi'), 'tank')
        weights = _weights('Ecaflip', ('int', 'agi'), 'tank', cell_table('Ecaflip', ('int', 'agi'), 'tank', ratios))
        self.assertGreater(weights['ap'], MAX_STAT_WEIGHT)
        char = SimpleNamespace(stats_weight=None, id=1, save=lambda: None)
        set_stats_weights(char, dict(weights))
        stored = read_char_blob(char.stats_weight, {}, 'stats_weight')
        self.assertEqual(MAX_STAT_WEIGHT, stored['ap'])
        self.assertTrue(all(abs(value) <= MAX_STAT_WEIGHT for value in stored.values()))
        self.assertEqual(weights['pow'], stored['pow'])
