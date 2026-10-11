# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A critical damage point is priced at the mean gain of the best turn over the crit range the second solve moves in."""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata.crit_curve import CritReading, concave_hull, crit_breakpoints, crit_hinges
from chardata.smart_build import _set_weights
from chardata.spell_combo import castable_spells
from chardata.weapon_terms import CHARACTERISTIC_STEP, TurnReader
from fashionistapulp.dofus_constants import STAT_KEY_TO_NAME, STAT_NAME_TO_KEY, STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal, model_result_from_minimal

MINOTOT_SCEPTRE = 8275
TEROID_AXE = 11761
AP = 12
PLAYED = ['str', 'int']
WEIGHTS = {'str': 120, 'int': 110, 'cha': 0, 'agi': 30, 'ch': 240, 'cridam': 100}


def _stats(**values):
    stats = {key: 0 for key in STAT_NAME_TO_KEY.values()}
    stats.update(values)
    return stats


STATS = _stats(str=900, int=700, pow=250, ch=30, cridam=40, ap=AP)
OWN = {'str': 900, 'int': 700, 'pow': 250, 'ch': 30, 'cridam': 40, 'ap': AP}


class _Solution(object):

    def __init__(self, stats):
        self.items = {'Weapon': []}
        self._stats = stats

    def get_stats_total(self):
        return dict(self._stats)


def _char(char_class='Sram', level=200, game_version='dofus3'):
    return SimpleNamespace(id=1, game_version=game_version, char_class=char_class, level=level)


def _read(char_class='Sram', level=200, game_version='dofus3', stored=None, engine=None, aspects=None,
          spells=None):
    """The reading of the stats STATS, the engine weighing WEIGHTS and the build storing `stored`."""
    patches = [('chardata.crit_curve.get_char_aspects', aspects or {'str'}),
               ('chardata.crit_curve.get_standard_weights', dict(WEIGHTS if engine is None else engine)),
               ('chardata.crit_curve.get_stats_weights', dict(WEIGHTS if stored is None else stored)),
               ('chardata.solution.get_solution_from_minimal', _Solution(STATS))]
    if spells is not None:
        patches.append(('chardata.spell_combo.castable_spells', spells))
    with ExitStack() as stack:
        for target, value in patches:
            stack.enter_context(mock.patch(target, return_value=value))
        return crit_hinges(_char(char_class, level, game_version), object(),
                           SimpleNamespace(objective_values=dict(WEIGHTS)))


def _paid():
    return sum(WEIGHTS[key] for key in PLAYED) / float(len(PLAYED))


def _per_point(reader, worn=None):
    raised = reader.full(worn, {key: CHARACTERISTIC_STEP for key in PLAYED})
    return (raised - reader.full(worn)) / float(CHARACTERISTIC_STEP * len(PLAYED))


def _gain(reader, stats, crit, worn=None):
    """What one critical damage point adds to the turn at `crit`, from two calls to the reader."""
    base = {'ch': crit - stats['ch']}
    raised = reader.full(worn, dict(base, cridam=CHARACTERISTIC_STEP))
    return (raised - reader.full(worn, base)) / float(CHARACTERISTIC_STEP)


def _first_break(reader, stats, worn=None):
    breaks = crit_breakpoints(reader.spells + ([worn] if worn is not None else []))
    hull = concave_hull([(crit, reader.full(worn, {'ch': crit - stats['ch']})) for crit in breaks])
    return hull[1][0]


class _DofusThree(SimpleTestCase):

    def setUp(self):
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')


