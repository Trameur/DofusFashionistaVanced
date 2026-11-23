# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Saved builds and rendered cards for the transcendence rune page tests."""

import pickle

from django.template.loader import render_to_string

from chardata.dracorune_fixtures import OPTIONS, eligible_items, element_key, element_move, runes
from chardata.solution_result import SolutionResult
from fashionistapulp import dracorunes
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import get_structure
from fashionistapulp.transcendence import load_runes
from fashionistapulp.transcendence_terms import rune_fits


def lines_of(item, version='beta'):
    """{stat key: value} of a catalogue piece."""
    lines = {}
    for stat_id, value in item.stats:
        key = get_structure(version).get_stat_by_id(stat_id).key
        lines[key] = lines.get(key, 0) + value
    return lines


def minimal_with(item_per_slot, transcendences=None, saved_dracorunes=None, options=None):
    """A saved build as the page reloads it, through a pickle round trip."""
    base = dict({name: 0 for name, _key in STATS_NAMES}, AP=7, MP=3)
    minimal = ModelResultMinimal(dict(item_per_slot),
                                 {'options': dict(options or OPTIONS), 'char_level': 200,
                                  'base_stats_by_attr': base}, None)
    if transcendences is not None:
        minimal.transcendences = transcendences
    if saved_dracorunes is not None:
        minimal.dracorunes = saved_dracorunes
    return pickle.loads(pickle.dumps(minimal))


def rune_of_stat(stat_key, version='beta', rank=1):
    """The version's rune of that stat and rank."""
    return next(rune for rune in load_runes(version)
                if rune['stat_key'] == stat_key and rune['rank'] == rank)


def plain_pieces(type_name, version='beta', count=2, rune=None):
    """The first catalogue pieces of that type with no set, whose lines take the rune."""
    found = [item for item in sorted(get_structure(version).get_available_items_list(),
                                     key=lambda one: one.id)
             if get_structure(version).get_type_name_by_id(item.type) == type_name
             and item.set is None and not item.removed
             and (rune is None or rune_fits(rune, lines_of(item, version).get(rune['stat_key'])))]
    return found[:count]


def draconizable_hat():
    """(hat, variant key) of a beta hat an element Dracorune can move."""
    source, target = element_move()
    key = element_key(source, target)
    hat = next(item for item in eligible_items('Hat')
               if lines_of(item).get(source, 0) > 0
               and key in dict(dracorunes.variants(list(lines_of(item).items()), runes())))
    return hat, key


def card_of(result, slot):
    """(piece, rendered card) of the slot, as the page renders it."""
    piece = next(item for item in SolutionResult(result).get_params()['all_items']
                 if item.slot == slot)
    return piece, render_to_string('chardata/solution_item.html', {'item': piece})


def piece_in(result, slot):
    return next(item for item in result.item_list if item.slot == slot)
