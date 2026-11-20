# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A closest set kept as the build's set goes on from its own runes, even one only the minimums kept."""

import time
from types import SimpleNamespace
from unittest import mock

from chardata import fashion_action
from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input, columns,
                                         element_key, element_move, piece)
from fashionistapulp import dracorunes

NEEDED = 40
STAT_NAMES = {'str': 'Strength', 'int': 'Intelligence', 'cha': 'Chance', 'agi': 'Agility'}


def column(item, key):
    kind, _, move = key.partition(':')
    return 'draco_%d_%s_%s' % (item.id, kind[:1], '_'.join(move.split('>')))


class UnprovenClosestModel(SmallModel):
    """Proves nothing, and keeps the barred column at zero once the minimums are elastic."""

    def __init__(self, items, barred=None):
        self._barred = barred
        super().__init__(items)

    def add_elastic_minimums(self, minimum_stats, level):
        shortfalls = super().add_elastic_minimums(minimum_stats, level)
        if self._barred:
            self.problem.pulp_vars[self._barred].upBound = 0
        return shortfalls

    def solution_is_proven(self):
        return False


class AClosestSetGoesOnFromItsOwnRunesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        _source, self.target = element_move()
        self.weighted, self.other = sorted(
            key for key, _damage in dracorunes.ELEMENT_PAIRS if key != self.target)[:2]
        self.hat = piece('Hat', {self.weighted: NEEDED, self.other: NEEDED})
        self.by_weight = column(self.hat, element_key(self.other, self.target))
        self.by_minimum = column(self.hat, element_key(self.weighted, self.target))
        self.char = SimpleNamespace(id=0, game_version='beta')

    def model_input(self, runes_allowed):
        return build_input({self.weighted: 1, 'vit': 0}, runes_allowed,
                           {STAT_NAMES[self.target]: NEEDED})

    def closest_answer(self, model_input, closest_model):
        with mock.patch.object(fashion_action, 'Model', return_value=closest_model), \
                mock.patch.dict(fashion_action._BUILD_SECONDS, {}, clear=True), \
                mock.patch.object(fashion_action, 'guard_plan', return_value=None):
            found = fashion_action._closest_solve(self.char, model_input, 'time',
                                                  time.monotonic() + 600)
            self.assertEqual('found', found['state'])
            self.assertTrue(found['meets_all'])
            self.assertFalse(found['tie_break']['proven'])
            return fashion_action._answer_of(self.char, model_input, found)

    def go_on(self, model_input, answer):
        """(the start was valid as the solver was handed it, the continuing model, what was saved)."""
        model = SmallModel([self.hat])
        lp = model.problem.pulp_lp
        solve = lp.solve
        seen = {}

        def handed(solver):
            seen['valid'] = lp.valid(1e-6)
            return solve(solver)

        with mock.patch.object(lp, 'solve', side_effect=handed), \
                mock.patch.object(fashion_action, 'borrow_model', return_value=model), \
                mock.patch.object(fashion_action, 'return_model'), \
                mock.patch.object(fashion_action, '_keep_in_memory'), \
                mock.patch.object(fashion_action, '_save_search') as save:
            fashion_action._continue_search(None, self.char, None, answer, model_input,
                                            time.monotonic() + 600)
        self.assertEqual(1, save.call_count)
        return seen['valid'], model, save.call_args[0][3]

    def test_the_stored_start_holds_on_the_continuing_model(self):
        model_input = self.model_input(1)
        answer = self.closest_answer(model_input,
                                     UnprovenClosestModel([self.hat], self.by_weight))
        start = fashion_action._unpack_start(answer.search['start'])
        self.assertEqual(1, start.get(self.by_minimum))
        valid, model, _saved = self.go_on(model_input, answer)
        self.assertIn(self.by_minimum, columns(model))
        self.assertTrue(valid)

    def test_the_search_that_goes_on_finds_the_better_rune(self):
        model_input = self.model_input(1)
        answer = self.closest_answer(model_input,
                                     UnprovenClosestModel([self.hat], self.by_weight))
        _valid, _model, saved = self.go_on(model_input, answer)
        self.assertEqual({'hat': (self.hat.id, element_key(self.other, self.target))},
                         saved.dracorunes)

    def test_without_runes_the_stored_search_is_the_one_it_was(self):
        hat = piece('Hat', {self.target: NEEDED})
        for runes_allowed in (None, 0):
            with self.subTest(runes_allowed=runes_allowed):
                model_input = self.model_input(runes_allowed)
                answer = self.closest_answer(model_input, UnprovenClosestModel([hat]))
                self.assertEqual({'objective', 'bound', 'start', 'limit', 'minimum_stats',
                                  'objective_values', 'item_terms', 'crit_hinges', 'key',
                                  'plan'}, set(answer.search))
