# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The tuner reads final damage on the scale of its other reads, and the engine's weights stay as they were."""
import math
import pickle
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata import presets
from chardata import weight_tuning as tuning
from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.crit_curve import SetView
from chardata.models import Char
from chardata.smart_build import _set_weights
from chardata.spell_combo import castable_spells
from chardata.stats_weights import get_stats_weights, set_stats_weights
from chardata.weapon_terms import TurnReader
from chardata.weight_table import (FINAL_STAT, RESIST_STATS, SCENARIO_ASPECTS, TABLE_STATS, apply_weight_table,
                                   cell_table, engine_ratios, engine_stat_weight, engine_weights,
                                   override_weight_table, unit_of)
from fashionistapulp.dofus_constants import NON_STAT_WEIGHT_KEYS, STAT_NAME_TO_KEY
from fashionistapulp.item_effects import effect_term

VERSION = 'dofus3'
AP = 12
PLAYED = ['str', 'int']
LAM = 0.25
CLASSES = ('Cra', 'Sram', 'Xelor')
CELLS = (('Iop', ('str',), 'plain'), ('Cra', ('agi',), 'glasscannon'), ('Ecaflip', ('int', 'agi'), 'tank'),
         ('Xelor', ('int', 'agi'), 'glasscannon'), ('Sacrier', ('str', 'cha'), 'plain'))


def _stats(**values):
    stats = {key: 0 for key in STAT_NAME_TO_KEY.values()}
    stats.update(values)
    return stats


STATS = _stats(str=700, int=650, cha=500, agi=450, pow=250, dam=40, earthdam=20, firedam=15, waterdam=10, airdam=10,
               neutdam=5, perspedam=12, perweadam=8, ch=30, cridam=40, ap=AP, hp=3200, vit=600)


def _totals(hp=3000, resist=20):
    totals = {key: resist for key in RESIST_STATS}
    totals['hp'] = hp
    return totals


class _Reader(object):
    """A turn of `base` that grows by `gain` per point of power."""

    game_version = VERSION
    ap = AP

    def __init__(self, base, gain=0.5):
        self.base = base
        self.gain = gain

    def cast(self, weapon=None, deltas=None, ap=None):
        total = self.base + self.gain * (deltas or {}).get('pow', 0)
        return total, [('hit', total)]

    def full(self, weapon=None, deltas=None):
        return self.cast(weapon, deltas)[0]


class _View(object):

    def __init__(self, reader, per_point=2.0, worn=object()):
        self.reader = reader
        self.worn = worn
        self._per_point = per_point

    def per_point(self, played):
        return self._per_point


def _real_view(char_class):
    spells = castable_spells(char_class, 200, VERSION)
    return SetView(TurnReader(STATS, spells, AP, VERSION, 200), None, STATS)


def _char(char_class, level=200):
    return SimpleNamespace(char_class=char_class, level=level, game_version=VERSION, minimum_stats=None)


def _weights(char_class, played, scenario, table):
    aspects = set(played) | SCENARIO_ASPECTS[scenario]
    with override_weight_table(VERSION, table):
        return _set_weights(_char(char_class), aspects, apply=False)


