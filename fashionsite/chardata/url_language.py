# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Page language from the URL slug or prefix instead of Accept-Language."""

import re

from django.conf import settings
from django.http import HttpResponsePermanentRedirect
from django.middleware.locale import LocaleMiddleware
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme

from fashionistapulp.translation import SUPPORTED_LANGUAGES

# Several languages can share a slug (untranslated proper nouns): English wins
_TIE_BREAK_ORDER = ['en', 'fr', 'es', 'pt', 'de']

# A variant row named "Belteen (#1)" slugifies to "belteen-1"
_VARIANT_NUMBER = re.compile(r'-\d+$')

# Query flag to open another language without being redirected back
KEEP_LANGUAGE_PARAM = 'keeplang'


def language_from_slug(candidate_names, slug, normalise):
    """Language whose slug matches the URL one, or None if nothing matches."""
    target = normalise(slug)
    if not target:
        return None

    matches = [lang for lang, name in candidate_names.items()
               if name and normalise(name) == target]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    for lang in _TIE_BREAK_ORDER:
        if lang in matches:
            return lang
    return matches[0]


def language_from_stale_slug(slug, normalise, *candidate_names):
    """Language of a current or outdated slug, or None if none matches."""
    current = normalise(slug or '')
    forms = [current]
    without_number = _VARIANT_NUMBER.sub('', current)
    if without_number and without_number != current:
        forms.append(without_number)
    for form in forms:
        for names in candidate_names:
            language = language_from_slug(names, form, normalise)
            if language is not None:
                return language
    return None


def redirect_to_own_address(request, build_path, language, guessed_language):
    """301 to the page's own address in this game version, or None if already there."""
    if request.method not in ('GET', 'HEAD'):
        return None
    with translation.override(language):
        target = build_path()
    if not target or target == request.path:
        return None
    query = request.META.get('QUERY_STRING', '')
    if query:
        target = '%s?%s' % (target, query)
    if not url_has_allowed_host_and_scheme(target, allowed_hosts=None):
        return None
    response = HttpResponsePermanentRedirect(target)
    if guessed_language:
        mark_varies_on_cookie(response)
    return response


def address_serves_language(candidate_names, language, normalise):
    """True when the url built from these names is served in `language`."""
    if language == 'en':
        return True
    name = candidate_names.get(language)
    if not name:
        return False
    return language_from_slug(candidate_names, normalise(name),
                              normalise) == language


def build_alternate_urls(url_builder, candidate_names, base_url, normalise):
    """Absolute URL of the page in each language, for hreflang."""
    alternates = {}
    for lang in SUPPORTED_LANGUAGES:
        name = candidate_names.get(lang)
        if not name:
            continue
        if not address_serves_language(candidate_names, lang, normalise):
            continue
        with translation.override(lang):
            path = url_builder(name)
        if path:
            alternates[lang] = base_url + path
    return alternates


def explicit_user_language(request):
    """Language the signed-in visitor chose for their account, or None."""
    # Touching request.user adds Vary: Cookie, check the cookie first
    if settings.SESSION_COOKIE_NAME not in request.COOKIES:
        return None

    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None

    try:
        from chardata.models import UserAlias
        alias = UserAlias.objects.filter(user=user).only('language').first()
    except Exception:
        return None

    if alias is None or not alias.language:
        return None

    lang = alias.language.split('-')[0]
    return lang if lang in SUPPORTED_LANGUAGES else None


def redirect_target_for_user(request, url_language, alternates):
    """Path to send a signed-in visitor to, or None to serve the page as is."""
    if request.method != 'GET':
        return None
    if request.GET.get(KEEP_LANGUAGE_PARAM):
        return None

    wanted = explicit_user_language(request)
    if wanted is None or wanted == url_language:
        return None

    target = alternates.get(wanted)
    if not target or target.endswith(request.path):
        return None
    return site_relative(target)


# Not in game_urls: only Dofus 3 has a most-used page
_ALSO_PUBLISHED_ONCE_PER_LANGUAGE = frozenset({'encyclopedia_most_used'})

