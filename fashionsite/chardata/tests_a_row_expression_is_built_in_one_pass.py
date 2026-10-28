# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import math
from unittest import mock

import pulp
from django.test import SimpleTestCase

from fashionistapulp.lpproblem import LpProblem2

NAMES = ['a', 'b', 'c', 'd']


def _problem():
    problem = LpProblem2()
    for name in NAMES:
        problem.declare_variable(name, 0, 10, integer=False)
    return problem


def _shape(expression):
    items = [(column.name, coefficient, type(coefficient))
             for column, coefficient in expression.items()]
    return items, expression.constant, type(expression.constant)


class ARowExpressionIsBuiltInOnePassTests(SimpleTestCase):
    def test_the_one_pass_expression_equals_the_library_sum_term_by_term(self):
        cases = [
            [(1, 'a')],
            [(2.5, 'a'), (3, 'b')],
            [(0, 'a'), (3, 'b')],
            [(0.0, 'a'), (-0.0, 'b'), (1.5, 'c')],
            [(-0.0, 'a')],
            [(-2, 'a'), (-1.25, 'b'), (7, 'c')],
            [(1, 'a'), (2, 'b'), (3, 'a'), (-1, 'b')],
            [(1.5, 'a'), (-1.5, 'a')],
            [(10 ** 20, 'a'), (1e-300, 'd')],
            [(True, 'a'), (3, 'b')],
        ]
        for terms in cases:
            with self.subTest(terms=terms):
                problem = _problem()
                expected = pulp.lpSum([coefficient * problem._column(name)
                                       for coefficient, name in terms])
                self.assertEqual(_shape(problem._expression(terms)), _shape(expected))

    def test_a_non_finite_coefficient_is_refused_as_the_library_refuses_it(self):
        for value in (math.nan, math.inf, -math.inf):
            for terms in ([(value, 'a')], [(1, 'a'), (value, 'b')], [(1, 'a'), (value, 'b'), (0, 'c')]):
                with self.subTest(terms=terms):
                    problem = _problem()
                    with self.assertRaises(pulp.PulpError) as new:
                        problem._expression(terms)
                    with self.assertRaises(pulp.PulpError) as old:
                        pulp.lpSum([coefficient * problem._column(name) for coefficient, name in terms])
                    self.assertEqual(str(new.exception), str(old.exception))

    def test_a_zero_coefficient_still_builds_its_column(self):
        problem = _problem()
        problem._expression([(0, 'a'), (2, 'b')])
        self.assertIn('a', problem._built)

    def test_no_term_gives_the_integer_zero(self):
        result = _problem()._expression([])
        self.assertEqual(result, 0)
        self.assertIs(type(result), int)

    def test_a_row_of_many_terms_makes_one_library_expression(self):
        problem = LpProblem2()
        names = ['x%d' % index for index in range(50)]
        for name in names:
            problem.declare_variable(name, 0, 1, integer=False)
        terms = [(index + 1, name) for index, name in enumerate(names)]
        for name in names:
            problem._column(name)
        original = pulp.LpAffineExpression.__init__
        with mock.patch.object(pulp.LpAffineExpression, '__init__', autospec=True,
                               side_effect=original) as constructed:
            problem._expression(terms)
        self.assertEqual(constructed.call_count, 1)
