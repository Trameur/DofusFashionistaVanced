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
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.conf import settings
from django.utils import translation
from django.utils.translation import get_language

from chardata.util import set_response
from chardata import guides_content
from chardata.encyclopedia_view import _absolute_versioned_url
from fashionistapulp.game_versions import prefixed_reader_versions

from chardata.url_language import split_language_prefix
from chardata.url_language import (mark_varies_on_cookie,
                                   redirect_target_for_user)

# The bodies are written with plain site paths ("/setup/"). Read under a
# version, those paths land on Dofus 3: a Retro reader following "build it
# here" left Retro without being told. Every path a body links to exists under
# every prefix, so the fix is to carry the reader's version along.
# Le registre repond : les versions que le lecteur atteint sous un
# prefixe. Ecrite a la main, cette liste etait la quatrieme copie de la
# meme reponse, et rien ne les comparait.
VERSION_PREFIXES = tuple(prefixed_reader_versions())
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
    """Url of one guide, always built without a language prefix.

    A guide's slug already names its language -- /guides/tacle-et-fuite/ is the
    French page and says so -- so a prefix on top would be a second url for one
    page. Since the version includes moved under i18n_patterns, reverse() adds
    that prefix from whatever language happens to be active, which made every
    versioned guide declare a canonical no sitemap contains: 44 of the 256 urls
    in sitemap-pages.xml stopped being their own canonical.
    """
    with translation.override(settings.LANGUAGE_CODE):
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
    # Le canonique se lit dans l'URL, pas dans l'en-tete du navigateur.
    # `{% game_url %}` passait par reverse(), qui ajoute le prefixe de la
    # langue ACTIVE : servi a un lecteur francais, /guides/ se declarait
    # copie de /fr/guides/ tout en restant le x-default et le membre
    # anglais de son propre groupe hreflang. Une page ne peut pas etre les
    # deux, et un canonique qui change avec un en-tete n'est pas un
    # canonique. Les fiches de guides, elles, tiraient deja le leur de leur
    # slug : seul le carrefour suivait le navigateur.
    prefixe, _reste = split_language_prefix(request.path_info)
    canonical_url = _absolute_versioned_url(
        '/guides/', game_version, language=prefixe.lstrip('/'))
    return set_response(
        request,
        'chardata/guides.html',
        {'request': request,
         'user': request.user,
         'char_id': char_id,
         'canonical_url': canonical_url,
         'guides': guides_content.list_guides(language, game_version)})


def guide(request, slug, char_id=0):
    game_version = getattr(request, 'game_version', 'dofus3')

    # The slug names the language. Resolving it here is what lets a crawler --
    # which sends no Accept-Language -- reach anything but the English text.
    key, url_language = guides_content.resolve_slug(slug)
    if key is None:
        # An unknown slug may still be a guide key from before the localised
        # slugs existed; keep serving it rather than 404ing a live URL.
        key, url_language = slug, get_language() or 'en'
    if url_language != (get_language() or 'en'):
        translation.activate(url_language)

    data = guides_content.get_guide(key, url_language, game_version)
    if data is None:
        raise Http404("Unknown guide")

    # Version-specific guides (e.g. critical hits) are canonical at their own
    # system's URL; plain guides stay canonical at the global /guides/ URL.
    canonical_version = guides_content.guide_canonical_version(key, game_version)
    canonical_url = 'https://dofusfashionista.gg' + _guide_url(
        canonical_version, data['slug'])
    alternate_urls = {
        language: 'https://dofusfashionista.gg' + _guide_url(
            canonical_version, other_slug)
        for language, other_slug in data['alternates'].items()
    }

    redirect_to = redirect_target_for_user(request, url_language, alternate_urls)
    if redirect_to:
        return mark_varies_on_cookie(redirect(redirect_to))

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
         'alternate_urls': alternate_urls,
         'other_guides': [g for g in guides_content.list_guides(
                              url_language, game_version)
                          if g['key'] != key]})