class TheTunerReadsAPointOfFinalDamageTests(SimpleTestCase):

    def _read(self, base, per_point, played=PLAYED[:1], lam=LAM, **view):
        return tuning.read_ratios(_View(_Reader(base), per_point, **view), _totals(), played, lam)

    def test_it_is_a_hundredth_of_the_turn_over_the_gain_of_a_characteristic(self):
        for base, per_point in ((1500.0, 2.0), (3200.0, 4.0), (900.0, 0.5)):
            with self.subTest(base=base, per_point=per_point):
                self.assertAlmostEqual(base / 100.0 / per_point, self._read(base, per_point).ratios[FINAL_STAT])

    def test_it_is_built_from_the_turn_and_the_gain_the_read_reports(self):
        read = self._read(1800.0, 3.0)
        self.assertAlmostEqual(read.turn / 100.0 / read.g_char, read.ratios[FINAL_STAT])

    def test_a_set_without_a_weapon_and_a_duo_read_it_too(self):
        self.assertAlmostEqual(7.5, self._read(1500.0, 2.0, worn=None).ratios[FINAL_STAT])
        self.assertAlmostEqual(7.5, self._read(1500.0, 2.0, played=PLAYED).ratios[FINAL_STAT])

    def test_lambda_does_not_move_it(self):
        low, high = (self._read(1500.0, 2.0, lam=lam).ratios[FINAL_STAT] for lam in (0.15, 0.4))
        self.assertEqual(low, high)

    def test_it_is_the_slope_the_reader_gives_a_point_of_final_damage(self):
        for char_class in CLASSES:
            view = _real_view(char_class)
            slope = (view.reader.full(view.worn, {FINAL_STAT: tuning.STEP}) - view.reader.full(view.worn)) / tuning.STEP
            read = tuning.read_ratios(view, _totals(), PLAYED, LAM)
            with self.subTest(char_class=char_class):
                self.assertGreater(slope, 0)
                self.assertGreater(view.per_point(PLAYED), 0)
                self.assertAlmostEqual(slope / view.per_point(PLAYED), read.ratios[FINAL_STAT], places=9)

    def test_it_is_a_stat_of_the_table_and_of_the_read(self):
        self.assertIn(FINAL_STAT, TABLE_STATS)
        self.assertIn(FINAL_STAT, tuning.READ_STATS)
        self.assertNotIn(FINAL_STAT, tuning.TURN_STATS)

    def test_the_blend_moves_it_like_any_other_stat(self):
        unit = unit_of(('str',), 'plain')
        blended = tuning.blend({FINAL_STAT: 8.0, 'pow': 1.0}, {FINAL_STAT: 5.0, 'pow': 1.0}, 0, unit)
        self.assertEqual(5.0, blended[FINAL_STAT])
        self.assertEqual(8.0, tuning.blend({FINAL_STAT: 8.0}, {FINAL_STAT: 5.0}, 0, unit, {FINAL_STAT})[FINAL_STAT])
        self.assertEqual(4.0, tuning.blend({FINAL_STAT: 8.0}, {FINAL_STAT: 1.0}, 0, unit)[FINAL_STAT])

    def test_a_pooled_entry_that_moved_is_applied_and_owned(self):
        entries = {FINAL_STAT: {'engine': 8.0, 'value': 5.0, 'weak': False}}
        self.assertEqual({FINAL_STAT: 5.0}, tuning.applied_ratios(entries))
        self.assertEqual([FINAL_STAT], tuning.owned_stats(entries))


BASE = 1500.0
GAIN = 2.0
WORN_FINALS = (0, 10, 25.5, -20)
SLOTS = {'str': 100, 'int': 0, 'cha': 0, 'agi': 0}


def _panel_turn(char, solution):
    """The panel's turn of a set whose power is the reader's: BASE plus GAIN per point of strength."""
    return BASE + GAIN * getattr(solution, '_extra', {}).get('str', 0)


def _credited(final, deltas=None):
    table = {'items': {'ring': {'site_ids': [1], 'equivalents': {FINAL_STAT: final}}}}
    solution = SimpleNamespace(item_list=[SimpleNamespace(id=1, item_added=True)])
    with mock.patch('chardata.presets._panel_turn', side_effect=_panel_turn):
        return tuning.credited_turn(SimpleNamespace(), solution, table, SLOTS, deltas)


