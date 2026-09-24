# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""DofusBook export page: the link, and what does not travel."""

import logging

from django.utils.translation import gettext as _

from django.http import Http404

from chardata import build_sites, dofusbook_export
from chardata.inventory_solver import get_effective_stat_overrides
from chardata.solution import get_solution
from chardata.temporix_mode import solution_uses_temporix
from chardata.translation_util import localized_stat_name
from chardata.util import (get_char_or_raise, get_stats_and_scrolled,
                           set_response)
from fashionistapulp import temporix
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.game_versions import get_game_version
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language

logger = logging.getLogger(__name__)


def _reasons():
    return {
        'unsupported_version': _('DofusBook has no site for this version of '
                                 'the game.'),
        'refused': _('DofusBook refused the request.'),
        'unreachable': _('DofusBook could not be reached. Try again later.'),
        'unreadable': _('DofusBook answered something we could not read.'),
        'empty': _('This build has no gear to send.'),
    }


def _solution(char):
    try:
        return get_solution(char)
    except Exception:
        logger.exception('could not read the solution of char %s', char.id)
        return None


def _worn_items(solution):
    """{slot: [ModelResultItem]} of worn items"""
    if solution is None:
        return {}
    porte = {}
    for slot, items in (solution.items or {}).items():
        gardes = [item for item in items
                  if getattr(item, 'item_added', False)
                  and getattr(item, 'name', None) != 'NoItem']
        if gardes:
            porte[slot] = gardes
    return porte


def _ankama_id(item, game_version):
    """Old pickles have no ankama_id: look it up in the build's version."""
    ankama = getattr(item, 'ankama_id', None)
    if ankama is not None:
        return ankama
    item_id = getattr(item, 'id', None)
    if item_id is None:
        return None
    catalogue = get_structure(game_version).get_item_by_id(item_id)
    return getattr(catalogue, 'ankama_id', None) if catalogue else None


def _named(item):
    return (getattr(item, 'localized_name', None)
            or getattr(item, 'name', None) or '')


def _points_and_scrolls(char):
    """Their `st` lists base stats in our order"""
    spent, scrolled = get_stats_and_scrolled(char)
    points = {}
    scrolls = {}
    for index, (element_name, _key) in enumerate(STATS_NAMES):
        points[index] = spent.get(element_name, 0)
        scrolls[index] = scrolled.get(element_name, 0)
    return points, scrolls


def _exos(char):
    from chardata.options import get_options
    options = get_options(char)
    drapeaux = 0
    if options.get('ap_exo'):
        drapeaux |= dofusbook_export.EXO_AP
    # 'gelano' is not the exo, the ring carries the MP itself
    if options.get('mp_exo') is True:
        drapeaux |= dofusbook_export.EXO_MP
    if options.get('range_exo'):
        drapeaux |= dofusbook_export.EXO_RANGE
    return drapeaux


def _partial_scrolls(char, scrolls):
    """Stats whose scroll cannot travel: their format holds 100 or nothing."""
    force = dofusbook_export.vitality_scroll_is_forced(char.level)
    noms = []
    for index, (element_name, _key) in enumerate(STATS_NAMES):
        if index == 0 and force:
            continue
        valeur = scrolls.get(index, 0)
        if 0 < valeur < dofusbook_export.SCROLL_STEP:
            noms.append(localized_stat_name(element_name, char.game_version))
    return noms


def _forgemagie(overrides, structure, item_by_ankama, their_values):
    """({position in their `fm`: total}, [stat keys with no position], exo bits)"""
    positions = dofusbook_export.index_by_stat_key()
    totaux, sans_place = {}, []
    drapeaux = 0
    for ankama, item_id in sorted(item_by_ankama.items()):
        jets = overrides.get(item_id)
        if not jets:
            continue
        leurs = their_values.get(ankama) or {}
        for stat_id, valeur in sorted(jets.items()):
            stat = structure.get_stat_by_id(stat_id)
            if stat is None:
                continue
            position = positions.get(stat.key)
            if position is None:
                if stat.key not in sans_place:
                    sans_place.append(stat.key)
                continue
            ecart = int(valeur) - int(leurs.get(dofusbook_export.VE[position], 0))
            if not ecart:
                continue
            # One exo point per stat for the whole build
            if position in dofusbook_export.EXO_INDEXES:
                if ecart > 0:
                    drapeaux |= dofusbook_export.EXO_BIT_BY_INDEX[position]
                continue
            totaux[position] = totaux.get(position, 0) + ecart
    return totaux, sans_place, drapeaux


def _shiny_forge(structure, item_by_ankama, their_values, overrides):
    """Shiny bonus sent as forgemagie, like _forgemagie minus the exo bits."""
    shiny_by_id = temporix.shiny_items_by_id(structure)
    positions = dofusbook_export.index_by_stat_key()
    totaux, sans_place = {}, []
    for ankama, item_id in sorted(item_by_ankama.items()):
        shiny = shiny_by_id.get(item_id)
        if shiny is None or item_id in overrides:
            continue
        leurs = their_values.get(ankama) or {}
        valeurs = {}
        for stat_id, valeur in shiny.stats:
            valeurs[stat_id] = valeurs.get(stat_id, 0) + valeur
        for stat_id, valeur in sorted(valeurs.items()):
            stat = structure.get_stat_by_id(stat_id)
            if stat is None:
                continue
            position = positions.get(stat.key)
            if position is None:
                if stat.key not in sans_place:
                    sans_place.append(stat.key)
                continue
            ecart = int(valeur) - int(leurs.get(dofusbook_export.VE[position], 0))
            if ecart:
                totaux[position] = totaux.get(position, 0) + ecart
    return totaux, sans_place


