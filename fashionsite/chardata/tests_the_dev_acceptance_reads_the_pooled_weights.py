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

    def __init__(self, instance, ratios, ids, score, proven=True, factors=FACTORS, contributions=None, item_sums=None,
                 moves=None, table_range=5, table_mp=0, panel_shift=0.0):
        self.instance = instance
        self.table_range = table_range
        self.table_mp = table_mp
        self.panel_shift = panel_shift
        self.factors = factors
        self.moves = moves or {}
        self.ratios = ratios
        self.set_ids = tuple(ids)
        self.score = score
        self.contributions = contributions or {item_id: 20.0 - item_id for item_id in range(1, 13)}
        self.item_sums = dict(item_sums or {})
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
        base = engine_ratios(self.instance.char_class, self.instance.elements, self.instance.scenario, VERSION)
        read = dict(base, pow=base['pow'] * factor)
        read.update({stat: base[stat] * move for stat, move in self.moves.items()})
        return tuning.Read(read, set(), self.turn, self.ehp, 2.0)

    def u_fit(self, lam):
        return 1.0 if self.ratios is None else 1.2

    def evaluation(self):
        table = self.ratios is not None
        return {'valid': self.proven is True, 'proven': self.proven, 'T': self.turn + (100.0 if table else 0.0),
                'E': self.ehp, 'T_panel': self.turn - 10.0 + (60.0 if table else 0.0),
                'credit': 10.0 + (40.0 if table else 0.0), 'u_acc': {'lo': self.score, 'hi': self.score},
                'u_panel': {end: self.score + (self.panel_shift if table else 0.0) for end in ('lo', 'hi')},
                'pow_share': 0.5, 'seconds': 1.0,
                'stats': {name: {'range': self.table_range if table else 5, 'mp': self.table_mp if table else 0}.get(
                    name, 0) for name in tuning.BLIND_STATS},
                'set': list(self.set_ids)}


class _Runner(object):
    """Solves nothing: every instance gets 1.0 on the engine's weights, 1.1 in a tuning round and `pooled` on the
    pooled ratios, which are the only call fed the moved stats alone: power and those of `moves`, a stat's multiple of
    the engine's ratio that the read gives."""
    game_version = VERSION

    def __init__(self, dev_pooled=1.05, test_pooled=1.05, unproven=0, factors=FACTORS, table_contributions=None,
                 unproven_tiers=None, item_sums=None, moves=None, table_range=5, table_mp=0, test_panel_shift=0.0):
        self.calls = []
        self.table_range = table_range
        self.table_mp = table_mp
        self.panel_shift = {'dev_a': 0.0, 'dev_b': 0.0, 'test': test_panel_shift}
        self.item_sums = item_sums
        self.moves = moves
        self.pooled_stats = {'pow'} | set(moves or ())
        self.table_contributions = table_contributions
        self.pooled = {'dev_a': dev_pooled, 'dev_b': dev_pooled, 'test': test_pooled}
        self.unproven = unproven
        self.unproven_tiers = unproven_tiers
        self.factors = factors
        self.attempts = {}

    def run(self, instance, ratios=None, forbid=(), time_limit=tuning.TIME_LIMIT, guarded=False, budget_factor=1):
        self.calls.append(SimpleNamespace(instance=instance, ratios=dict(ratios) if ratios else None,
                                          forbid=set(forbid), time_limit=time_limit, guarded=guarded))
        ids = (len(self.calls),)
        facts = {'factors': self.factors, 'item_sums': self.item_sums, 'moves': self.moves,
                 'table_range': self.table_range, 'table_mp': self.table_mp,
                 'panel_shift': self.panel_shift[instance.split]}
        if ratios is None:
            return _Result(instance, None, ids, 1.0, **facts)
        if set(ratios) == self.pooled_stats:
            key = tuning.instance_key(instance)
            self.attempts[key] = self.attempts.get(key, 0) + 1
            proven = (self.attempts[key] > self.unproven or instance.split == 'test'
                      or (self.unproven_tiers is not None and instance.tier not in self.unproven_tiers))
            contributions = self.table_contributions if instance.tier == 'high' else None
            return _Result(instance, ratios, ids, self.pooled[instance.split], proven, contributions=contributions,
                           **facts)
        return _Result(instance, ratios, ids, 1.1, **facts)


def _tune(cell=CELL, **runner_options):
    runner = _Runner(**runner_options)
    return runner, tuning.tune_group(runner, [cell], max_rounds=1)[0]


