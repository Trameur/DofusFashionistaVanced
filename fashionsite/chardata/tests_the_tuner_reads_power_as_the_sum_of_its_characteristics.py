# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The tuner reads a point of power as the points of the four characteristics, over the same step, and nothing else."""
import math
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.crit_curve import SetView
from chardata.spell_combo import best_turn, castable_spells
from chardata.weapon_terms import CHARACTERISTIC_STEP, TurnReader
from chardata.weight_table import DAMAGE_STATS, RESIST_STATS, SHARE_STATS, TABLE_STATS
from fashionistapulp.dofus_constants import MAIN_STATS, STAT_NAME_TO_KEY, get_stat_maximum
from fashionistapulp.item_effects import PLAYED_SHARE

AP = 12
CLASSES = ('Cra', 'Iop', 'Sram', 'Xelor')
# Classes with no spell that takes the best of the elements
SINGLE_ELEMENT_CLASSES = ('Cra', 'Iop', 'Sram')
NOT_READ = ('ch', 'cridam', 'permedam', 'perrandam', 'ap_before_floor', 'wis', 'mp', 'range', 'init', 'heals', 'lock',
            'dodge', 'pp')


def _stats(**values):
    stats = {key: 0 for key in STAT_NAME_TO_KEY.values()}
    stats.update(values)
    return stats


STATS = _stats(str=700, int=650, cha=500, agi=450, pow=250, dam=40, earthdam=20, firedam=15, waterdam=10, airdam=10,
               neutdam=5, perspedam=12, perweadam=8, ch=30, cridam=40, ap=AP, hp=3200, vit=600)
PLAYED = ['str', 'int']
LAM = 0.25


def _view(char_class, stats=STATS, ap=AP):
    spells = castable_spells(char_class, 200, 'dofus3')
    stats = dict(stats, ap=ap)
    return SetView(TurnReader(stats, spells, ap, 'dofus3', 200), None, stats)


def _turn(char_class, stats, ap=AP):
    spells = castable_spells(char_class, 200, 'dofus3')
    return best_turn(dict(stats, ap=ap), spells, ap, standing={}, game_version='dofus3', pushback=False,
                     caster_level=200)[0]


class _Reader(object):
    """A turn that grows by a fixed amount per point of each stat, per AP, and whose cast list can change."""

    def __init__(self, gains, base=1500.0, ap=AP, per_ap=40.0, joint=0.0, flips=()):
        self.gains = gains
        self.base = base
        self.ap = ap
        self.per_ap = per_ap
        self.joint = joint
        self.flips = flips
        self.game_version = 'dofus3'

    def cast(self, weapon=None, deltas=None, ap=None):
        deltas = deltas or {}
        total = self.base + sum(self.gains.get(key, 0.0) * value for key, value in deltas.items())
        if len(deltas) > 1:
            total += self.joint * math.prod(deltas.values())
        if ap is not None:
            total += self.per_ap * (ap - self.ap)
        order = [('hit', total)] + ([('extra', 1.0)] if any(key in self.flips for key in deltas) else [])
        return total, order

    def full(self, weapon=None, deltas=None):
        return self.cast(weapon, deltas)[0]


class _Curve(_Reader):
    """A turn that depends on the AP alone, by the table `curve`, for a set that has `ap` points."""

    def __init__(self, curve, ap):
        super().__init__({}, base=curve[ap], ap=ap)
        self.curve = curve

    def cast(self, weapon=None, deltas=None, ap=None):
        return self.curve[self.ap if ap is None else ap], [('hit', 1.0)]


class _View(object):

    def __init__(self, reader, per_point=2.0):
        self.reader = reader
        self.worn = None
        self._per_point = per_point

    def per_point(self, played):
        return self._per_point


def _totals(hp=3000, resist=20):
    totals = {key: resist for key in RESIST_STATS}
    totals['hp'] = hp
    return totals


