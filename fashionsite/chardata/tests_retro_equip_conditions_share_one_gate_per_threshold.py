# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Retro equip conditions go through one gate per threshold and still bind; other versions keep one row per piece."""
from unittest import mock

from django.test import SimpleTestCase

from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure, set_current_game_version

OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False, 'dofus': True,
           'trophies': True, 'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
           'prysmaradite': False}
LEVEL = 200
HIGHEST_THRESHOLD = 300
_MODELS = {}


def _solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


def _model(version):
    """One model per version for the module; every test sets it up again."""
    if version not in _MODELS:
        _MODELS[version] = Model()
    return _MODELS[version]


def _gate(stat, value):
    return 'gate_%s_%s' % (stat, value)


def _input(locked=None):
    return ModelInput(LEVEL, {'AP': 7, 'MP': 3}, {}, dict(locked or {}), set(),
                      {'vit': 1, 'str': -10}, dict(OPTIONS), 'Iop', 5 * (LEVEL - 1))


class _VersionMixin(object):
    version = 'retro'

    def setUp(self):
        set_current_game_version(self.version)
        self.structure = get_structure(self.version)

    def tearDown(self):
        set_current_game_version('dofus3')

    def thresholds(self, model):
        return {(stat, value) for item in model.items_list
                for stat, value in item.min_stats_to_equip}


class TheRetroModelHoldsOneGatePerThresholdTests(_VersionMixin, SimpleTestCase):

    def test_each_distinct_threshold_has_one_gate_and_each_piece_points_to_its_own(self):
        model = _model(self.version)
        names = {variable.name for variable in model.problem.pulp_lp.variables()}
        gates = {name for name in names if name.startswith('gate_')}
        self.assertEqual(len(self.thresholds(model)), len(gates))
        self.assertGreater(len(gates), 100)
        rows = 0
        for item in model.items_list:
            for stat, value in item.min_stats_to_equip:
                row = model.restrictions.min_condition_contraints[(item.id, stat)]
                terms = {variable.name: coefficient for variable, coefficient in row.items()}
                self.assertEqual({'p_%d' % item.id: 1, _gate(stat, value): -1}, terms)
                self.assertEqual(0, row.constant)
                rows += 1
        self.assertGreater(rows, len(gates))

    def test_each_gate_holds_its_stat_at_its_threshold_with_the_usual_big_m(self):
        model = _model(self.version)
        gate_rows = {}
        for row in model.problem.pulp_lp.constraints.values():
            terms = {variable.name: coefficient for variable, coefficient in row.items()}
            gates = [name for name in terms if name.startswith('gate_')]
            if len(gates) == 1 and len(terms) == 2 and not any(
                    name.startswith('p_') for name in terms):
                gate_rows[gates[0]] = (terms, row.constant)
        for stat, value in self.thresholds(model):
            self.assertEqual(({_gate(stat, value): value + 10000, 'stat_%d' % stat: -1}, -10000),
                             gate_rows[_gate(stat, value)])


class TheDofus3ModelKeepsOneRowPerPieceTests(_VersionMixin, SimpleTestCase):
    version = 'dofus3'

    def test_a_dofus3_condition_is_its_own_big_m_row_and_there_is_no_gate(self):
        model = _model(self.version)
        self.assertFalse([variable.name for variable in model.problem.pulp_lp.variables()
                          if variable.name.startswith('gate_')])
        checked = 0
        for item in model.items_list:
            for stat, value in item.min_stats_to_equip:
                row = model.restrictions.min_condition_contraints[(item.id, stat)]
                terms = {variable.name: coefficient for variable, coefficient in row.items()}
                self.assertEqual({'p_%d' % item.id: value + 10000, 'stat_%d' % stat: -1}, terms)
                checked += 1
        self.assertGreater(checked, 0)


class AGatedRetroConditionStillBindsTests(_VersionMixin, SimpleTestCase):

    def setUp(self):
        super().setUp()
        if not _solver_available():
            self.skipTest('no pulp solver available')

    def weapon(self, model):
        """The weapon asking the most Strength up to HIGHEST_THRESHOLD, with no other condition."""
        strength = self.structure.get_stat_by_name('Strength').id
        best = None
        for item in model.items_list:
            conditions = item.min_stats_to_equip
            if (len(conditions) != 1 or conditions[0][0] != strength or item.max_stats_to_equip
                    or item.level > LEVEL
                    or self.structure.get_type_name_by_id(item.type) != 'Weapon'):
                continue
            value = conditions[0][1]
            if value <= HIGHEST_THRESHOLD and (best is None or value > best[1]):
                best = (item, value)
        self.assertIsNotNone(best)
        return best[0], strength, best[1]

    def solve(self, model, model_input, warm_start=None):
        model.setup(model_input)
        model.run(2, warm_start=warm_start)
        self.assertEqual('Optimal', model.get_solved_status())
        self.assertTrue(model.solution_is_proven())
        return model.get_search_state()

    def test_a_locked_weapon_brings_strength_to_its_threshold_that_the_build_skips_without_it(self):
        model = _model(self.version)
        weapon, strength, threshold = self.weapon(model)
        free = self.solve(model, _input())
        self.assertLess(free['values'].get('stat_%d' % strength, 0), threshold)
        locked = self.solve(model, _input({'weapon': weapon.id}))
        self.assertEqual(1, locked['values'].get('x_%d' % weapon.id))
        self.assertGreaterEqual(locked['values'].get('stat_%d' % strength, 0), threshold)
        self.assertEqual(1, locked['values'].get(_gate(strength, threshold)))

    def test_the_gated_model_scores_what_one_row_per_piece_scores(self):
        model = _model(self.version)
        weapon, _strength, _threshold = self.weapon(model)
        model_input = _input({'weapon': weapon.id})
        gated = self.solve(model, model_input)
        with mock.patch.object(Model, '_GATED_CONDITION_VERSIONS', frozenset()):
            plain_model = Model()
        self.assertFalse(plain_model._condition_gates)
        plain = self.solve(plain_model, model_input)
        self.assertAlmostEqual(plain['objective'], gated['objective'])

    def test_a_start_saved_without_gates_is_still_taken(self):
        model = _model(self.version)
        weapon, strength, threshold = self.weapon(model)
        model_input = _input({'weapon': weapon.id})
        solved = self.solve(model, model_input)
        self.assertEqual(1, solved['values'].get(_gate(strength, threshold)))
        old_start = {name: number for name, number in solved['values'].items()
                     if not name.startswith('gate_')}
        warm = self.solve(model, model_input, warm_start=old_start)
        self.assertIs(True, warm['start_accepted'])
        self.assertAlmostEqual(solved['objective'], warm['start_objective'])
        self.assertAlmostEqual(solved['objective'], warm['objective'])