class TheTunerReadsFinalDamageOnTheCreditedTurnTests(SimpleTestCase):

    def _read(self, final, played=PLAYED[:1]):
        return tuning.read_ratios(_View(_Reader(BASE), GAIN), _totals(), played, LAM, final)

    def test_a_worn_final_damage_divides_the_turn_by_one_hundred_plus_it(self):
        for final in WORN_FINALS:
            with self.subTest(final=final):
                self.assertAlmostEqual(BASE / (100.0 + final) / GAIN, self._read(final).ratios[FINAL_STAT])

    def test_a_set_that_wears_none_reads_the_hundredth_of_the_turn(self):
        self.assertAlmostEqual(BASE / 100.0 / GAIN, self._read(0).ratios[FINAL_STAT])
        read = tuning.read_ratios(_View(_Reader(BASE), GAIN), _totals(), PLAYED[:1], LAM)
        self.assertEqual(read.ratios, self._read(0).ratios)

    def test_the_more_it_wears_the_less_a_point_of_it_is_worth_against_a_characteristic(self):
        self.assertGreater(self._read(0).ratios[FINAL_STAT], self._read(40).ratios[FINAL_STAT])

    def test_no_other_ratio_moves_with_it(self):
        bare, worn = self._read(0).ratios, self._read(40).ratios
        self.assertEqual({stat: value for stat, value in bare.items() if stat != FINAL_STAT},
                         {stat: value for stat, value in worn.items() if stat != FINAL_STAT})

    def test_a_duo_reads_it_the_same(self):
        self.assertAlmostEqual(BASE / 125.0 / GAIN, self._read(25, PLAYED).ratios[FINAL_STAT])

    def test_a_worn_final_that_leaves_no_factor_reads_nothing(self):
        for final in (-100, -150):
            with self.subTest(final=final):
                self.assertIsNone(self._read(final))

    def test_it_is_the_ratio_of_the_two_slopes_of_the_credited_turn(self):
        for final in WORN_FINALS:
            per_final = _credited(final + 1) - _credited(final)
            per_point = _credited(final, {'str': 1}) - _credited(final)
            with self.subTest(final=final):
                self.assertAlmostEqual(BASE / 100.0, per_final)
                self.assertAlmostEqual(GAIN * (1 + final / 100.0), per_point)
                self.assertAlmostEqual(per_final / per_point, self._read(final).ratios[FINAL_STAT])

    def test_a_door_result_reads_with_the_final_its_set_wears(self):
        instance = SimpleNamespace(elements=('str',))
        result = tuning.DoorResult(instance, None, view=_View(_Reader(BASE), GAIN), totals=_totals(), final_worn=25)
        self.assertAlmostEqual(BASE / 125.0 / GAIN, result.read(LAM).ratios[FINAL_STAT])
        self.assertEqual(0, tuning.DoorResult(instance, None).final_worn)

    def test_the_runner_takes_the_final_from_the_effect_table_items_the_set_wears(self):
        runner = tuning.DoorRunner.__new__(tuning.DoorRunner)
        runner.structure = mock.Mock()
        runner.effect_table = {'items': {'ring': {'site_ids': [1], 'equivalents': {FINAL_STAT: 25}},
                                         'hat': {'site_ids': [2], 'equivalents': {FINAL_STAT: 10}}}}
        solution = SimpleNamespace(item_list=[SimpleNamespace(id=1, item_added=True, slot='ring'),
                                              SimpleNamespace(id=3, item_added=True, slot='cape')],
                                   get_stats_total=_totals)
        view = _View(_Reader(BASE), GAIN)
        result = tuning.DoorResult(SimpleNamespace(elements=('str',)), None)
        with mock.patch('chardata.solution.get_solution', return_value=solution), \
                mock.patch('chardata.solution.get_solver_facts', return_value=(True, 1.0, None)), \
                mock.patch('chardata.presets.guard_facts', return_value=None), \
                mock.patch('chardata.presets._panel_turn', side_effect=_panel_turn), \
                mock.patch('chardata.stats_weights.get_stats_weights', return_value=dict(SLOTS)), \
                mock.patch('chardata.weapon_terms.stat_lines_value', return_value=0), \
                mock.patch('chardata.crit_curve._set_view', return_value=view), \
                mock.patch.object(tuning, 'item_stat_sums', return_value={}), \
                mock.patch.object(tuning, 'power_share', return_value=None):
            runner._read(mock.Mock(level=200), result, 0)
        self.assertEqual(25, result.final_worn)
        self.assertAlmostEqual(BASE / 125.0 / GAIN, result.read(LAM).ratios[FINAL_STAT])
        self.assertAlmostEqual(BASE * 1.25, result.credit.turn)


