# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""What the failure page shows: why no set was found, and the set closest to the build's minimums."""
import logging
import math
import time

from chardata.data_versions import current_data_version
from chardata.lock_forbid import get_inclusions_dict
from chardata.min_stats import get_min_stats_digested
from chardata.translation_util import localized_stat_name
from chardata.wear_conditions import reasons_the_build_cannot_wear, still_locked_text
from fashionistapulp.dofus_constants import percent_resist_cap, slots_for
from fashionistapulp.modelresult import ModelResultMinimal, get_item_in_slot
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language

logger = logging.getLogger(__name__)

SESSION_KEY = 'closest_set'
#: How long the failure page can show the set found and keep it
KEPT_SECONDS = 900


def remember_failure(request, char, key, entry):
    """Keeps the failure of the build's solve, with key its input's cache key, for this visitor's failure page."""
    session = getattr(request, 'session', None)
    if session is None:
        return
    now = time.time()
    failures = {build: kept for build, kept in (session.get(SESSION_KEY) or {}).items()
                if isinstance(kept, dict) and kept.get('expires', 0) > now}
    failures[str(char.id)] = dict({name: value for name, value in entry.items()
                                   if name not in ('minimal', 'tie_break')},
                                  key=str(key),
                                  data_version=current_data_version(char.game_version),
                                  expires=now + KEPT_SECONDS)
    session[SESSION_KEY] = failures


def forget_failure(request, char):
    session = getattr(request, 'session', None)
    failures = dict((session.get(SESSION_KEY) or {}) if session is not None else {})
    if failures.pop(str(char.id), None) is not None:
        session[SESSION_KEY] = failures


def current_input(request, char):
    """The solver input of the build's settings now, None when no weight is set."""
    from chardata.fashion_action import _model_input
    from chardata.stats_weights import get_stats_weights
    if not char.stats_weight:
        return None
    try:
        weights = get_stats_weights(char, persist=False)
        if not any(value != 0 for value in weights.values()):
            return None
        return _model_input(request, char, weights)
    except Exception:
        logger.exception('could not read the solver input of char %s', char.id)
        return None


def read_failure(request, char, model_input=None):
    """The build's last failure, while its settings and the item data are the ones it was solved on."""
    session = getattr(request, 'session', None)
    entry = (session.get(SESSION_KEY) or {}).get(str(char.id)) if session is not None else None
    if not isinstance(entry, dict) or entry.get('expires', 0) <= time.time():
        return None
    if entry.get('data_version') != current_data_version(char.game_version):
        return None
    if model_input is None:
        model_input = current_input(request, char)
    if model_input is None or str(model_input.cache_key()) != entry.get('key'):
        return None
    return entry


def closest_minimal(entry, model_input):
    """The closest set of a failure, shaped like a solve's result."""
    minimal = ModelResultMinimal.from_item_id_list(
        list(entry['items']), model_input.get_old_input(), dict(entry['stats']))
    minimal.proven = None
    minimal.closest = {'shortfall': entry.get('shortfall'),
                       'proven': entry.get('closest_proven') is True,
                       'limit': entry.get('closest_seconds')}
    minimal.solve_seconds = entry.get('solve_seconds')
    minimal.candidate_pool = entry.get('pool')
    minimal.data_version = entry.get('data_version')
    return minimal


def _row(name, asked, reached, advanced=False):
    missing = max(asked - reached, 0)
    percent = None
    if asked > 0:
        percent = max(0, min(100, math.floor(100.0 * reached / asked)))
    return {'name': name, 'asked': asked, 'reached': reached, 'missing': missing,
            'percent': percent, 'met': reached >= asked, 'advanced': advanced}


def minimum_rows(char, solution):
    """[{name, asked, reached, missing, percent, met, advanced}] for each minimum the build asks, read on solution."""
    minimums = get_min_stats_digested(char)
    totals = solution.get_stats_total()
    structure = get_structure()
    rows = []
    for stat in structure.get_stats_list():
        asked = minimums.get(stat.name)
        if not isinstance(asked, int) or isinstance(asked, bool) or stat.key not in totals:
            continue
        rows.append(_row(localized_stat_name(stat.name), asked,
                         int(round(totals[stat.key]))))
    advanced = minimums.get('adv_mins') or {}
    cap = percent_resist_cap(structure.game_version)
    for stat in structure.get_adv_mins():
        asked = advanced.get(stat['name'])
        if not isinstance(asked, int) or isinstance(asked, bool):
            continue
        percent_sum = all(name.strip().startswith('%') and name.strip().endswith('Resist')
                          for name in stat['stats'])
        reached = 0
        for name in stat['stats']:
            key = structure.get_stat_by_name(name).key
            value = totals.get(key, 0)
            reached += min(value, cap) if percent_sum else value
        rows.append(_row(str(stat['local_name']), asked, int(round(reached)), True))
    return rows