class ThePowerIsTheSumOfTheCharacteristicsTests(SimpleTestCase):

    def test_a_point_of_power_is_worth_the_four_characteristics_together(self):
        for char_class in CLASSES:
            gains, _switched = tuning.read_gains(_view(char_class), ('pow',) + tuple(MAIN_STATS))
            with self.subTest(char_class=char_class):
                self.assertGreater(gains['pow'], 0)
                self.assertAlmostEqual(gains['pow'], sum(gains[key] for key in MAIN_STATS), places=6)

    def test_a_fixed_damage_is_worth_the_five_kinds_together(self):
        for char_class in SINGLE_ELEMENT_CLASSES:
            gains, _switched = tuning.read_gains(_view(char_class), DAMAGE_STATS)
            with self.subTest(char_class=char_class):
                self.assertGreater(gains['dam'], 0)
                self.assertAlmostEqual(gains['dam'], sum(gains[key] for key in DAMAGE_STATS if key != 'dam'), places=6)

    def test_every_gain_is_read_over_the_step_of_twenty(self):
        self.assertEqual(20, tuning.STEP)
        self.assertEqual(CHARACTERISTIC_STEP, tuning.STEP)
        base = _turn('Iop', STATS)
        for key in ('pow', 'dam', 'earthdam', 'perspedam'):
            gains, _switched = tuning.read_gains(_view('Iop'), (key,))
            raised = _turn('Iop', dict(STATS, **{key: STATS[key] + 20}))
            with self.subTest(key=key):
                self.assertAlmostEqual((raised - base) / 20.0, gains[key], places=9)

    def test_the_gain_of_the_characteristics_is_read_over_the_joint_raise(self):
        view = _view('Iop')
        raised = _turn('Iop', dict(STATS, str=STATS['str'] + 20, int=STATS['int'] + 20))
        self.assertAlmostEqual((raised - _turn('Iop', STATS)) / 40.0, view.per_point(PLAYED), places=9)

    def test_below_the_ap_cap_the_ap_gain_is_the_turn_on_one_more_ap_less_the_turn(self):
        self.assertLess(AP - 2, get_stat_maximum('dofus3')['AP'])
        view = _view('Iop', ap=AP - 2)
        self.assertAlmostEqual(_turn('Iop', STATS, AP - 1) - _turn('Iop', STATS, AP - 2), tuning.ap_gain(view),
                               places=9)
        self.assertGreater(tuning.ap_gain(view), 0)

    def test_at_the_ap_cap_the_ap_gain_is_the_turn_less_the_turn_on_one_less_ap(self):
        self.assertEqual(AP, get_stat_maximum('dofus3')['AP'])
        view = _view('Iop')
        self.assertAlmostEqual(_turn('Iop', STATS, AP) - _turn('Iop', STATS, AP - 1), tuning.ap_gain(view), places=9)
        self.assertGreater(tuning.ap_gain(view), 0)

    def test_the_ap_gain_at_the_cap_is_not_the_one_of_an_ap_the_set_cannot_have(self):
        beyond = _turn('Iop', STATS, AP + 1) - _turn('Iop', STATS, AP)
        self.assertNotAlmostEqual(beyond, tuning.ap_gain(_view('Iop')), places=3)


