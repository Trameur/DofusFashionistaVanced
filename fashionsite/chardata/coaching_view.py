# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Coaching / Quick Start flow for newcomers.

Three dropdowns (class, level, play style) → a fully configured project +
optimization, no scary wizard. Reuses `set_char_aspects` so the resulting
build is identical to what an expert would get through the normal flow.
"""

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
from fashionistapulp.dofus_constants import CHARACTER_CLASSES, STATS_NAMES


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
    """Return [(key, localized_name), ...] sorted by localized name,
    filtered for the current game version (e.g. no Forgelance on /dofus2/)."""
    items = [(key, str(name)) for key, name in LOCALIZED_CHARACTER_CLASSES.items()
             if key in CHARACTER_CLASSES]
    allowed = set(filter_classes_for_version([k for k, _ in items], game_version))
    items = [(k, n) for k, n in items if k in allowed]
    items.sort(key=lambda kv: kv[1])
    return items


def coaching(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    if request.method == 'POST':
        return _create_from_coaching(request, game_version)

    return set_response(request,
                        'chardata/coaching.html',
                        {'class_options': _locale_class_options(game_version),
                         'level_options': DEFAULT_LEVELS,
                         'play_styles': PLAY_STYLES,
                         'login_problem': is_anon_cant_create(request)})


def create_build(request, char_class, char_level, aspects, game_version, name=None):
    """Create a fully configured Char + base stats and return it.

    Shared by the Quick Start (coaching) flow and the natural-language build
    generator. `aspects` is a set of smart_build aspect keys."""
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
    # Retro shields only work in PvP, so a PvM preset forbids them by default;
    # the PvP preset (and every non-retro version) keeps them.
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

    for stat_name, _localized in STATS_NAMES:
        CharBaseStats.objects.create(char=char, stat=stat_name,
                                     scrolled_value=100, total_value=100)

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

    # char_class validation/fallback happens inside create_build; compute
    # aspects against the (possibly defaulted) class afterwards is fine since
    # _style_aspects tolerates any class.
    aspects = _style_aspects(style, char_class if char_class in CHARACTER_CLASSES else CHARACTER_CLASSES[0])
    char = create_build(request, char_class, char_level, aspects, game_version)

    return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))
