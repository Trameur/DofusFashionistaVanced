# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The tuning loop blends at a falling step inside a trust region, stops on a repeat and keeps the best round."""
from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.weight_table import TABLE_STATS, engine_ratios, unit_of

VERSION = 'dofus3'
INSTANCE = tuning.Instance('Iop', ('str',), 'plain', '200', 'high', 'dev_a')
DUO = tuning.Instance('Cra', ('agi', 'int'), 'plain', '200', 'high', 'dev_a')
ENGINE = engine_ratios(INSTANCE.char_class, INSTANCE.elements, INSTANCE.scenario, VERSION)
UNIT = unit_of(INSTANCE.elements, INSTANCE.scenario)


def _read(**changes):
    return dict(ENGINE, **changes)


class _Result(object):
    """What a door gives back, scripted: the read of the set, its fit score, its pieces, whether it was proven."""

    def __init__(self, read=None, u_fit=1.0, ids=(1,), proven=True, infeasible=False, turn=1000.0, switched=()):
        self._read = read
        self._u_fit = u_fit
        self.set_ids = tuple(ids)
        self.proven = proven
        self.infeasible = infeasible
        self.turn = turn
        self.view = object()
        self.ehp = 5000.0
        self.seconds = 1.0
        self.wall = 1.5
        self.notes = []
        self.switched = switched
        self.ratios = None

    def read(self, lam):
        if self._read is None:
            return None
        return tuning.Read(dict(self._read), set(self.switched), self.turn, self.ehp, 2.0)

    def u_fit(self, lam):
        return self._u_fit

    def evaluation(self):
        return {'u_acc': {'lo': self._u_fit, 'hi': self._u_fit}}


class _Runner(object):
    game_version = VERSION

    def __init__(self, *results):
        self.script = list(results)
        self.calls = []

    def run(self, instance, ratios=None, forbid=(), time_limit=tuning.TIME_LIMIT, guarded=False):
        self.calls.append({'ratios': dict(ratios) if ratios else None, 'forbid': tuple(forbid),
                           'time_limit': time_limit})
        return self.script.pop(0)


def _tune(*results, **kwargs):
    runner = _Runner(*results)
    return tuning.tune_instance(runner, kwargs.pop('instance', INSTANCE), **kwargs), runner