def _pooled_calls(runner):
    return [call for call in runner.calls if call.ratios is not None and set(call.ratios) == runner.pooled_stats]


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
        self.assertEqual({'engine', 'table', 'delta'}, set(record['test']))

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
        _runner_, record = _tune(test_pooled=0.95, test_panel_shift=0.05)
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
        self.assertEqual([False], [pairs['table']['valid'] for pairs in record['dev']])
        self.assertEqual(['unproven'], [pairs['table']['dropped'] for pairs in record['dev']])

    def test_a_lower_tier_that_stays_unproven_leaves_its_pair_out_and_the_cell_on_the_engine(self):
        runner, record = _tune(unproven=2, unproven_tiers=('rest',))
        self.assertEqual(('engine', 'dev_runs'), (record['status'], record['reason']))
        self.assertEqual([True, True, False, True], [pairs['table']['valid'] for pairs in record['dev']])
        self.assertEqual([], [call for call in runner.calls if call.instance.split == 'test'])


#: a table high set whose pieces are not the engine's: its best six are 101 to 106, the engine's are 1 to 6
OTHER_SET = {item_id: 130.0 - item_id for item_id in range(101, 113)}


def _forbids(runner, tier, table):
    """The pieces the engine solves (table False) or the pooled solves of the tier's dev instance were denied."""
    calls = [call for call in runner.calls if call.instance.tier == tier and call.instance.split != 'test'
             and (call.ratios is not None) == table and (not table or set(call.ratios) == {'pow'})]
    return [call.forbid for call in calls]


class ThePiecesAPairGivesUpAreTheSameOnBothSidesTests(SimpleTestCase):

    def test_the_test_pair_forbids_both_high_sets_best_six_to_both_sides(self):
        runner, _record = _tune(table_contributions=OTHER_SET)
        test = [call for call in runner.calls if call.instance.split == 'test']
        self.assertEqual(2, len(test))
        wanted = set(range(1, 7)) | set(range(101, 107))
        self.assertEqual([wanted, wanted], [call.forbid for call in test])

    def test_the_test_pair_forbids_the_engine_sets_best_six_when_both_sets_agree(self):
        runner, _record = _tune()
        test = [call for call in runner.calls if call.instance.split == 'test']
        self.assertEqual([set(range(1, 7))] * 2, [call.forbid for call in test])

    def test_each_dev_pair_loses_its_tiers_cut_of_both_high_sets_on_both_sides(self):
        runner, record = _tune(table_contributions=OTHER_SET)
        cuts = {'mid': {1, 2, 3, 101, 102, 103}, 'rest': {7, 8, 9, 107, 108, 109},
                'tail': {10, 11, 12, 110, 111, 112}}
        for tier, wanted in cuts.items():
            with self.subTest(tier=tier):
                self.assertEqual(wanted, _forbids(runner, tier, table=True)[0])
                self.assertEqual(wanted, _forbids(runner, tier, table=False)[-1])
        self.assertEqual(4, len(record['dev']))

    def test_the_high_pair_forbids_nothing(self):
        runner, _record = _tune(table_contributions=OTHER_SET)
        self.assertEqual([set()], _forbids(runner, 'high', table=True))

    def test_the_tables_high_set_is_solved_before_the_tiers_that_cut_it(self):
        runner, _record = _tune(table_contributions=OTHER_SET)
        pooled = _pooled_calls(runner)
        self.assertEqual(['high', 'mid', 'rest', 'tail'], [call.instance.tier for call in pooled[:4]])
        later = [call for call in runner.calls[runner.calls.index(pooled[0]):] if call.ratios is None
                 and call.instance.split != 'test']
        self.assertEqual(['mid', 'rest', 'tail'], [call.instance.tier for call in later])

    def test_an_engine_run_is_kept_when_both_high_sets_cut_the_same_pieces(self):
        runner, _record = _tune()
        after = runner.calls[runner.calls.index(_pooled_calls(runner)[0]):]
        self.assertEqual([], [call for call in after if call.ratios is None and call.instance.split != 'test'])

    def test_the_cell_records_the_pieces_it_forbade_per_tier(self):
        _runner_, record = _tune(table_contributions=OTHER_SET)
        self.assertEqual([1, 2, 3, 101, 102, 103], record['forbids']['mid'])
        self.assertEqual([1, 2, 3, 4, 5, 6, 101, 102, 103, 104, 105, 106], record['forbids']['low'])

    def test_a_high_pair_that_is_not_proven_leaves_the_tiers_without_a_table_set_to_cut(self):
        runner, record = _tune(unproven=2)
        self.assertEqual(('engine', 'dev_runs'), (record['status'], record['reason']))
        self.assertEqual({}, record['forbids'])
        self.assertEqual(1, len(record['dev']))
        self.assertEqual([], [call for call in runner.calls if call.instance.split == 'test'])


