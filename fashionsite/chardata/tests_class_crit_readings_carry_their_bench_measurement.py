# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A class crit reading names its anchor rule, and a typed scale carries the bench measurement behind it."""
import statistics
from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.crit_curve import ANCHORS, ENVELOPE_WIDTH, _style_of, class_reading, crit_hinges, ranked_weapons
from chardata.data_versions import current_data_version
from chardata.presets import STYLE_BY_KEY, VERSION_PRESETS
from chardata.smart_build import RACE_PROFILE_OVERRIDES_BY_VERSION, _set_weights
from chardata.weapon_terms import TurnReader, weapon_hit_terms, weapon_swing
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES, MAIN_STATS, STAT_KEY_TO_NAME, STAT_NAME_TO_KEY,
                                             STATS_NAMES)
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal
from fashionistapulp.structure import get_structure, set_current_game_version

TABLE = RACE_PROFILE_OVERRIDES_BY_VERSION['dofus3']
MEASUREMENT = {'value', 'builds', 'n', 'spread', 'data', 'date', 'source', 'weak'}
READING_FIELDS = {'anchor', 'scale'}
STYLE_KEYS = {'balanced', 'all_presets'} | set(STYLE_BY_KEY)
ELEMENTS = {'agi', 'int'}
PRESET_ASPECTS = {'balanced': ELEMENTS, 'solo_pvm': ELEMENTS | {'glasscannon'}}

CAPTAIN_CHAFERS_DAGGERS = 30855
# The first set of a level 200 Xelor agi/int solve, and the points its build holds on top of the pieces
FIRST_SET = {'dofus1': 694, 'dofus2': 7043, 'dofus3': 7112, 'dofus4': 7754, 'dofus5': 18043, 'dofus6': 22013,
             'shield': 18715, 'cloak': 19979, 'hat': 19980, 'ring1': 24035, 'ring2': 24035, 'belt': 30856,
             'boots': 30857, 'weapon': 33607, 'amulet': 33608, 'pet': 1033285}
OWN = {'ap': 8, 'mp': 4, 'agi': 365, 'int': 366, 'str': 100, 'cha': 100, 'vit': 100, 'wis': 100, 'summon': 1}


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

    def test_every_scale_is_a_positive_number(self):
        for char_class, key, style, value in _readings(TABLE):
            if 'scale' in value:
                with self.subTest(char_class=char_class, key=key, style=style):
                    self.assertIsInstance(value['scale']['value'], (int, float))
                    self.assertGreater(value['scale']['value'], 0)

    def test_the_only_entry_is_the_xelor_agi_int_weapon_envelope(self):
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

    def test_an_entry_for_all_presets_is_read_as_balanced_whatever_the_style(self):
        table = {'Iop': {'str': {'crit_reading': {'all_presets': {'anchor': 'weapon_envelope'}}}}}
        with mock.patch.dict(TABLE, table), mock.patch('chardata.crit_curve._style_of') as style_of:
            for aspects in ({'str'}, {'str', 'glasscannon'}, {'str', 'vit', 'res'}, {'str', 'wis', 'pp'}):
                self.assertEqual({'anchor': 'weapon_envelope'}, class_reading('Iop', aspects))
        style_of.assert_not_called()

    def test_the_style_is_the_first_of_the_version_whose_aspects_the_build_holds(self):
        for aspects, style in (({'glasscannon'}, 'solo_pvm'), ({'vit', 'res'}, 'group_pvm'),
                               ({'pvp', 'crit'}, 'pvp'), ({'wis', 'pp'}, 'farm'),
                               ({'glasscannon', 'wis', 'pp'}, 'solo_pvm'), ({'vit'}, 'balanced'), (set(), 'balanced')):
            with self.subTest(aspects=aspects):
                self.assertEqual(style, _style_of(aspects, 'dofus3'))

    def test_a_scale_that_is_not_a_positive_number_gives_the_default(self):
        for scale in (_measured(value=0), _measured(value=-1.5), _measured(value=float('nan')),
                      _measured(value=float('inf')), _measured(value=True), _measured(value='2'),
                      {}, 1.3, None):
            table = {'Iop': {'str': {'crit_reading': {'all_presets': {'anchor': 'weapon_envelope',
                                                                      'scale': scale}}}}}
            with self.subTest(scale=scale), mock.patch.dict(TABLE, table), \
                    self.assertLogs('chardata.crit_curve', 'ERROR'):
                self.assertEqual({}, class_reading('Iop', {'str'}))

    def test_a_positive_scale_is_served_with_its_entry(self):
        scale = _measured()
        entry = {'anchor': 'weapon_envelope', 'scale': scale}
        table = {'Iop': {'str': {'crit_reading': {'all_presets': entry}}}}
        with mock.patch.dict(TABLE, table):
            self.assertEqual(entry, class_reading('Iop', {'str'}))


