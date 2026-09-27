# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A priority solve keeps the safeguard's share of the balanced build; a build without one solves as before."""
import math
import pickle
import unittest
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils import translation

from chardata import fashion_action, presets
from chardata.char_blobs import read_char_blob
from chardata.coaching_view import create_build
from chardata.min_stats import get_min_stats_digested
from chardata.options import set_options
from chardata.solution import get_solution
from chardata.stats_weights import get_stats_weights
from chardata.wizard_sliders import set_wizard_sliders
from fashionistapulp import lpproblem
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import (EFFECTIVE_HP_CONSTRAINT, EFFECTIVE_HP_MINIMUM, Model,
                                   ModelInput)
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure, set_current_game_version

NEW_SENTENCES = (
    'Safeguard not applied: the solver found no balanced set to compare with.',
    "Safeguard not applied: the solver found no set keeping %(share)s%% of the balanced "
    "build's effective HP (%(balanced)s), so this set does without it.",
    "Safeguard not applied: the solver found no set keeping %(share)s%% of the balanced "
    "build's best turn (%(balanced)s), so this set does without it.",
    'Safeguard: effective HP at least %(share)s%% of the balanced build '
    '(%(kept)s of %(balanced)s).',
    'Safeguard: best turn at least %(share)s%% of the balanced build (%(kept)s of %(balanced)s).',
    'Safeguard: effective HP at %(reached)s%% of the balanced build (%(kept)s of %(balanced)s), '
    'short of the %(share)s%% aimed for.',
    'Safeguard: best turn at %(reached)s%% of the balanced build (%(kept)s of %(balanced)s), '
    'short of the %(share)s%% aimed for.',
    "Safeguard not applied: the balanced build's best turn could not be computed.",
    'Safeguard: the solver ran out of time before it found a set for the priority, so this is '
    'the balanced build.',
    'This set trails the balanced build on both counts: best turn %(turn)s against '
    '%(balanced_turn)s, effective HP %(hp)s against %(balanced_hp)s.',
    'Compared with the balanced build, a Damage priority gives up at most this share of '
    'effective HP, and a Defense or Heals priority aims to give up at most this share of best '
    'turn damage. The build page shows what was kept.',
)


def _solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


def _hat_with_vitality(version='dofus3'):
    structure = get_structure(version)
    hats = structure.get_unique_items_by_type_and_level('Hat', 200)
    vitality = structure.get_stat_by_key('vit').id
    return max(hats, key=lambda item: dict(item.stats).get(vitality, 0))


def _answer(model_input, item_per_slot, proven=True):
    """What the solver hands back: a set and its stats, in the shape fashion() stores."""
    input_ = {'options': model_input.options, 'base_stats_by_attr':
              dict(model_input.base_stats_by_attr), 'char_level': model_input.char_level,
              'origin': 'generated', 'locked_equips': {}}
    stats = {key: 0 for _name, key in STATS_NAMES}
    result = ModelResultMinimal(dict(item_per_slot), input_, stats)
    result.proven = proven
    result.solve_seconds = 1.0
    return 'Optimal', stats, result


class _Memory(object):
    """Answers every solve from a rule instead of running the solver."""

    def __init__(self, rule):
        self.rule = rule
        self.asked = []

    def get(self, model_input):
        self.asked.append(model_input)
        return self.rule(model_input)

    def put(self, model_input, result_tuple):
        raise AssertionError('the solver ran')


class _EmptyMemory(object):

    def __init__(self):
        self.kept = []

    def get(self, model_input):
        return None

    def put(self, model_input, result_tuple):
        self.kept.append(model_input)


class _Clock(object):

    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now


class _TimedModel(object):
    """Stands in for a pooled model: each run takes its seconds on the clock and ends on its status."""

    def __init__(self, clock, runs, hat, proven=False):
        self.clock = clock
        self.runs = list(runs)
        self.hat = hat
        self.proven = proven
        self.limits = []
        self.status = None

    def setup(self, model_input):
        self.input = model_input

    def run(self, retries):
        seconds, self.status = self.runs.pop(0)
        self.limits.append(lpproblem.SOLVER.timeLimit)
        self.clock.now += seconds

    def get_solved_status(self):
        return self.status

    def solution_is_proven(self):
        return self.proven

    def get_candidate_pool(self):
        return {}

    def get_stats(self):
        return _answer(self.input, {})[1]

    def get_result_minimal(self):
        result = _answer(self.input, {'hat': self.hat.id}, self.proven)[2]
        result.weights_seen = dict(self.input.objective_values)
        return result


