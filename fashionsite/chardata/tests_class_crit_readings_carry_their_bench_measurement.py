# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A class crit reading names its anchor rule, and a typed scale carries the bench measurement behind it."""
import statistics
from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.crit_curve import ANCHORS, ENVELOPE_WIDTH, class_reading, crit_hinges
from chardata.data_versions import current_data_version
from chardata.presets import STYLE_BY_KEY, VERSION_PRESETS
from chardata.smart_build import RACE_PROFILE_OVERRIDES_BY_VERSION
from chardata.weapon_terms import TurnReader, weapon_swing
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES, MAIN_STATS, STAT_KEY_TO_NAME, STAT_NAME_TO_KEY,
                                             STATS_NAMES)
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

TABLE = RACE_PROFILE_OVERRIDES_BY_VERSION['dofus3']
MEASUREMENT = {'value', 'builds', 'n', 'spread', 'data', 'date', 'source', 'weak'}
READING_FIELDS = {'anchor', 'scale'}
STYLE_KEYS = {'balanced', 'all_presets'} | set(STYLE_BY_KEY)
ELEMENTS = {'agi', 'int'}

CAPTAIN_CHAFERS_DAGGERS = 30855
ATCHAM_SABRES = 17586
FLINTY_DAGGERS = 14132
DREGGON_DAGGERS = 8414
OWN = {'agi': 800, 'int': 800, 'pow': 250, 'ch': -14, 'cridam': 40, 'ap': 12}
WEIGHTS = {'str': 0, 'int': 110, 'cha': 0, 'agi': 120, 'ch': 240, 'cridam': 100}
TERMS = {CAPTAIN_CHAFERS_DAGGERS: 100000.0, ATCHAM_SABRES: 50000.0, FLINTY_DAGGERS: 20000.0}


def _measurement_flaws(scale):
    """What is wrong with the measurement a scale carries, [] when it is whole."""
    if not isinstance(scale, dict) or set(scale) != MEASUREMENT:
        return ['not a measurement']
    builds = list(scale['builds'].values())
    if not builds:
        return ['no builds']
    wanted = {'value': statistics.median(builds), 'n': len(builds), 'spread': (min(builds), max(builds)),
              'weak': len(builds) <= 2, 'data': current_data_version('dofus3')}
    flaws = [key for key, value in wanted.items()
             if (tuple(scale[key]) if key == 'spread' else scale[key]) != value]
    try:
        date.fromisoformat(scale['date'])
    except (TypeError, ValueError):
        flaws.append('date')
    if not str(scale['source']).startswith('bench/'):
        flaws.append('source')
    return flaws


def _measured(builds=None, **changes):
    builds = {'huz-1': 1.5, 'huz-2': 2.5, 'huz-3': 2.0} if builds is None else builds
    scale = {'value': statistics.median(builds.values()), 'builds': builds, 'n': len(builds),
             'spread': (min(builds.values()), max(builds.values())), 'data': current_data_version('dofus3'),
             'date': '2026-10-11', 'source': 'bench/crit6fd_2026-10-11/results_6fd_84.json',
             'weak': len(builds) <= 2}
    scale.update(changes)
    return scale


def _holds(node, key):
    return isinstance(node, dict) and (key in node or any(_holds(child, key) for child in node.values()))


def _readings(table):
    """[(class, key, style, value)] of a class table."""
    for char_class, by_key in table.items():
        if char_class == 'default':
            continue
        for key, entry in by_key.items():
            for style, value in (entry.get('crit_reading') or {}).items():
                yield char_class, key, style, value


class TheTableHoldsOnlyKnownReadingsTests(SimpleTestCase):

    def test_dofus_three_has_a_default_that_corrects_nothing(self):
        self.assertEqual({'crit_reading': None}, TABLE['default'])

    def test_every_entry_is_of_a_class_an_element_key_and_a_style_that_exist(self):
        entries = list(_readings(TABLE))
        self.assertTrue(entries)
        for char_class, key, style, _value in entries:
            with self.subTest(char_class=char_class, key=key, style=style):
                self.assertIn(char_class, CHARACTER_CLASSES)
                parts = key.split('/')
                self.assertTrue(key == 'all' or (set(parts) <= set(MAIN_STATS) and parts == sorted(parts)))
                self.assertIn(style, STYLE_KEYS)

    def test_every_entry_names_a_known_anchor_and_nothing_but_an_anchor_and_a_scale(self):
        for char_class, key, style, value in _readings(TABLE):
            with self.subTest(char_class=char_class, key=key, style=style):
                self.assertTrue(set(value) <= READING_FIELDS)
                self.assertIn(value.get('anchor', 'top_weapon'), ANCHORS)

    def test_every_scale_carries_its_measurement(self):
        for char_class, key, style, value in _readings(TABLE):
            if 'scale' in value:
                with self.subTest(char_class=char_class, key=key, style=style):
                    self.assertEqual([], _measurement_flaws(value['scale']))

    def test_the_one_entry_the_bench_kept_is_the_xelor_envelope(self):
        self.assertEqual([('Xelor', 'agi/int', 'all_presets', {'anchor': 'weapon_envelope'})],
                         list(_readings(TABLE)))

    def test_no_other_version_has_a_crit_reading(self):
        others = [version for version in RACE_PROFILE_OVERRIDES_BY_VERSION if version != 'dofus3']
        self.assertTrue({'beta', 'dofus2', 'touch', 'retro'} <= set(others))
        for version in others:
            with self.subTest(version=version):
                self.assertFalse(_holds(RACE_PROFILE_OVERRIDES_BY_VERSION[version], 'crit_reading'))