class TheBlendTests(SimpleTestCase):

    def test_the_step_is_two_over_the_index_of_the_round_read_plus_two(self):
        current, read = {'pow': 1.0}, {'pow': 1.6}
        for index in range(5):
            with self.subTest(index=index):
                moved = tuning.blend(current, read, index, UNIT)['pow']
                step = 2.0 / (index + 2)
                self.assertAlmostEqual(min(max(1.0 + step * 0.6, 0.5), 2.0), moved)

    def test_the_first_read_jumps_all_the_way(self):
        self.assertAlmostEqual(1.6, tuning.blend({'pow': 1.0}, {'pow': 1.6}, 0, UNIT)['pow'])

    def test_a_step_moves_towards_the_read_from_either_side(self):
        self.assertAlmostEqual(1.4, tuning.blend({'pow': 1.0}, {'pow': 1.6}, 1, UNIT)['pow'])
        self.assertAlmostEqual(0.8, tuning.blend({'pow': 1.0}, {'pow': 0.7}, 1, UNIT)['pow'])

    def test_a_ratio_moves_at_most_to_twice_or_half_what_it_was(self):
        self.assertEqual(2, tuning.TRUST_FACTOR)
        self.assertEqual(2.0, tuning.blend({'pow': 1.0}, {'pow': 9.0}, 0, UNIT)['pow'])
        self.assertEqual(0.5, tuning.blend({'pow': 1.0}, {'pow': 0.1}, 0, UNIT)['pow'])

    def test_the_trust_region_follows_the_ratio_as_it_grows(self):
        current = {'pow': 1.0}
        wanted = []
        for index in range(3):
            current = tuning.blend(current, {'pow': 50.0}, index, UNIT)
            wanted.append(current['pow'])
        self.assertEqual([2.0, 4.0, 8.0], wanted)

    def test_a_read_below_zero_halves_a_ratio_at_most_and_never_makes_one_negative(self):
        self.assertEqual(0.25, tuning.blend({'pow': 0.5}, {'pow': -9.0}, 0, UNIT)['pow'])
        self.assertEqual(0.0, tuning.blend({'cha': 0.0}, {'cha': -3.0}, 0, UNIT)['cha'])

    def test_a_change_under_one_unit_of_weight_leaves_the_ratio_as_it_was(self):
        read = {'pow': 1.0 + 0.4 / UNIT, 'dam': 1.0 + 1.6 / UNIT}
        out = tuning.blend({'pow': 1.0, 'dam': 1.0}, read, 0, UNIT)
        self.assertEqual(1.0, out['pow'])
        self.assertAlmostEqual(read['dam'], out['dam'])

    def test_a_stat_the_engine_weighs_at_zero_stays_at_zero(self):
        out = tuning.blend({'earthdam': 0.0, 'pow': 1.0}, {'earthdam': 3.0, 'pow': 1.5}, 0, UNIT)
        self.assertEqual(0.0, out['earthdam'])

    def test_a_stat_a_set_without_a_weapon_cannot_read_keeps_its_ratio_through_the_rounds(self):
        engine = ENGINE['perweadam']
        read = {stat: value for stat, value in _read(pow=3.0).items() if stat not in tuning.WEAPON_ONLY_STATS}
        run, _runner_ = _tune(_Result(read, ids=(1,)), _Result(read, ids=(2,)), _Result(read, ids=(3,)), max_rounds=2)
        self.assertEqual([engine] * 3, [item.ratios['perweadam'] for item in run.rounds])

    def test_a_stat_the_read_leaves_out_keeps_its_ratio(self):
        self.assertEqual({'pow': 1.0, 'hp': 0.7}, tuning.blend({'pow': 1.0, 'hp': 0.7}, {}, 0, UNIT))

    def test_the_shares_of_a_duo_stay_apart_and_sum_to_two(self):
        out = tuning.blend({'agi': 1.0, 'int': 1.0}, {'agi': 1.9, 'int': 0.1}, 0, unit_of(DUO.elements, 'plain'))
        self.assertAlmostEqual(2.0, out['agi'] + out['int'])
        self.assertEqual(tuning.clamp_shares({'agi': 1.9, 'int': 0.5}), {'agi': out['agi'], 'int': out['int']})

    def test_a_stat_flagged_as_switched_keeps_its_ratio(self):
        out = tuning.blend({'pow': 1.0, 'dam': 1.0}, {'pow': 1.6, 'dam': 1.6}, 0, UNIT, {'dam'})
        self.assertEqual(1.0, out['dam'])
        self.assertAlmostEqual(1.6, out['pow'])

    def test_every_stat_flagged_as_switched_is_held_at_its_current_weight(self):
        current = {'pow': 1.0, 'dam': 1.0, 'ap': 2.0, 'perspedam': 0.5}
        read = {'pow': 1.8, 'dam': 1.8, 'ap': 3.5, 'perspedam': 0.9}
        out = tuning.blend(current, read, 0, UNIT, {'dam', 'perspedam'})
        self.assertEqual((1.0, 0.5), (out['dam'], out['perspedam']))
        self.assertEqual(tuning.blend(current, read, 0, UNIT, set())['pow'], out['pow'])
        self.assertNotEqual(2.0, out['ap'])

    def test_no_flag_leaves_the_blend_as_it_was(self):
        read = {'pow': 1.6, 'dam': 0.7}
        self.assertEqual(tuning.blend({'pow': 1.0, 'dam': 1.0}, read, 1, UNIT),
                         tuning.blend({'pow': 1.0, 'dam': 1.0}, read, 1, UNIT, ()))

    def test_every_stat_the_blend_returns_was_given(self):
        out = tuning.blend(dict(ENGINE), _read(pow=2.0), 0, UNIT)
        self.assertEqual(set(ENGINE), set(out))
        self.assertLessEqual(set(TABLE_STATS), set(out))


