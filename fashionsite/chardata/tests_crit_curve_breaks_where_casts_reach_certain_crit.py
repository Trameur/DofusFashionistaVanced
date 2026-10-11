# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The crit curve breaks where a throw reaches a certain crit and prices the points between the breaks."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.crit_curve import (SetView, concave_hull, crit_breakpoints, crit_hinges, read_curve,
                                 slopes_of)
from chardata.spell_combo import best_turn, castable_spells
from chardata.weapon_terms import CHARACTERISTIC_STEP, TurnReader, weapon_swing
from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY

MINOTOT_SCEPTRE = 8275
SRAMBAD_DAGGERS = 15493
AP = 12


def _stats(**values):
    stats = {key: 0 for key in STAT_NAME_TO_KEY.values()}
    stats.update(values)
    return stats


STATS = _stats(str=900, int=700, pow=250, ch=30, cridam=40, ap=AP)
WEIGHTS = {'str': 120, 'int': 110, 'cha': 0, 'agi': 30, 'ch': 240}
PLAYED = ['str', 'int']


def _weapon(item_id):
    from fashionistapulp.structure import get_structure
    return weapon_swing(get_structure('dofus3').get_item_by_id(item_id), STATS)


def _turn(spells, stats, worn=None):
    return best_turn(stats, spells + ([worn] if worn is not None else []), AP, standing={},
                     game_version='dofus3', pushback=False, caster_level=200)[0]


def _per_point(spells):
    raised = _turn(spells, dict(STATS, **{key: STATS[key] + CHARACTERISTIC_STEP for key in PLAYED}))
    return (raised - _turn(spells, STATS)) / float(CHARACTERISTIC_STEP * len(PLAYED))


class _Solution(object):

    def __init__(self, stats):
        self.items = {'Weapon': []}
        self._stats = stats

    def get_stats_total(self):
        return dict(self._stats)


def _read(char_class='Sram', level=200, game_version='dofus3', stored=None, aspects=None,
          weights=None):
    char = SimpleNamespace(id=1, game_version=game_version, char_class=char_class, level=level)
    weights = dict(WEIGHTS if weights is None else weights)
    with mock.patch('chardata.crit_curve.get_char_aspects', return_value=aspects or {'str'}), \
            mock.patch('chardata.crit_curve.get_standard_weights', return_value=dict(WEIGHTS)), \
            mock.patch('chardata.crit_curve.get_stats_weights',
                       return_value=dict(WEIGHTS if stored is None else stored)), \
            mock.patch('chardata.solution.get_solution_from_minimal',
                       return_value=_Solution(STATS)):
        return crit_hinges(char, object(), SimpleNamespace(objective_values=weights))


