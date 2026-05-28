# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Natural-language build generator (no LLM).

A single text box: type "Iop 200 terre PvM" and get a ready build. Parsing is
keyword-based (see nl_parser), works in FR/EN/ES/PT, offline and free — our
answer to Dafous' conversational generator, backed by the LP solver.
"""

from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _

from chardata.coaching_view import create_build
from chardata.create_project_view import is_anon_cant_create
from chardata.nl_parser import parse_build_request
from chardata.util import set_response, version_reverse
from fashionistapulp.dofus_constants import CHARACTER_CLASSES


EXAMPLE_QUERIES = [
    'Iop 200 terre PvM',
    'Cra agi pvp niveau 150',
    'Eniripsa feu soigneur',
    'Enutrof farm drop 100',
]


def smart_build(request):
    game_version = getattr(request, 'game_version', 'dofus3')

    if request.method == 'POST':
        query = (request.POST.get('q') or '').strip()
        parsed = parse_build_request(query)

        if not parsed['matched_class']:
            # Can't build without a class — re-render with an error + parsed hints.
            return set_response(request, 'chardata/smart_build.html', {
                'query': query,
                'error': _("Tell us which class — e.g. \"Iop 200 earth PvM\"."),
                'examples': EXAMPLE_QUERIES,
                'login_problem': is_anon_cant_create(request),
            })

        name = _('%(cls)s %(style)s lvl %(lvl)s') % {
            'cls': parsed['char_class'],
            'style': parsed['style'].replace('_', ' '),
            'lvl': parsed['level'],
        }
        char = create_build(request, parsed['char_class'], parsed['level'],
                            parsed['aspects'], game_version, name=name)
        return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))

    return set_response(request, 'chardata/smart_build.html', {
        'query': '',
        'examples': EXAMPLE_QUERIES,
        'login_problem': is_anon_cant_create(request),
    })