class TheMeasurementIsCheckedTests(SimpleTestCase):

    def test_a_whole_measurement_has_no_flaw(self):
        self.assertEqual([], _measurement_flaws(_measured()))
        self.assertEqual([], _measurement_flaws(_measured({'huz-1': 1.5, 'huz-2': 2.5})))

    def test_a_scale_without_a_measurement_is_flawed(self):
        for scale in (1.3, {'value': 1.3}, None):
            with self.subTest(scale=scale):
                self.assertTrue(_measurement_flaws(scale))

    def test_each_part_of_the_measurement_is_checked(self):
        changes = {'value': 2.1, 'n': 4, 'spread': (1.0, 2.5), 'weak': True, 'data': '3.0.0.0',
                   'date': 'yesterday', 'source': 'somewhere'}
        for key, wrong in changes.items():
            with self.subTest(key=key):
                self.assertEqual([key], _measurement_flaws(_measured(**{key: wrong})))

    def test_a_scale_over_two_builds_is_weak_and_over_three_is_not(self):
        self.assertEqual(['weak'], _measurement_flaws(_measured({'huz-1': 1.5, 'huz-2': 2.5}, weak=False)))
        self.assertEqual(['weak'], _measurement_flaws(_measured(weak=True)))


class TheResolutionTests(SimpleTestCase):

    def test_the_class_the_elements_and_the_style_give_the_entry(self):
        for aspects in ({'agi', 'int'}, {'int', 'agi'}, {'agi', 'int', 'glasscannon'}, {'agi', 'int', 'vit', 'res'}):
            with self.subTest(aspects=aspects):
                self.assertEqual({'anchor': 'weapon_envelope'}, class_reading('Xelor', aspects))

    def test_another_class_gets_the_default(self):
        for char_class in set(CHARACTER_CLASSES) - {'Xelor'}:
            with self.subTest(char_class=char_class):
                self.assertEqual({}, class_reading(char_class, {'agi', 'int'}))

    def test_other_elements_get_the_default(self):
        for aspects in ({'agi'}, {'int'}, {'str', 'agi'}, {'agi', 'int', 'cha'}, {'glasscannon'}, set()):
            with self.subTest(aspects=aspects):
                self.assertEqual({}, class_reading('Xelor', aspects))

    def test_another_version_gets_the_default(self):
        for version in ('beta', 'dofus2', 'touch', 'retro'):
            with self.subTest(version=version):
                self.assertEqual({}, class_reading('Xelor', {'agi', 'int'}, version))

    def test_one_element_reads_its_own_entry_before_all(self):
        table = {'Iop': {'str': {'crit_reading': {'all_presets': {'anchor': 'top_weapon'}}},
                         'all': {'crit_reading': {'all_presets': {'anchor': 'weapon_envelope'}}}}}
        with mock.patch.dict(TABLE, table):
            self.assertEqual({'anchor': 'top_weapon'}, class_reading('Iop', {'str'}))
            self.assertEqual({'anchor': 'weapon_envelope'}, class_reading('Iop', {'agi'}))
            self.assertEqual({'anchor': 'weapon_envelope'}, class_reading('Iop', {'str', 'agi'}))
            self.assertEqual({'anchor': 'weapon_envelope'}, class_reading('Iop', set()))

    def test_several_elements_read_their_sorted_combination_before_all(self):
        table = {'Iop': {'agi/str': {'crit_reading': {'all_presets': {'anchor': 'top_weapon'}}},
                         'all': {'crit_reading': {'all_presets': {'anchor': 'weapon_envelope'}}}}}
        with mock.patch.dict(TABLE, table):
            self.assertEqual({'anchor': 'top_weapon'}, class_reading('Iop', {'str', 'agi'}))
            self.assertEqual({'anchor': 'weapon_envelope'}, class_reading('Iop', {'str'}))

    def test_the_style_of_the_aspects_picks_the_value_and_balanced_is_the_rest(self):
        """A style without a value, and without all_presets, gets the default."""
        values = {'balanced': {'anchor': 'top_weapon'}, 'solo_pvm': {'anchor': 'weapon_envelope'},
                  'group_pvm': {'scale': _measured()}}
        table = {'Iop': {'str': {'crit_reading': values}}}
        with mock.patch.dict(TABLE, table):
            self.assertEqual(values['balanced'], class_reading('Iop', {'str'}))
            self.assertEqual(values['solo_pvm'], class_reading('Iop', {'str', 'glasscannon'}))
            self.assertEqual(values['group_pvm'], class_reading('Iop', {'str', 'vit', 'res'}))
            self.assertEqual({}, class_reading('Iop', {'str', 'pvp', 'crit'}))
        self.assertEqual({'glasscannon'}, STYLE_BY_KEY['solo_pvm'].aspects)
        self.assertEqual(['solo_pvm', 'group_pvm', 'pvp', 'farm'], list(VERSION_PRESETS['dofus3']['styles']))

    def test_all_presets_serves_the_styles_without_a_value(self):
        table = {'Iop': {'str': {'crit_reading': {'pvp': {'anchor': 'top_weapon'},
                                                  'all_presets': {'anchor': 'weapon_envelope'}}}}}
        with mock.patch.dict(TABLE, table):
            self.assertEqual({'anchor': 'weapon_envelope'}, class_reading('Iop', {'str', 'glasscannon'}))
            self.assertEqual({'anchor': 'weapon_envelope'}, class_reading('Iop', {'str'}))


