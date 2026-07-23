# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Natural-language build generator (no LLM).

A single text box: type "Iop 200 terre PvM" and get a ready build. Parsing is
keyword-based (see nl_parser), works in FR/EN/ES/PT/DE, offline and free, our
answer to Dafous' conversational generator, backed by the LP solver.
"""

from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _, get_language

from chardata.coaching_view import create_build
from chardata.create_project_view import is_anon_cant_create
from chardata.nl_parser import parse_build_request
from chardata.smart_build import ASPECT_TO_NAME, ALL_ASPECTS_LIST
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from chardata.util import set_response, version_reverse


# Example chips shown under the box, in the active UI language so they read like
# what a player of that language would actually type (the parser understands all
# five). Clicking one fills the box, so every example must itself parse to a
# class. Keywords are the ones nl_parser recognizes per language.
EXAMPLE_QUERIES_BY_LANG = {
    'en': ['Iop 200 earth PvM', 'Cra agi pvp level 150', 'Eniripsa fire healer',
           'Enutrof farm drop 100'],
    'fr': ['Iop 200 terre PvM', 'Cra agi pvp niveau 150', 'Eniripsa feu soigneur',
           'Enutrof farm drop 100'],
    'es': ['Iop 200 tierra PvM', 'Cra agi pvp nivel 150', 'Eniripsa fuego sanador',
           'Enutrof farm drop 100'],
    'pt': ['Iop 200 terra PvM', 'Cra agi pvp nível 150', 'Eniripsa fogo cura',
           'Enutrof farm drop 100'],
    'de': ['Iop 200 Erde PvM', 'Crâ Flinkheit PvP Stufe 150', 'Eniripsa Feuer Heiler',
           'Enutrof farmen Stufe 100'],
}


def _example_queries():
    lang = (get_language() or 'en').split('-')[0]
    return EXAMPLE_QUERIES_BY_LANG.get(lang, EXAMPLE_QUERIES_BY_LANG['en'])


def _style_name(style):
    # Short localized style label for the auto-generated build name; the raw key
    # ("group_pvm") would otherwise leak into the name. Distinct from
    # coaching_view's verbose dropdown labels, which are too long here and omit
    # "farm".
    return {
        'solo_pvm': _('solo PvM'),
        'group_pvm': _('group PvM'),
        'pvp': _('PvP'),
        'farm': _('farm'),
    }.get(style, style.replace('_', ' '))


def _aspect_labels(aspects):
    ordered = sorted(aspects, key=lambda a: ALL_ASPECTS_LIST.index(a)
                     if a in ALL_ASPECTS_LIST else len(ALL_ASPECTS_LIST))
    return [str(ASPECT_TO_NAME.get(a, a)) for a in ordered]


def _interpretation(parsed, confirmed):
    """Human-readable echo of what the parser understood, so a misread is
    visible before a build is created. When the class is missing we only show
    the bits we actually recognized (no defaulted aspects)."""
    if confirmed:
        cls = parsed['char_class']
        return {
            'class_name': str(LOCALIZED_CHARACTER_CLASSES.get(cls, cls)),
            'level': parsed['level'],
            'aspect_labels': _aspect_labels(parsed['aspects']),
        }
    return {
        'class_name': None,
        'level': parsed['level'] if parsed['matched_level'] else None,
        'aspect_labels': _aspect_labels(parsed['extra_aspects']) if parsed['extra_aspects'] else [],
    }


def smart_build(request):
    game_version = getattr(request, 'game_version', 'dofus3')

    if request.method == 'POST':
        query = (request.POST.get('q') or '').strip()
        parsed = parse_build_request(query)

        if not parsed['matched_class']:
            # Can't build without a class, so re-render with an error and whatever
            # else we did recognize, so the user can see what to add.
            return set_response(request, 'chardata/smart_build.html', {
                'query': query,
                'error': _("Tell us which class, e.g. \"Iop 200 earth PvM\"."),
                'interpretation': _interpretation(parsed, confirmed=False),
                'examples': _example_queries(),
                'login_problem': is_anon_cant_create(request),
            })

        if not request.POST.get('confirm'):
            # Echo the interpretation and let the user confirm or edit before we
            # build, keeps a misread from silently producing the wrong set.
            return set_response(request, 'chardata/smart_build.html', {
                'query': query,
                'interpretation': _interpretation(parsed, confirmed=True),
                'confirm': True,
                'examples': _example_queries(),
                'login_problem': is_anon_cant_create(request),
            })

        name = _('%(cls)s %(style)s lvl %(lvl)s') % {
            'cls': parsed['char_class'],
            'style': _style_name(parsed['style']),
            'lvl': parsed['level'],
        }
        char = create_build(request, parsed['char_class'], parsed['level'],
                            parsed['aspects'], game_version, name=name)
        return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))

    return set_response(request, 'chardata/smart_build.html', {
        'query': '',
        'examples': _example_queries(),
        'login_problem': is_anon_cant_create(request),
    })
