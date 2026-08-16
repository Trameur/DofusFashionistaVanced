# -*- coding: utf-8 -*-
"""Views for the Guides section (original editorial content).

Two pages: a hub listing every guide, and a single-guide page. Content comes
from chardata.guides_content (hand-written, per language); these views just
pick the right language slice and render it. Both are global (not version-
prefixed): the canonical URL is always /guides/... so versioned copies, if any
are ever linked, don't create duplicate content.
"""
import re

from django.http import Http404
from django.urls import reverse, NoReverseMatch
from django.utils.translation import get_language

from chardata.util import set_response
from chardata import guides_content

# The bodies are written with plain site paths ("/setup/"). Read under a
# version, those paths land on Dofus 3: a Retro reader following "build it
# here" left Retro without being told. Every path a body links to exists under
# every prefix, so the fix is to carry the reader's version along.
VERSION_PREFIXES = ('beta', 'dofus2', 'touch', 'retro')
_BODY_LINK = re.compile(r'href="(/[^"]*)"')


def add_version_prefix(html, game_version):
    if not html or game_version == 'dofus3' or game_version not in VERSION_PREFIXES:
        return html

    def prefixed(match):
        path = match.group(1)
        first = path.split('/', 2)[1] if path.count('/') > 1 else ''
        if first in VERSION_PREFIXES or first in ('static', 'media'):
            return match.group(0)
        return 'href="/%s%s"' % (game_version, path)

    return _BODY_LINK.sub(prefixed, html)


def _guide_url(version, slug):
    """Reverse the single-guide URL under a version's namespace (dofus3 = the
    unprefixed default)."""
    if version != 'dofus3':
        try:
            return reverse('%s:guide' % version, args=[slug])
        except NoReverseMatch:
            pass
    return reverse('guide', args=[slug])


# The guides run from 1600 to 4200 characters. At 3000 only two of the
# twenty-seven were ever cut; at 2400 with four sections, half of them are, and
# each half still holds a section the reader came for.
MIN_SPLIT_LENGTH = 2400
MIN_SPLIT_SECTIONS = 4


def split_body(body):
    """A guide in two halves, so a unit can stand between them.

    The break lands on the section heading nearest the middle, never inside a
    paragraph. A guide too short, or with too few sections to cut without
    stranding one, comes back whole and gets no unit in its text.
    """
    body = body or ''
    starts = [index for index in range(len(body))
              if body.startswith('<h2', index)]
    if len(body) < MIN_SPLIT_LENGTH or len(starts) < MIN_SPLIT_SECTIONS:
        return body, ''
    middle = len(body) // 2
    # The first heading opens the guide, the last closes it; cutting at either
    # would put the unit against the lead or against the foot.
    cut = min(starts[1:-1], key=lambda index: abs(index - middle))
    return body[:cut], body[cut:]


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
    body_top, body_rest = split_body(
        add_version_prefix(data.get('body'), game_version))
    return set_response(
        request,
        'chardata/guide.html',
        {'request': request,
         'user': request.user,
         'char_id': char_id,
         'guide': data,
         'guide_body_top': body_top,
         'guide_body_rest': body_rest,
         'canonical_url': canonical_url,
         'other_guides': [g for g in guides_content.list_guides(
                              language, game_version)
                          if g['slug'] != slug]})