class TheFitScoreSeesTheFinalDamageTheSetWearsTests(SimpleTestCase):

    def _fit(self, final):
        return tuning.fit_score(_View(_Reader(BASE), GAIN), _totals(), LAM, final)

    def test_it_is_the_log_of_the_credited_turn_plus_lambda_times_the_log_of_the_effective_hp(self):
        ehp = tuning.effective_hp(_totals())
        for final in WORN_FINALS:
            with self.subTest(final=final):
                self.assertAlmostEqual(math.log(_credited(final)) + LAM * math.log(ehp), self._fit(final))

    def test_without_a_worn_final_it_is_the_score_of_the_reader_alone(self):
        self.assertEqual(tuning.fit_score(_View(_Reader(BASE), GAIN), _totals(), LAM), self._fit(0))
        self.assertAlmostEqual(math.log(BASE) + LAM * math.log(tuning.effective_hp(_totals())), self._fit(0))

    def test_a_set_that_wears_more_scores_higher(self):
        self.assertGreater(self._fit(30), self._fit(0))

    def test_a_worn_final_that_leaves_no_factor_scores_nothing(self):
        for final in (-100, -150):
            with self.subTest(final=final):
                self.assertIsNone(self._fit(final))

    def test_a_door_result_scores_with_the_final_its_set_wears(self):
        result = tuning.DoorResult(SimpleNamespace(elements=('str',)), None, view=_View(_Reader(BASE), GAIN),
                                   totals=_totals(), final_worn=25)
        self.assertAlmostEqual(self._fit(25), result.u_fit(LAM))


class TheEffectTablePricesFinalDamageTests(SimpleTestCase):

    WEIGHTS = {'str': 100, 'int': 90, 'permedam': 30, 'perrandam': 50, 'ap': 1000}
    ENTRY = {'equivalents': {'final': 3}}

    def test_without_the_key_it_is_the_melee_and_the_ranged_lines_together(self):
        self.assertEqual(3 * 80, effect_term(self.ENTRY, self.WEIGHTS, 200))

    def test_with_the_key_it_is_the_key(self):
        weights = dict(self.WEIGHTS, final=45)
        self.assertEqual(3 * 45, effect_term(self.ENTRY, weights, 200))

    def test_the_key_at_zero_is_paid_at_zero(self):
        self.assertEqual(0, effect_term(self.ENTRY, dict(self.WEIGHTS, final=0), 200))

    def test_a_loss_of_final_damage_is_paid_the_same_way(self):
        entry = {'equivalents': {'final': -2}}
        self.assertEqual(-2 * 80, effect_term(entry, self.WEIGHTS, 200))
        self.assertEqual(-2 * 45, effect_term(entry, dict(self.WEIGHTS, final=45), 200))

    def test_the_other_equivalents_do_not_read_the_key(self):
        entry = {'equivalents': {'final': 2, 'ap': 0.5}}
        self.assertEqual(2 * 45 + 0.5 * 1000, effect_term(entry, dict(self.WEIGHTS, final=45), 200))

    def test_the_element_count_picks_its_own_final_damage_and_the_key_prices_it(self):
        entry = {'equivalents': {'final': 2}, 'equivalents_by_elements': {'2': {'final': 3}}}
        weights = dict(self.WEIGHTS, final=45)
        self.assertEqual(3 * 45, effect_term(entry, weights, 200))
        self.assertEqual(2 * 45, effect_term(entry, dict(weights, int=60), 200))