class ThePriceIsTheMeanGainOverTheCritRangeTests(_DofusThree):

    def test_the_price_is_the_mean_of_two_direct_readings_of_the_turn(self):
        for char_class in ('Sram', 'Iop'):
            with self.subTest(char_class=char_class):
                reader = TurnReader(STATS, castable_spells(char_class, 200, 'dofus3'), AP, 'dofus3', 200)
                first = _first_break(reader, STATS)
                at_set, at_break = _gain(reader, STATS, STATS['ch']), _gain(reader, STATS, first)
                self.assertGreater(first, STATS['ch'])
                self.assertNotAlmostEqual(at_set, at_break)
                price = (at_set + at_break) / 2.0 / _per_point(reader) * _paid()
                self.assertAlmostEqual(price, _read(char_class).cridam, places=5)

    def test_the_price_is_neither_of_the_two_readings_alone(self):
        for char_class in ('Sram', 'Iop'):
            with self.subTest(char_class=char_class):
                reader = TurnReader(STATS, castable_spells(char_class, 200, 'dofus3'), AP, 'dofus3', 200)
                for crit in (STATS['ch'], _first_break(reader, STATS)):
                    alone = _gain(reader, STATS, crit) / _per_point(reader) * _paid()
                    self.assertNotAlmostEqual(alone, _read(char_class).cridam, places=3)

    def test_the_reading_carries_the_price_beside_the_curve(self):
        reading = _read('Iop')
        self.assertIsInstance(reading, CritReading)
        self.assertGreater(reading.ch, 0)
        self.assertTrue(reading.hinges)
        self.assertGreater(reading.cridam, 0)


class ThePriceStaysZeroWhereNothingCritsTests(_DofusThree):

    def test_without_a_throw_that_crits_the_price_is_zero(self):
        flat = [spell for spell in castable_spells('Sram', 200, 'dofus3')
                if spell.crit_rate == 0 and spell.plain_alternatives]
        self.assertTrue(flat)
        reading = _read(spells=flat)
        self.assertEqual(CritReading(None, (), 0), reading)

    def test_without_a_throw_that_crits_the_crit_keeps_its_weight(self):
        flat = [spell for spell in castable_spells('Sram', 200, 'dofus3')
                if spell.crit_rate == 0 and spell.plain_alternatives]
        self.assertIsNone(_read(spells=flat).ch)
        self.assertEqual((), _read(spells=flat).hinges)


class ThePriceKeepsItsHandPickedValueTests(_DofusThree):

    def test_a_cridam_weight_picked_by_hand_keeps_its_price(self):
        hand = dict(WEIGHTS, cridam=WEIGHTS['cridam'] + 55)
        priced, kept = _read('Iop'), _read('Iop', stored=hand)
        self.assertIsNotNone(priced.cridam)
        self.assertIsNone(kept.cridam)
        self.assertEqual((priced.ch, priced.hinges), (kept.ch, kept.hinges))

    def test_the_damage_priority_keeps_its_price(self):
        char = _char('Sram')
        engine = _set_weights(char, {'str'}, apply=False)
        pushed = _set_weights(char, {'str', 'glasscannon'}, apply=False)
        self.assertNotEqual(engine['cridam'], pushed['cridam'])
        priced, kept = _read('Sram', stored=engine, engine=engine), _read('Sram', stored=pushed, engine=engine)
        self.assertIsNotNone(priced.cridam)
        self.assertIsNone(kept.cridam)

    def test_the_crit_and_noncrit_aspects_keep_their_price(self):
        for aspect in ('crit', 'noncrit'):
            with self.subTest(aspect=aspect):
                self.assertIsNone(_read('Iop', aspects={'str', aspect}))

    def test_a_crit_weight_picked_by_hand_keeps_both(self):
        self.assertIsNone(_read('Iop', stored=dict(WEIGHTS, ch=WEIGHTS['ch'] + 60)))


class ThePriceStaysInItsScopeTests(_DofusThree):

    def test_levels_under_two_hundred_have_no_price(self):
        self.assertIsNotNone(_read('Iop', level=200).cridam)
        for level in (199, 150):
            with self.subTest(level=level):
                self.assertIsNone(_read('Iop', level=level))

    def test_the_other_versions_have_no_price_and_read_no_turn(self):
        for game_version in ('beta', 'dofus2', 'touch', 'retro'):
            with self.subTest(game_version=game_version):
                with mock.patch.object(TurnReader, 'full') as full:
                    self.assertIsNone(_read('Iop', game_version=game_version))
                full.assert_not_called()