class _BuildMixin(object):
    version = 'dofus3'
    prefix = ''

    def setUp(self):
        set_current_game_version(self.version)
        self.owner = User.objects.create_user('guard', 'guard@test.local', 'pw-42-solid')
        self.client.force_login(self.owner)
        self.hat = _hat_with_vitality(self.version)

    def tearDown(self):
        set_current_game_version('dofus3')

    def build(self, aspects, priority=None, guard_pct=None, char_class='Iop'):
        request = RequestFactory().post('/')
        request.user = self.owner
        char = create_build(request, char_class, 200, set(aspects), self.version)
        if priority:
            presets.apply_setup_choices(char, set(aspects), priority=priority,
                                        set_minimums=False, guard_pct=guard_pct)
        return char

    def solve(self, char, rule):
        memory = _Memory(rule)
        with mock.patch('chardata.fashion_action.MEMORY', memory):
            response = self.client.get('%s/fashion/%d/' % (self.prefix, char.pk))
        self.assertEqual(302, response.status_code)
        char.refresh_from_db()
        return memory.asked, response

    def facts(self, char):
        return getattr(read_char_blob(char.minimal_solution, None, 'minimal_solution', char), 'guard', None)

    def page(self, char, prefix=''):
        response = self.client.get('%s%s/solution/%d/' % (prefix, self.prefix, char.pk),
                                   HTTP_ACCEPT_LANGUAGE=prefix.strip('/') or 'en')
        self.assertEqual(200, response.status_code)
        return response.content.decode('utf-8')

    def wearing_the_hat(self, model_input):
        return _answer(model_input, {'hat': self.hat.id})


class TheSafeguardIsReadFromTheBuildTests(_BuildMixin, TestCase):

    def test_a_build_without_a_priority_has_no_safeguard(self):
        self.assertIsNone(presets.guard_plan(self.build({'str'})))

    def test_each_priority_guards_its_own_quantity_at_ten_percent(self):
        expected = {'damage': 'effective_hp', 'defense': 'turn', 'heals': 'turn'}
        for priority, kind in expected.items():
            with self.subTest(priority=priority):
                self.assertEqual((kind, 10),
                                 presets.guard_plan(self.build({'int'}, priority)))

    def test_a_chosen_percent_is_kept_and_the_default_is_not_stored(self):
        char = self.build({'str'}, 'damage', guard_pct=20)
        self.assertEqual(('effective_hp', 20), presets.guard_plan(char))
        presets.apply_setup_choices(char, {'str'}, priority='damage', set_minimums=False,
                                    guard_pct=10)
        options = read_char_blob(char.options, {}, 'options', char)
        self.assertNotIn('guard_pct', options)
        self.assertEqual(10, presets.stored_guard(char))

    def test_saving_without_a_percent_keeps_the_stored_one(self):
        char = self.build({'str'}, 'damage', guard_pct=5)
        presets.apply_setup_choices(char, {'str'}, priority='defense', set_minimums=False)
        self.assertEqual(('turn', 5), presets.guard_plan(char))

    def test_a_percent_saved_without_new_weights_is_kept_and_the_weights_are_not(self):
        char = self.build({'str'}, 'damage')
        weights = char.stats_weight
        presets.apply_setup_choices(char, {'str'}, priority='defense', reset=False, guard_pct=20)
        self.assertEqual(('effective_hp', 20), presets.guard_plan(char))
        self.assertEqual(weights, char.stats_weight)

    def test_an_unknown_percent_reads_as_the_default(self):
        for value in (0, 7, 'abc', None, 100):
            with self.subTest(value=value):
                self.assertEqual(presets.GUARD_DEFAULT_PERCENT, presets.offered_guard(value))

    def test_a_form_without_the_field_keeps_the_stored_percent(self):
        char = self.build({'str'}, 'damage', guard_pct=15)
        self.assertEqual(15, presets.posted_guard({}, char))
        self.assertEqual(5, presets.posted_guard({'guard_pct': '5'}, char))
        self.assertEqual(10, presets.posted_guard({'guard_pct': '12'}, char))

    def test_the_balanced_weights_are_those_of_the_same_boxes_without_a_priority(self):
        chosen = self.build({'str', 'crit'}, 'damage')
        plain = self.build({'str', 'crit'})
        weights = get_stats_weights(chosen, persist=False)
        self.assertEqual(get_stats_weights(plain, persist=False),
                         presets.balanced_weights(chosen, weights))
        self.assertNotEqual(weights, presets.balanced_weights(chosen, weights))