def _locked_item(structure, value, slot):
    if isinstance(value, int):
        return get_item_in_slot(structure, value, slot)
    members = structure.get_or_item_by_name(value)
    if members:
        return members[0]
    return structure.get_item_by_name(value)


def locked_piece_notes(char):
    """[{name, image_url, reasons, conditions}] for each locked piece in slot order, reasons and conditions as text."""
    from chardata.encyclopedia_view import _format_condition_groups
    from chardata.image_store import get_image_url
    from static_s3.templatetags.static_s3 import static
    structure = get_structure()
    language = get_supported_language()
    locks = {}
    for slot, value in (get_inclusions_dict(char) or {}).items():
        if value in ('', None):
            continue
        item = _locked_item(structure, value, slot)
        if item is not None:
            locks[slot] = item
    notes = []
    for slot in slots_for(char.game_version):
        item = locks.get(slot)
        if item is None:
            continue
        beside = {other.id for other_slot, other in locks.items() if other_slot != slot}
        reasons = reasons_the_build_cannot_wear(char, item, beside)
        groups = _format_condition_groups(structure, [item], language)
        notes.append({
            'name': structure.get_item_name_in_language(item, language) or item.name,
            'image_url': static(get_image_url(structure.get_type_name_by_id(item.type),
                                              item.name, char.game_version)),
            'reasons': still_locked_text(reasons) if reasons else '',
            'conditions': ' / '.join(', '.join(group) for group in groups if group),
        })
    return notes


def failure_context(request, char):
    """The failure page's facts about the build's last solve; empty when they are gone."""
    from chardata.fashion_action import GUARD_BUDGET_SECONDS, solve_budget_seconds
    from chardata.shared_builds_view import _get_preview_items
    from chardata.solution import get_solution_from_minimal
    from chardata.util import version_reverse
    budget = solve_budget_seconds(char)
    context = {'gone': bool(request.GET.get('gone')),
               'again_seconds': budget,
               'again_budget': budget,
               'closest_budget': GUARD_BUDGET_SECONDS,
               'again_url': version_reverse(request, 'search_again', char.id),
               'closest_url': version_reverse(request, 'find_closest_set', char.id),
               'keep_url': version_reverse(request, 'keep_closest_set', char.id)}
    model_input = current_input(request, char)
    entry = read_failure(request, char, model_input) if model_input is not None else None
    if entry is None:
        return context
    context.update(cause=entry.get('cause'), seconds=entry.get('seconds'),
                   closest_state=entry.get('state'))
    if entry.get('state') == 'found':
        try:
            minimal = closest_minimal(entry, model_input)
            solution = get_solution_from_minimal(char, minimal, refresh_base_stats=False)
            rows = minimum_rows(char, solution)
        except Exception:
            logger.exception('could not show the closest set of char %s', char.id)
            context['closest_state'] = 'error'
            return context
        structure = get_structure()
        context.update(closest_items=_get_preview_items(minimal, structure, char.game_version),
                       rows=rows,
                       asked_count=len(rows),
                       reached_count=sum(1 for row in rows if row['met']),
                       all_met=all(row['met'] for row in rows),
                       closest_proven=entry.get('closest_proven') is True,
                       closest_seconds=entry.get('closest_seconds'))
    elif entry.get('state') == 'locks':
        try:
            context['lock_notes'] = locked_piece_notes(char)
        except Exception:
            logger.exception('could not read the locked pieces of char %s', char.id)
            context['lock_notes'] = []
    return context


def closest_set_facts(char, minimal, solution):
    """{'advanced_missed': rows, 'missed': bool, 'proven': bool} when the stored set is a closest set, else None."""
    closest = getattr(minimal, 'closest', None)
    if not isinstance(closest, dict) or solution is None:
        return None
    try:
        rows = minimum_rows(char, solution)
    except Exception:
        logger.warning('could not read the minimums of the closest set of char %s', char.id)
        return None
    return {'advanced_missed': [row for row in rows if row['advanced'] and not row['met']],
            'missed': any(not row['met'] for row in rows),
            'proven': closest.get('proven') is True}