class TheEngineRatioOfFinalDamageTests(SimpleTestCase):

    def test_the_engine_has_no_weight_for_it_and_its_ratio_is_the_two_lines_over_the_unit(self):
        for char_class, played, scenario in CELLS:
            engine = engine_weights(char_class, played, scenario, VERSION)
            ratios = engine_ratios(char_class, played, scenario, VERSION)
            with self.subTest(char_class=char_class, elements=played, scenario=scenario):
                self.assertNotIn(FINAL_STAT, engine)
                self.assertEqual(engine['permedam'] + engine['perrandam'], engine_stat_weight(engine, FINAL_STAT))
                self.assertGreater(ratios[FINAL_STAT], 0)
                self.assertAlmostEqual((engine['permedam'] + engine['perrandam']) / float(unit_of(played, scenario)),
                                       ratios[FINAL_STAT])

    def test_every_other_table_stat_keeps_its_own_weight(self):
        engine = engine_weights('Iop', ('str',), 'plain', VERSION)
        for stat in set(TABLE_STATS) - {FINAL_STAT}:
            with self.subTest(stat=stat):
                self.assertEqual(engine[stat], engine_stat_weight(engine, stat))


class TheTableWritesFinalDamageAndNothingAroundItTests(SimpleTestCase):

    def _doubled(self, char_class, played, scenario):
        engine = engine_weights(char_class, played, scenario, VERSION)
        ratio = 2.0 * (engine['permedam'] + engine['perrandam']) / unit_of(played, scenario)
        return engine, _weights(char_class, played, scenario,
                                cell_table(char_class, played, scenario, {FINAL_STAT: ratio}))

    def test_a_cell_sets_it_to_the_ratio_times_the_unit(self):
        for char_class, played, scenario in CELLS:
            engine, table = self._doubled(char_class, played, scenario)
            with self.subTest(char_class=char_class, elements=played, scenario=scenario):
                self.assertEqual(2 * (engine['permedam'] + engine['perrandam']), table[FINAL_STAT])

    def test_the_melee_and_the_ranged_lines_stay_the_engines(self):
        for char_class, played, scenario in CELLS:
            engine, table = self._doubled(char_class, played, scenario)
            for stat in ('permedam', 'perrandam'):
                with self.subTest(char_class=char_class, elements=played, scenario=scenario, stat=stat):
                    self.assertEqual(engine[stat], table[stat])

    def test_nothing_else_moves(self):
        for char_class, played, scenario in CELLS:
            engine, table = self._doubled(char_class, played, scenario)
            with self.subTest(char_class=char_class, elements=played, scenario=scenario):
                self.assertEqual(set(engine) | {FINAL_STAT}, set(table))
                self.assertEqual(engine, {stat: value for stat, value in table.items() if stat != FINAL_STAT})

    def test_a_cell_at_the_engine_ratios_prices_it_as_the_engine_does(self):
        for char_class, played, scenario in CELLS:
            engine = engine_weights(char_class, played, scenario, VERSION)
            ratios = engine_ratios(char_class, played, scenario, VERSION)
            table = _weights(char_class, played, scenario, cell_table(char_class, played, scenario, ratios))
            with self.subTest(char_class=char_class, elements=played, scenario=scenario):
                self.assertEqual(engine['permedam'] + engine['perrandam'], table[FINAL_STAT])
                self.assertEqual(engine, {stat: value for stat, value in table.items() if stat != FINAL_STAT})

    def test_a_weak_entry_writes_nothing(self):
        table = cell_table('Iop', ('str',), 'plain', {FINAL_STAT: 5.0})
        table['cells']['Iop']['str']['plain']['200']['ratios'][FINAL_STAT]['weak'] = True
        self.assertNotIn(FINAL_STAT, _weights('Iop', ('str',), 'plain', table))

    def test_a_cell_that_does_not_carry_it_leaves_the_key_out(self):
        self.assertNotIn(FINAL_STAT, _weights('Iop', ('str',), 'plain', cell_table('Iop', ('str',), 'plain',
                                                                                    {'pow': 1.0})))

    def test_an_empty_table_leaves_the_engine_weights_and_no_key(self):
        for char_class, played, scenario in CELLS:
            engine = engine_weights(char_class, played, scenario, VERSION)
            for table in (None, {}):
                with self.subTest(char_class=char_class, elements=played, scenario=scenario, table=table):
                    weights = _weights(char_class, played, scenario, table)
                    self.assertEqual(engine, weights)
                    self.assertNotIn(FINAL_STAT, weights)

    def test_a_build_without_a_cell_keeps_the_engine_weights_and_no_key(self):
        engine = engine_weights('Iop', ('str',), 'plain', VERSION)
        table = cell_table('Cra', ('agi',), 'plain', {FINAL_STAT: 5.0})
        weights = _weights('Iop', ('str',), 'plain', table)
        self.assertEqual(engine, weights)
        self.assertNotIn(FINAL_STAT, weights)

    def test_apply_weight_table_reports_it_only_when_a_cell_applies(self):
        engine = engine_weights('Iop', ('str',), 'plain', VERSION)
        unit = unit_of(('str',), 'plain')
        with override_weight_table(VERSION, None):
            w = dict(engine)
            self.assertEqual([], apply_weight_table(w, _char('Iop'), {'str'}, unit, {}))
            self.assertEqual(engine, w)
        with override_weight_table(VERSION, cell_table('Iop', ('str',), 'plain', {FINAL_STAT: 5.0})):
            w = dict(engine)
            self.assertEqual([FINAL_STAT], apply_weight_table(w, _char('Iop'), {'str'}, unit, {}))
            self.assertEqual(5.0 * unit, w[FINAL_STAT])
            self.assertEqual(engine, {stat: value for stat, value in w.items() if stat != FINAL_STAT})


