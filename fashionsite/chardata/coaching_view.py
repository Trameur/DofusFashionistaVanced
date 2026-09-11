# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Coaching / Quick Start flow: class + level + play style to a configured project."""

import pickle

from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _, gettext_lazy

from chardata.create_project_view import is_anon_cant_create
from chardata.lock_forbid import get_default_exclusions, set_exclusions_list_and_check_inclusions
from chardata.anon_projects import remember_anon_char
from chardata.models import Char, CharBaseStats
from chardata.options import set_options
from chardata.smart_build import set_char_aspects
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from chardata.util import set_response, version_reverse
from chardata.version_compat import class_exists_in_version, filter_classes_for_version
from fashionistapulp.dofus_constants import (CHARACTER_CLASSES, STATS_NAMES,
                                             max_scroll_for_version)


CLASS_DEFAULT_ELEMENT = {
    'Iop': 'str',
    'Cra': 'agi',
    'Sram': 'agi',
    'Xelor': 'cha',
    'Eniripsa': 'int',
    'Feca': 'int',
    'Sacrier': 'agi',
    'Sadida': 'cha',
    'Enutrof': 'cha',
    'Osamodas': 'cha',
    'Ecaflip': 'cha',
    'Pandawa': 'str',
    'Eliotrope': 'cha',
    'Huppermage': 'int',
    'Ouginak': 'agi',
    'Masqueraider': 'agi',
    'Foggernaut': 'int',
    'Rogue': 'agi',
    'Forgelance': 'str',
}

PLAY_STYLES = [
    ('solo_pvm', gettext_lazy('Solo PvM: focus damage')),
    ('group_pvm', gettext_lazy('Group PvM: tanky / support')),
    ('pvp', gettext_lazy('PvP: critical hits')),
    ('farm', gettext_lazy('Farm / Level-up: Prospecting & Wisdom')),
]

DEFAULT_LEVELS = [20, 50, 100, 150, 180, 200]

STYLE_BASE_ASPECTS = {
    'solo_pvm': {'glasscannon'},
    'group_pvm': {'vit', 'res'},
    'pvp': {'pvp', 'crit'},
    'farm': {'wis', 'pp'},
}


def _style_aspects(style, char_class):
    aspects = set(STYLE_BASE_ASPECTS.get(style, set()))
    if style != 'farm':  # farm builds are element-agnostic
        element = CLASS_DEFAULT_ELEMENT.get(char_class, 'str')
        aspects.add(element)
    return aspects


def _locale_class_options(game_version):
    """[(key, localized_name)] sorted by name, filtered for the game version
    (no Forgelance on /dofus2/)."""
    items = [(key, str(name)) for key, name in LOCALIZED_CHARACTER_CLASSES.items()
             if key in CHARACTER_CLASSES]
    allowed = set(filter_classes_for_version([k for k, _ in items], game_version))
    items = [(k, n) for k, n in items if k in allowed]
    items.sort(key=lambda kv: kv[1])
    return items


def included_item_for(game_version, value, language=None):
    """The item a fiche asked the quick start to build around, or None.

    `value` is the `item` parameter: the item's internal id (the one the
    inclusions store), as the fiche wrote it in its link. Anything that is
    not an equipment item of THIS game version is None: an id typed by
    hand, an id from another version (they do not agree), a removed item.
    The slot is the first one of the item's type (a ring goes to ring1).
    """
    from django.utils import translation
    from fashionistapulp.dofus_constants import SLOT_NAME_TO_TYPE
    from fashionistapulp.structure import get_structure
    try:
        item_id = int(value)
    except (TypeError, ValueError):
        return None
    structure = get_structure(game_version)
    item = structure.get_item_by_id(item_id)
    if item is None or getattr(item, 'removed', False):
        return None
    type_name = structure.get_type_name_by_id(item.type)
    slot = next((s for s, t in SLOT_NAME_TO_TYPE.items() if t == type_name),
                None)
    if slot is None:
        return None
    language = language or (translation.get_language() or 'en')[:2]
    return {'id': item.id,
            'name': structure.get_item_name_in_language(item, language) or item.name,
            'level': item.level,
            'type_name': type_name,
            'slot': slot}


def included_set_for(game_version, value, language=None):
    """The panoply a set page asked the quick start to build around, or None.

    Every piece of the set that is an equipment item of THIS game version
    takes the first free slot of its type (two rings go to ring1 and ring2).
    The level is the highest piece's: the lowest character that can wear
    the whole set. None for anything that is not a set id of this version,
    or a set with no wearable piece.
    """
    from django.utils import translation
    from fashionistapulp.dofus_constants import SLOT_NAME_TO_TYPE
    from fashionistapulp.structure import get_structure
    try:
        set_id = int(value)
    except (TypeError, ValueError):
        return None
    structure = get_structure(game_version)
    item_set = structure.get_set_by_id(set_id)
    if item_set is None:
        return None
    language = language or (translation.get_language() or 'en')[:2]
    taken = set()
    pieces = []
    for item_id in getattr(item_set, 'items', None) or []:
        item = structure.get_item_by_id(item_id)
        if item is None or getattr(item, 'removed', False):
            continue
        type_name = structure.get_type_name_by_id(item.type)
        slot = next((s for s, t in SLOT_NAME_TO_TYPE.items()
                     if t == type_name and s not in taken), None)
        if slot is None:
            continue
        taken.add(slot)
        pieces.append({'id': item.id,
                       'name': structure.get_item_name_in_language(item, language) or item.name,
                       'level': item.level,
                       'slot': slot})
    if not pieces:
        return None
    names = getattr(item_set, 'localized_names', None) or {}
    return {'id': item_set.id,
            'name': names.get(language) or names.get('en') or item_set.name,
            'level': max(piece['level'] for piece in pieces),
            'count': len(pieces),
            'pieces': pieces}


