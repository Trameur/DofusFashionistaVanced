# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A dev median of zero that identical sets cause passes the dev gain when no pair loses more than a hundredth and a
pair gains more than a hundredth; every other zero median still fails it."""
from django.test import SimpleTestCase

from chardata import tests_a_weight_cell_ships_only_when_both_folds_agree as pooling
from chardata import tests_the_dev_acceptance_reads_the_pooled_weights as doors
from chardata import weight_tuning as tuning

ENGINE_SET = [1, 2, 3]
GLASSCANNON = tuning.Cell('Iop', ('str',), 'glasscannon', '200')


def _pair(lo, hi=None, same=False):
    """A pair whose table scores `lo` and `hi` above the engine's zero at both ends, on the same set or another."""
    hi = lo if hi is None else hi
    pair = pooling._pair()
    for side, scores in (('engine', (0.0, 0.0)), ('table', (lo, hi))):
        pair[side]['u_acc'] = dict(zip(('lo', 'hi'), scores))
        pair[side]['u_panel'] = dict(zip(('lo', 'hi'), scores))
    pair['engine']['set'] = list(ENGINE_SET)
    pair['table']['set'] = list(ENGINE_SET) if same else [1, 2, 4]
    return pair


def _same():
    return _pair(0.0, 0.0, same=True)


def _reason(dev):
    return pooling._accept(dev=dev)['reason']


class ADevMedianHeldAtZeroByIdenticalSetsPassesTests(SimpleTestCase):

    def test_three_identical_sets_and_one_pair_that_gains_pass(self):
        verdict = pooling._accept(dev=[_same(), _same(), _same(), _pair(0.15, 0.125)])
        self.assertEqual(('shipped', None), (verdict['status'], verdict['reason']))
        self.assertEqual({'lo': 0.0, 'hi': 0.0}, verdict['u_acc_gain'])
        self.assertIs(True, verdict['weak_dominance'])

    def test_it_is_the_median_of_an_odd_number_of_pairs_too(self):
        self.assertIsNone(_reason([_same(), _same(), _same(), _pair(0.0625), _pair(0.1)]))

    def test_a_pair_that_loses_a_hundredth_or_less_is_allowed(self):
        self.assertIsNone(_reason([_same(), _same(), _pair(-0.01), _pair(0.2)]))

    def test_a_median_that_gains_on_its_own_is_not_called_weak_dominance(self):
        verdict = pooling._accept()
        self.assertEqual('shipped', verdict['status'])
        self.assertNotIn('weak_dominance', verdict)

    def test_the_dev_failure_that_picks_the_step_agrees(self):
        self.assertIsNone(tuning.dev_failure([_same(), _same(), _same(), _pair(0.15)]))