def _named_stats(structure, game_version, keys):
    noms = []
    for key in keys:
        stat = structure.get_stat_by_key(key)
        if stat is not None:
            noms.append(localized_stat_name(stat.name, game_version))
    return noms


def _keys_of_positions(positions, wanted):
    par_position = {}
    for key, position in positions.items():
        par_position.setdefault(position, key)
    return [par_position[p] for p in wanted if p in par_position]


def dofusbook_export_page(request, char_id):
    if not build_sites.enabled(build_sites.DOFUSBOOK):
        raise Http404
    char = get_char_or_raise(request, char_id)
    params = {
        'char': char,
        'char_id': char.id,
        'version_label': get_game_version(char.game_version).label,
    }

    if not dofusbook_export.supports(char.game_version):
        params['error'] = _reasons()['unsupported_version']
        return set_response(request, 'chardata/dofusbook_export.html', params)

    solution = _solution(char)
    porte = _worn_items(solution)
    retenus = {}
    restants = []
    codes_par_slot = dict(dofusbook_export.GROUPS)
    for slot, items in porte.items():
        codes = codes_par_slot.get(slot)
        gardes = []
        for item in items:
            ankama = _ankama_id(item, char.game_version)
            if codes is None or ankama is None or len(gardes) >= len(codes):
                restants.append(_named(item))
            else:
                gardes.append((ankama, item))
        if gardes:
            retenus[slot] = gardes
    groupes = dofusbook_export.group_ankama_ids(
        {slot: [a for a, _item in paires]
         for slot, paires in retenus.items()})
    if not any(groupes):
        params['error'] = _reasons()['empty']
        return set_response(request, 'chardata/dofusbook_export.html', params)

    try:
        # Their item values are the baseline for forgemagie
        leurs_entrees = dofusbook_export.stuffer_items(char.game_version,
                                                       groupes)
    except dofusbook_export.ExportError as erreur:
        params['error'] = _reasons().get(erreur.reason,
                                         _reasons()['unreadable'])
        return set_response(request, 'chardata/dofusbook_export.html', params)
    connus = dofusbook_export.ids_of(leurs_entrees)
    leurs_valeurs = dofusbook_export.their_line_values(leurs_entrees)

    partants = []
    item_par_ankama = {}
    for _slot, paires in retenus.items():
        for ankama, item in paires:
            if ankama in connus:
                partants.append(_named(item))
                item_par_ankama[ankama] = getattr(item, 'id', None)
            else:
                restants.append(_named(item))

    connus_par_groupe = dofusbook_export.keep_known(groupes, connus)
    points, scrolls = _points_and_scrolls(char)
    structure = get_structure(char.game_version)
    overrides = get_effective_stat_overrides(char) or {}
    totaux, sans_place, exos_des_jets = _forgemagie(
        overrides, structure, item_par_ankama, leurs_valeurs)
    rayonnant = {}
    if solution_uses_temporix(solution, char.game_version):
        rayonnant, sans_place_rayonnant = _shiny_forge(
            structure, item_par_ankama, leurs_valeurs, overrides)
        sans_place += [key for key in sans_place_rayonnant
                       if key not in sans_place]
        for position, total in rayonnant.items():
            if position not in dofusbook_export.EXO_INDEXES:
                totaux[position] = totaux.get(position, 0) + total
    forge, refusees = dofusbook_export.carriable_forge(totaux, scrolls,
                                                       char.level)
    # Shiny AP, MP and Range are real points, not the exo bit
    for position in dofusbook_export.EXO_INDEXES:
        if rayonnant.get(position):
            forge[position] = rayonnant[position]
    exos = _exos(char) | exos_des_jets
    charge = dofusbook_export.payload(connus_par_groupe, char.level,
                                      points=points, scrolls=scrolls,
                                      exos=exos, forge=forge)
    params.update({
        'link': dofusbook_export.build_url(char.game_version,
                                           get_supported_language(), charge),
        'going': sorted(partants),
        'staying': sorted(restants),
        'partial_scrolls': _partial_scrolls(char, scrolls),
        'forge_travels': bool(forge) or bool(exos),
        'shiny_travels': bool(rayonnant),
        'forge_staying': _named_stats(
            structure, char.game_version,
            sans_place + _keys_of_positions(
                dofusbook_export.index_by_stat_key(), refusees)),
        'vitality_scroll_forced': (
            dofusbook_export.vitality_scroll_is_forced(char.level)
            and scrolls.get(0, 0) < dofusbook_export.SCROLL_STEP),
    })
    return set_response(request, 'chardata/dofusbook_export.html', params)