_prefixed_page_names = None


def prefixed_page_names():
    """Url names of the pages that exist once per language, under a prefix."""
    global _prefixed_page_names
    if _prefixed_page_names is None:
        # Local import: game_urls imports the views, which import this module
        from chardata.game_urls import routes_published_once_per_language
        _prefixed_page_names = frozenset(
            {entry.name for entry in routes_published_once_per_language()
             if entry.name} | _ALSO_PUBLISHED_ONCE_PER_LANGUAGE)
    return _prefixed_page_names


SITE_URL = 'https://dofusfashionista.gg'


def site_relative(url):
    """One of our own absolute urls reduced to a path, anything else untouched."""
    if url.startswith(SITE_URL):
        return url[len(SITE_URL):] or '/'
    return url


def split_language_prefix(path):
    """(prefix, rest): ('/es', '/guides/') for '/es/guides/', ('', path) if none."""
    parts = path.lstrip('/').split('/', 1)
    codes = {code for code, _name in settings.LANGUAGES}
    if parts and parts[0] in codes:
        return '/' + parts[0], '/' + (parts[1] if len(parts) > 1 else '')
    return '', path


def strip_language_prefix(path):
    """The path without its language prefix, if it has one."""
    return split_language_prefix(path)[1]


def prefixed_page_alternates(request):
    """{language: absolute url} for a language-prefixed page, else {}."""
    match = getattr(request, 'resolver_match', None)
    if match is None or match.url_name not in prefixed_page_names():
        return {}

    path = strip_language_prefix(request.path)
    alternates = {}
    for code, _name in settings.LANGUAGES:
        prefix = '' if code == settings.LANGUAGE_CODE else '/%s' % code
        alternates[code] = '%s%s%s' % (SITE_URL, prefix, path)
    return alternates


def canonical_the_page_will_render(request, params):
    """Canonical url as base.html will print it."""
    # canonical_url is absolute, canonical_path relative, none means request.path
    if params.get('canonical_url'):
        return params['canonical_url']
    if params.get('canonical_path'):
        return SITE_URL + params['canonical_path']
    return SITE_URL + request.path


def hreflang_alternates(request, canonical_url):
    """Alternates of a prefixed page, or {} when they disagree with its canonical."""
    alternates = prefixed_page_alternates(request)
    if not alternates:
        return alternates
    if not canonical_url:
        return alternates

    # Google drops a group without the canonical in it (e.g. ?page=N lists)
    prefix, _rest = split_language_prefix(request.path)
    language = prefix.lstrip('/') or settings.LANGUAGE_CODE
    if alternates.get(language) != canonical_url:
        return {}
    return alternates


class PrefixOptionalLocaleMiddleware(LocaleMiddleware):
    """Negotiates the language on unprefixed urls (Django pins LANGUAGE_CODE)."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        # i18n_patterns needs the default language active while resolving
        if translation.get_language_from_path(request.path_info):
            return None

        language = translation.get_language_from_request(
            request, check_path=False)
        if language and language != translation.get_language():
            translation.activate(language)
            request.LANGUAGE_CODE = translation.get_language()
        return None


def negotiate_language_for_unmatched_path(request):
    """Same as PrefixOptionalLocaleMiddleware, for a 404 (no process_view)."""
    if translation.get_language_from_path(request.path_info):
        return
    language = translation.get_language_from_request(request, check_path=False)
    if language and language != translation.get_language():
        translation.activate(language)
        request.LANGUAGE_CODE = translation.get_language()


class RestoreLanguageMiddleware(object):
    """Restores the thread's language after each request. First in MIDDLEWARE."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        previous = translation.get_language()
        try:
            return self.get_response(request)
        finally:
            translation.activate(previous)


def mark_varies_on_cookie(response):
    """Tell caches the response depends on who is signed in."""
    existing = response.get('Vary', '')
    parts = [part.strip() for part in existing.split(',') if part.strip()]
    if not any(part.lower() == 'cookie' for part in parts):
        parts.append('Cookie')
        response['Vary'] = ', '.join(parts)
    return response