class TheLoopFeedsTheDoorTests(SimpleTestCase):

    def test_round_zero_runs_the_engine_weights_and_a_start_table_replaces_them(self):
        run, runner = _tune(_Result(_read(), ids=(1,)), max_rounds=0)
        self.assertIsNone(runner.calls[0]['ratios'])
        self.assertEqual(ENGINE, run.rounds[0].ratios)
        start = _read(pow=1.5)
        run, runner = _tune(_Result(_read(), ids=(1,)), max_rounds=0, start=start)
        self.assertEqual(start, runner.calls[0]['ratios'])

    def test_each_round_is_fed_the_blend_of_the_one_before(self):
        run, runner = _tune(_Result(_read(pow=3.0), ids=(1,)), _Result(_read(pow=3.0), ids=(2,)),
                            _Result(_read(pow=3.0), ids=(3,)), max_rounds=2)
        first = tuning.blend(ENGINE, _read(pow=3.0), 0, UNIT)
        second = tuning.blend(first, _read(pow=3.0), 1, UNIT)
        self.assertEqual(first, runner.calls[1]['ratios'])
        self.assertEqual(second, runner.calls[2]['ratios'])
        self.assertEqual([ENGINE, first, second], [item.ratios for item in run.rounds])

    def test_the_forbidden_pieces_and_the_limit_reach_every_call(self):
        run, runner = _tune(_Result(_read(pow=3.0), ids=(1,)), _Result(_read(pow=3.0), ids=(2,)), max_rounds=1,
                            forbid={7, 5}, time_limit=33)
        self.assertEqual([{5, 7}, {5, 7}], [set(call['forbid']) for call in runner.calls])
        self.assertEqual([33, 33], [call['time_limit'] for call in runner.calls])

    def test_a_round_records_the_weights_that_changed_since_the_one_before(self):
        run, _runner_ = _tune(_Result(_read(pow=3.0), ids=(1,)), _Result(_read(pow=3.0), ids=(2,)), max_rounds=1)
        self.assertEqual({}, run.rounds[0].changed)
        before = int(round(ENGINE['pow'] * UNIT))
        after = int(round(run.rounds[1].ratios['pow'] * UNIT))
        self.assertEqual([before, after], run.rounds[1].changed['pow'])

    def test_the_callback_sees_each_round_as_it_ends(self):
        seen = []
        _tune(_Result(_read(pow=3.0), ids=(1,)), _Result(_read(pow=3.0), ids=(2,)), max_rounds=1,
              on_round=lambda item: seen.append(item.index))
        self.assertEqual([0, 1], seen)

    def test_a_round_records_the_pieces_that_came_and_went(self):
        run, _runner_ = _tune(_Result(_read(pow=3.0), ids=(1, 2)), _Result(_read(pow=3.0), ids=(2, 3)), max_rounds=1)
        self.assertEqual(([3], [1]), run.rounds[1].set_change)