class TheRatioIsTheGainOverTheGainOfACharacteristicTests(SimpleTestCase):

    def _read(self, gains, hp=3000, resist=20, lam=LAM, per_point=2.0, **reader):
        view = _View(_Reader(gains, **reader), per_point)
        return tuning.read_ratios(view, _totals(hp, resist), PLAYED[:1], lam), view

    def test_a_damage_stat_is_its_gain_over_the_characteristic_gain(self):
        read, _view_ = self._read({'pow': 0.5, 'dam': 1.5, 'perspedam': 3.0})
        self.assertAlmostEqual(0.25, read.ratios['pow'])
        self.assertAlmostEqual(0.75, read.ratios['dam'])
        self.assertAlmostEqual(1.5, read.ratios['perspedam'])
        self.assertEqual(0.0, read.ratios['earthdam'])

    def test_hp_and_vitality_are_the_closed_form_of_the_effective_hp(self):
        read, _view_ = self._read({'pow': 0.5})
        self.assertAlmostEqual(LAM * 1500.0 / 3000.0 / 2.0, read.ratios['hp'])
        self.assertEqual(read.ratios['hp'], read.ratios['vit'])

    def test_each_percent_resist_is_the_closed_form_of_the_effective_hp(self):
        read, _view_ = self._read({'pow': 0.5}, resist=20)
        expected = LAM * 1500.0 / (5 * (100 - 20)) / 2.0
        for stat in RESIST_STATS:
            with self.subTest(stat=stat):
                self.assertAlmostEqual(expected, read.ratios[stat])

    def test_the_closed_form_agrees_with_raising_the_stat(self):
        hp, resist, turn, g_char = 3000.0, 20.0, 1500.0, 2.0
        ehp = lambda hp_, res_: hp_ / (1 - res_ / 100.0)
        read, _view_ = self._read({'pow': 0.5}, hp=hp, resist=resist)
        base = ehp(hp, resist)
        small = 1e-6
        per_hp = ehp(hp + 1, resist) - base
        per_resist = (ehp(hp, resist + small / 5) - base) / small
        self.assertAlmostEqual(LAM * turn / base * per_hp / g_char, read.ratios['hp'], places=4)
        self.assertAlmostEqual(LAM * turn / base * per_resist / g_char, read.ratios['neutresper'], places=4)

    def test_the_weight_of_defence_follows_lambda(self):
        low, _view_ = self._read({'pow': 0.5}, lam=0.15)
        high, _view_ = self._read({'pow': 0.5}, lam=0.4)
        self.assertAlmostEqual(0.4 / 0.15, high.ratios['hp'] / low.ratios['hp'])
        self.assertAlmostEqual(0.4 / 0.15, high.ratios['airresper'] / low.ratios['airresper'])
        self.assertEqual(low.ratios['pow'], high.ratios['pow'])

    def test_the_ap_ratio_is_the_secant_over_the_characteristic_gain(self):
        read, _view_ = self._read({'pow': 0.5}, per_ap=40.0)
        self.assertAlmostEqual(20.0, read.ratios['ap'])
        self.assertEqual(40.0, tuning.ap_gain(_View(_Reader({}, per_ap=40.0))))

    def test_the_ap_ratio_reads_the_last_ap_of_a_set_at_the_cap_and_the_next_one_below_it(self):
        curve = {AP - 2: 1000.0, AP - 1: 1100.0, AP: 1250.0, AP + 1: 1700.0}
        at_cap = tuning.read_ratios(_View(_Curve(curve, AP)), _totals(), PLAYED[:1], LAM)
        below = tuning.read_ratios(_View(_Curve(curve, AP - 1)), _totals(), PLAYED[:1], LAM)
        self.assertAlmostEqual(150.0 / 2.0, at_cap.ratios['ap'])
        self.assertAlmostEqual(150.0 / 2.0, below.ratios['ap'])
        lower = tuning.read_ratios(_View(_Curve(curve, AP - 2)), _totals(), PLAYED[:1], LAM)
        self.assertAlmostEqual(100.0 / 2.0, lower.ratios['ap'])

    def test_only_the_stats_the_table_reads_come_back(self):
        read, _view_ = self._read({'pow': 0.5})
        self.assertEqual(set(TABLE_STATS), set(read.ratios))
        for stat in NOT_READ:
            self.assertNotIn(stat, read.ratios)

    def test_a_duo_reads_its_shares_too_and_a_single_element_none(self):
        view = _View(_Reader({'str': 1.1, 'int': 0.9}, joint=0.0))
        duo = tuning.read_ratios(view, _totals(), PLAYED, LAM)
        self.assertEqual(set(TABLE_STATS) | set(PLAYED), set(duo.ratios))
        single, _view_ = self._read({'pow': 0.5})
        self.assertFalse(set(SHARE_STATS) & set(single.ratios))

    def test_a_set_with_no_turn_or_no_life_is_not_read(self):
        self.assertIsNone(self._read({'pow': 0.5}, base=0.0)[0])
        self.assertIsNone(self._read({'pow': 0.5}, hp=0)[0])
        self.assertIsNone(tuning.read_ratios(_View(_Reader({}), per_point=0.0), _totals(), PLAYED[:1], LAM))


class ASwitchedReadIsFlaggedTests(SimpleTestCase):

    def test_a_raise_that_changes_the_cast_list_is_flagged(self):
        view = _View(_Reader({'pow': 0.5, 'dam': 1.0}, flips=('dam',)))
        gains, switched = tuning.read_gains(view, ('pow', 'dam'), 20)
        self.assertEqual({'dam'}, switched)
        self.assertEqual(0.5, gains['pow'])

    def test_the_read_carries_the_flags(self):
        view = _View(_Reader({'pow': 0.5, 'dam': 1.0}, flips=('dam',)))
        self.assertEqual({'dam'}, tuning.read_ratios(view, _totals(), PLAYED[:1], LAM).switched)

    def test_one_more_ap_that_changes_the_cast_list_does_not_flag_ap(self):
        class Casting(_Reader):
            def cast(self, weapon=None, deltas=None, ap=None):
                total, order = super().cast(weapon, deltas, ap)
                return total, order + ([('extra', 1.0)] if ap is not None and ap != AP else [])
        view = _View(Casting({'pow': 0.5}))
        self.assertEqual(set(), tuning.read_ratios(view, _totals(), PLAYED[:1], LAM).switched)