class _DofusThree(SimpleTestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')


class TheBreaksAreWhereACastReachesCertainCritTests(_DofusThree):

    def test_the_breaks_are_zero_and_a_hundred_less_each_rate_the_spells_carry(self):
        for char_class in ('Sram', 'Iop'):
            with self.subTest(char_class=char_class):
                spells = castable_spells(char_class, 200, 'dofus3')
                rates = {spell.crit_rate for spell in spells
                         if spell.crit_rate > 0 and spell.plain_alternatives}
                self.assertGreater(len(rates), 1)
                self.assertEqual(sorted({0} | {100 - rate for rate in rates}),
                                 crit_breakpoints(spells))

    def test_a_spell_without_a_rate_adds_no_break(self):
        spells = castable_spells('Sram', 200, 'dofus3')
        flat = [spell for spell in spells if spell.crit_rate == 0 and spell.plain_alternatives]
        self.assertTrue(flat)
        self.assertEqual([0], crit_breakpoints(flat))

    def test_a_spell_without_a_plain_line_adds_no_break(self):
        spells = castable_spells('Iop', 200, 'dofus3')
        bare = [spell for spell in spells if spell.crit_rate > 0 and not spell.plain_alternatives]
        self.assertTrue(bare)
        self.assertEqual([0], crit_breakpoints(bare))

    def test_a_throw_that_crits_for_certain_adds_no_break(self):
        certain = SimpleNamespace(crit_rate=100, plain_alternatives=[[object()]])
        self.assertEqual([0], crit_breakpoints([certain]))

    def test_a_weapon_without_a_crit_rate_adds_no_break(self):
        spells = castable_spells('Xelor', 200, 'dofus3')
        dagger = _weapon(SRAMBAD_DAGGERS)
        self.assertEqual(0, dagger.crit_rate)
        self.assertTrue(dagger.plain_alternatives)
        self.assertEqual(crit_breakpoints(spells), crit_breakpoints(spells + [dagger]))

    def test_the_worn_weapon_adds_the_break_of_its_rate(self):
        spells = castable_spells('Xelor', 200, 'dofus3')
        sceptre = _weapon(MINOTOT_SCEPTRE)
        self.assertGreater(sceptre.crit_rate, 0)
        reached = 100 - sceptre.crit_rate
        self.assertNotIn(reached, crit_breakpoints(spells))
        self.assertIn(reached, crit_breakpoints(spells + [sceptre]))

    def test_the_turn_at_a_break_is_best_turn_itself(self):
        for char_class in ('Sram', 'Iop'):
            spells = castable_spells(char_class, 200, 'dofus3')
            view = SetView(TurnReader(STATS, spells, AP, 'dofus3', 200), None, STATS)
            for crit in view.breaks:
                with self.subTest(char_class=char_class, crit=crit):
                    self.assertEqual(_turn(spells, dict(STATS, ch=crit)), view.turn(crit))

    def test_a_point_of_each_played_characteristic_is_read_over_the_step(self):
        spells = castable_spells('Iop', 200, 'dofus3')
        view = SetView(TurnReader(STATS, spells, AP, 'dofus3', 200), None, STATS)
        self.assertAlmostEqual(_per_point(spells), view.per_point(PLAYED))
        self.assertNotAlmostEqual(_per_point(spells), view.per_point(PLAYED[:1]))


class TheBreakFollowsTheRankOfTheLevelTests(SimpleTestCase):
    """On Retro the break of a throw follows the rank of the spell the level reaches."""

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('retro')
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_break_of_a_throw_sits_at_the_rate_of_the_rank_the_level_reaches(self):
        from chardata.spell_buffs import _decide_spell_level
        moved = 0
        for level in (50, 100, 200):
            spells = castable_spells('Ecaflip', level, 'retro')
            rates = set()
            for spell in spells:
                by_rank = (spell.spell.casting or {}).get('crit') or []
                rank = _decide_spell_level(spell.spell.level_req, level)
                rate = by_rank[rank] if rank < len(by_rank) else 0
                moved += bool(by_rank) and rate != by_rank[-1]
                if 0 < rate < 100 and spell.plain_alternatives:
                    rates.add(rate)
            with self.subTest(level=level):
                self.assertTrue(rates)
                self.assertEqual(sorted({0} | {100 - rate for rate in rates}), crit_breakpoints(spells))
        self.assertTrue(moved)


class TheEnvelopeTests(SimpleTestCase):

    def test_a_concave_curve_is_kept(self):
        points = [(0, 0), (10, 20), (20, 30), (30, 35)]
        self.assertEqual(points, concave_hull(points))

    def test_a_point_under_the_chord_is_dropped(self):
        self.assertEqual([(0, 0), (20, 20)], concave_hull([(0, 0), (10, 2), (20, 20)]))

    def test_a_point_on_the_chord_is_dropped(self):
        self.assertEqual([(0, 0), (20, 20)], concave_hull([(0, 0), (10, 10), (20, 20)]))

    def test_the_curve_is_cut_at_the_first_vertex_that_reaches_the_top(self):
        self.assertEqual([(0, 0), (10, 10)], concave_hull([(0, 0), (10, 10), (20, 10), (30, 10)]))

    def test_the_slopes_are_the_rises_over_the_runs(self):
        self.assertEqual([2.0, 0.5], slopes_of([(0, 0), (10, 20), (30, 30)]))


class TheHingesPriceTheSlopesTests(_DofusThree):

    def test_the_weight_and_the_hinges_follow_the_turn_read_by_best_turn(self):
        for char_class in ('Sram', 'Iop'):
            with self.subTest(char_class=char_class):
                spells = castable_spells(char_class, 200, 'dofus3')
                breaks = crit_breakpoints(spells)
                hull = concave_hull([(crit, _turn(spells, dict(STATS, ch=crit))) for crit in breaks])
                paid = sum(WEIGHTS[key] for key in PLAYED) / float(len(PLAYED))
                slopes = [value / _per_point(spells) * paid for value in slopes_of(hull)]
                reading = _read(char_class)
                self.assertAlmostEqual(slopes[0], reading.ch, places=5)
                self.assertEqual([vertex[0] for vertex in hull[1:]],
                                 [crit for crit, _drop in reading.hinges])
                for k, (_crit, drop) in enumerate(reading.hinges):
                    follow = slopes[k + 1] if k + 1 < len(slopes) else 0.0
                    self.assertAlmostEqual(slopes[k] - follow, drop, places=5)

    def test_the_slopes_fall_and_reach_zero_after_the_last_break(self):
        for char_class in ('Sram', 'Iop'):
            with self.subTest(char_class=char_class):
                reading = _read(char_class)
                self.assertTrue(reading.hinges)
                drops = [drop for _crit, drop in reading.hinges]
                self.assertTrue(all(drop > 0 for drop in drops))
                slopes = [sum(drops[k:]) for k in range(len(drops))]
                self.assertEqual(sorted(slopes, reverse=True), slopes)
                self.assertAlmostEqual(reading.ch, slopes[0], places=5)
                crits = [crit for crit, _drop in reading.hinges]
                self.assertEqual(sorted(set(crits)), crits)

    def test_casts_that_cap_at_different_crits_give_several_slopes(self):
        self.assertGreater(len(_read('Iop').hinges), 2)

    def test_no_slope_means_no_reading(self):
        spells = castable_spells('Sram', 200, 'dofus3')
        view = SetView(TurnReader(STATS, spells, AP, 'dofus3', 200), None, STATS)
        with mock.patch.object(TurnReader, 'full', return_value=1000.0):
            self.assertIsNone(read_curve(view, WEIGHTS))

    def test_no_played_characteristic_means_no_reading(self):
        self.assertIsNone(_read(weights={'ch': 240, 'hp': 25}))

    def test_a_characteristic_far_under_the_heaviest_is_not_played(self):
        self.assertEqual(_read(), _read(weights=dict(WEIGHTS, agi=WEIGHTS['agi'] // 3)))


class TheCurveStaysInItsScopeTests(_DofusThree):

    def test_levels_under_two_hundred_have_no_curve(self):
        self.assertIsNotNone(_read(level=200))
        for level in (199, 150, 100):
            with self.subTest(level=level):
                self.assertIsNone(_read(level=level))

    def test_a_level_under_two_hundred_reads_no_weights(self):
        char = SimpleNamespace(id=1, game_version='dofus3', char_class='Sram', level=199)
        with mock.patch('chardata.crit_curve.get_char_aspects') as aspects, \
                mock.patch('chardata.crit_curve.get_standard_weights') as standard, \
                mock.patch('chardata.crit_curve.get_stats_weights') as stored:
            self.assertIsNone(crit_hinges(char, object(), SimpleNamespace(objective_values=WEIGHTS)))
        for read in (aspects, standard, stored):
            read.assert_not_called()

    def test_the_other_versions_have_no_curve_and_read_no_turn(self):
        for game_version in ('beta', 'dofus2', 'touch', 'retro'):
            with self.subTest(game_version=game_version):
                with mock.patch.object(TurnReader, 'full') as full:
                    self.assertIsNone(_read(game_version=game_version))
                full.assert_not_called()

    def test_a_crit_weight_picked_by_hand_keeps_the_crit_linear(self):
        self.assertIsNone(_read(stored=dict(WEIGHTS, ch=WEIGHTS['ch'] + 60)))

    def test_a_crit_weight_the_floors_once_raised_still_gets_the_curve(self):
        stored = dict(WEIGHTS, ch=840, ch_before_floor=WEIGHTS['ch'])
        self.assertEqual(_read(), _read(stored=stored))
        self.assertIsNotNone(_read(stored=stored))

    def test_the_crit_and_noncrit_aspects_keep_the_crit_linear(self):
        for aspect in ('crit', 'noncrit'):
            with self.subTest(aspect=aspect):
                self.assertIsNone(_read(aspects={'str', aspect}))

    def test_a_missing_first_set_has_no_curve(self):
        char = SimpleNamespace(id=1, game_version='dofus3', char_class='Sram', level=200)
        self.assertIsNone(crit_hinges(char, None, SimpleNamespace(objective_values=WEIGHTS)))

    def test_a_first_set_that_cannot_be_read_has_no_curve(self):
        char = SimpleNamespace(id=1, game_version='dofus3', char_class='Sram', level=200)
        with mock.patch('chardata.crit_curve.get_char_aspects', return_value={'str'}), \
                mock.patch('chardata.crit_curve.get_standard_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.crit_curve.get_stats_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.solution.get_solution_from_minimal', side_effect=ValueError), \
                self.assertLogs('chardata.crit_curve', 'ERROR'):
            self.assertIsNone(crit_hinges(char, object(), SimpleNamespace(objective_values=WEIGHTS)))
