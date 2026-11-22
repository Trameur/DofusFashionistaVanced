# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A pooled model that solved with transcendence runes solves the next build like a fresh one."""

from collections import defaultdict
from queue import Queue
from unittest import mock

import pulp

from fashionistapulp import model_pool
from fashionistapulp.model import dracorune_count

from chardata.dracorune_fixtures import (NOT_ASKED, VERSION, BetaModelTestCase, SmallModel, mps,
                                         element_move, piece)
from chardata.transcendence_fixtures import trans_input, trans_traces

EMPTY_TRACES = {'known': [], 'known_ids': [], 'columns': [], 'variables': [], 'rows': [],
                'terms': [], 'objective': [], 'classes_kept': {}, 'columns_kept': {}}


def worn(model):
    return {name: round(variable.varValue or 0)
            for name, variable in model.problem.pulp_vars.items() if name.startswith('x_')}


class TheNextBuildChoosesNoRuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(model_pool, '_model_queues', defaultdict(Queue))
        patcher.start()
        self.addCleanup(patcher.stop)
        source, target = element_move()
        self.weights = {target: 1, 'int': 1, 'vit': 1}
        self.items = [piece('Hat', {source: 50, 'vit': 100}), piece('Amulet', {source: 50, 'vit': 300})]
        model_pool._model_queues[VERSION].put(SmallModel(self.items))

    def first_solve(self, how, model):
        first = trans_input(self.weights, 2, 1)
        model.setup(first)
        self.assertTrue(model.dracorune_columns)
        if how == 'continue':
            model._rebuild_rune_terms(dracorune_count(first.options), first, for_minimums=True)
        model.run(0, change_of=(how == 'retry'))

    def test_the_next_build_solves_like_a_fresh_model(self):
        for how in ('run', 'retry', 'continue'):
            for allowed in (NOT_ASKED, 0):
                with self.subTest(first_solve=how, allowed=allowed):
                    model = model_pool.borrow_model()
                    try:
                        self.first_solve(how, model)
                        self.assertEqual('Optimal', model.get_solved_status())
                        self.assertTrue(model.chosen_transcendences())
                    finally:
                        model_pool.return_model(model)
                    again = model_pool.borrow_model()
                    try:
                        self.assertIs(model, again)
                        second = trans_input(self.weights, allowed)
                        fresh = SmallModel(self.items)
                        self.assertEqual(mps(again, second), mps(fresh, second))
                        again.run(0)
                        fresh.run(0)
                        self.assertEqual('Optimal', again.get_solved_status())
                        self.assertEqual('Optimal', fresh.get_solved_status())
                        self.assertEqual([], again.chosen_transcendences())
                        self.assertEqual(EMPTY_TRACES, trans_traces(again))
                        self.assertAlmostEqual(pulp.value(fresh.problem.pulp_lp.objective),
                                               pulp.value(again.problem.pulp_lp.objective),
                                               delta=1e-6)
                        self.assertEqual(worn(fresh), worn(again))
                    finally:
                        model_pool.return_model(again)