class AMovedWeightStaysMovedInTheBalancedBuildTests(_BuildMixin, TestCase):

    def shares(self, aspects, priority):
        chosen = self.build(aspects, priority)
        plain = get_stats_weights(self.build(aspects), persist=False)
        weights = get_stats_weights(chosen, persist=False)
        return chosen, plain, weights

    def test_a_moved_slider_moves_the_balanced_weight_by_as_much(self):
        chosen, plain, weights = self.shares({'str'}, 'damage')
        set_wizard_sliders(chosen, {'slider_vit': str(int(weights['vit']) + 7)})
        tuned = get_stats_weights(chosen, persist=False)
        self.assertEqual(weights['vit'] + 7, tuned['vit'])
        balanced = presets.balanced_weights(chosen, tuned)
        self.assertEqual(plain['vit'] + 7, balanced['vit'])
        self.assertEqual(set(tuned), set(balanced))
        for key in ('str', 'earthdam', 'ap', 'mp'):
            self.assertEqual(plain[key], balanced[key], key)

    def test_a_weight_lowered_below_the_priority_share_stops_at_zero_unless_set_negative(self):
        chosen, plain, weights = self.shares({'str'}, 'damage')
        raised = max((key for key in weights if isinstance(weights[key], int)),
                     key=lambda key: weights[key] - plain.get(key, 0))
        self.assertGreater(weights[raised], plain[raised])
        self.assertEqual(0, presets.balanced_weights(chosen, dict(weights, **{raised: 0}))[raised])
        shift = weights[raised] - plain[raised]
        self.assertEqual(-5 - shift,
                         presets.balanced_weights(chosen, dict(weights, **{raised: -5}))[raised])

    def test_a_tuned_priority_build_is_compared_with_its_own_tuning(self):
        chosen, plain, weights = self.shares({'str'}, 'damage')
        set_wizard_sliders(chosen, {'slider_vit': str(int(weights['vit']) + 7)})
        tuned = get_stats_weights(chosen, persist=False)
        asked, _response = self.solve(chosen, self.wearing_the_hat)
        self.assertEqual(2, len(asked))
        self.assertEqual(presets.balanced_weights(chosen, tuned), asked[0].objective_values)
        self.assertEqual(plain['vit'] + 7, asked[0].objective_values['vit'])
        self.assertEqual(tuned, asked[1].objective_values)

    def test_a_priority_the_boxes_already_hold_solves_once_and_says_nothing(self):
        char = self.build({'str', 'glasscannon'}, 'damage')
        asked, _response = self.solve(char, self.wearing_the_hat)
        self.assertEqual(1, len(asked))
        self.assertNotIn(EFFECTIVE_HP_MINIMUM, asked[0].minimum_stats)
        self.assertIsNone(self.facts(char))


class TheFloorsGoOnACopyOfTheMinimumsTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')

    def test_effective_hp_divides_hp_by_what_the_mean_resist_lets_through(self):
        totals = {'hp': 5000, 'neutresper': 20, 'earthresper': 30, 'fireresper': 40,
                  'waterresper': 10, 'airresper': 0}
        self.assertAlmostEqual(6250.0, presets.effective_hp(totals))

    def test_the_effective_hp_floor_is_the_share_of_the_balanced_value(self):
        minimums = {'AP': 11, 'adv_mins': {'Power + Strength': 300}}
        guarded = presets.guard_minimums(minimums, 'effective_hp', 10, {'value': 8000.0}, {'str'})
        self.assertAlmostEqual(7200.0, guarded[EFFECTIVE_HP_MINIMUM])
        self.assertEqual({'AP': 11, 'adv_mins': {'Power + Strength': 300}}, minimums)
        self.assertEqual(11, guarded['AP'])

    def test_the_turn_floor_keeps_ap_and_the_share_of_crit_and_damage_stats(self):
        structure = get_structure('dofus3')
        crit = structure.get_stat_by_key('ch').name
        totals = {'ap': 12, 'ch': 41, 'pow': 200, 'str': 900, 'dam': 30, 'earthdam': 45,
                  'int': 50, 'firedam': -8}
        minimums = {'AP': 11, crit: 50, 'adv_mins': {'Damage + Earth Damage': 10}}
        guarded = presets.guard_minimums(minimums, 'turn', 10, {'totals': totals, 'value': 1},
                                         {'str', 'int'})
        self.assertEqual(12, guarded['AP'])
        self.assertEqual(50, guarded[crit])
        self.assertEqual({'Power + Strength': 990, 'Damage + Earth Damage': 67,
                          'Power + Intelligence': 225, 'Damage + Fire Damage': 19},
                         guarded['adv_mins'])
        self.assertEqual({'AP': 11, crit: 50, 'adv_mins': {'Damage + Earth Damage': 10}},
                         minimums)

    def test_a_negative_total_is_its_own_floor(self):
        self.assertEqual(-10, presets._scaled_floor(-10, 0.9))
        self.assertEqual(36, presets._scaled_floor(41, 0.9))