def level_options_for(included_level):
    """(levels offered, level selected) for the quick start form.

    Without an item: the defaults, 200 selected. With one: the item's own
    level, the lowest that can wear it, then the defaults above it; 200
    stays selected when it is offered, else that lowest level (no version
    carries an item above 200 today, but the arithmetic does not depend on
    it).
    """
    if included_level is None:
        return DEFAULT_LEVELS, 200
    levels = [lvl for lvl in DEFAULT_LEVELS if lvl >= included_level]
    if included_level not in levels:
        levels = sorted(levels + [included_level])
    return levels, (200 if 200 in levels else levels[0])


def coaching(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    if request.method == 'POST':
        return _create_from_coaching(request, game_version)

    # A fiche of the encyclopedia sends its item along: the build will keep
    # it, so the levels below the item's are not offered.
    included = included_item_for(game_version, request.GET.get('item'))
    # A set page sends its panoply the same way; one or the other, the
    # item first when both are given.
    included_set = (None if included is not None
                    else included_set_for(game_version, request.GET.get('set')))
    floor = None
    if included is not None:
        floor = included['level']
    elif included_set is not None:
        floor = included_set['level']
    level_options, selected_level = level_options_for(floor)

    return set_response(request,
                        'chardata/coaching.html',
                        {'class_options': _locale_class_options(game_version),
                         'level_options': level_options,
                         'selected_level': selected_level,
                         'included_item': included,
                         'included_set': included_set,
                         'play_styles': PLAY_STYLES,
                         'login_problem': is_anon_cant_create(request)})


def create_build(request, char_class, char_level, aspects, game_version, name=None):
    """Create a fully configured Char + base stats. `aspects` is a set of
    smart_build aspect keys."""
    if (char_class not in CHARACTER_CLASSES
            or not class_exists_in_version(char_class, game_version)):
        fallback = filter_classes_for_version(CHARACTER_CLASSES, game_version)
        char_class = fallback[0] if fallback else CHARACTER_CLASSES[0]

    char_level = max(1, min(int(char_level), 230))

    char = Char()
    if not request.user.is_anonymous:
        char.owner = request.user
    char.name = name or (_('Quick Start %(cls)s lvl %(lvl)s')
                         % {'cls': char_class, 'lvl': char_level})
    char.char_name = char_class
    char.char_class = char_class
    char.char_build = ''
    char.level = char_level
    char.minimum_stats = pickle.dumps({})
    char.stats_weight = pickle.dumps({})
    char.options = pickle.dumps({})
    char.link_shared = False
    char.game_version = game_version

    set_char_aspects(char, aspects, True, False)
    set_exclusions_list_and_check_inclusions(char, get_default_exclusions(char))
    # Retro 1.29 has no AP/MP/range exotismes, Turquoise Dofus or prysmaradites.
    exos = game_version != 'retro'
    # Retro shields only work in PvP.
    shields = game_version != 'retro' or 'pvp' in aspects
    set_options(char, {'ap_exo': exos and char_level >= 200,
                       'mp_exo': exos and char_level >= 200,
                       'turq_dofus': exos and char_level >= 199,
                       'dragoturkey': True,
                       'rhineetle': True,
                       'seemyool': True,
                       'prysmaradite': exos and char_level >= 200,
                       'shields': shields})
    char.save()

    full_scroll = max_scroll_for_version(char.game_version)
    for stat_name, _localized in STATS_NAMES:
        CharBaseStats.objects.create(char=char, stat=stat_name,
                                     scrolled_value=full_scroll,
                                     total_value=full_scroll)

    if request.user.is_anonymous:
        remember_anon_char(request, char)

    return char


def _create_from_coaching(request, game_version):
    char_class = request.POST.get('char_class', '')

    try:
        char_level = int(request.POST.get('char_level', 200))
    except (TypeError, ValueError):
        char_level = 200

    style = request.POST.get('play_style', 'solo_pvm')
    if style not in dict(PLAY_STYLES):
        style = 'solo_pvm'

    aspects = _style_aspects(style, char_class if char_class in CHARACTER_CLASSES else CHARACTER_CLASSES[0])
    char = create_build(request, char_class, char_level, aspects, game_version)

    # The item the fiche asked for, locked into its slot. After create_build
    # on purpose: that call seeds the default exclusions, and an item the
    # reader explicitly asked for must win over a default that hides it,
    # which is what set_inclusions_dict_and_check_exclusions does. An item
    # above the character's level cannot be worn, so it is not locked, and
    # the form does not offer such a level anyway.
    included = included_item_for(game_version, request.POST.get('item'))
    locked = {}
    if included is not None and included['level'] <= char.level:
        locked[included['slot']] = included['id']
    elif included is None:
        # A whole panoply: every piece the character can wear, each in its
        # own slot. The form starts its levels at the highest piece, so
        # normally all of them; a level posted by hand below that keeps
        # only the pieces that fit.
        included_set = included_set_for(game_version, request.POST.get('set'))
        if included_set is not None:
            for piece in included_set['pieces']:
                if piece['level'] <= char.level:
                    locked[piece['slot']] = piece['id']
    if locked:
        from chardata.lock_forbid import set_inclusions_dict_and_check_exclusions
        set_inclusions_dict_and_check_exclusions(char, locked)

    return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))