class TheLoopStopsTests(SimpleTestCase):

    def test_it_stops_when_the_set_is_one_it_has_seen(self):
        run, runner = _tune(_Result(_read(pow=3.0), ids=(1,)), _Result(_read(pow=3.0), ids=(2,)),
                            _Result(_read(pow=3.0), ids=(1,)), _Result(_read(pow=3.0), ids=(9,)), max_rounds=4)
        self.assertEqual((True, 'repeat', 3), (run.converged, run.stop, len(run.rounds)))
        self.assertEqual(3, len(runner.calls))

    def test_it_stops_when_the_whole_weights_no_longer_change(self):
        run, runner = _tune(_Result(_read(), ids=(1,)), _Result(_read(), ids=(2,)), max_rounds=4)
        self.assertEqual((True, 'fixed', 1), (run.converged, run.stop, len(run.rounds)))
        self.assertEqual(1, len(runner.calls))

    def test_a_switched_stat_stays_at_the_weight_the_door_was_fed_through_the_rounds(self):
        run, runner = _tune(_Result(_read(pow=3.0, dam=9.0), ids=(1,), switched=('dam',)),
                            _Result(_read(pow=3.0, dam=9.0), ids=(2,), switched=('dam',)),
                            _Result(_read(pow=3.0, dam=9.0), ids=(3,), switched=('dam',)), max_rounds=2)
        self.assertEqual([ENGINE['dam']] * 3, [item.ratios['dam'] for item in run.rounds])
        self.assertNotEqual(ENGINE['pow'], run.rounds[1].ratios['pow'])

    def test_it_stops_when_the_clamped_weights_no_longer_change(self):
        from chardata.stats_weights import MAX_STAT_WEIGHT
        huge = MAX_STAT_WEIGHT * 4.0 / UNIT
        start = _read(ap=huge)
        run, runner = _tune(_Result(_read(ap=huge * 2), ids=(1,)), _Result(_read(ap=huge * 2), ids=(2,)),
                            max_rounds=4, start=start)
        self.assertEqual((True, 'fixed', 1), (run.converged, run.stop, len(run.rounds)))

    def test_the_whole_weights_are_clamped_like_the_stored_ones(self):
        from chardata.stats_weights import MAX_STAT_WEIGHT
        huge = MAX_STAT_WEIGHT * 3.0 / UNIT
        out = tuning.integer_weights({'ap': huge, 'pow': 1.0, 'dam': -huge}, UNIT)
        self.assertEqual({'ap': MAX_STAT_WEIGHT, 'pow': int(round(UNIT)), 'dam': -MAX_STAT_WEIGHT}, out)

    def test_it_stops_after_the_rounds_it_was_given(self):
        results = [_Result(_read(pow=3.0 + index), ids=(index + 1,)) for index in range(6)]
        run, runner = _tune(*results, max_rounds=3)
        self.assertEqual((False, 'rounds', 4), (run.converged, run.stop, len(run.rounds)))
        self.assertEqual(4, len(runner.calls))

    def test_no_round_after_the_engine_run_when_none_were_asked(self):
        run, runner = _tune(_Result(_read(pow=3.0)), max_rounds=0)
        self.assertEqual(('rounds', 1), (run.stop, len(run.rounds)))
        self.assertEqual(1, len(runner.calls))


class TheBestRoundIsKeptTests(SimpleTestCase):

    def _scored(self, scores, **kwargs):
        results = [_Result(_read(pow=3.0 + index), u_fit=score, ids=(index + 1,)) for index, score in enumerate(scores)]
        return _tune(*results, max_rounds=len(scores) - 1, **kwargs)[0]

    def test_the_round_with_the_highest_fit_score_is_the_best(self):
        run = self._scored([1.0, 1.4, 1.2, 1.3])
        self.assertEqual(1, run.best)
        self.assertEqual(1, run.best_round.index)

    def test_the_engine_round_is_the_best_when_nothing_beats_it(self):
        run = self._scored([1.5, 1.4, 1.2])
        self.assertEqual(0, run.best)
        self.assertIs(run.engine, run.best_round.result)

    def test_the_earlier_round_wins_a_tie(self):
        run = self._scored([1.0, 1.4, 1.4, 1.0])
        self.assertEqual(1, run.best)

    def test_a_best_round_that_is_proven_makes_the_run_usable(self):
        self.assertTrue(self._scored([1.0, 1.4]).usable)

    def test_a_run_without_a_round_has_no_best_round_and_is_not_usable(self):
        run, _runner_ = _tune(_Result(proven=False), _Result(proven=False), max_rounds=1)
        self.assertIsNone(run.best)
        self.assertIsNone(run.best_round)
        self.assertFalse(run.usable)
        self.assertIsNone(run.engine)

    def test_the_record_names_the_best_round_and_why_the_run_stopped(self):
        record = self._scored([1.0, 1.4, 1.2]).record()
        self.assertEqual((1, 'rounds', 3), (record['best'], record['stop'], len(record['rounds'])))
        self.assertEqual(INSTANCE.split, record['split'])


