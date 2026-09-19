# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Put an imported build's gear on a character, without running the solver."""

import logging

from chardata.solution import set_minimal_solution
from chardata.util import base_stats_by_attr_for
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES,
                                             TYPE_NAME_TO_SLOT_NUMBER)
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import (get_structure, get_current_game_version,
                                       set_current_game_version)

logger = logging.getLogger(__name__)


# DofusBook's character_class is not Ankama's numbering: the player picks the class
def _classes_for(game_version):
    from chardata.version_compat import filter_classes_for_version
    noms = filter_classes_for_version(CHARACTER_CLASSES, game_version)
    return [(nom, str(LOCALIZED_CHARACTER_CLASSES.get(nom, nom)))
            for nom in noms]


def _preview(build):
    """The gear, named in the reader's language, before anything is created."""
    structure = get_structure(build['game_version'])
    pieces = []
    for item_id in build['item_ids']:
        item = structure.get_item_by_id(item_id)
        if item is None:
            continue
        pieces.append({
            'id': item_id,
            'name': structure.get_item_name_in_language(
                item, _language_code()),
            'level': item.level,
        })
    return pieces


def _language_code():
    from fashionistapulp.translation import get_supported_language
    return get_supported_language()


def _solution_path(char):
    """The build's own version prefix, not the request's."""
    version = getattr(char, 'game_version', None) or 'dofus3'
    prefixe = '' if version == 'dofus3' else '/' + version
    return '%s/solution/%d/' % (prefixe, char.id)


def _place_items(char, item_ids, origin='dofusbook'):
    """Put the gear on the character without solving anything."""
    # from_item_id_list reads the catalogue of the thread local version
    precedente = get_current_game_version()
    set_current_game_version(char.game_version)
    try:
        # from_item_id_list raises KeyError on more items than slots: keep what fits
        structure = get_structure(char.game_version)
        restants = dict(TYPE_NAME_TO_SLOT_NUMBER)
        gardes = []
        for item_id in item_ids:
            item = structure.get_item_by_id(item_id)
            if item is None:
                continue
            type_name = structure.get_type_name_by_id(item.type)
            if restants.get(type_name, 0) <= 0:
                continue
            restants[type_name] -= 1
            gardes.append(item_id)
        item_ids = gardes
        # The char's real options: model_result_from_minimal reads ap_exo and co
        from chardata.options import get_options as get_char_options
        entree = {
            'locked_equips': {},
            'options': get_char_options(char),
            'base_stats_by_attr': base_stats_by_attr_for(char),
            'char_level': char.level,
            'origin': origin,
        }
        solution = ModelResultMinimal.from_item_id_list(item_ids, entree, None)
        set_minimal_solution(char, solution)
    finally:
        set_current_game_version(precedente)


def dofusbook(request):
    """Old address of the link import, redirects to the import page."""
    from django.http import HttpResponsePermanentRedirect
    from chardata.text_build_view import _url_pour_version
    version = getattr(request, 'game_version', None) or get_current_game_version()
    return HttpResponsePermanentRedirect(_url_pour_version(version))
