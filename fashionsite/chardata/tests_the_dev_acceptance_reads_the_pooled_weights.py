# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The acceptance judges the weights a cell would ship: its dev instances are solved again on the pooled ratios."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.weight_table import engine_ratios

VERSION = 'dofus3'
CELL = tuning.Cell('Iop', ('str',), 'plain', '200')
ENGINE = engine_ratios(CELL.char_class, CELL.elements, CELL.scenario, VERSION)
#: what each dev instance reads for power, as a multiple of the engine's: no instance reads the median of them
FACTORS = {'high': 1.3, 'mid': 1.45, 'rest': 1.6, 'tail': 1.55}
POOLED = ENGINE['pow'] * 1.5


class _Result(object):
    """A door's answer: its read moves power by the factor of its instance, and its score is scripted."""

    def __init__(self, instance, ratios, ids, score, proven=True, factors=FACTORS):
        self.instance = instance
        self.factors = factors
        self.ratios = ratios
        self.set_ids = tuple(ids)
        self.score = score
        self.contributions = {item_id: 20.0 - item_id for item_id in range(1, 13)}
        self.proven = proven
        self.infeasible = False
        self.turn = 1000.0
        self.view = object()
        self.ehp = 5000.0
        self.seconds = 1.0
        self.wall = 1.5
        self.notes = []
        self.guard = None

    def read(self, lam):
        factor = self.factors.get(self.instance.tier, 1.0)
        return tuning.Read(dict(ENGINE, pow=ENGINE['pow'] * factor), set(), self.turn, self.ehp, 2.0)

    def u_fit(self, lam):
        return 1.0 if self.ratios is None else 1.2

    def evaluation(self):
        return {'valid': self.proven is True, 'proven': self.proven, 'T': self.turn, 'E': self.ehp,
                'u_acc': {'lo': self.score, 'hi': self.score}, 'pow_share': 0.5, 'seconds': 1.0,
                'set': list(self.set_ids)}


class _Runner(object):
    """Solves nothing: every instance gets 1.0 on the engine's weights, 1.1 in a tuning round and `pooled` on the
    pooled ratios, which are the only call fed power alone."""
    game_version = VERSION

    def __init__(self, dev_pooled=1.05, test_pooled=1.05, unproven=0, factors=FACTORS):
        self.calls = []
        self.pooled = {'dev_a': dev_pooled, 'dev_b': dev_pooled, 'test': test_pooled}
        self.unproven = unproven
        self.factors = factors
        self.attempts = {}

    def run(self, instance, ratios=None, forbid=(), time_limit=tuning.TIME_LIMIT, guarded=False):
        self.calls.append(SimpleNamespace(instance=instance, ratios=dict(ratios) if ratios else None,
                                          forbid=set(forbid), time_limit=time_limit, guarded=guarded))
        ids = (len(self.calls),)
        if ratios is None:
            return _Result(instance, None, ids, 1.0, factors=self.factors)
        if set(ratios) == {'pow'}:
            key = tuning.instance_key(instance)
            self.attempts[key] = self.attempts.get(key, 0) + 1
            proven = self.attempts[key] > self.unproven or instance.split == 'test'
            return _Result(instance, ratios, ids, self.pooled[instance.split], proven, self.factors)
        return _Result(instance, ratios, ids, 1.1, factors=self.factors)


def _tune(**runner_options):
    runner = _Runner(**runner_options)
    return runner, tuning.tune_group(runner, [CELL], max_rounds=1)[0]


def _pooled_calls(runner):
    return [call for call in runner.calls if call.ratios is not None and set(call.ratios) == {'pow'}]