class TheModelHoldsTheFloorOnlyWhileAskedTests(SimpleTestCase):
    version = 'dofus3'

    def setUp(self):
        set_current_game_version(self.version)

    def tearDown(self):
        set_current_game_version('dofus3')

    def _input(self, minimums):
        return ModelInput(
            200, {'AP': 7, 'MP': 3, 'Range': 0, 'Summon': 1, 'Vitality': 100, 'Wisdom': 100,
                  'Strength': 100, 'Intelligence': 100, 'Chance': 100, 'Agility': 100,
                  'Prospecting': 100},
            minimums, {}, set(), {'vit': 20, 'str': 10, 'ap': 800},
            {'ap_exo': False, 'mp_exo': False, 'range_exo': False, 'dofus': True,
             'trophies': True, 'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
             'prysmaradite': False}, 'Iop', 0)

    def test_the_floor_is_one_linear_row_that_leaves_with_the_next_setup(self):
        model = Model()
        lp = model.problem.pulp_lp
        rows = len(lp.constraints)
        model.setup(self._input({EFFECTIVE_HP_MINIMUM: 5000.0}))
        row = lp.constraints[EFFECTIVE_HP_CONSTRAINT]
        coefficients = {variable.name: value for variable, value in row.items()}
        structure = get_structure(self.version)
        for name in ('% Neutral Resist', '% Earth Resist', '% Fire Resist', '% Water Resist',
                     '% Air Resist'):
            self.assertAlmostEqual(10.0, coefficients['stat_%d' % structure.get_stat_by_name(
                name).id])
        for name in ('HP', 'Vitality'):
            self.assertEqual(1, coefficients['stat_%d' % structure.get_stat_by_name(name).id])
        self.assertEqual(7, len(coefficients))
        self.assertAlmostEqual(5000.0 - (50 + 5 * 200), -row.constant)
        self.assertEqual(rows + 1, len(lp.constraints))

        model.setup(self._input({}))
        self.assertNotIn(EFFECTIVE_HP_CONSTRAINT, lp.constraints)
        self.assertEqual(rows, len(lp.constraints))
        self.assertFalse([c for c in lp.modifiedConstraints if c is row])

    def test_a_floor_changes_the_cache_key_and_no_floor_leaves_it(self):
        self.assertEqual(self._input({'AP': 11}).cache_key(), self._input({'AP': 11}).cache_key())
        self.assertNotEqual(self._input({'AP': 11}).cache_key(),
                            self._input({'AP': 11, EFFECTIVE_HP_MINIMUM: 1.0}).cache_key())


class TheTouchModelHoldsTheFloorTooTests(TheModelHoldsTheFloorOnlyWhileAskedTests):
    version = 'touch'


