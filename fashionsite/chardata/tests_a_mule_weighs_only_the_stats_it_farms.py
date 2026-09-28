# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A build without an element weighs only its Leeching, Prospecting and Pods stats, and Chance where Chance gives Prospecting."""
from itertools import combinations
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata.smart_build import MULE_STATS, _set_weights, level_minimums, mule_stats
from fashionistapulp.dofus_constants import NON_STAT_WEIGHT_KEYS
from fashionistapulp.modelresult import characteristic_passives

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
CLASSES = ('Iop', 'Xelor', 'Enutrof', 'Sram', 'Eniripsa', 'Osamodas', 'Huppermage')
LEVELS = (1, 60, 199, 200)
ELEMENTS = ('str', 'int', 'cha', 'agi', 'omni')
OTHER_BOXES = ('vit', 'res', 'glasscannon', 'dam', 'heal', 'aprape', 'mprape', 'crit', 'noncrit',
               'pvp', 'duel', 'trap', 'summon', 'pushback')


def _char(version, char_class='Iop', level=200):
    return SimpleNamespace(char_class=char_class, level=level, game_version=version,
                           minimum_stats=None)


def _weights(version, aspects, char_class='Iop', level=200):
    return _set_weights(_char(version, char_class, level), set(aspects), apply=False)


def _mules():
    return [set(boxes) for count in (1, 2, 3) for boxes in combinations(sorted(MULE_STATS), count)]


def _weighed(weights):
    return {key for key, value in weights.items() if value and key not in NON_STAT_WEIGHT_KEYS}


def _characteristics(version, stats):
    """Chance where the version's Chance gives Prospecting; never Strength behind Pods."""
    return {characteristic: (per, gain)
            for stat, characteristic, per, gain in characteristic_passives(version)
            if stat in stats and stat == 'pp'}


class AMuleWeighsNothingElseTests(SimpleTestCase):

    def test_a_mule_weighs_its_stats_and_their_characteristic_alone(self):
        checked = 0
        for version in VERSIONS:
            for boxes in _mules():
                stats = {MULE_STATS[box] for box in boxes}
                expected = stats | set(_characteristics(version, stats))
                for extra in (None,) + OTHER_BOXES:
                    aspects = boxes | ({extra} if extra else set())
                    for char_class in CLASSES:
                        for level in LEVELS:
                            with self.subTest(version=version, aspects=sorted(aspects),
                                              char_class=char_class, level=level):
                                self.assertEqual(stats, mule_stats(aspects))
                                self.assertEqual(expected, _weighed(
                                    _weights(version, aspects, char_class, level)))
                                checked += 1
        self.assertEqual(5 * 7 * 15 * 7 * 4, checked)

    def test_chance_is_priced_at_the_prospecting_it_gives(self):
        for version in VERSIONS:
            for boxes in _mules():
                stats = {MULE_STATS[box] for box in boxes}
                weights = _weights(version, boxes)
                for stat, characteristic, per, gain in characteristic_passives(version):
                    if stat in stats and stat == 'pp':
                        with self.subTest(version=version, boxes=sorted(boxes), stat=stat):
                            self.assertEqual(round(weights[stat] * gain / per),
                                             weights[characteristic])

    def test_touch_gives_prospecting_and_pods_no_characteristic(self):
        self.assertEqual({'pp', 'pod'}, _weighed(_weights('touch', {'pp', 'pods'})))

    def test_chance_gives_prospecting_elsewhere_and_strength_stays_at_zero(self):
        for version in ('dofus3', 'beta', 'dofus2', 'retro'):
            with self.subTest(version=version):
                self.assertIn(('pod', 'str', 1, 5), characteristic_passives(version))
                weights = _weights(version, {'pp', 'pods'})
                self.assertEqual(weights['pp'] / 10.0, weights['cha'])
                self.assertEqual(0, weights['str'])


class TheSpecialDofusGetNoPriceOnAMuleTests(SimpleTestCase):
    """model.py prices the special Dofus of Dofus 3 and the Beta from the combat weights."""

    def _terms(self, version, weights, level=200):
        from fashionistapulp.model import Model
        from fashionistapulp.structure import get_structure, set_current_game_version
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(version)
        model = Model.__new__(Model)
        model.structure = get_structure(version)

        class Collector(object):
            def __init__(self):
                self.terms = {}

            def add_to_of(self, category, item_id, weight):
                key = (category, item_id)
                self.terms[key] = self.terms.get(key, 0) + weight

        model.problem = Collector()
        model.add_weird_item_weights_to_objective_funcion(weights, level)
        return {key: value for key, value in model.problem.terms.items() if value}

    def test_no_special_dofus_term_for_any_mule(self):
        checked = 0
        for version in ('dofus3', 'beta'):
            for boxes in _mules():
                for extra in (set(), {'pvp'}, {'duel'}, {'vit'}):
                    for level in (60, 200):
                        aspects = boxes | extra
                        with self.subTest(version=version, aspects=sorted(aspects), level=level):
                            weights = _weights(version, aspects, 'Enutrof', level)
                            self.assertEqual({}, self._terms(version, weights, level))
                            checked += 1
        self.assertEqual(2 * 7 * 4 * 2, checked)

    def test_a_strength_weight_would_price_them(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertTrue(self._terms(version, {'pod': 200, 'str': 1000}))


class AMuleKeepsTheStrengthOfItsBoxesTests(SimpleTestCase):

    def test_each_stat_weighs_the_same_alone_or_with_the_others(self):
        for version in VERSIONS:
            alone = {box: _weights(version, {box})[MULE_STATS[box]] for box in MULE_STATS}
            for boxes in _mules():
                weights = _weights(version, boxes)
                for box in boxes:
                    with self.subTest(version=version, boxes=sorted(boxes), box=box):
                        self.assertEqual(alone[box], weights[MULE_STATS[box]])

    def test_wisdom_prospecting_and_pods_weigh_five_two_and_two(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                weights = _weights(version, {'wis', 'pp', 'pods'})
                self.assertEqual(weights['wis'] * 2, weights['pp'] * 5)
                self.assertEqual(weights['pp'], weights['pod'])

    def test_an_xp_mule_weighs_wisdom_the_same_with_the_removal_and_pvp_boxes(self):
        for version in VERSIONS:
            plain = _weights(version, {'wis'})['wis']
            for extra in ({'aprape'}, {'mprape'}, {'aprape', 'mprape', 'pvp', 'duel'}):
                with self.subTest(version=version, extra=sorted(extra)):
                    self.assertEqual(plain, _weights(version, {'wis'} | extra)['wis'])


class AnElementKeepsTheFightingWeightsTests(SimpleTestCase):

    def test_an_element_with_the_mule_boxes_is_no_mule(self):
        for version in VERSIONS:
            for element in ELEMENTS:
                aspects = {element, 'wis', 'pp', 'pods'}
                with self.subTest(version=version, element=element):
                    self.assertEqual(set(), mule_stats(aspects))
                    weights = _weights(version, aspects)
                    for key in ('ap', 'mp', 'vit', 'wis', 'pp', 'pod'):
                        self.assertGreater(weights[key], 0, key)


class AMuleAsksNoApMpOrRangeTests(SimpleTestCase):

    def test_every_mule_has_no_ap_mp_or_range_minimum(self):
        for version in VERSIONS:
            for boxes in _mules():
                for level in LEVELS:
                    with self.subTest(version=version, boxes=sorted(boxes), level=level):
                        minimums = level_minimums(_char(version, 'Iop', level), boxes)
                        self.assertEqual((0, 0, 0), (minimums['AP'], minimums['MP'],
                                                     minimums['Range']))
