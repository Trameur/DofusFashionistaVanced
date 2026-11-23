# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the transcendence runes of a build page hold up: its count and the minimums it would fail without them."""

import logging
import pickle

from django.utils.translation import gettext

from chardata.closest_set import minimum_rows
from chardata.presets import effective_hp, short_of_floors
from chardata.solution import get_solution_from_minimal
from chardata.translation_util import localized_stat_name
from fashionistapulp.structure import get_structure

logger = logging.getLogger(__name__)


def theoretical_build(char, minimal, solution, refresh_base_stats=True):
    """{'count', 'minimums'} of a set that counts transcendence runes, None on a set without one; the bare set reads the base stats as the page's set does."""
    count = sum(1 for item in getattr(solution, 'item_list', ())
                if getattr(item, 'transcendence_rune', None))
    if not count:
        return None
    try:
        bare = pickle.loads(pickle.dumps(minimal))
        bare.transcendences = None
        without = get_solution_from_minimal(char, bare, refresh_base_stats=refresh_base_stats)
        names = _named(_rows_met_only_with(char, solution, without)
                       + _floors_met_only_with(minimal, solution, without))
    except Exception:
        logger.exception('could not read the build without its transcendence runes (char %s)',
                         getattr(char, 'id', '?'))
        return {'count': count, 'minimums': []}
    return {'count': count, 'minimums': names}


def _named(names):
    return list(dict.fromkeys(names))


def _rows_met_only_with(char, solution, without):
    bare_rows = {row['name']: row for row in minimum_rows(char, without)}
    return [row['name'] for row in minimum_rows(char, solution)
            if row['met'] and row['name'] in bare_rows and not bare_rows[row['name']]['met']]


def _floors_met_only_with(minimal, solution, without):
    """The safeguard floors the solve recorded, read on both sets; the turn guard's adv_mins floors are not stored."""
    facts = getattr(minimal, 'guard', None)
    if not isinstance(facts, dict) or facts.get('fallback'):
        return []
    totals, bare_totals = solution.get_stats_total(), without.get_stats_total()
    floors = facts.get('floors') or {}
    structure = get_structure()
    names = []
    if facts.get('kind') == 'effective_hp' and facts.get('balanced'):
        floor = (100 - facts['percent']) / 100.0 * facts['balanced']
        if effective_hp(totals) >= floor > effective_hp(bare_totals):
            names.append(gettext('Effective HP'))
    held = set(short_of_floors(floors, bare_totals)) - set(short_of_floors(floors, totals))
    for key in sorted(held):
        stat = structure.get_stat_by_key(key)
        if stat is not None:
            names.append(localized_stat_name(stat.name))
    return names