class EveryEvaluationRecordsWhatTheScoreCannotSeeTests(SimpleTestCase):

    def test_a_pair_carries_the_panel_turn_against_the_effect_credit(self):
        _runner_, record = _tune()
        for pair in record['dev'] + [record['test']]:
            delta = pair['delta']
            self.assertEqual((100.0, 60.0, 40.0), (delta['T'], delta['T_panel'], delta['credit']))

    def test_a_pair_carries_the_change_of_the_stats_the_score_cannot_see(self):
        _runner_, record = _tune(table_range=3)
        stats = record['dev'][0]['delta']['stats']
        self.assertEqual(set(tuning.BLIND_STATS), set(stats))
        self.assertEqual(-2, stats['range'])
        self.assertEqual(0, stats['mp'])

    def test_a_pair_with_a_dropped_side_has_no_delta(self):
        _runner_, record = _tune(unproven=2)
        self.assertIsNone(record['dev'][0]['delta'])

    def test_the_record_keeps_the_panel_gain_the_acceptance_read(self):
        _runner_, record = _tune()
        self.assertAlmostEqual(0.05, record['panel_gain']['lo'])


class TheTestPanelAndTheBlindStatsReachTheRecordTests(SimpleTestCase):

    def test_a_cell_whose_sets_keep_the_range_and_the_mp_ships(self):
        _runner_, record = _tune()
        self.assertEqual(('shipped', None), (record['status'], record['reason']))
        self.assertEqual({'dev_median': 0, 'test': 0}, record['range_delta'])
        self.assertEqual({'dev': [0, 0, 0, 0], 'test': 0}, record['mp_delta'])

    def test_a_cell_whose_table_sets_lose_two_range_keeps_the_engine(self):
        _runner_, record = _tune(table_range=3)
        self.assertEqual(('engine', 'range'), (record['status'], record['reason']))
        self.assertEqual({'dev_median': -2, 'test': -2}, record['range_delta'])

    def test_a_cell_whose_table_sets_gain_an_mp_keeps_the_engine(self):
        _runner_, record = _tune(table_mp=1)
        self.assertEqual(('engine', 'mp'), (record['status'], record['reason']))

    def test_a_test_pair_that_gains_only_through_the_effect_credit_keeps_the_engine(self):
        _runner_, record = _tune(test_panel_shift=-0.2)
        self.assertEqual(('engine', 'test_panel'), (record['status'], record['reason']))
        self.assertAlmostEqual(-0.15, record['test_panel_gain']['lo'])
        self.assertAlmostEqual(0.05, record['test_gain']['lo'])


#: what the engine's high set brings; its fixed damage is half of what it is worth under the read
SUMS = {'pow': 100, 'earthdam': 200, 'hp': 600}
HALVED = {'earthdam': 0.5}


