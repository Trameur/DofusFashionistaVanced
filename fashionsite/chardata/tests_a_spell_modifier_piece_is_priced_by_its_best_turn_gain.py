# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece's spell modifiers are priced from the best turn they add on the stats of a set of the build."""

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata import spell_modifier_values as values
from chardata.spells_view import _best_combo
from chardata.version_compat import filter_classes_for_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES, STAT_NAME_TO_KEY
from fashionistapulp.structure import (fits_the_class, get_structure,
                                       set_current_game_version)

HONOH_RING = 8714
CAP_RICOTT = 8632
BELT_ATIO = 8656


def _stats(**given):
    stats = {key: 0 for key in STAT_NAME_TO_KEY.values()}
    stats.update(given)
    return stats


# Stats of solved balanced level 200 sets
CRA_SET = _stats(str=790, int=821, cha=260, agi=432, pow=250, ch=102, cridam=110,
                 earthdam=40, firedam=40, neutdam=20, ap=12)
SADIDA_SET = _stats(str=160, int=1118, cha=140, agi=140, pow=370, ch=23, cridam=80,
                    firedam=30, ap=12)
CRA_WEIGHTS = {'str': 100, 'int': 100, 'agi': 20, 'pow': 160, 'ch': 1600, 'cridam': 567,
               'dam': 1260, 'earthdam': 600, 'firedam': 600, 'vit': 18}


class _Piece(object):

    def __init__(self, ankama_id):
        self.item_added = True
        self.id = get_structure('dofus3').get_item_by_ankama_id(ankama_id).id
        self.ankama_id = ankama_id
        self.ankama_type = 'equipment'
        self.name = self.localized_name = str(ankama_id)


class _Solution(object):
    """What the spells panel reads of a set: its stats and the pieces it wears."""

    def __init__(self, stats, *ankama_ids):
        self.stats = stats
        self.items = {'Ring': [_Piece(ankama_id) for ankama_id in ankama_ids]}
        self.input = {}

    def get_stats_total(self):
        return dict(self.stats)


def _turn(char_class, stats, *ankama_ids):
    combo = _best_combo(SimpleNamespace(char_class=char_class, level=200),
                        _Solution(stats, *ankama_ids), 'dofus3')
    return combo['total'] + combo['later_total']


