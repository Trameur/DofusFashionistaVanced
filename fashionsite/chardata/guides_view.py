# -*- coding: utf-8 -*-
"""Guides hub and guide pages."""
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
                                   redirect_target_for_user,
                                   SITE_URL)

# Guide bodies link plain paths ("/setup/"), add the reader's version prefix
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
    """Guide url without a language prefix, the slug names the language."""
    with translation.override(settings.LANGUAGE_CODE):
        if version != 'dofus3':
            try:
                return reverse('%s:guide' % version, args=[slug])
            except NoReverseMatch:
                pass
        return reverse('guide', args=[slug])


MIN_SPLIT_LENGTH = 2400
MIN_SPLIT_SECTIONS = 4


def split_body(body):
    """(top, rest) cut at the h2 nearest the middle, (body, '') if too short."""
    body = body or ''
    starts = [index for index in range(len(body))
              if body.startswith('<h2', index)]
    if len(body) < MIN_SPLIT_LENGTH or len(starts) < MIN_SPLIT_SECTIONS:
        return body, ''
    middle = len(body) // 2
    # Never at the first or last heading
    cut = min(starts[1:-1], key=lambda index: abs(index - middle))
    return body[:cut], body[cut:]


def guides(request, char_id=0):
    language = get_language() or 'en'
    game_version = getattr(request, 'game_version', 'dofus3')
    # Canonical from the URL prefix, not the active language
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

    # The slug names the language, crawlers send no Accept-Language
    key, url_language = guides_content.resolve_slug(slug)
    if key is None:
        # Old guide key from before the localised slugs
        key, url_language = slug, get_language() or 'en'
    if url_language != (get_language() or 'en'):
        translation.activate(url_language)

    data = guides_content.get_guide(key, url_language, game_version)
    if data is None:
        raise Http404("Unknown guide")

    # Version-specific guides are canonical under their own version
    canonical_version = guides_content.guide_canonical_version(key, game_version)
    canonical_url = SITE_URL + _guide_url(
        canonical_version, data['slug'])
    alternate_urls = {
        language: SITE_URL + _guide_url(
            canonical_version, other_slug)
        for language, other_slug in data['alternates'].items()
    }

    # The language redirect keeps the reader's version
    redirect_alternates = {
        language: SITE_URL + _guide_url(game_version, other_slug)
        for language, other_slug in data['alternates'].items()
    }
    redirect_to = redirect_target_for_user(request, url_language,
                                           redirect_alternates)
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
