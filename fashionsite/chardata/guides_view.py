# -*- coding: utf-8 -*-
"""Views for the Guides section (original editorial content).

Two pages: a hub listing every guide, and a single-guide page. Content comes
from chardata.guides_content (hand-written, per language); these views just
pick the right language slice and render it. Both are global (not version-
prefixed): the canonical URL is always /guides/... so versioned copies, if any
are ever linked, don't create duplicate content.
"""
from django.http import Http404
from django.utils.translation import get_language

from chardata.util import set_response
from chardata import guides_content


def guides(request, char_id=0):
    language = get_language() or 'en'
    return set_response(
        request,
        'chardata/guides.html',
        {'request': request,
         'user': request.user,
         'char_id': char_id,
         'guides': guides_content.list_guides(language)})


def guide(request, slug, char_id=0):
    language = get_language() or 'en'
    data = guides_content.get_guide(slug, language)
    if data is None:
        raise Http404("Unknown guide")
    return set_response(
        request,
        'chardata/guide.html',
        {'request': request,
         'user': request.user,
         'char_id': char_id,
         'guide': data,
         'other_guides': [g for g in guides_content.list_guides(language)
                          if g['slug'] != slug]})
