# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A cell whose spell rows are priced as if they all landed holds power to the number of elements played."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning

PLAN = {split: [tier for tier, planned in tuning.INSTANCE_PLAN if planned == split] for split in tuning.DEV_SPLITS}
ENGINE = {'pow': 0.667, 'hp': 0.2}
NOTED = (tuning.BLUFF_NOTE,)


def _runs(*powers, hp=0.2, elements=('int',), engine=None):
    """The four dev runs, two per fold, whose best round holds these power ratios (one value for all four)."""
    powers = powers * 4 if len(powers) == 1 else powers
    runs = []
    for position, power in enumerate(powers):
        split, which = tuning.DEV_SPLITS[position // 2], position % 2
        instance = tuning.Instance('Ecaflip', elements, 'glasscannon', '200', PLAN[split][which], split)
        run = tuning.TuneRun(instance)
        run.engine_ratios = dict(engine or ENGINE)
        read = tuning.Read({}, set(), 1000.0, 5000.0, 2.0)
        run.rounds = [tuning.Round(0, {'pow': power, 'hp': hp}, SimpleNamespace(proven=True, set_ids=(position,), notes=[]), read, 1.0, {})]
        run.best = 0
        runs.append(run)
    return runs


def _pool(*powers, notes=NOTED, engine=None, **kwargs):
    return tuning.pool_cell(_runs(*powers, engine=engine, **kwargs), engine or ENGINE, notes=notes)


class PowerIsHeldToTheElementsPlayedTests(SimpleTestCase):

    def test_a_mono_cell_with_the_note_never_goes_above_one(self):
        entry = _pool(1.4)['pow']
        self.assertEqual((1.0, 'bound'), (entry['value'], entry['reason']))

    def test_a_duo_cell_with_the_note_never_goes_above_two(self):
        entry = _pool(2.5, elements=('int', 'agi'))['pow']
        self.assertEqual((2.0, 'bound'), (entry['value'], entry['reason']))
        entry = _pool(1.4, elements=('int', 'agi'))['pow']
        self.assertEqual((1.4, None), (entry['value'], entry.get('reason')))

    def test_a_ratio_under_the_count_is_read_as_before(self):
        entry = _pool(0.9)['pow']
        self.assertEqual((0.9, None), (entry['value'], entry.get('reason')))

    def test_without_the_note_power_keeps_the_general_bounds(self):
        entry = _pool(1.4, notes=())['pow']
        self.assertEqual((1.4, None), (entry['value'], entry.get('reason')))
        self.assertNotIn('limits', entry)

    def test_an_engine_weight_above_the_count_stays_the_highest_ratio(self):
        engine = {'pow': 1.6, 'hp': 0.2}
        entry = _pool(2.0, engine=engine)['pow']
        self.assertEqual((1.6, 'bound', 1.6), (entry['value'], entry['reason'], entry['limits'][1]))

    def test_only_power_is_held(self):
        entries = _pool(1.4, hp=0.5)
        self.assertEqual(0.5, entries['hp']['value'])
        self.assertNotIn('limits', entries['hp'])

    def test_the_limits_are_recorded_with_the_entry(self):
        limits = _pool(1.4)['pow']['limits']
        self.assertAlmostEqual(tuning.BOUNDS[0] * 0.667, limits[0])
        self.assertEqual(1.0, limits[1])

    def test_a_value_pooled_over_the_group_is_held_too(self):
        cell = _runs(1.2, 1.2, 2.0, 2.0)
        group = cell + _runs(1.5) * 2
        entries = tuning.pool_cell(cell, ENGINE, group, notes=NOTED)
        self.assertEqual(('bound', 1.0), (entries['pow']['reason'], entries['pow']['value']))
        free = tuning.pool_cell(cell, ENGINE, group)
        self.assertEqual(('pooled', 1.5), (free['pow']['reason'], free['pow']['value']))


class TheNoteComesFromTheClassTests(SimpleTestCase):

    def test_ecaflip_carries_it_and_iop_does_not(self):
        runs = _runs(1.4)
        self.assertIn(tuning.BLUFF_NOTE, tuning._notes(tuning.Cell('Ecaflip', ('int',), 'glasscannon', '200'), runs))
        self.assertNotIn(tuning.BLUFF_NOTE, tuning._notes(tuning.Cell('Iop', ('str',), 'glasscannon', '200'), runs))
