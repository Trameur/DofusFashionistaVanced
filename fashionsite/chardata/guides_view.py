# -*- coding: utf-8 -*-
"""Views for the Guides section (original editorial content).

Two pages: a hub listing every guide, and a single-guide page. Content comes
from chardata.guides_content (hand-written, per language); these views just
pick the right language slice and render it. Both are global (not version-
prefixed): the canonical URL is always /guides/... so versioned copies, if any
are ever linked, don't create duplicate content.
"""
from django.http import Http404
from django.urls import reverse, NoReverseMatch
from django.utils.translation import get_language

from chardata.util import set_response
from chardata import guides_content


def _guide_url(version, slug):
    """Reverse the single-guide URL under a version's namespace (dofus3 = the
    unprefixed default)."""
    if version != 'dofus3':
        try:
            return reverse('%s:guide' % version, args=[slug])
        except NoReverseMatch:
            pass
    return reverse('guide', args=[slug])


def guides(request, char_id=0):
    language = get_language() or 'en'
    game_version = getattr(request, 'game_version', 'dofus3')
    return set_response(
        request,
        'chardata/guides.html',
        {'request': request,
         'user': request.user,
         'char_id': char_id,
         'guides': guides_content.list_guides(language, game_version)})


def guide(request, slug, char_id=0):
    language = get_language() or 'en'
    game_version = getattr(request, 'game_version', 'dofus3')
    data = guides_content.get_guide(slug, language, game_version)
    if data is None:
        raise Http404("Unknown guide")
    # Version-specific guides (e.g. critical hits) are canonical at their own
    # system's URL; plain guides stay canonical at the global /guides/ URL.
    canonical_version = guides_content.guide_canonical_version(slug, game_version)
    canonical_url = 'https://dofusfashionista.gg' + _guide_url(
        canonical_version, slug)
    return set_response(
        request,
        'chardata/guide.html',
        {'request': request,
         'user': request.user,
         'char_id': char_id,
         'guide': data,
         'canonical_url': canonical_url,
         'other_guides': [g for g in guides_content.list_guides(
                              language, game_version)
                          if g['slug'] != slug]})