class ThePriceFollowsTheAnchorWeaponTests(_DofusThree):
    """The set is read on the top weapon, the price at the crit of the first set and at the first break of the first set."""

    def minimal(self, weapon_id):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({STAT_KEY_TO_NAME[key]: value for key, value in OWN.items()})
        given = {'options': {'ap_exo': False, 'mp_exo': False, 'range_exo': False},
                 'base_stats_by_attr': base, 'char_level': 200, 'origin': 'generated'}
        return ModelResultMinimal({'weapon': weapon_id}, given, {})

    def read(self, terms):
        model_input = SimpleNamespace(objective_values=dict(WEIGHTS), forbidden_equips=set(), locked_equips={},
                                      empty_slot_types=[])
        with mock.patch('chardata.crit_curve.get_char_aspects', return_value={'str'}), \
                mock.patch('chardata.crit_curve.get_standard_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.crit_curve.get_stats_weights', return_value=dict(WEIGHTS)), \
                mock.patch('chardata.solution.get_solution_from_minimal',
                           side_effect=lambda char, minimal, refresh_base_stats=True:
                           model_result_from_minimal(minimal)):
            return crit_hinges(_char('Iop'), self.minimal(MINOTOT_SCEPTRE), model_input, terms)

    def reader_of(self, weapon_id):
        from chardata.spell_combo import combat_ap
        from chardata.spells_view import _weapon_castable
        solution = model_result_from_minimal(self.minimal(weapon_id))
        stats = dict(solution.get_stats_total())
        spells = castable_spells('Iop', 200, 'dofus3')
        return (TurnReader(stats, spells, combat_ap(stats.get('ap'), 'dofus3', temporix=False), 'dofus3', 200),
                stats, _weapon_castable(solution))

    def test_the_price_is_read_on_the_swapped_set_up_to_the_first_break_of_the_first_set(self):
        first, first_stats, first_worn = self.reader_of(MINOTOT_SCEPTRE)
        anchor, anchor_stats, anchor_worn = self.reader_of(TEROID_AXE)
        up_to = _first_break(first, first_stats, first_worn)
        own_break = _first_break(anchor, anchor_stats, anchor_worn)
        self.assertNotEqual(up_to, own_break)

        def at(crit):
            base = {'ch': crit - anchor_stats['ch'], 'cridam': first_stats['cridam'] - anchor_stats['cridam']}
            raised = dict(base, cridam=base['cridam'] + CHARACTERISTIC_STEP)
            return (anchor.full(anchor_worn, raised) - anchor.full(anchor_worn, base)) / float(CHARACTERISTIC_STEP)

        per_point = _per_point(anchor, anchor_worn)
        wanted = (at(first_stats['ch']) + at(up_to)) / 2.0 / per_point * _paid()
        mistaken = (at(first_stats['ch']) + at(own_break)) / 2.0 / per_point * _paid()
        self.assertNotAlmostEqual(wanted, mistaken, places=3)
        self.assertAlmostEqual(wanted, self.read({TEROID_AXE: 100000.0, MINOTOT_SCEPTRE: 1.0}).cridam,
                               places=5)

    def test_without_terms_the_price_is_read_on_the_first_set(self):
        first, first_stats, first_worn = self.reader_of(MINOTOT_SCEPTRE)
        up_to = _first_break(first, first_stats, first_worn)
        gain = (_gain(first, first_stats, first_stats['ch'], first_worn)
                + _gain(first, first_stats, up_to, first_worn)) / 2.0
        wanted = gain / _per_point(first, first_worn) * _paid()
        self.assertAlmostEqual(wanted, self.read({}).cridam, places=5)