class AGuardedSolveAsksForTheBalancedBuildFirstTests(_BuildMixin, TestCase):

    def test_a_build_without_a_priority_asks_once_with_its_own_weights_and_minimums(self):
        char = self.build({'str'})
        minimums = char.minimum_stats
        asked, _response = self.solve(char, self.wearing_the_hat)
        self.assertEqual(1, len(asked))
        self.assertEqual(get_stats_weights(char, persist=False), asked[0].objective_values)
        self.assertEqual(get_min_stats_digested(char), asked[0].minimum_stats)
        self.assertNotIn(EFFECTIVE_HP_MINIMUM, asked[0].minimum_stats)
        self.assertIsNone(self.facts(char))
        self.assertEqual(minimums, char.minimum_stats)

    def test_a_damage_priority_asks_for_ninety_percent_of_the_balanced_effective_hp(self):
        char = self.build({'str'}, 'damage')
        plain = self.build({'str'})
        minimums = char.minimum_stats
        asked, _response = self.solve(char, self.wearing_the_hat)
        self.assertEqual(2, len(asked))
        balanced, guarded = asked
        self.assertEqual(get_stats_weights(plain, persist=False), balanced.objective_values)
        self.assertEqual(get_min_stats_digested(char), balanced.minimum_stats)
        self.assertEqual(get_stats_weights(char, persist=False), guarded.objective_values)
        ehp = presets.effective_hp(get_solution(char).get_stats_total())
        self.assertAlmostEqual(0.9 * ehp, guarded.minimum_stats.pop(EFFECTIVE_HP_MINIMUM))
        self.assertEqual(get_min_stats_digested(char), guarded.minimum_stats)
        self.assertEqual(minimums, char.minimum_stats)
        facts = self.facts(char)
        self.assertEqual(('effective_hp', 10, False), (facts['kind'], facts['percent'],
                                                       facts['fallback']))
        self.assertAlmostEqual(ehp, facts['balanced'])
        self.assertAlmostEqual(ehp, facts['kept'])
        self.assertAlmostEqual(1.0, facts['other_seconds'])

    def test_a_chosen_percent_sets_the_floor(self):
        char = self.build({'str'}, 'damage', guard_pct=20)
        asked, _response = self.solve(char, self.wearing_the_hat)
        ehp = presets.effective_hp(get_solution(char).get_stats_total())
        self.assertAlmostEqual(0.8 * ehp, asked[1].minimum_stats[EFFECTIVE_HP_MINIMUM])

    def test_defense_keeps_the_balanced_ap_and_records_the_best_turn(self):
        char = self.build({'str'}, 'defense')
        asked, _response = self.solve(char, self.wearing_the_hat)
        self.assertEqual(2, len(asked))
        totals = get_solution(char).get_stats_total()
        guarded = asked[1].minimum_stats
        self.assertNotIn(EFFECTIVE_HP_MINIMUM, guarded)
        self.assertEqual(max(totals['ap'], get_min_stats_digested(char).get('AP', 0)),
                         guarded['AP'])
        self.assertEqual(math.floor(0.9 * (totals['pow'] + totals['str'])),
                         guarded['adv_mins']['Power + Strength'])
        facts = self.facts(char)
        self.assertEqual('turn', facts['kind'])
        self.assertGreater(facts['balanced'], 0)
        self.assertAlmostEqual(facts['balanced'], facts['kept'])

    def test_when_no_set_passes_the_floor_the_priority_solves_without_it_and_says_so(self):
        def rule(model_input):
            if EFFECTIVE_HP_MINIMUM in model_input.minimum_stats:
                return 'Infeasible', None, None
            return self.wearing_the_hat(model_input)
        char = self.build({'str'}, 'damage')
        asked, response = self.solve(char, rule)
        self.assertEqual(3, len(asked))
        self.assertNotIn(EFFECTIVE_HP_MINIMUM, asked[2].minimum_stats)
        self.assertEqual(get_stats_weights(char, persist=False), asked[2].objective_values)
        self.assertIn('/solution/', response.url)
        self.assertTrue(self.facts(char)['fallback'])
        self.assertIn("Safeguard not applied: the solver found no set keeping 90% of the "
                      "balanced build's effective HP", self.page(char))

    def test_without_a_balanced_set_the_priority_solves_alone_and_says_so(self):
        balanced = None

        def rule(model_input):
            if model_input.objective_values == balanced:
                return 'Infeasible', None, None
            return self.wearing_the_hat(model_input)
        char = self.build({'str'}, 'damage')
        balanced = presets.balanced_weights(char, get_stats_weights(char, persist=False))
        asked, _response = self.solve(char, rule)
        self.assertEqual(2, len(asked))
        self.assertTrue(self.facts(char)['no_reference'])
        self.assertIn('Safeguard not applied: the solver found no balanced set to compare with.',
                      self.page(char))

    def test_an_unreadable_balanced_turn_applies_no_floor_and_says_so(self):
        char = self.build({'str'}, 'defense')
        with mock.patch('chardata.presets._panel_turn', return_value=None):
            asked, _response = self.solve(char, self.wearing_the_hat)
        self.assertEqual(2, len(asked))
        self.assertEqual(get_min_stats_digested(char), asked[1].minimum_stats)
        self.assertEqual(get_stats_weights(char, persist=False), asked[1].objective_values)
        facts = self.facts(char)
        self.assertTrue(facts['no_turn'])
        self.assertIn("Safeguard not applied: the balanced build's best turn could not be "
                      "computed.", self.page(char))

    def test_an_infeasible_priority_build_still_lands_on_the_infeasible_page(self):
        char = self.build({'str'}, 'damage')
        asked, response = self.solve(char, lambda model_input: ('Infeasible', None, None))
        self.assertEqual(2, len(asked))
        self.assertIn('infeasible', response.url)


