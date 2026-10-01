# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""In every version, the closest solve counts each minimum as the hard minimum of the solver and the set page do."""
import pickle
import sys
from unittest import mock

import pulp
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.utils import translation

from chardata import closest_set
from chardata.coaching_view import create_build
from chardata.fashion_action import _solver_time_limit
from chardata.solution import get_solution_from_minimal
from chardata.tests_a_build_with_no_set_is_shown_its_closest_set import _solver_available
from chardata.translation_util import localized_stat_name
from fashionistapulp.dofus_constants import percent_resist_cap
from fashionistapulp.game_versions import version_keys
from fashionistapulp.model import Model
from fashionistapulp.structure import (get_current_game_version, get_structure,
                                       set_current_game_version)

SOLVE_SECONDS = 20
ALWAYS_MET = -10000
UNREACHABLE = {'HP': 99999, 'Dodge': 999, 'Lock': 999, 'AP Reduction': 999,
               'Initiative': 99999, 'Prospecting': 9999, 'Pods': 99999}
REACHABLE = {'Wisdom': 50}
PERCENT_RESIST_SUM = 'Sum of all % Resists'
#: Not a setUpTestData attribute, which Django deep-copies for each test
_MODELS = {}


def _at_least(constraint):
    """({variable name: coefficient}, bound) of a constraint written as a sum at least bound."""
    exported = constraint.toDict()
    coefficients = {term['name']: term['value'] for term in exported['coefficients']}
    if exported['sense'] == pulp.LpConstraintLE:
        return {name: -value for name, value in coefficients.items()}, exported['constant']
    return coefficients, -exported['constant']