class TheSplitOfADuoTests(SimpleTestCase):

    def _split(self, **reader):
        view = _View(_Reader({'str': 1.1, 'int': 0.9}, **reader))
        return tuning.element_split(view, PLAYED)

    def test_the_gains_that_add_up_set_the_shares(self):
        split = self._split()
        self.assertAlmostEqual(1.1, split['str'])
        self.assertAlmostEqual(0.9, split['int'])
        self.assertAlmostEqual(2.0, sum(split.values()))

    def test_gains_that_do_not_add_up_to_the_joint_one_give_the_equal_split(self):
        for joint in (0.5, -0.5):
            with self.subTest(joint=joint):
                self.assertEqual({'str': 1.0, 'int': 1.0}, self._split(joint=joint))

    def test_a_gain_off_by_less_than_the_tolerance_still_counts(self):
        view = _View(_Reader({'str': 1.1, 'int': 0.9}, joint=0.00005))
        self.assertAlmostEqual(1.1, tuning.element_split(view, PLAYED)['str'], places=3)

    def test_a_joint_gain_at_or_below_zero_gives_the_equal_split(self):
        view = _View(_Reader({'str': 0.0, 'int': 0.0}))
        self.assertEqual({'str': 1.0, 'int': 1.0}, tuning.element_split(view, PLAYED))

    def test_one_element_and_three_give_the_equal_split(self):
        view = _View(_Reader({'str': 1.1, 'int': 0.9, 'cha': 1.0}))
        self.assertEqual({'str': 1.0}, tuning.element_split(view, ['str']))
        self.assertEqual({key: 1.0 for key in ('str', 'int', 'cha')}, tuning.element_split(view, ['str', 'int', 'cha']))

    def test_the_shares_keep_both_elements_played(self):
        low = 2 * PLAYED_SHARE / (1 + PLAYED_SHARE)
        for share in (0.0, 0.3, 1.0, 1.7, 2.0):
            shares = tuning.clamp_shares({'str': share, 'int': 2 - share})
            with self.subTest(share=share):
                self.assertAlmostEqual(2.0, sum(shares.values()))
                self.assertGreater(min(shares.values()), low)
                self.assertLess(min(shares.values()) / max(shares.values()), 1.0001)
                self.assertGreaterEqual(min(shares.values()) / max(shares.values()), PLAYED_SHARE)

    def test_shares_already_close_are_left_as_they_are(self):
        self.assertEqual({'str': 1.05, 'int': 0.95}, tuning.clamp_shares({'str': 1.05, 'int': 0.95}))

    def test_one_share_or_three_are_left_as_they_are(self):
        self.assertEqual({'str': 2.0}, tuning.clamp_shares({'str': 2.0}))
        shares = {'str': 1.0, 'int': 1.0, 'cha': 1.0}
        self.assertEqual(shares, tuning.clamp_shares(shares))


class TheFitScoreTests(SimpleTestCase):

    def test_it_is_the_log_of_the_turn_plus_lambda_times_the_log_of_the_effective_hp(self):
        view = _View(_Reader({}, base=1500.0))
        totals = _totals(3000, 20)
        expected = math.log(1500.0) + LAM * math.log(3000 / 0.8)
        self.assertAlmostEqual(expected, tuning.fit_score(view, totals, LAM))

    def test_it_is_none_without_a_turn_or_without_life(self):
        self.assertIsNone(tuning.fit_score(_View(_Reader({}, base=0.0)), _totals(), LAM))
        self.assertIsNone(tuning.fit_score(_View(_Reader({})), _totals(0), LAM))

    def test_the_effective_hp_is_the_sites_own(self):
        from chardata.presets import effective_hp
        self.assertEqual(effective_hp(_totals(3000, 20)), tuning.effective_hp(_totals(3000, 20)))
        self.assertAlmostEqual(3750.0, tuning.effective_hp(_totals(3000, 20)))


class TheReaderHoldsNoClassOrNumberOfItsOwnTests(SimpleTestCase):

    def test_the_read_stats_are_the_table_stats_and_a_duos_shares(self):
        self.assertEqual(tuple(TABLE_STATS) + tuple(SHARE_STATS), tuning.READ_STATS)

    def test_the_stats_the_engine_keeps_are_in_no_read_list(self):
        for stat in NOT_READ:
            for stats in (tuning.READ_STATS, tuning.TURN_STATS):
                self.assertNotIn(stat, stats)