class AnUnprovenOrEmptySolveIsHandledTests(SimpleTestCase):

    def test_an_unproven_solve_is_made_again_at_twice_the_limit(self):
        run, runner = _tune(_Result(_read(pow=3.0), proven=False), _Result(_read(pow=3.0), proven=True), max_rounds=0,
                            time_limit=40)
        self.assertEqual([40, 40 * tuning.RETRY_FACTOR], [call['time_limit'] for call in runner.calls])
        self.assertEqual(80, 40 * tuning.RETRY_FACTOR)
        self.assertTrue(run.rounds[0].result.proven)
        self.assertEqual([], run.dropped)

    def test_a_solve_still_unproven_after_that_is_dropped(self):
        run, runner = _tune(_Result(_read(pow=3.0)), _Result(proven=False), _Result(proven=None), max_rounds=3)
        self.assertEqual(1, len(run.rounds))
        self.assertEqual([{'round': 1, 'reason': 'unproven'}], run.dropped)
        self.assertEqual('unproven', run.stop)
        self.assertFalse(run.converged)
        self.assertEqual(3, len(runner.calls))

    def test_the_rounds_before_a_dropped_one_are_kept_and_the_best_of_them_wins(self):
        run, _runner_ = _tune(_Result(_read(pow=3.0), u_fit=1.0, ids=(1,)),
                              _Result(_read(pow=3.0), u_fit=1.3, ids=(2,)),
                              _Result(proven=False), _Result(proven=False), max_rounds=4)
        self.assertEqual(2, len(run.rounds))
        self.assertEqual(1, run.best)
        self.assertTrue(run.usable)
        self.assertEqual('unproven', run.stop)

    def test_an_infeasible_door_is_dropped_without_a_second_try(self):
        run, runner = _tune(_Result(infeasible=True), max_rounds=3)
        self.assertEqual([{'round': 0, 'reason': 'infeasible'}], run.dropped)
        self.assertEqual(('infeasible', 0, 1), (run.stop, len(run.rounds), len(runner.calls)))

    def test_a_retry_that_turns_out_infeasible_is_dropped_as_infeasible(self):
        run, runner = _tune(_Result(proven=False), _Result(infeasible=True), max_rounds=3)
        self.assertEqual('infeasible', run.stop)
        self.assertEqual(2, len(runner.calls))

    def test_a_set_with_no_turn_is_dropped_with_its_reason(self):
        run, _runner_ = _tune(_Result(_read(pow=3.0)), _Result(read=None), max_rounds=3)
        self.assertEqual([{'round': 1, 'reason': 'no_turn'}], run.dropped)
        self.assertEqual(('no_turn', 1), (run.stop, len(run.rounds)))

    def test_a_set_with_no_fit_score_is_dropped_with_its_reason(self):
        run, _runner_ = _tune(_Result(_read(pow=3.0), u_fit=None), max_rounds=3)
        self.assertEqual([{'round': 0, 'reason': 'no_turn'}], run.dropped)
        self.assertEqual(0, len(run.rounds))

    def test_a_turn_at_or_below_zero_is_dropped(self):
        for turn in (0.0, -5.0):
            with self.subTest(turn=turn):
                run, _runner_ = _tune(_Result(read=None, turn=turn), max_rounds=2)
                self.assertEqual(('no_turn', 0), (run.stop, len(run.rounds)))