class AMedianAtZeroThatTheWeakDominanceDoesNotCoverStillFailsTests(SimpleTestCase):

    def test_no_pair_gaining_keeps_dev_gain(self):
        self.assertEqual('dev_gain', _reason([_same() for _ in range(4)]))
        self.assertEqual('dev_gain', tuning.dev_failure([_same() for _ in range(4)]))

    def test_a_pair_that_gains_a_hundredth_or_less_is_not_enough(self):
        self.assertEqual('dev_gain', _reason([_same(), _same(), _same(), _pair(0.01)]))
        self.assertEqual('dev_gain', _reason([_same(), _same(), _same(), _pair(0.0078125)]))
        self.assertEqual('dev_gain', tuning.dev_failure([_same(), _same(), _same(), _pair(0.01)]))

    def test_the_gain_must_come_at_the_end_whose_median_is_zero(self):
        self.assertEqual('dev_gain', _reason([_same(), _same(), _same(), _pair(0.2, 0.0078125)]))
        self.assertEqual('dev_gain', _reason([_same(), _same(), _same(), _pair(0.0078125, 0.2)]))
        self.assertIsNone(_reason([_same(), _same(), _same(), _pair(0.2, 0.2)]))

    def test_a_pair_that_loses_more_than_a_hundredth_keeps_dev_gain_not_the_loss_reason(self):
        dev = [_same(), _same(), _pair(0.2), _pair(-0.0625)]
        self.assertEqual('dev_gain', _reason(dev))
        self.assertEqual('dev_gain', tuning.dev_failure(dev))

    def test_the_loss_may_come_at_either_end(self):
        self.assertEqual('dev_gain', _reason([_same(), _same(), _pair(0.2, 0.2), _pair(0.3, -0.0625)]))

    def test_a_median_at_zero_that_no_identical_set_causes_is_no_weak_dominance(self):
        dev = [_pair(-0.0078125), _pair(-0.00390625), _pair(0.00390625), _pair(0.03125)]
        self.assertEqual(0.0, tuning._median_gains([tuning._gains(pairs) for pairs in dev])['lo'])
        self.assertEqual('dev_gain', _reason(dev))

    def test_a_zero_gain_from_another_set_is_not_an_identical_set(self):
        self.assertEqual('dev_gain', _reason([_pair(0.0), _pair(0.0), _pair(0.0), _pair(0.2)]))

    def test_a_median_below_zero_is_no_weak_dominance(self):
        self.assertEqual('dev_gain', _reason([_pair(-0.0078125), _pair(-0.0078125), _same(), _pair(0.2)]))

    def test_a_set_missing_from_the_evaluation_is_not_an_identical_one(self):
        bare = pooling._pair(0.0, 0.0)
        self.assertEqual('dev_gain', _reason([bare, bare, bare, _pair(0.2)]))

    def test_the_other_checks_still_apply_after_it(self):
        dev = [_same(), _same(), _same(), _pair(0.2)]
        self.assertEqual('test_gain', pooling._accept(dev=dev, test=pooling._pair(gain_lo=0.0))['reason'])
        dev = [dict(pair, table=dict(pair['table'], pow_share=0.9)) for pair in dev]
        self.assertEqual('ceiling', _reason(dev))


class _IdenticalRunner(doors._Runner):
    """The dev door, whose solves on the pooled ratios of the tiers in `same` give the engine's own set."""

    def __init__(self, same=('high', 'mid', 'rest'), **options):
        super().__init__(**options)
        self.same = same
        self.engine_sets = {}

    def run(self, instance, ratios=None, forbid=(), time_limit=tuning.TIME_LIMIT, guarded=False, budget_factor=1):
        result = super().run(instance, ratios, forbid, time_limit, guarded, budget_factor)
        key = tuning.instance_key(instance)
        if ratios is None:
            self.engine_sets[key] = result.set_ids
        elif (set(ratios) == self.pooled_stats and instance.split != 'test' and instance.tier in self.same
              and not guarded):
            result.set_ids, result.score = self.engine_sets[key], 1.0
        if guarded:
            result.credit, result.judgeable = object(), True
        return result


def _tune(cell=doors.CELL, **options):
    runner = _IdenticalRunner(**options)
    return runner, tuning.tune_group(runner, [cell], max_rounds=1)[0]


class ACellWhoseDevSetsAreMostlyTheEnginesShipsAtTheFullStepTests(SimpleTestCase):

    def test_it_ships_on_the_pair_that_gained_without_a_damped_step(self):
        _runner, record = _tune()
        self.assertEqual(('shipped', None, 'full'), (record['status'], record['reason'], record['step']))
        self.assertIsNone(record['fallback'])
        self.assertIs(True, record['weak_dominance'])
        self.assertEqual([0.0, 0.0, 0.0], [pair['table']['u_acc']['lo'] - pair['engine']['u_acc']['lo']
                                          for pair in record['dev']][:3])

    def test_the_guarded_pair_of_such_a_cell_is_solved_as_for_any_cell_that_reaches_it(self):
        runner, record = _tune(GLASSCANNON)
        self.assertEqual('shipped', record['status'])
        self.assertEqual(2, len([call for call in runner.calls if call.guarded]))

    def test_with_no_pair_that_gained_it_keeps_the_engine_and_tries_the_damped_step(self):
        _runner, record = _tune(same=('high', 'mid', 'rest', 'tail'))
        self.assertEqual(('engine', 'dev_gain'), (record['status'], record['reason']))
        self.assertEqual('dev_gain', record['fallback']['trigger'])
        self.assertNotIn('weak_dominance', record)