class TheStoredWeightsKeepItTests(SimpleTestCase):

    def test_it_is_a_weight_key_that_no_stat_carries(self):
        self.assertIn(FINAL_STAT, NON_STAT_WEIGHT_KEYS)
        self.assertNotIn(FINAL_STAT, STAT_NAME_TO_KEY.values())

    def test_a_build_stores_it_and_reads_it_back(self):
        table = cell_table('Iop', ('str',), 'plain', {FINAL_STAT: 5.0})
        weights = _weights('Iop', ('str',), 'plain', table)
        char = SimpleNamespace(stats_weight=pickle.dumps(weights), id=1, save=lambda: None)
        stored = get_stats_weights(char, persist=False)
        self.assertEqual(weights[FINAL_STAT], stored[FINAL_STAT])
        set_stats_weights(char, dict(stored))
        self.assertEqual(weights[FINAL_STAT], get_stats_weights(char, persist=False)[FINAL_STAT])

    def test_a_build_saved_without_it_reads_back_without_it(self):
        weights = _weights('Iop', ('str',), 'plain', None)
        char = SimpleNamespace(stats_weight=pickle.dumps(weights), id=1, save=lambda: None)
        self.assertNotIn(FINAL_STAT, get_stats_weights(char, persist=False))


class AnEditOfTheMeleeOrRangedLineDropsTheStaleFinalTests(SimpleTestCase):

    def _stored(self):
        weights = _weights('Iop', ('str',), 'plain', cell_table('Iop', ('str',), 'plain', {FINAL_STAT: 5.0}))
        return SimpleNamespace(stats_weight=pickle.dumps(weights), id=1, save=lambda: None), weights

    def _saved(self, char, weights):
        set_stats_weights(char, weights)
        return read_char_blob(char.stats_weight, {}, 'stats_weight')

    def test_an_edit_of_either_line_leaves_the_price_to_the_lines(self):
        for line in ('permedam', 'perrandam'):
            char, weights = self._stored()
            with self.subTest(line=line):
                after = self._saved(char, dict(weights, **{line: weights[line] + 10}))
                self.assertEqual(weights[line] + 10, after[line])
                self.assertNotIn(FINAL_STAT, after)

    def test_an_edit_of_another_stat_keeps_it(self):
        char, weights = self._stored()
        after = self._saved(char, dict(weights, vit=weights['vit'] + 7))
        self.assertEqual(weights['vit'] + 7, after['vit'])
        self.assertEqual(weights[FINAL_STAT], after[FINAL_STAT])

    def test_a_save_that_changes_nothing_keeps_it(self):
        char, weights = self._stored()
        self.assertEqual(weights[FINAL_STAT], self._saved(char, dict(weights))[FINAL_STAT])

    def test_a_reset_that_brings_a_fresh_one_keeps_the_fresh_one(self):
        char, weights = self._stored()
        fresh = dict(weights, permedam=weights['permedam'] + 10, **{FINAL_STAT: 2 * weights[FINAL_STAT]})
        self.assertEqual(2 * weights[FINAL_STAT], self._saved(char, fresh)[FINAL_STAT])

    def test_a_build_that_never_had_it_gets_none_from_an_edit(self):
        weights = _weights('Iop', ('str',), 'plain', None)
        char = SimpleNamespace(stats_weight=pickle.dumps(weights), id=1, save=lambda: None)
        self.assertNotIn(FINAL_STAT, self._saved(char, dict(weights, permedam=weights['permedam'] + 10)))


