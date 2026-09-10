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

from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _

from chardata.coaching_view import create_build
from chardata.create_project_view import is_anon_cant_create
from chardata.dofusbook_import import ImportError_, read_build
from chardata.solution import set_minimal_solution
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from chardata.util import set_response
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES,
                                             TYPE_NAME_TO_SLOT_NUMBER)
from fashionistapulp.game_versions import get_game_version
from fashionistapulp.modelresult import ModelResultMinimal
from fashionistapulp.structure import (get_structure, get_current_game_version,
                                       set_current_game_version)

logger = logging.getLogger(__name__)


def _reasons():
    """One sentence per refusal the reader can actually hit."""
    return {
        'not_a_link': _('That is not a DofusBook build link.'),
        'short_link': _('Short d-bk.net links do not say which game the build '
                        'belongs to. Open the link and paste the full address.'),
        'not_found': _('DofusBook does not have a public build at that link.'),
        'refused': _('DofusBook refused the request.'),
        'unreachable': _('DofusBook could not be reached. Try again later.'),
        'unreadable': _('DofusBook answered something we could not read.'),
        'empty': _('That build came back with no items.'),
        'wrong_version': _('Those items do not exist in that version of the '
                           'game. Check the link.'),
    }


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
    """The page. GET shows the field, POST reads the link, confirm creates."""
    url = (request.POST.get('url') or '').strip()

    if request.method != 'POST' or not url:
        return set_response(request, 'chardata/dofusbook.html', {
            'url': '',
            'login_problem': is_anon_cant_create(request),
        })

    try:
        build = read_build(url)
    except ImportError_ as erreur:
        return set_response(request, 'chardata/dofusbook.html', {
            'url': url,
            'error': _reasons().get(erreur.reason, _reasons()['unreadable']),
            'login_problem': is_anon_cant_create(request),
        })

    char_class = request.POST.get('char_class') or ''
    if not request.POST.get('confirm') or char_class not in CHARACTER_CLASSES:
        return set_response(request, 'chardata/dofusbook.html', {
            'url': url,
            'confirm': True,
            'build': build,
            'version_label': get_game_version(build['game_version']).label,
            'pieces': _preview(build),
            'classes': _classes_for(build['game_version']),
            'login_problem': is_anon_cant_create(request),
        })

    char = create_build(request, char_class, build['level'] or 200, set(),
                        build['game_version'],
                        name=build['name'] or _('Imported build'))
    _place_items(char, build['item_ids'])
    logger.info('imported dofusbook build %s from %s into char %s',
                build['build_id'], build['source_host'], char.id)
    return HttpResponseRedirect(_solution_path(char))