class TheDevInstancesAreSolvedAgainTests(SimpleTestCase):

    def test_the_cell_applies_the_median_of_what_its_dev_instances_read(self):
        _runner_, record = _tune()
        self.assertEqual(['pow'], record['applied'])
        self.assertAlmostEqual(POOLED, record['ratios']['pow']['value'])

    def test_no_dev_round_was_fed_the_pooled_weight(self):
        runner, _record = _tune()
        fed = [call.ratios['pow'] for call in runner.calls if call.ratios is not None and len(call.ratios) > 1]
        self.assertTrue(fed)
        for value in fed:
            self.assertNotAlmostEqual(POOLED, value)

    def test_each_dev_instance_is_solved_again_on_the_pooled_ratios_with_its_own_forbidden_pieces(self):
        runner, record = _tune()
        again = _pooled_calls(runner)[:4]
        self.assertEqual(['high', 'mid', 'rest', 'tail'], [call.instance.tier for call in again])
        for call in again:
            self.assertAlmostEqual(POOLED, call.ratios['pow'])
            self.assertEqual({'pow'}, set(call.ratios))
            self.assertEqual(tuning.TIER_FORBIDDEN[call.instance.tier][1], len(call.forbid))
        self.assertEqual(4, len(record['dev']))

    def test_the_test_instance_is_solved_on_the_engine_and_on_the_pooled_ratios_as_before(self):
        runner, record = _tune()
        test = [call for call in runner.calls if call.instance.split == 'test']
        self.assertEqual(2, len(test))
        self.assertIsNone(test[0].ratios)
        self.assertEqual({'pow'}, set(test[1].ratios))
        self.assertAlmostEqual(POOLED, test[1].ratios['pow'])
        self.assertEqual({'engine', 'table'}, set(record['test']))

    def test_nothing_is_solved_again_when_nothing_is_applied(self):
        runner, record = _tune(factors={})
        self.assertEqual([], record['applied'])
        self.assertEqual([], record['dev'])
        self.assertEqual([], _pooled_calls(runner))
        self.assertEqual(('engine', 'no_change'), (record['status'], record['reason']))


class TheAcceptanceReadsTheSolvesOnThePooledRatiosTests(SimpleTestCase):

    def test_a_cell_whose_pooled_solves_gain_ships(self):
        _runner_, record = _tune()
        self.assertEqual(('shipped', None), (record['status'], record['reason']))
        self.assertEqual([1.05] * 4, [pairs['table']['u_acc']['lo'] for pairs in record['dev']])
        self.assertEqual([1.0] * 4, [pairs['engine']['u_acc']['lo'] for pairs in record['dev']])

    def test_a_loss_on_the_pooled_ratios_keeps_the_engine_whatever_the_rounds_gained(self):
        _runner_, record = _tune(dev_pooled=0.95)
        self.assertEqual(('engine', 'dev_gain'), (record['status'], record['reason']))
        self.assertEqual([0.95] * 4, [pairs['table']['u_acc']['lo'] for pairs in record['dev']])
        self.assertTrue(all(run['rounds'][run['best']]['u_acc']['lo'] == 1.1 for run in record['instances']))

    def test_the_test_instance_decides_as_before(self):
        _runner_, record = _tune(test_pooled=0.95)
        self.assertEqual(('engine', 'test_gain'), (record['status'], record['reason']))

    def test_a_solve_that_is_not_proven_is_made_again_at_twice_the_limit(self):
        runner, record = _tune(unproven=1)
        again = [call for call in _pooled_calls(runner) if call.instance.split != 'test']
        self.assertEqual(8, len(again))
        self.assertEqual([tuning.TIME_LIMIT, tuning.TIME_LIMIT * tuning.RETRY_FACTOR] * 4,
                         [call.time_limit for call in again])
        self.assertEqual(('shipped', None), (record['status'], record['reason']))

    def test_a_solve_that_stays_unproven_leaves_the_pair_out_and_the_cell_on_the_engine(self):
        runner, record = _tune(unproven=2)
        self.assertEqual(('engine', 'dev_runs'), (record['status'], record['reason']))
        self.assertEqual([False] * 4, [pairs['table']['valid'] for pairs in record['dev']])
        self.assertEqual(['unproven'] * 4, [pairs['table']['dropped'] for pairs in record['dev']])