class ABalancedBuildWithoutTheKeyDoesNotPriceFinalDamageAtZeroTests(TestCase):

    def test_a_priority_cell_that_carries_it_over_a_balanced_cell_that_does_not(self):
        owner = User.objects.create_user('balfinal', 'bf@test.local', 'pw-bal-31')
        request = RequestFactory().post('/')
        request.user = owner
        with override_weight_table(VERSION, cell_table('Iop', ('str',), 'glasscannon', {FINAL_STAT: 5.0})):
            char = create_build(request, 'Iop', 200, {'str'}, VERSION)
            presets.apply_setup_choices(char, {'str'}, priority='damage', set_minimums=False)
            weights = get_stats_weights(char, persist=False)
            self.assertIn(FINAL_STAT, weights)
            balanced = presets.balanced_weights(char, dict(weights, vit=weights['vit'] + 7))
        self.assertNotIn(FINAL_STAT, balanced)
        self.assertEqual(3 * (balanced['permedam'] + balanced['perrandam']),
                         effect_term({'equivalents': {FINAL_STAT: 3}}, balanced, 200))


class TheWeightsPageKeepsItTests(TestCase):

    def test_saving_the_page_keeps_the_stored_key_and_does_not_show_it(self):
        from chardata.weights_minimums import page_state
        weights = _weights('Iop', ('str',), 'plain', cell_table('Iop', ('str',), 'plain', {FINAL_STAT: 5.0}))
        owner = User.objects.create_user('finalkey', 'fk@test.local', 'pw-final-84')
        char = Char.objects.create(
            name='Fk', char_name='fk', char_class='Iop', char_build='build', level=200, minimum_stats=b'',
            minimum_crits=b'', stats_weight=pickle.dumps(weights), options=b'', inclusions=b'', exclusions=b'',
            aspects=pickle.dumps({'str'}), owner=owner, link_shared=False, game_version=VERSION)
        shown = get_stats_weights(char)
        self.assertNotIn(FINAL_STAT, page_state(char)['weights'])
        posted = {'weight_%s' % key: str(int(value)) for key, value in shown.items() if key not in NON_STAT_WEIGHT_KEYS}
        posted['weight_vit'] = '77'
        self.client.force_login(owner)
        self.assertEqual(200, self.client.post('/statspost/%d/' % char.id, posted).status_code)
        after = read_char_blob(Char.objects.get(id=char.id).stats_weight, {}, 'stats_weight')
        self.assertEqual(77, after['vit'])
        self.assertEqual(weights[FINAL_STAT], after[FINAL_STAT])
