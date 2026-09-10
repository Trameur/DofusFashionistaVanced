# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Open a build on DofusBook, and say what does not travel before it goes.

The page exists instead of a plain link for one measured reason. On
`retro.dofusbook.net`, three of sixteen Ankama ids in a real build are not in
their catalogue, and their page drops them without a word: the player would
land on a draft missing a hat, an amulet and a weapon and have no way to know
it came from us. So the ids are checked against their own endpoint first and
the answer is shown here, where it can still change the player's mind.

The other half of the page is the list of what their format cannot carry at
all: the build name, the class and the per item jets. Saying it here is
cheaper than letting the player discover it on their side and conclude our
export is broken.
"""

import logging

from django.utils.translation import gettext as _

from chardata import dofusbook_export
from chardata.solution import get_solution
from chardata.util import (get_char_or_raise, get_stats_and_scrolled,
                           set_response)
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


def _worn_items(char):
    """{slot: [ModelResultItem]} for what the character actually wears."""
    try:
        solution = get_solution(char)
    except Exception:
        logger.exception('could not read the solution of char %s', char.id)
        return {}
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
    """Their key and ours. A pickle written before the field existed carries
    no ankama_id, so the catalogue answers for it rather than the item being
    dropped.

    The catalogue is asked for the BUILD's version and not the thread local
    one: the same item id names different gear from one version to the next,
    so a lookup in the wrong catalogue would send a plausible stranger.
    """
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
    """Their two arrays, indexed the way their decoder reads them.

    Both sides list the six base characteristics in the same order, ours as
    BASE_STATS and theirs as `st`, so the index is the whole mapping.
    """
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
    # mp_exo is either a bool or the string 'gelano', and both mean the build
    # carries the point.
    if options.get('mp_exo'):
        drapeaux |= dofusbook_export.EXO_MP
    if options.get('range_exo'):
        drapeaux |= dofusbook_export.EXO_RANGE
    return drapeaux


def _partial_scrolls(char, scrolls):
    """The characteristics whose scroll cannot travel, named for the reader.

    Their format holds 100 or nothing, so a Touch build scrolled to 150 and a
    build scrolled to 50 both lose something, and the second loses all of it.

    Vitality is left out when their format forces a full scroll on it anyway:
    the page says that in one sentence of its own, and listing it twice would
    tell the reader two different things about the same number.
    """
    force = dofusbook_export.vitality_scroll_is_forced(char.level)
    noms = []
    for index, (element_name, _key) in enumerate(STATS_NAMES):
        if index == 0 and force:
            continue
        valeur = scrolls.get(index, 0)
        if 0 < valeur < dofusbook_export.SCROLL_STEP:
            noms.append(element_name)
    return noms


def dofusbook_export_page(request, char_id):
    char = get_char_or_raise(request, char_id)
    params = {
        'char': char,
        'char_id': char.id,
        'version_label': get_game_version(char.game_version).label,
    }

    if not dofusbook_export.supports(char.game_version):
        params['error'] = _reasons()['unsupported_version']
        return set_response(request, 'chardata/dofusbook_export.html', params)

    porte = _worn_items(char)
    # One pass builds both the payload and the two lists the page shows, so
    # they cannot end up disagreeing about which piece went where: an item
    # cut here for want of a slot has to be named as staying, not counted as
    # travelling because the group happened to have room after a filter.
    retenus = {}
    restants = []
    codes_par_slot = dict(dofusbook_export.GROUPS)
    for slot, items in porte.items():
        codes = codes_par_slot.get(slot)
        gardes = []
        for item in items:
            ankama = _ankama_id(item, char.game_version)
            if codes is None or ankama is None or len(gardes) >= len(codes):
                # A slot their format does not have at all, an item our own
                # catalogue has no Ankama id for, or more items than the group
                # holds. Either way the payload leaves them out.
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
        connus = dofusbook_export.known_ankama_ids(char.game_version, groupes)
    except dofusbook_export.ExportError as erreur:
        params['error'] = _reasons().get(erreur.reason,
                                         _reasons()['unreadable'])
        return set_response(request, 'chardata/dofusbook_export.html', params)

    partants = []
    for _slot, paires in retenus.items():
        for ankama, item in paires:
            if ankama in connus:
                partants.append(_named(item))
            else:
                restants.append(_named(item))

    connus_par_groupe = dofusbook_export.keep_known(groupes, connus)
    points, scrolls = _points_and_scrolls(char)
    charge = dofusbook_export.payload(connus_par_groupe, char.level,
                                      points=points, scrolls=scrolls,
                                      exos=_exos(char))
    params.update({
        'link': dofusbook_export.build_url(char.game_version,
                                           get_supported_language(), charge),
        'going': sorted(partants),
        'staying': sorted(restants),
        'partial_scrolls': _partial_scrolls(char, scrolls),
        # Only worth a sentence when it actually differs from the build.
        'vitality_scroll_forced': (
            dofusbook_export.vitality_scroll_is_forced(char.level)
            and scrolls.get(0, 0) < dofusbook_export.SCROLL_STEP),
    })
    return set_response(request, 'chardata/dofusbook_export.html', params)
