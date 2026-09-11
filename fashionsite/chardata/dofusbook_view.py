# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Paste a DofusBook link, get the same gear here.

Two deliberate refusals, both of them the point of the feature rather than
limitations of it.

**It does not run the solver.** The player asked to get their build back, not
to be given another one. What comes out is their gear, piece for piece, and
optimising it afterwards is a separate decision they make. A builder whose
solver is a function, not a machine that answers a question nobody asked.

**It does not guess the class.** DofusBook's `character_class` is their own
numbering and not Ankama's: build 7894460 is called "Zobal M 200" and carries
12, where 12 is Pandawa in Ankama's order. Nothing in the payload names the
class, so the player picks it on the confirmation step.
"""

import logging

from chardata.solution import set_minimal_solution
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES,
                                             TYPE_NAME_TO_SLOT_NUMBER)
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import (get_structure, get_current_game_version,
                                       set_current_game_version)

logger = logging.getLogger(__name__)

# The refusals a link can earn live with the page that reads links now,
# text_build_view._raisons_du_lien, worded for any site rather than one.


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
    """The build's own version prefix, not the request's.

    Same rule as shared_build_path: a build lives in one version and its page
    only exists under that prefix. A Retro build imported while the reader was
    browsing Dofus 3 would otherwise be handed a URL that 404s.
    """
    version = getattr(char, 'game_version', None) or 'dofus3'
    prefixe = '' if version == 'dofus3' else '/' + version
    return '%s/solution/%d/' % (prefixe, char.id)


def _place_items(char, item_ids, origin='dofusbook'):
    """Put the gear on the character without solving anything.

    `origin` is stamped into the solution's input and read back by
    `solution_result` as `is_generated`, which is what stops the page saying
    the solver produced a set the solver never saw. Any value but 'generated'
    gives that answer, so this parameter changes nothing for the reader; it
    keeps the row from claiming a build came from DofusBook when it was
    pasted in as text.

    from_item_id_list reads the catalogue through the thread local current
    version, so it is set to the BUILD's version here: importing a Retro link
    from the Dofus 3 site would otherwise look every item up in the wrong
    catalogue and quietly dress the character in different gear.
    """
    precedente = get_current_game_version()
    set_current_game_version(char.game_version)
    try:
        # from_item_id_list raises KeyError as soon as a type brings more
        # items than it has slots, so a payload with three rings or seven
        # dofus would be a 500 rather than an import. Their data is theirs;
        # we take what fits, in the order they sent it.
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
        # The char's real options, not an empty dict: model_result_from_minimal
        # reads ap_exo and its neighbours straight out of this and raises
        # KeyError on anything it does not find.
        from chardata.options import get_options as get_char_options
        entree = {
            'locked_equips': {},
            'options': get_char_options(char),
            'base_stats_by_attr': {},
            'char_level': char.level,
            'origin': origin,
        }
        solution = ModelResultMinimal.from_item_id_list(item_ids, entree, None)
        set_minimal_solution(char, solution)
    finally:
        set_current_game_version(precedente)


def dofusbook(request):
    """The old address of the link import, kept for the links that carry it.

    On 2026-09-11 the import became one page, site neutral (text_build_view):
    a link pasted there is read the same way, next to item names and
    screenshots. The page that only took a link is gone; its address sends
    the reader to the one page, under the same game version.
    """
    from django.http import HttpResponsePermanentRedirect
    from chardata.text_build_view import _url_pour_version
    version = getattr(request, 'game_version', None) or get_current_game_version()
    return HttpResponsePermanentRedirect(_url_pour_version(version))
