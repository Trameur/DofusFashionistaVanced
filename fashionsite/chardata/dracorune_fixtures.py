# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Solver models for the dracorune tests: whole catalogues, and small ones of written lines."""

import itertools
import os
import tempfile
from copy import deepcopy

from django.test import SimpleTestCase

from fashionistapulp import dracorune_terms, dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.structure import get_structure, set_current_game_version

VERSION = 'beta'
OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False, 'dofus': True,
           'trophies': True, 'dragoturkey': True, 'seemyool': True, 'rhineetle': True,
           'prysmaradite': False, 'shields': True}
NOT_ASKED = object()


def runes():
    return dracorunes.load_runes(VERSION)


def structure():
    return get_structure(VERSION)


def stat_id(key):
    return structure().get_stat_by_key(key).id


def element_move():
    """(source, target) characteristic keys of the first element rune of the runes file."""
    target = next(rune['target'] for rune in runes()['runes'] if rune['kind'] == 'element')
    source = next(key for key, _damage in dracorunes.ELEMENT_PAIRS if key != target)
    return source, target


def element_key(source, target):
    return 'element:%s>%s' % (source, target)


def eligible_items(type_name):
    """The setless catalogue pieces of that type a rune can go on, by id."""
    found = structure()
    rules = runes()
    for item in sorted(found.get_available_items_list(), key=lambda one: one.id):
        if (found.get_type_name_by_id(item.type) == type_name and item.set is None
                and dracorune_terms.is_eligible(item, found, rules)):
            yield item


def piece(type_name, lines, number=0, keep_lines=False):
    """A copy of the number-th eligible piece of that type, with these lines and no condition."""
    return bare(deepcopy(next(itertools.islice(eligible_items(type_name), number, None))),
                lines, keep_lines)


def bare(item, lines, keep_lines=False):
    """item with these lines and no condition."""
    if not keep_lines:
        item.stats = [(stat_id(key), value) for key, value in lines.items()]
        item.stat_ranges = {}
    item.level = 1
    item.max_level = None
    item.min_stats_to_equip = []
    item.max_stats_to_equip = []
    item.or_conditions = []
    item.weird_conditions = {'light_set': False, 'prysmaradite': False}
    item.flags = []
    item.classes = ()
    item.not_worn_with = ()
    item.spell_conditions = ()
    item.unusable = False
    return item


class _WithoutOrRows:

    def __init__(self, found):
        self._found = found

    def __getattr__(self, name):
        return getattr(self._found, name)

    def get_available_or_items(self):
        return {}


class SmallModel(Model):
    """A Beta model that offers only the given pieces and sets."""

    def __init__(self, items, sets=(), stat_overrides=None):
        self._pieces = (list(items), list(sets))
        super().__init__(stat_overrides)

    def create_structure(self):
        super().create_structure()
        self.structure = _WithoutOrRows(self.structure)
        self.items_list = list(self._pieces[0])
        self.sets_list = list(self._pieces[1])


class OrGroupModel(Model):
    """A Beta model that offers only the given pieces, the rows of each group being one item."""

    def __init__(self, items, groups):
        self._pieces = list(items)
        self._groups = groups
        super().__init__(None)

    def create_structure(self):
        super().create_structure()
        groups = self._groups

        class WithGroups(_WithoutOrRows):
            def get_available_or_items(self):
                return groups

        self.structure = WithGroups(self.structure)
        self.items_list = list(self._pieces)
        self.sets_list = []


def build_input(weights, runes_allowed=None, minimums=None, locked=None, forbidden=()):
    options = dict(OPTIONS)
    if runes_allowed is not None:
        options['dracorunes'] = runes_allowed
    base = {name: 0 for name, _key in STATS_NAMES}
    return ModelInput(200, base, dict(minimums or {}), dict(locked or {}), list(forbidden),
                      dict(weights), options, 'Iop', 0, [], {})


def columns(model):
    return sorted(variable.name for variable in model.problem.pulp_lp.variables()
                  if variable.name.startswith('draco_'))


def stat_value(model, key):
    return model.problem.pulp_vars['stat_%d' % stat_id(key)].varValue


class BetaModelTestCase(SimpleTestCase):

    def setUp(self):
        set_current_game_version(VERSION)
        self.addCleanup(set_current_game_version, 'dofus3')

    def solve(self, model, model_input):
        model.setup(model_input)
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        return model.get_result_minimal()


def real_input(runes_allowed=NOT_ASKED):
    """A level 200 build with weights, minimums and a crit hinge, for whole catalogues."""
    options = dict(OPTIONS)
    if runes_allowed is not NOT_ASKED:
        options['dracorunes'] = runes_allowed
    base = {name: 0 for name, _key in STATS_NAMES}
    base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100, 'Pods': 1000})
    minimums = {'AP': 11, 'Initiative': 2000, 'Effective HP': 5000, 'adv_mins': {'Power + Strength': 300}}
    return ModelInput(200, base, minimums, {}, [], {'str': 1, 'pow': 1, 'earthdam': 4, 'vit': 1},
                      options, 'Iop', 995, [], {}, crit_hinges=((40, 1),))


def written(model, runes_allowed=NOT_ASKED):
    """The MPS bytes of the model set up for real_input, under one problem name."""
    return mps(model, real_input(runes_allowed))


def mps(model, model_input):
    """The MPS bytes of the model set up for model_input, under one problem name."""
    model.setup(model_input)
    handle, path = tempfile.mkstemp(suffix='.mps')
    os.close(handle)
    try:
        model.problem.pulp_lp.name = 'build'
        model.problem.pulp_lp.writeMPS(path)
        with open(path, 'rb') as mps:
            return mps.read()
    finally:
        os.remove(path)
