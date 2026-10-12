# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""AP stays at the engine's weight: its read is recorded for later, never fed to a round and never applied."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.weight_table import engine_ratios, unit_of

VERSION = 'dofus3'
INSTANCE = tuning.Instance('Iop', ('str',), 'plain', '200', 'high', 'dev_a')
ENGINE = engine_ratios(INSTANCE.char_class, INSTANCE.elements, INSTANCE.scenario, VERSION)
UNIT = unit_of(INSTANCE.elements, INSTANCE.scenario)
PLAN = {split: [tier for tier, planned in tuning.INSTANCE_PLAN if planned == split] for split in tuning.DEV_SPLITS}


class _Result(object):
    def __init__(self, read, ids):
        self._read = read
        self.set_ids = tuple(ids)
        self.proven = True
        self.infeasible = False
        self.turn = 1000.0
        self.view = object()
        self.ehp = 5000.0
        self.seconds = 1.0
        self.wall = 1.5
        self.notes = []
        self.ratios = None

    def read(self, lam):
        return tuning.Read(dict(self._read), set(), self.turn, self.ehp, 2.0)

    def u_fit(self, lam):
        return 1.0


class _Runner(object):
    game_version = VERSION

    def __init__(self, read):
        self.read = read
        self.calls = []

    def run(self, instance, ratios=None, forbid=(), time_limit=tuning.TIME_LIMIT, guarded=False):
        self.calls.append(dict(ratios) if ratios else None)
        return _Result(self.read, (len(self.calls),))


def _runs(ap_reads, engine):
    runs = []
    for position, ap in enumerate(ap_reads):
        split, which = tuning.DEV_SPLITS[position // 2], position % 2
        instance = tuning.Instance('Iop', ('str',), 'plain', '200', PLAN[split][which], split)
        run = tuning.TuneRun(instance)
        run.engine_ratios = dict(engine)
        read = tuning.Read({'ap': ap, 'pow': 1.0}, set(), 1000.0, 5000.0, 2.0)
        round_ratios = {'ap': engine['ap'], 'pow': 1.0}
        run.rounds = [tuning.Round(0, round_ratios, SimpleNamespace(proven=True), read, 1.0, {})]
        run.best = 0
        runs.append(run)
    return runs


class APIsNeverFedToARoundTests(SimpleTestCase):

    def test_a_read_that_triples_ap_leaves_it_at_the_engine_weight_in_every_round(self):
        runner = _Runner(dict(ENGINE, ap=ENGINE['ap'] * 3, pow=ENGINE['pow'] * 3))
        run = tuning.tune_instance(runner, INSTANCE, max_rounds=2)
        self.assertEqual(3, len(run.rounds))
        self.assertEqual([ENGINE['ap']] * 3, [item.ratios['ap'] for item in run.rounds])
        self.assertGreater(run.rounds[1].ratios['pow'], ENGINE['pow'])

    def test_the_held_stats_are_ap_alone(self):
        self.assertEqual(('ap',), tuning.HELD_STATS)


class APIsPooledAsHeldTests(SimpleTestCase):

    def _pool(self, ap_reads=(1.5, 1.6, 1.7, 1.8)):
        engine = {'ap': 1.0, 'pow': 1.0}
        return tuning.pool_cell(_runs(ap_reads, engine), engine)

    def test_the_entry_keeps_the_engine_weight_and_is_weak(self):
        entry = self._pool()['ap']
        self.assertEqual((1.0, True, 'held'), (entry['value'], entry['weak'], entry['reason']))

    def test_the_entry_records_what_each_build_read_and_the_median(self):
        entry = self._pool()['ap']
        self.assertEqual([1.5, 1.6, 1.7, 1.8], sorted(entry['read']['builds'].values()))
        self.assertEqual(1.65, entry['read']['median'])

    def test_the_cell_applies_no_ap_whatever_the_builds_read(self):
        entries = self._pool(ap_reads=(3.0, 3.0, 3.0, 3.0))
        self.assertNotIn('ap', tuning.applied_ratios(entries))

    def test_a_cell_with_no_run_keeps_the_engine_weight_and_reads_nothing(self):
        engine = {'ap': 1.0, 'pow': 1.0}
        entry = tuning.pool_cell([], engine)['ap']
        self.assertEqual((1.0, True, 'held'), (entry['value'], entry['weak'], entry['reason']))
        self.assertEqual({'builds': {}, 'median': None}, entry['read'])