class _Xelor(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')

    def read(self, game_version='dofus3', table=None, aspects=ELEMENTS):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({STAT_KEY_TO_NAME[key]: value for key, value in OWN.items()})
        given = {'options': {'ap_exo': False, 'mp_exo': False, 'range_exo': False},
                 'base_stats_by_attr': base, 'char_level': 200, 'origin': 'generated'}
        result = ModelResultMinimal({'weapon': DREGGON_DAGGERS}, given, {})
        model_input = SimpleNamespace(objective_values=dict(WEIGHTS), forbidden_equips=set(), locked_equips={},
                                      empty_slot_types=[])
        char = SimpleNamespace(id=1, game_version=game_version, char_class='Xelor', level=200)
        with mock.patch('chardata.crit_curve.get_char_aspects', return_value=set(aspects)), \
                mock.patch('chardata.crit_curve.get_standard_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.crit_curve.get_stats_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.solution.get_solution_from_minimal',
                           side_effect=lambda char, minimal, refresh_base_stats=True:
                           model_result_from_minimal(minimal)), \
                mock.patch.dict(TABLE, table or {}):
            return crit_hinges(char, result, model_input, TERMS)


class TheEnvelopeIsWorthItTests(_Xelor):

    def alone(self):
        return self.read(table={'Xelor': {}})

    def test_a_weapon_without_crit_leads_the_terms(self):
        stats = {key: 0 for key in STAT_NAME_TO_KEY.values()}
        structure = get_structure('dofus3')
        self.assertEqual(0, weapon_swing(structure.get_item_by_id(CAPTAIN_CHAFERS_DAGGERS), stats).crit_rate)
        self.assertGreater(weapon_swing(structure.get_item_by_id(ATCHAM_SABRES), stats).crit_rate, 0)
        self.assertLessEqual(len(TERMS), ENVELOPE_WIDTH)

    def test_the_first_slope_of_the_envelope_exceeds_the_one_of_the_weapon_alone(self):
        envelope, alone = self.read(), self.alone()
        self.assertGreater(envelope.ch, alone.ch)
        self.assertGreater(envelope.cridam, alone.cridam)

    def test_the_envelope_is_the_reading_the_class_entry_asks_for(self):
        table = {'Xelor': {'agi/int': {'crit_reading': {'all_presets': {'anchor': 'top_weapon'}}}}}
        self.assertEqual(self.alone(), self.read(table=table))
        self.assertNotEqual(self.alone(), self.read())

    def test_the_entry_does_not_reach_another_element_or_version(self):
        self.assertEqual(self.alone(), self.read(aspects={'agi'}))
        for game_version in ('beta', 'dofus2', 'touch', 'retro'):
            with self.subTest(game_version=game_version):
                with mock.patch.object(TurnReader, 'full') as full:
                    self.assertIsNone(self.read(game_version=game_version))
                full.assert_not_called()

    def test_a_scale_multiplies_the_slopes_and_the_price(self):
        scale = _measured({'huz-1': 1.5, 'huz-2': 2.5, 'huz-3': 2.0})
        table = {'Xelor': {'agi/int': {'crit_reading': {'all_presets': {'anchor': 'weapon_envelope',
                                                                        'scale': scale}}}}}
        plain, scaled = self.read(), self.read(table=table)
        self.assertAlmostEqual(plain.ch * scale['value'], scaled.ch, places=3)
        self.assertAlmostEqual(plain.cridam * scale['value'], scaled.cridam, places=3)
        self.assertEqual([crit for crit, _drop in plain.hinges], [crit for crit, _drop in scaled.hinges])
        for (_crit, drop), (_scaled, scaled_drop) in zip(plain.hinges, scaled.hinges):
            self.assertAlmostEqual(drop * scale['value'], scaled_drop, places=3)
