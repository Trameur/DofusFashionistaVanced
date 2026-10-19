# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Reads the rows and the objective of a model from its row table, with no solver library in sight."""
import operator

_COMPARE = {'<=': operator.le, '>=': operator.ge, '==': operator.eq}


def coefficients(terms):
    """{variable name: coefficient} of a handle's terms or of an objective, repeats added."""
    if hasattr(terms, 'terms'):
        terms = terms.terms
    merged = {}
    for coefficient, name in terms:
        merged[name] = merged.get(name, 0) + coefficient
    return merged


def evaluate(terms, values):
    """The terms at values, {variable name: number}; a column missing from values counts as 0."""
    if hasattr(terms, 'terms'):
        terms = terms.terms
    return sum(coefficient * values.get(name, 0) for coefficient, name in terms)


def holds(row, values):
    """Whether the row is satisfied at values."""
    return _COMPARE[row.sense](evaluate(row, values), row.rhs)


def row_value(row, values):
    """The row as terms + constant, the way the solver library reads it."""
    return evaluate(row, values) + row.constant


def solved_values(problem):
    """{column name: value} of the last solve, for the columns the solver was given."""
    return {name: problem.value(name) for name in problem.column_names()}


def minimum_rows(structure):
    """The model's minimum stat rows on a real problem: (model, {stat name: row handle})."""
    from types import SimpleNamespace

    from fashionistapulp.lpproblem import LpProblem2
    from fashionistapulp.model import Model

    problem = LpProblem2()
    stats_list = structure.get_stats_list()
    for stat in stats_list:
        problem.declare_variable('stat_%s' % stat.id, 0, None)
    model = SimpleNamespace(
        stats_list=stats_list, problem=problem, structure=structure,
        restrictions=SimpleNamespace(minimum_stat_constraints={}),
        modify_advanced_minimum_stat_constraints=lambda minimums: None)
    Model.create_minimum_stat_constraints(model)
    return model, model.restrictions.minimum_stat_constraints


def derived_rates(structure):
    """{stat name: {source stat name: rate}} the minimum rows give each stat."""
    model, rows = minimum_rows(structure)
    name_by_column = {'stat_%s' % stat.id: stat.name for stat in model.stats_list}
    derived = {}
    for name, row in rows.items():
        sources = {name_by_column[column]: -coefficient
                   for coefficient, column in row.terms
                   if name_by_column[column] != name}
        if sources:
            derived[name] = sources
    return derived


def hp_floors(structure, minimums, level):
    """{stat name: right-hand side} after modify_minimum_stat_constraints."""
    from fashionistapulp.model import Model

    model, rows = minimum_rows(structure)
    Model.modify_minimum_stat_constraints(model, minimums, level)
    return {name: row.rhs for name, row in rows.items()}