class _Version(SimpleTestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version('dofus3')
        self.structure = get_structure('dofus3')

    def site_id(self, ankama_id):
        return self.structure.get_item_by_ankama_id(ankama_id).id


class ThePlayedCharacteristicsTests(SimpleTestCase):

    def test_a_characteristic_is_played_from_seven_tenths_of_the_heaviest(self):
        self.assertEqual(('str',), values.played_characteristics(
            {'str': 180, 'agi': 20, 'cha': 1}))
        self.assertEqual(('str', 'int', 'cha', 'agi'), values.played_characteristics(
            {'str': 60, 'int': 60, 'cha': 60, 'agi': 60}))
        self.assertEqual(('str', 'agi'), values.played_characteristics(
            {'str': 100, 'agi': 70, 'cha': 69}))


class TheTurnPriceTests(SimpleTestCase):

    def test_the_price_is_the_cheapest_damage_stat_per_point_of_turn(self):
        per_unit = {('str',): 1.5, ('earthdam',): 4.0, ('pow',): 1.5, ('ch',): 0.0}
        self.assertAlmostEqual(80 / 1.5, values.turn_price(
            {'str': 120, 'earthdam': 720, 'pow': 80, 'ch': 1}, per_unit))

    def test_a_stat_the_turn_does_not_follow_or_the_weights_ignore_sets_no_price(self):
        per_unit = {('str',): 1.5, ('pow',): 1.5, ('ch',): 0.0}
        self.assertAlmostEqual(120 / 1.5, values.turn_price({'str': 120, 'ch': 1}, per_unit))
        self.assertEqual(0.0, values.turn_price({'vit': 10}, per_unit))

    def test_a_build_that_weighs_no_damage_stat_prices_nothing(self):
        self.assertEqual(({}, {}), values.modifier_values('dofus3', 'Cra', 200, {'vit': 10},
                                                          CRA_SET))


class TheApTotalsPricedTests(SimpleTestCase):

    def test_a_capped_version_prices_from_the_ap_reached_to_its_cap(self):
        self.assertEqual((11, 12), values.ap_tiers('dofus3', 11))
        self.assertEqual((12,), values.ap_tiers('dofus3', 12))
        self.assertEqual((7, 8, 9, 10, 11, 12), values.ap_tiers('touch', 7))

    def test_an_uncapped_version_prices_a_span_from_the_ap_reached(self):
        self.assertEqual(tuple(range(11, 11 + values.UNCAPPED_TIERS)),
                         values.ap_tiers('retro', 11))
        self.assertEqual(tuple(range(13, 13 + values.UNCAPPED_TIERS)),
                         values.ap_tiers('touch', 13, temporix=True))

    def test_no_value_is_priced_below_the_ap_the_set_reaches(self):
        priced, _overlaps = values.modifier_values('dofus3', 'Cra', 200, CRA_WEIGHTS, CRA_SET)
        self.assertTrue(priced)
        self.assertEqual({12}, {ap for per_ap in priced.values() for ap in per_ap})


class TheHonohRingIsPricedForTheCraTests(_Version):

    def test_the_value_is_the_turn_gain_at_the_turn_price(self):
        ring = self.site_id(HONOH_RING)
        gains, _overlaps, per_unit = values.item_gains('dofus3', 'Cra', 200, CRA_SET,
                                                       ('str', 'int'), 12)
        priced, _overlaps = values.modifier_values('dofus3', 'Cra', 200, CRA_WEIGHTS, CRA_SET)
        self.assertGreater(gains[ring], 0)
        self.assertEqual({12: int(round(gains[ring] * values.turn_price(CRA_WEIGHTS,
                                                                        per_unit)))},
                         priced[ring])

    def test_the_gain_is_the_one_the_spells_panel_shows(self):
        ring = self.site_id(HONOH_RING)
        gains, _overlaps, _per_unit = values.item_gains('dofus3', 'Cra', 200, CRA_SET,
                                                        ('str', 'int'), 12)
        shown = _turn('Cra', CRA_SET, HONOH_RING) - _turn('Cra', CRA_SET)
        self.assertGreater(shown, 0)
        self.assertAlmostEqual(shown, gains[ring], delta=values.PANEL_ROUNDING)

    def test_no_other_class_is_priced_for_it(self):
        ring = self.site_id(HONOH_RING)
        for char_class in ('Iop', 'Feca', 'Sadida'):
            gains, _overlaps, _per_unit = values.item_gains('dofus3', char_class, 200, CRA_SET,
                                                            ('str',), 12)
            self.assertNotIn(ring, gains)


class TwoPiecesWornTogetherLoseTheirOverlapTests(_Version):

    def test_the_overlap_is_the_pair_turn_less_each_piece_alone(self):
        cap, belt = self.site_id(CAP_RICOTT), self.site_id(BELT_ATIO)
        gains, overlaps, _per_unit = values.item_gains('dofus3', 'Sadida', 200, SADIDA_SET,
                                                       ('int',), 12)
        both = _turn('Sadida', SADIDA_SET, CAP_RICOTT, BELT_ATIO) - _turn('Sadida', SADIDA_SET)
        self.assertLess(both, gains[cap] + gains[belt])
        self.assertAlmostEqual(both - gains[cap] - gains[belt], overlaps[(cap, belt)],
                               delta=values.PANEL_ROUNDING)

    def test_a_priced_overlap_needs_both_pieces_priced_at_that_ap(self):
        priced, overlaps = values.modifier_values('dofus3', 'Sadida', 200,
                                                  {'int': 120, 'pow': 80}, SADIDA_SET)
        self.assertTrue(overlaps)
        for pair, per_ap in overlaps.items():
            for ap, value in per_ap.items():
                self.assertLess(value, 0)
                self.assertTrue(all(ap in priced[item_id] for item_id in pair))


class OnlyAPieceTheClassCanWearIsPricedTests(_Version):

    def test_every_piece_that_changes_a_cast_fits_its_class_in_every_version_with_class_items(self):
        for version in ('dofus3', 'beta', 'dofus2', 'retro'):
            set_current_game_version(version)
            structure = get_structure(version)
            seen = 0
            for char_class in filter_classes_for_version(CHARACTER_CLASSES, version):
                for rows, _modifiers in values.turn_changers(version, char_class, 200):
                    for item_id in rows:
                        seen += 1
                        self.assertTrue(fits_the_class(structure.get_item_by_id(item_id),
                                                       char_class), (version, char_class, item_id))
            self.assertGreater(seen, 0, version)

    def test_a_piece_on_the_class_spells_is_not_priced_once_the_class_cannot_wear_it(self):
        ring = self.site_id(HONOH_RING)

        def priced_rows():
            return {row for rows, _modifiers in values.turn_changers('dofus3', 'Cra', 200)
                    for row in rows}
        with mock.patch.object(values, '_CHANGERS', {}):
            self.assertIn(ring, priced_rows())
        with mock.patch.object(values, '_CHANGERS', {}), \
                mock.patch.object(values, 'fits_the_class',
                                  lambda item, char_class: item.id != ring):
            self.assertNotIn(ring, priced_rows())

    def test_no_touch_seal_changes_a_cast_of_the_one_turn_evaluator(self):
        set_current_game_version('touch')
        structure = get_structure('touch')
        emblem = structure.get_type_id_by_name('Emblem')
        for char_class in filter_classes_for_version(CHARACTER_CLASSES, 'touch'):
            seals = [structure.get_item_by_id(item_id).name
                     for rows, _modifiers in values.turn_changers('touch', char_class, 200)
                     for item_id in rows
                     if structure.get_item_by_id(item_id).type == emblem]
            self.assertEqual([], seals, char_class)


class ATurnItsCharacteristicsDoNotRaiseIsPricedThroughPowerTests(_Version):

    def test_a_retro_feca_playing_agility(self):
        set_current_game_version('retro')
        stats = _stats(str=100, int=100, cha=100, agi=700, pow=20, ap=11)
        base, per_unit = values.turn_prices('retro', 'Feca', 200, stats, ('agi',), 11)
        self.assertGreater(base, 0)
        self.assertEqual(0, per_unit[('agi',)])
        self.assertGreater(per_unit[('pow',)], 0)
        self.assertAlmostEqual(120 / per_unit[('pow',)],
                               values.turn_price({'agi': 180, 'pow': 120}, per_unit))
