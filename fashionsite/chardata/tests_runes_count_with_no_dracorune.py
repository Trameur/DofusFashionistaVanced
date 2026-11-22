# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Transcendence runes are offered whatever the Dracorune path does, and forgotten with the build."""

from collections import defaultdict
from queue import Queue
from unittest import mock

from fashionistapulp import model_pool
from fashionistapulp.model import Model

from chardata.dracorune_fixtures import (NOT_ASKED, BetaModelTestCase, SmallModel, columns,
                                         element_move, mps, piece, real_input)
from chardata.transcendence_fixtures import (trans_columns, trans_input, trans_traces,
                                             with_transcendence)

TYPES = ('Hat', 'Cloak', 'Amulet', 'Belt')


class RunesCountWithNoDracoruneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()

    def model_of(self, lines):
        return SmallModel([piece(type_name, lines) for type_name in TYPES])

    def test_runes_count_with_the_dracorune_option_absent_or_zero(self):
        for dracorunes in (None, 0):
            with self.subTest(dracorunes=dracorunes):
                model = self.model_of({self.source: 50})
                self.solve(model, trans_input({'vit': 1}, 2, dracorunes))
                self.assertEqual([], columns(model))
                self.assertEqual(2, len(model.chosen_transcendences()))

    def test_runes_count_when_no_piece_takes_a_dracorune(self):
        model = self.model_of({'vit': 0})
        self.assertEqual({}, model.dracorune_candidates)
        self.solve(model, trans_input({'vit': 1}, 2, 2))
        self.assertEqual(2, len(model.chosen_transcendences()))

    def test_runes_count_when_every_dracorune_is_pruned(self):
        model = self.model_of({self.source: 50})
        self.assertTrue(model.dracorune_candidates)
        self.solve(model, trans_input({'vit': 1}, 2, 2))
        self.assertEqual([], columns(model))
        self.assertEqual(2, len(model.chosen_transcendences()))

    def test_both_kinds_are_offered_together(self):
        model = self.model_of({self.source: 50})
        self.solve(model, trans_input({self.target: 1, 'vit': 1}, 1, 1))
        self.assertTrue(columns(model))
        self.assertTrue(trans_columns(model))
        constraints = model.problem.pulp_lp.constraints
        self.assertEqual(1, -constraints['draco_total'].constant)
        self.assertEqual(1, -constraints['trans_total'].constant)
        self.assertEqual(1, len(model.chosen_dracorunes()))
        self.assertEqual(1, len(model.chosen_transcendences()))

    def test_a_setup_without_dracorunes_forgets_them_and_writes_the_runes_of_a_fresh_model(self):
        weights = {self.target: 1, 'vit': 1}
        model = self.model_of({self.source: 50})
        both = mps(model, trans_input(weights, 2, 2))
        self.assertIn(b'draco_', both)
        self.assertIn(b'trans_', both)
        again = mps(model, trans_input(weights, 2))
        self.assertNotIn(b'draco_', again)
        self.assertEqual(again, mps(self.model_of({self.source: 50}), trans_input(weights, 2)))
        neither = mps(model, trans_input(weights))
        self.assertNotIn(b'trans_', neither)
        self.assertEqual(neither, mps(self.model_of({self.source: 50}), trans_input(weights)))

    def test_the_elastic_minimums_keep_the_same_runes(self):
        for dracorunes in (None, 1):
            with self.subTest(dracorunes=dracorunes):
                model = self.model_of({'vit': 100})
                minimums = {'Vitality': 150}
                model.setup(trans_input({'str': 1}, 2, dracorunes, minimums))
                before = trans_columns(model)
                self.assertTrue(before)
                model.add_elastic_minimums(minimums, 200)
                self.assertEqual(before, trans_columns(model))


class ThePoolForgetsTheLastBuildsTranscendencesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(model_pool, '_model_queues', defaultdict(Queue))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_next_build_without_runes_gets_the_model_of_a_fresh_one(self):
        model = model_pool.borrow_model()
        try:
            mps(model, with_transcendence(real_input(2), 2))
            self.assertTrue(trans_traces(model)['columns'])
        finally:
            model_pool.return_model(model)
        again = model_pool.borrow_model()
        try:
            self.assertIs(model, again)
            reused = mps(again, real_input(NOT_ASKED))
            self.assertEqual({'known': [], 'known_ids': [], 'columns': [], 'variables': [],
                              'rows': [], 'terms': [], 'objective': [], 'classes_kept': {},
                              'columns_kept': {}},
                             trans_traces(again))
        finally:
            model_pool.return_model(again)
        self.assertEqual(mps(Model(), real_input(NOT_ASKED)), reused)

    def test_two_builds_in_a_row_keep_only_the_last_runes(self):
        model = model_pool.borrow_model()
        try:
            mps(model, with_transcendence(real_input(NOT_ASKED), 2))
            first = trans_traces(model)
            mps(model, with_transcendence(real_input(NOT_ASKED), 1))
            second = trans_traces(model)
        finally:
            model_pool.return_model(model)
        self.assertTrue(first['columns'])
        self.assertEqual(first['columns'], second['columns'])
        total = model.problem.pulp_lp.constraints['trans_total']
        self.assertEqual(1, -total.constant)