def _solved_as_it_stands(char, minimal, refresh_base_stats=True):
    return model_result_from_minimal(minimal)


class _Xelor(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')

    def the_set(self, game_version='dofus3', preset='balanced'):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({STAT_KEY_TO_NAME[key]: value for key, value in OWN.items()})
        given = {'options': {'ap_exo': False, 'mp_exo': False, 'range_exo': False},
                 'base_stats_by_attr': base, 'char_level': 200, 'origin': 'generated'}
        result = ModelResultMinimal(dict(FIRST_SET), given, {})
        weights = _set_weights(SimpleNamespace(char_class='Xelor', level=200, game_version='dofus3'),
                               PRESET_ASPECTS[preset], apply=False)
        model_input = SimpleNamespace(objective_values=weights, forbidden_equips=set(), locked_equips={},
                                      empty_slot_types=[])
        char = SimpleNamespace(id=1, game_version=game_version, char_class='Xelor', level=200)
        return char, result, model_input

    def terms(self, preset='balanced'):
        char, result, model_input = self.the_set(preset=preset)
        with mock.patch('chardata.solution.get_solution_from_minimal', side_effect=_solved_as_it_stands):
            return weapon_hit_terms(char, result, model_input)

    def read(self, game_version='dofus3', table=None, aspects=None, preset='balanced'):
        char, result, model_input = self.the_set(game_version, preset)
        weights = model_input.objective_values
        aspects = PRESET_ASPECTS[preset] if aspects is None else aspects
        with mock.patch('chardata.crit_curve.get_char_aspects', return_value=set(aspects)), \
                mock.patch('chardata.crit_curve.get_standard_weights', return_value=dict(weights)), \
                mock.patch('chardata.crit_curve.get_stats_weights', return_value=dict(weights)), \
                mock.patch('chardata.solution.get_solution_from_minimal', side_effect=_solved_as_it_stands), \
                mock.patch.dict(TABLE, table or {}):
            return crit_hinges(char, result, model_input, weapon_hit_terms(char, result, model_input))


class TheEnvelopeIsWorthItTests(_Xelor):

    def alone(self, preset='balanced'):
        return self.read(table={'Xelor': {}}, preset=preset)

    def test_a_weapon_without_crit_leads_the_terms_over_weapons_with_crit(self):
        stats = {key: 0 for key in STAT_NAME_TO_KEY.values()}
        structure = get_structure('dofus3')
        for preset in PRESET_ASPECTS:
            with self.subTest(preset=preset):
                char, _result, model_input = self.the_set(preset=preset)
                ranked = ranked_weapons(self.terms(preset), model_input, char.game_version)
                crit_rates = [weapon_swing(structure.get_item_by_id(item_id), stats).crit_rate
                              for item_id in ranked[:ENVELOPE_WIDTH]]
                self.assertEqual(CAPTAIN_CHAFERS_DAGGERS, ranked[0])
                self.assertEqual(0, crit_rates[0])
                self.assertTrue(all(rate > 0 for rate in crit_rates[1:]))

    def test_the_first_slope_of_the_envelope_exceeds_the_one_of_the_weapon_alone(self):
        for preset in PRESET_ASPECTS:
            with self.subTest(preset=preset):
                envelope, alone = self.read(preset=preset), self.alone(preset)
                self.assertGreater(envelope.ch, alone.ch)
                self.assertGreater(envelope.cridam, alone.cridam)

    def test_the_envelope_is_the_reading_the_class_entry_asks_for(self):
        table = {'Xelor': {'agi/int': {'crit_reading': {'all_presets': {'anchor': 'top_weapon'}}}}}
        for preset in PRESET_ASPECTS:
            with self.subTest(preset=preset):
                self.assertEqual(self.alone(preset), self.read(table=table, preset=preset))
                self.assertNotEqual(self.alone(preset), self.read(preset=preset))

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
