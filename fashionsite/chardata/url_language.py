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

"""Deriving the page language from the URL instead of the request header.

Encyclopedia pages already have one slug per language -- /44-twiggy-sword/,
/44-epee-de-boisaille/, /44-espada-de-maderucha/ all name the same item. Until
now the language came from Accept-Language, so all three served whichever
language the visitor's browser asked for, and each declared a canonical
pointing at whatever slug that language produced.

Googlebot sends no Accept-Language. It therefore fetched every localised URL,
received English, and read a canonical naming the English URL -- every French,
Spanish, Portuguese and German page in the sitemap told Google it was a
duplicate of the English one. Google obeys canonicals, which is why ~42 700
submitted URLs produce so few ranked queries.

The slug already carries the language. Reading it from there makes each URL
serve one language deterministically, to crawlers and humans alike, with no
change to the URL space and therefore no risk to AJAX endpoints, OAuth
callbacks or the service worker.
"""

from django.conf import settings
from django.utils import translation

from fashionistapulp.translation import SUPPORTED_LANGUAGES

# Order used to break ties when several languages slugify to the same string.
# That is not a rare case: proper nouns are frequently left untranslated, so a
# monster called Crocodyl is Crocodyl in five languages and its slug names all
# of them.
#
# English first, because an ambiguous slug has to keep answering exactly as it
# did before this change: English is the historical default and the URL that is
# already indexed. Putting it last -- as this list first did -- silently served
# Portuguese on every such page.
_TIE_BREAK_ORDER = ['en', 'fr', 'es', 'pt', 'de']

# Query flag letting a visitor look at a language other than their own without
# being bounced back. Without it, a user whose profile says French could never
# open a Spanish link on purpose.
KEEP_LANGUAGE_PARAM = 'keeplang'


def language_from_slug(candidate_names, slug, normalise):
    """Language whose localised slug matches the one in the URL.

    `candidate_names` maps a language code to the item name in that language.
    Returns None when the slug matches nothing, in which case the caller must
    keep the language it already had -- an unknown slug is not a reason to
    change behaviour.
    """
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


def build_alternate_urls(url_builder, candidate_names, base_url):
    """Absolute URL of the page in each language, for hreflang.

    `url_builder` is called once per language with that language active, so
    helpers deriving a localised path segment from get_language() produce the
    right URL without needing to be changed.
    """
    alternates = {}
    for lang in SUPPORTED_LANGUAGES:
        name = candidate_names.get(lang)
        if not name:
            continue
        with translation.override(lang):
            path = url_builder(name)
        if path:
            alternates[lang] = base_url + path
    return alternates


def explicit_user_language(request):
    """Language the signed-in visitor chose for their account, or None.

    Deliberately restricted to authenticated visitors with a stored choice.
    Anonymous visitors -- which every crawler is -- must never be redirected:
    that is what keeps each URL deterministic for indexing.

    The session cookie is checked before request.user on purpose. Touching
    request.user marks the session as accessed, which makes Django add
    Vary: Cookie to the response and stops the CDN caching a page that is in
    fact identical for everyone. Requests carrying no session cookie cannot be
    signed in, so there is nothing to look up.
    """
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
    """Path to send a signed-in visitor to, or None to serve the page as is.

    Applied only to GET: redirecting a POST would drop the body. Skipped when
    the visitor asked to stay, and when the target URL is the current one --
    which also makes a redirect loop impossible.
    """
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
    return target


class RestoreLanguageMiddleware(object):
    """Puts the thread's language back the way it was after each request.

    A view that reads its language from the URL calls translation.activate(),
    which changes state for the whole thread and outlives the request: nothing
    resets it, and LocaleMiddleware activates a language per request without
    ever deactivating one. Anything running afterwards without setting a
    language of its own -- a management command, a template rendered outside a
    request, the next test in a suite -- would inherit a language it never
    asked for, and silently render in it.

    Must sit first in MIDDLEWARE so it wraps everything, including
    LocaleMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        previous = translation.get_language()
        try:
            return self.get_response(request)
        finally:
            translation.activate(previous)


def mark_varies_on_cookie(response):
    """Tell caches the response depends on who is signed in.

    Without this a CDN can serve one visitor's language redirect to everyone,
    crawlers included -- which would undo the whole point of deriving the
    language from the URL.
    """
    existing = response.get('Vary', '')
    parts = [part.strip() for part in existing.split(',') if part.strip()]
    if not any(part.lower() == 'cookie' for part in parts):
        parts.append('Cookie')
        response['Vary'] = ', '.join(parts)
    return response
