# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Inputs, pieces and LP readings for the transcendence rune solver tests."""

from copy import deepcopy

from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import TRANSCENDENCE_OPTION, ModelInput
from fashionistapulp.transcendence import load_runes

from chardata.dracorune_fixtures import NOT_ASKED, OPTIONS, VERSION, bare, build_input, structure


def plain_piece(type_name, lines, number=0):
    """A copy of the number-th setless piece of that type, with these lines and no condition."""
    found = structure()
    items = [item for item in sorted(found.get_available_items_list(), key=lambda one: one.id)
             if found.get_type_name_by_id(item.type) == type_name and item.set is None]
    return bare(deepcopy(items[number]), lines)


def with_transcendence(model_input, allowed):
    """model_input with the transcendence option at allowed, left out when NOT_ASKED."""
    if allowed is not NOT_ASKED:
        model_input.options = dict(model_input.options, **{TRANSCENDENCE_OPTION: allowed})
    return model_input


def trans_input(weights, allowed=NOT_ASKED, dracorunes=None, minimums=None):
    return with_transcendence(build_input(weights, dracorunes, minimums), allowed)


def plain_input(allowed=NOT_ASKED):
    """A level 200 build weighing five stats, for whole catalogues of any version."""
    base = {name: 0 for name, _key in STATS_NAMES}
    return with_transcendence(
        ModelInput(200, base, {}, {}, [], {'vit': 1, 'str': 1, 'int': 1, 'cha': 1, 'agi': 1},
                   dict(OPTIONS), 'Iop', 0, [], {}), allowed)


def trans_columns(model):
    return sorted(v.name for v in model.problem.pulp_lp.variables() if v.name.startswith('trans_'))


def trans_traces(model):
    """Every place a transcendence name can stay in the LP."""
    lp = model.problem.pulp_lp

    def named(names):
        return sorted(name for name in names if name.startswith('trans_'))

    return {'known': named(v.name for v in lp._variables),
            'known_ids': named(v.name for v in lp._variable_ids.values()),
            'columns': named(v.name for v in lp.variables()),
            'variables': named(model.problem.pulp_vars),
            'rows': named(lp.constraints),
            'terms': named(v.name for row in lp.constraints.values() for v in row.keys()),
            'objective': named(v.name for v in lp.objective.keys()),
            'classes_kept': dict(getattr(model, 'transcendence_classes', {})),
            'columns_kept': dict(getattr(model, 'transcendence_columns', {}))}


def beta_rune(stat_key, rank):
    return next(rune for rune in load_runes(VERSION)
                if rune['stat_key'] == stat_key and rune['rank'] == rank)
