# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A pooled model that solved a build with runes writes a fresh model for the next build."""

from collections import defaultdict
from queue import Queue
from unittest import mock

from fashionistapulp import model_pool
from fashionistapulp.model import Model

from chardata.dracorune_fixtures import NOT_ASKED, BetaModelTestCase, written


def draco_traces(model):
    lp = model.problem.pulp_lp
    return {
        'columns': [v.name for v in lp.variables() if v.name.startswith('draco')],
        'variables': [name for name in model.problem.pulp_vars if name.startswith('draco')],
        'rows': [name for name in lp.constraints if name.startswith('draco')],
        'terms': [variable.name for row in lp.constraints.values() for variable in row.keys()
                  if variable.name.startswith('draco')],
        'objective': [variable.name for variable in lp.objective.keys()
                      if variable.name.startswith('draco')],
        'known': [variable.name for variable in lp._variables
                  if variable.name.startswith('draco')],
        'known_ids': [variable.name for variable in lp._variable_ids.values()
                      if variable.name.startswith('draco')],
        'columns_kept': dict(model.dracorune_columns),
    }


class ThePoolForgetsTheLastBuildsRunesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(model_pool, '_model_queues', defaultdict(Queue))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_next_build_without_runes_gets_the_model_of_a_fresh_one(self):
        model = model_pool.borrow_model()
        try:
            written(model, 2)
            self.assertTrue(draco_traces(model)['columns'])
            model.run()
            self.assertEqual('Optimal', model.get_solved_status())
        finally:
            model_pool.return_model(model)
        again = model_pool.borrow_model()
        try:
            self.assertIs(model, again)
            reused = written(again, 0)
            self.assertEqual({'columns': [], 'variables': [], 'rows': [], 'terms': [],
                              'objective': [], 'known': [], 'known_ids': [],
                              'columns_kept': {}},
                             draco_traces(again))
        finally:
            model_pool.return_model(again)
        self.assertEqual(written(Model(), NOT_ASKED), reused)

    def test_two_builds_with_runes_in_a_row_keep_only_the_last_ones(self):
        model = model_pool.borrow_model()
        try:
            written(model, 2)
            first = draco_traces(model)
            written(model, 1)
            second = draco_traces(model)
        finally:
            model_pool.return_model(model)
        self.assertEqual(first['columns'], second['columns'])
        self.assertEqual(len(first['columns']), len(model.dracorune_columns))
        total = model.problem.pulp_lp.constraints['draco_total']
        self.assertEqual(1, -total.constant)