class ASetBehindTheBalancedOneOnBothCountsIsNamedTests(_BuildMixin, TestCase):

    def bare_when_guarded(self, model_input):
        if EFFECTIVE_HP_MINIMUM in model_input.minimum_stats:
            return _answer(model_input, {})
        return self.wearing_the_hat(model_input)

    def test_less_damage_and_less_effective_hp_than_balanced_is_said(self):
        char = self.build({'str'}, 'damage')
        with mock.patch('chardata.presets._panel_turn', side_effect=[2000.0, 1500.0]):
            _asked, _response = self.solve(char, self.bare_when_guarded)
        facts = self.facts(char)
        self.assertLess(facts['kept'], facts['balanced'])
        self.assertEqual((2000.0, 1500.0), (facts['other_balanced'], facts['other_kept']))
        self.assertIn('This set trails the balanced build on both counts: best turn 1500 '
                      'against 2000, effective HP %d against %d.'
                      % (round(facts['kept']), round(facts['balanced'])), self.page(char))

    def test_more_damage_for_less_effective_hp_is_the_trade_asked_for(self):
        char = self.build({'str'}, 'damage')
        with mock.patch('chardata.presets._panel_turn', side_effect=[1500.0, 2000.0]):
            self.solve(char, self.bare_when_guarded)
        self.assertNotIn('This set trails', self.page(char))

    def test_a_set_that_keeps_the_balanced_effective_hp_reads_no_turn(self):
        char = self.build({'str'}, 'damage')
        with mock.patch('chardata.presets._panel_turn') as turn:
            self.solve(char, self.wearing_the_hat)
        turn.assert_not_called()
        self.assertNotIn('other_kept', self.facts(char))


class TheSolvesOfOneRequestShareOneBudgetTests(_BuildMixin, TestCase):

    def run_fashion(self, char, runs, proven=False, build_seconds=None):
        clock = _Clock()
        model = _TimedModel(clock, runs, self.hat, proven)
        memory = _EmptyMemory()

        def built_model(**kwargs):
            clock.now += build_seconds
            return model
        overrides = {self.hat.id: {'Vitality': 1}} if build_seconds else {}
        with mock.patch('chardata.fashion_action.MEMORY', memory), \
                mock.patch('chardata.fashion_action.time', clock), \
                mock.patch('chardata.fashion_action.borrow_model', return_value=model), \
                mock.patch('chardata.fashion_action.return_model'), \
                mock.patch('chardata.fashion_action.Model', side_effect=built_model), \
                mock.patch('chardata.fashion_action.get_effective_stat_overrides',
                           return_value=overrides):
            response = self.client.get('/fashion/%d/' % char.pk)
        self.assertEqual(302, response.status_code)
        char.refresh_from_db()
        return model, memory

    def test_the_balanced_solve_is_shortened_and_the_priority_one_keeps_the_usual_limit(self):
        char = self.build({'str'}, 'damage')
        model, _memory = self.run_fashion(char, [(5, 'Optimal'), (20, 'Optimal')])
        self.assertEqual([fashion_action.BALANCED_SECONDS,
                          lpproblem.TIME_LIMIT_SECONDS], model.limits)
        self.assertEqual(lpproblem.TIME_LIMIT_SECONDS, lpproblem.SOLVER.timeLimit)
        self.assertIsNone(self.facts(char)['time_limit'])

    def test_a_model_built_for_each_solve_spends_its_build_time_from_the_limits(self):
        char = self.build({'str'}, 'damage')
        model, _memory = self.run_fashion(char, [(5, 'Optimal'), (20, 'Optimal')],
                                          build_seconds=12)
        self.assertEqual([fashion_action.BALANCED_SECONDS - 12,
                          fashion_action.GUARD_BUDGET_SECONDS - 12 - 5 - 12], model.limits)

    def test_a_slow_balanced_solve_leaves_the_priority_what_the_budget_has_left(self):
        char = self.build({'str'}, 'damage')
        model, _memory = self.run_fashion(char, [(40, 'Optimal'), (20, 'Optimal')])
        left = fashion_action.GUARD_BUDGET_SECONDS - 40
        self.assertEqual(left, model.limits[1])
        facts = self.facts(char)
        self.assertEqual(left, facts['time_limit'])
        self.assertEqual(40, facts['other_seconds'])
        page = self.page(char)
        self.assertIn('Best set found in %d seconds.' % left, page)
        self.assertIn('Computed in 60.0 s.', page)

    def test_a_shortened_solve_the_limit_decided_is_not_remembered(self):
        char = self.build({'str'}, 'damage')
        _model, memory = self.run_fashion(char, [(5, 'Optimal'), (20, 'Optimal')])
        self.assertEqual(1, len(memory.kept))
        self.assertIn(EFFECTIVE_HP_MINIMUM, memory.kept[0].minimum_stats)
        other = self.build({'str'}, 'damage')
        _model, memory = self.run_fashion(other, [(5, 'Optimal'), (20, 'Optimal')], proven=True)
        self.assertEqual(2, len(memory.kept))

    def test_with_no_time_left_after_a_failed_floor_the_balanced_set_is_shown(self):
        char = self.build({'str'}, 'damage')
        model, _memory = self.run_fashion(char, [(25, 'Optimal'), (70, 'Not Solved')])
        self.assertEqual(2, len(model.limits))
        facts = self.facts(char)
        self.assertTrue(facts['out_of_time'])
        self.assertEqual(70, facts['other_seconds'])
        self.assertEqual(presets.balanced_weights(char, get_stats_weights(char, persist=False)),
                         read_char_blob(char.minimal_solution, None, 'minimal_solution', char).weights_seen)
        self.assertIn('Safeguard: the solver ran out of time before it found a set for the '
                      'priority, so this is the balanced build.', self.page(char))

    def test_a_failed_floor_with_time_left_solves_the_priority_within_the_budget(self):
        char = self.build({'str'}, 'damage')
        model, _memory = self.run_fashion(char, [(10, 'Optimal'), (5, 'Infeasible'),
                                                 (20, 'Optimal')])
        self.assertEqual([fashion_action.BALANCED_SECONDS,
                          fashion_action.GUARD_BUDGET_SECONDS - 10,
                          fashion_action.GUARD_BUDGET_SECONDS - 15], model.limits)
        self.assertTrue(self.facts(char)['fallback'])
        self.assertFalse(self.facts(char)['out_of_time'])

    def test_a_build_without_a_priority_keeps_the_usual_limit_and_memory(self):
        char = self.build({'str'})
        model, memory = self.run_fashion(char, [(95, 'Optimal')])
        self.assertEqual([lpproblem.TIME_LIMIT_SECONDS], model.limits)
        self.assertEqual(1, len(memory.kept))
        self.assertFalse(hasattr(read_char_blob(char.minimal_solution, None, 'minimal_solution', char), 'time_limit'))