class _EveryMinimumMixin(object):
    """Asks every minimum of the version once, on a fresh model, then reads the solver and the set page."""
    version = None

    @classmethod
    def setUpTestData(cls):
        previous = get_current_game_version()
        set_current_game_version(cls.version)
        try:
            cls._ask_every_minimum()
        finally:
            set_current_game_version(previous)

    @classmethod
    def tearDownClass(cls):
        _MODELS.pop(cls.version, None)
        super().tearDownClass()

    @classmethod
    def _minimums(cls, structure):
        asked = {stat.name: ALWAYS_MET for stat in structure.get_stats_list()}
        asked.update({name: value for name, value in dict(UNREACHABLE, **REACHABLE).items()
                      if name in asked})
        advanced = {stat['name']: ALWAYS_MET for stat in structure.get_adv_mins()}
        advanced[PERCENT_RESIST_SUM] = 5 * percent_resist_cap(cls.version) + 50
        asked['adv_mins'] = advanced
        return asked

    @classmethod
    def _ask_every_minimum(cls):
        structure = get_structure(cls.version)
        owner = User.objects.create_user('every-minimum', 'every@test.local', 'pw-42-solid')
        creation = RequestFactory().post('/')
        creation.user = owner
        char = create_build(creation, 'Iop', 200, {'str'}, cls.version)
        char.minimum_stats = pickle.dumps(cls._minimums(structure))
        char.allow_points_distribution = True
        char.save()
        request = RequestFactory().get('/')
        request.user = owner
        SessionMiddleware(lambda r: None).process_request(request)
        request.game_version = cls.version
        model_input = closest_set.current_input(request, char)

        model = _MODELS[cls.version] = Model()
        model.setup(model_input)
        hard = {name: _at_least(restriction)
                for name, restriction in model.restrictions.minimum_stat_constraints.items()}
        for stat in structure.get_adv_mins():
            hard[stat['name']] = _at_least(
                model.restrictions.advanced_minimum_stat_constraints[stat['key']])
        shortfalls = model.add_elastic_minimums(model_input.minimum_stats, model_input.char_level)
        constraints = model.problem.pulp_lp.constraints
        cls.asked = (set(model_input.minimum_stats) - {'adv_mins'}) | set(
            model_input.minimum_stats['adv_mins'])
        cls.mirrors = [(name, variable.name, hard[name], _at_least(constraints['elastic_%d' % number]))
                       for number, (name, variable, _asked, _weight) in enumerate(shortfalls)]
        cls.status = None
        if not _solver_available():
            return
        model.minimise_shortfall(shortfalls)
        with _solver_time_limit(None, SOLVE_SECONDS):
            model.run(2)
        cls.status = model.get_solved_status()
        if cls.status != 'Optimal':
            return
        # The constraint reads sum + shortfall - bound, so this is bound - sum
        cls.solver_missing = {
            name: max(0.0, variable.varValue - constraints['elastic_%d' % number].value())
            for number, (name, variable, _asked, _weight) in enumerate(shortfalls)}
        solution = get_solution_from_minimal(char, model.get_result_minimal(),
                                             refresh_base_stats=False)
        with translation.override('en'):
            rows = closest_set.minimum_rows(char, solution)
            labels = {stat.name: localized_stat_name(stat.name, cls.version)
                      for stat in structure.get_stats_list()}
            labels.update({stat['name']: str(stat['local_name'])
                           for stat in structure.get_adv_mins()})
        by_label = {row['name']: row for row in rows}
        cls.labels_unique = len(by_label) == len(rows)
        cls.page = {name: by_label.get(label) for name, label in labels.items()}

    def test_every_minimum_of_the_version_gets_a_shortfall(self):
        self.assertEqual(self.asked, {name for name, _variable, _hard, _elastic in self.mirrors})

    def test_each_shortfall_constraint_mirrors_its_hard_minimum(self):
        for name, variable, hard, (coefficients, bound) in self.mirrors:
            with self.subTest(minimum=name):
                coefficients = dict(coefficients)
                self.assertEqual(1, coefficients.pop(variable))
                self.assertEqual(hard, (coefficients, bound))

    def test_each_shortfall_is_what_the_set_page_shows_missing(self):
        if self.status is None:
            self.skipTest('no pulp solver available')
        self.assertEqual('Optimal', self.status)
        self.assertTrue(self.labels_unique)
        for name, missing in self.solver_missing.items():
            with self.subTest(minimum=name):
                self.assertIsNotNone(self.page[name])
                # The page floors Agility / 10 and the Wisdom share, the solver does not
                self.assertLessEqual(abs(missing - self.page[name]['missing']), 1)
        for name in REACHABLE:
            self.assertTrue(self.page[name]['met'], name)
        self.assertGreater(self.page['HP']['missing'], 0)
        self.assertGreater(self.page[PERCENT_RESIST_SUM]['missing'], 0)

    def test_a_minimum_without_a_solver_variable_stops_the_closest_solve(self):
        model = _MODELS[self.version]
        variables = model.problem.pulp_vars
        vitality = 'stat_%s' % model.structure.get_stat_by_name('Vitality').id
        kept = {name: variable for name, variable in variables.items() if name != vitality}
        with mock.patch.dict(variables, kept, clear=True):
            with self.assertRaisesRegex(ValueError, 'HP'):
                model.add_elastic_minimums({'HP': 5000}, 200)


class Dofus3CountsEachMinimumTests(_EveryMinimumMixin, TestCase):
    version = 'dofus3'


class BetaCountsEachMinimumTests(_EveryMinimumMixin, TestCase):
    version = 'beta'


class Dofus2CountsEachMinimumTests(_EveryMinimumMixin, TestCase):
    version = 'dofus2'


class TouchCountsEachMinimumTests(_EveryMinimumMixin, TestCase):
    version = 'touch'


class RetroCountsEachMinimumTests(_EveryMinimumMixin, TestCase):
    version = 'retro'


class EveryVersionIsCountedTests(TestCase):

    def test_each_version_of_the_registry_has_its_class(self):
        module = sys.modules[__name__]
        covered = {value.version for value in vars(module).values()
                   if isinstance(value, type) and issubclass(value, _EveryMinimumMixin)
                   and value is not _EveryMinimumMixin}
        self.assertEqual(set(version_keys()), covered)
