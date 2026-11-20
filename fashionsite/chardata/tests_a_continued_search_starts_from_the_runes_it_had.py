# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A search that goes on starts from the stored set with its runes, and from the same set as before without them."""

from unittest import mock

from chardata import fashion_action
from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece)

LINE = 40


class AContinuedSearchStartsFromTheStoredRunesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.pieces = [piece('Hat', {self.source: LINE}), piece('Amulet', {'vit': 100})]

    def stored_start(self, model_input):
        model = SmallModel(self.pieces)
        first = self.solve(model, model_input)
        state = model.get_search_state()
        search = fashion_action._new_search(state, model_input, 30)
        return first, state, fashion_action._unpack_start(search['start'])

    def start_as_read(self, model_input, start):
        """Whether the start, as the solver is handed it, holds every row and bound, and its objective."""
        model = SmallModel(self.pieces)
        model.setup(model_input)
        lp = model.problem.pulp_lp
        seen = {}

        def handed(_solver):
            seen['valid'] = lp.valid(1e-6)

        with mock.patch.object(lp, 'solve', side_effect=handed):
            model.problem.run(start)
        return seen['valid'], model.get_search_state()['start_objective']

    def go_on(self, model_input, start):
        model = SmallModel(self.pieces)
        model.setup(model_input)
        model.run(2, warm_start=start)
        self.assertEqual('Optimal', model.get_solved_status())
        return model.get_search_state(), model.get_result_minimal()

    def test_the_stored_start_holds_the_rune_column(self):
        first, _state, start = self.stored_start(build_input({self.target: 1}, 1))
        self.assertEqual({'hat': (self.pieces[0].id, element_key(self.source, self.target))},
                         first.dracorunes)
        self.assertEqual(1, sum(1 for name in start if name.startswith('draco_')))

    def test_the_next_model_reads_a_start_that_holds_with_its_rune(self):
        _first, state, start = self.stored_start(build_input({self.target: 1}, 1))
        valid, objective = self.start_as_read(build_input({self.target: 1}, 1), start)
        self.assertTrue(valid)
        self.assertAlmostEqual(state['objective'], objective)

    def test_the_start_does_not_hold_on_a_model_without_the_rune(self):
        _first, _state, start = self.stored_start(build_input({self.target: 1}, 1))
        valid, _objective = self.start_as_read(build_input({self.target: 1}, 0), start)
        self.assertFalse(valid)

    def test_the_search_that_goes_on_keeps_the_rune(self):
        first, state, start = self.stored_start(build_input({self.target: 1}, 1))
        again, result = self.go_on(build_input({self.target: 1}, 1), start)
        self.assertAlmostEqual(state['objective'], again['start_objective'])
        self.assertAlmostEqual(state['objective'], again['objective'])
        self.assertEqual(first.dracorunes, result.dracorunes)

    def test_without_runes_the_start_is_the_set_alone(self):
        for runes_allowed in (None, 0):
            with self.subTest(runes_allowed=runes_allowed):
                first, state, start = self.stored_start(build_input({'vit': 1}, runes_allowed))
                self.assertFalse(any(name.startswith('draco_') for name in start))
                self.assertFalse(getattr(first, 'dracorunes', None))
                valid, objective = self.start_as_read(build_input({'vit': 1}, runes_allowed),
                                                      start)
                self.assertTrue(valid)
                self.assertAlmostEqual(state['objective'], objective)