class TheBuildPageShowsWhatTheSafeguardKeptTests(_BuildMixin, TestCase):

    def stored(self, char, proven=True, solve_seconds=None, **facts):
        base = {'kind': 'effective_hp', 'percent': 10, 'balanced': 4680.4, 'kept': 4212.2,
                'fallback': False, 'no_reference': False, 'no_turn': False,
                'out_of_time': False, 'other_seconds': 3.0, 'time_limit': None}
        base.update(facts)
        input_ = {'options': {'ap_exo': False, 'mp_exo': False}, 'origin': 'generated',
                  'char_level': char.level, 'base_stats_by_attr': {}, 'locked_equips': {}}
        minimal = ModelResultMinimal({}, input_, {})
        minimal.proven = proven
        if solve_seconds is not None:
            minimal.solve_seconds = solve_seconds
        minimal.guard = base
        char.minimal_solution = pickle.dumps(minimal)
        char.save()

    def test_the_kept_effective_hp_is_named_with_the_balanced_one(self):
        char = self.build({'str'}, 'damage')
        self.stored(char)
        page = self.page(char)
        self.assertIn('Safeguard: effective HP at least 90% of the balanced build '
                      '(4212 of 4680).', page)
        self.assertLess(page.index('Mode: General (all content) · Priority: Damage'),
                        page.index('Safeguard: effective HP'))

    def test_a_turn_below_the_share_says_how_far_it_fell(self):
        char = self.build({'str'}, 'defense')
        self.stored(char, kind='turn', percent=20, balanced=2000.0, kept=1500.0)
        self.assertIn('Safeguard: best turn at 75% of the balanced build (1500 of 2000), '
                      'short of the 80% aimed for.', self.page(char))

    def test_a_defense_set_behind_on_both_counts_names_the_turn_first(self):
        char = self.build({'str'}, 'defense')
        self.stored(char, kind='turn', balanced=2000.0, kept=1900.0, other_balanced=5000.0,
                    other_kept=4900.0)
        self.assertIn('This set trails the balanced build on both counts: best turn 1900 '
                      'against 2000, effective HP 4900 against 5000.', self.page(char))

    def test_the_time_counts_both_solves_and_quotes_the_limit_this_one_had(self):
        char = self.build({'str'}, 'damage')
        self.stored(char, proven=False, solve_seconds=2.5, time_limit=60)
        page = self.page(char)
        self.assertIn('Computed in 5.5 s.', page)
        self.assertIn('Best set found in 60 seconds.', page)
        self.assertNotIn('Best set found in %d seconds' % lpproblem.TIME_LIMIT_SECONDS, page)

    def test_the_share_text_quotes_the_limit_this_one_had(self):
        from chardata.solution_view import _build_share_text
        char = self.build({'str'}, 'damage')
        self.stored(char, proven=False, time_limit=60)
        text = _build_share_text(RequestFactory().get('/'), char, get_solution(char))
        self.assertIn('Best set found in 60 seconds.', text)

    def test_the_sentence_speaks_the_page_language(self):
        char = self.build({'str'}, 'damage')
        self.stored(char)
        expected = {'fr': 'Garde-fou : au moins 90 % des PV effectifs du build équilibré '
                          '(4212 sur 4680).',
                    'es': 'Margen de seguridad: al menos el 90% de los PdV efectivos del build '
                          'equilibrado (4212 de 4680).',
                    'pt': 'Margem de segurança: pelo menos 90% dos PV efetivos do build '
                          'equilibrado (4212 de 4680).',
                    'de': 'Sicherheitsmarge: mindestens 90 % der effektiven LP des '
                          'ausgewogenen Builds (4212 von 4680).'}
        for language, sentence in expected.items():
            with self.subTest(language=language):
                self.assertIn(sentence, self.page(char, '/' + language))

    def test_a_solution_without_facts_shows_no_line(self):
        char = self.build({'str'}, 'damage')
        self.stored(char)
        minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
        del minimal.guard
        char.minimal_solution = pickle.dumps(minimal)
        char.save()
        page = self.page(char)
        self.assertIn('Why this result?', page)
        self.assertNotIn('solver-setup-guard', page)

    def test_the_setup_page_no_longer_calls_the_safeguard_coming_soon(self):
        page = self.client.get('/setup/', HTTP_ACCEPT_LANGUAGE='en').content.decode('utf-8')
        self.assertIn('The build page shows what was kept.', page)
        self.assertNotIn('Coming soon, no effect yet', page)

    def test_every_new_sentence_is_translated_in_four_languages(self):
        for language in ('fr', 'es', 'pt', 'de'):
            with translation.override(language):
                for sentence in NEW_SENTENCES:
                    with self.subTest(language=language, sentence=sentence[:40]):
                        self.assertNotEqual(sentence, translation.gettext(sentence))