class ThePooledPricesAreNeverRescaledTests(SimpleTestCase):
    """Every ratio is read against the played characteristic, which is in no basket: one factor over the owned stats
    would move all their prices against it."""

    def _record(self):
        return _tune(item_sums=SUMS, moves=HALVED)[1]

    def test_the_prices_keep_the_value_the_runs_read_when_the_tables_set_is_worth_less(self):
        record = self._record()
        self.assertAlmostEqual(POOLED, record['ratios']['pow']['value'])
        self.assertAlmostEqual(ENGINE['earthdam'] * 0.5, record['ratios']['earthdam']['value'])
        self.assertEqual(ENGINE['hp'], record['ratios']['hp']['value'])
        self.assertEqual(['earthdam', 'pow'], record['applied'])

    def test_a_stat_the_pooling_left_at_the_engine_stays_there(self):
        record = self._record()
        for stat in ('hp', 'vit', 'airresper', 'perspedam'):
            with self.subTest(stat=stat):
                self.assertEqual(ENGINE[stat], record['ratios'][stat]['value'])
                self.assertEqual('unchanged', record['ratios'][stat]['reason'])
                self.assertNotIn('pooled', record['ratios'][stat])

    def test_the_dev_instances_are_solved_on_the_pooled_prices(self):
        runner, _record = _tune(item_sums=SUMS, moves=HALVED)
        fed = _pooled_calls(runner)
        self.assertEqual(5, len(fed))
        for call in fed:
            self.assertAlmostEqual(POOLED, call.ratios['pow'])
            self.assertAlmostEqual(ENGINE['earthdam'] * 0.5, call.ratios['earthdam'])

    def test_the_factor_is_recorded_as_a_diagnostic(self):
        numeraire = self._record()['numeraire']
        engine_value = sum(ENGINE[stat] * SUMS[stat] for stat in SUMS)
        table_value = POOLED * SUMS['pow'] + ENGINE['earthdam'] * 0.5 * SUMS['earthdam'] + ENGINE['hp'] * SUMS['hp']
        self.assertAlmostEqual(engine_value, numeraire['engine_value'])
        self.assertAlmostEqual(table_value, numeraire['table_value'])
        self.assertAlmostEqual(engine_value / table_value, numeraire['factor'])
        self.assertGreater(numeraire['factor'], 1.0)
        self.assertTrue({'pow', 'earthdam', 'hp'} <= set(numeraire['owned']))

    def test_a_cell_with_no_item_sums_records_a_factor_of_one(self):
        _runner_, record = _tune(moves=HALVED)
        self.assertEqual(1.0, record['numeraire']['factor'])
        self.assertAlmostEqual(POOLED, record['ratios']['pow']['value'])


ECAFLIP = tuning.Cell('Ecaflip', ('int',), 'plain', '200')
ECAFLIP_DUO = tuning.Cell('Ecaflip', ('int', 'agi'), 'plain', '200')
#: power read at 1.8 times the engine's on every dev instance: 1.2 for the mono cell, 2.88 for the duo
RISING = {'high': 1.8, 'mid': 1.8, 'rest': 1.8, 'tail': 1.8}


class ABluffCellHoldsPowerThroughTheTuningTests(SimpleTestCase):
    """The limit on power reaches a real cell only through the notes `tune_group` hands to the pooling."""

    def test_a_mono_cell_holds_power_at_one_and_records_the_limits(self):
        runner, record = _tune(ECAFLIP, factors=RISING)
        entry = record['ratios']['pow']
        self.assertEqual(1.0, entry['limits'][1])
        self.assertEqual((1.0, 'bound'), (entry['value'], entry['reason']))
        self.assertIn(tuning.BLUFF_NOTE, record['notes'])
        for call in _pooled_calls(runner):
            self.assertEqual(1.0, call.ratios['pow'])

    def test_a_duo_cell_holds_power_at_two(self):
        _runner_, record = _tune(ECAFLIP_DUO, factors=RISING)
        entry = record['ratios']['pow']
        self.assertEqual(2.0, entry['limits'][1])
        self.assertEqual((2.0, 'bound'), (entry['value'], entry['reason']))

    def test_a_class_without_the_note_is_not_held(self):
        _runner_, record = _tune(factors=RISING)
        self.assertNotIn(tuning.BLUFF_NOTE, record['notes'])
        self.assertNotIn('limits', record['ratios']['pow'])
        self.assertGreater(record['ratios']['pow']['value'], 1.0)


class ABluffCellKeepsTheEngineUntilItsRowsAreVerifiedTests(SimpleTestCase):

    def test_a_cell_that_gains_everywhere_is_held_with_its_reason(self):
        _runner_, record = _tune(ECAFLIP, factors=RISING)
        self.assertEqual(('engine', tuning.BLUFF_NOTE), (record['status'], record['reason']))

    def test_the_evidence_of_the_held_cell_is_kept(self):
        _runner_, record = _tune(ECAFLIP, factors=RISING)
        self.assertEqual(['pow'], record['applied'])
        self.assertEqual(4, len(record['dev']))
        self.assertAlmostEqual(0.05, record['u_acc_gain']['lo'])
        self.assertAlmostEqual(0.05, record['test_gain']['lo'])

    def test_a_cell_that_would_not_ship_anyway_keeps_its_own_reason(self):
        _runner_, record = _tune(ECAFLIP, factors=RISING, dev_pooled=0.95)
        self.assertEqual(('engine', 'dev_gain'), (record['status'], record['reason']))

    def test_a_class_without_the_note_still_ships(self):
        _runner_, record = _tune(factors=RISING)
        self.assertEqual(('shipped', None), (record['status'], record['reason']))