class AGuardOnTouchTemporixReadsTheTouchSetTests(_BuildMixin, TestCase):
    version = 'touch'
    prefix = '/touch'

    def test_a_temporix_damage_priority_floors_effective_hp_on_the_touch_totals(self):
        char = self.build({'str'}, 'damage')
        options = read_char_blob(char.options, {}, 'options', char)
        options['temporix'] = True
        set_options(char, options)
        asked, _response = self.solve(char, self.wearing_the_hat)
        self.assertEqual(2, len(asked))
        for model_input in asked:
            self.assertTrue(model_input.options.get('temporix'))
        ehp = presets.effective_hp(get_solution(char).get_stats_total())
        self.assertAlmostEqual(0.9 * ehp, asked[1].minimum_stats[EFFECTIVE_HP_MINIMUM])
        self.assertAlmostEqual(ehp, self.facts(char)['kept'])


class AGuardOnRetroKeepsItsTurnStatsTests(_BuildMixin, TestCase):
    version = 'retro'
    prefix = '/retro'

    def test_a_retro_defense_priority_floors_the_turn_stats_of_its_element(self):
        char = self.build({'str'}, 'defense')
        asked, _response = self.solve(char, self.wearing_the_hat)
        self.assertEqual(2, len(asked))
        totals = get_solution(char).get_stats_total()
        guarded = asked[1].minimum_stats
        self.assertEqual(math.floor(0.9 * (totals.get('pow', 0) + totals['str'])),
                         guarded['adv_mins']['Power + Strength'])
        facts = self.facts(char)
        self.assertEqual('turn', facts['kind'])
        self.assertGreater(facts['balanced'], 0)


class ARealGuardedSolveKeepsItsFloorTests(_BuildMixin, TestCase):

    @unittest.skipUnless(_solver_available(), 'no pulp solver available')
    def test_the_damage_set_keeps_ninety_percent_of_the_balanced_effective_hp(self):
        char = self.build({'str'}, 'damage')
        self.client.get('/fashion/%d/' % char.pk)
        char.refresh_from_db()
        facts = self.facts(char)
        self.assertFalse(facts['fallback'])
        kept = presets.effective_hp(get_solution(char).get_stats_total())
        self.assertAlmostEqual(kept, facts['kept'], places=3)
        self.assertGreaterEqual(kept, 0.9 * facts['balanced'] - 0.5)

        plain = self.build({'str'})
        self.client.get('/fashion/%d/' % plain.pk)
        plain.refresh_from_db()
        self.assertAlmostEqual(presets.effective_hp(get_solution(plain).get_stats_total()),
                               facts['balanced'], places=3)
        self.assertIsNone(self.facts(plain))
