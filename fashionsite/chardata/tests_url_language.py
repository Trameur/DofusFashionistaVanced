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

"""The page language comes from the URL slug, not from Accept-Language.

The property that matters for indexing is negative and easy to break silently:
an anonymous request must never be redirected and must never depend on a
request header. Every crawler is anonymous and sends no Accept-Language, so any
regression here puts the site back to serving English everywhere and declaring
every localised URL a duplicate.
"""

import re
import unicodedata

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from chardata.url_language import (KEEP_LANGUAGE_PARAM, build_alternate_urls,
                                   explicit_user_language, language_from_slug,
                                   mark_varies_on_cookie,
                                   redirect_target_for_user)

BASE = 'https://dofusfashionista.gg'

# The real item 44, in the five supported languages.
TWIGGY_SWORD = {
    'en': 'Twiggy Sword',
    'fr': 'Epee de Boisaille',
    'es': 'Espada de maderucha',
    'pt': 'Espada de Galhinho',
    'de': 'Zweigschwert',
}


def normalise(value):
    """Mirrors chardata.encyclopedia_view._normalized_slug closely enough."""
    if not value:
        return ''
    text = unicodedata.normalize('NFKD', value.lower())
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')


class LanguageFromSlugTest(TestCase):

    def test_each_localised_slug_selects_its_own_language(self):
        for lang, name in TWIGGY_SWORD.items():
            self.assertEqual(
                language_from_slug(TWIGGY_SWORD, normalise(name), normalise),
                lang,
                '%s should resolve to %s' % (name, lang))

    def test_accents_and_case_do_not_matter(self):
        self.assertEqual(
            language_from_slug(TWIGGY_SWORD, 'epee-de-boisaille', normalise),
            'fr')

    def test_unknown_slug_returns_none_so_the_caller_keeps_its_language(self):
        # A stale or hand-edited slug must not silently switch the page.
        self.assertIsNone(
            language_from_slug(TWIGGY_SWORD, 'not-a-real-item', normalise))

    def test_empty_slug_returns_none(self):
        self.assertIsNone(language_from_slug(TWIGGY_SWORD, '', normalise))
        self.assertIsNone(language_from_slug(TWIGGY_SWORD, None, normalise))

    def test_identical_names_resolve_deterministically(self):
        # Item names are often the same in English and German. Whatever we
        # pick, it must be the same on every request: a canonical that moves
        # between requests is what caused the original problem.
        names = {'en': 'Gelano', 'de': 'Gelano', 'fr': 'Gelano'}
        first = language_from_slug(names, 'gelano', normalise)
        self.assertEqual(first, language_from_slug(names, 'gelano', normalise))
        self.assertIn(first, names)

    def test_missing_translation_is_skipped(self):
        names = dict(TWIGGY_SWORD, pt=None)
        self.assertEqual(
            language_from_slug(names, 'twiggy-sword', normalise), 'en')


class AlternateUrlsTest(TestCase):

    def _builder(self, name):
        return '/encyclopedia/item/equipment/44-%s/' % normalise(name)

    def test_one_url_per_language(self):
        alternates = build_alternate_urls(self._builder, TWIGGY_SWORD, BASE)
        self.assertEqual(sorted(alternates), ['de', 'en', 'es', 'fr', 'pt'])

    def test_urls_are_absolute_and_localised(self):
        alternates = build_alternate_urls(self._builder, TWIGGY_SWORD, BASE)
        self.assertEqual(
            alternates['fr'],
            BASE + '/encyclopedia/item/equipment/44-epee-de-boisaille/')
        self.assertEqual(
            alternates['es'],
            BASE + '/encyclopedia/item/equipment/44-espada-de-maderucha/')

    def test_every_alternate_is_distinct(self):
        # Two languages pointing at one URL would tell Google they are the
        # same page, which is the bug this whole change exists to remove.
        alternates = build_alternate_urls(self._builder, TWIGGY_SWORD, BASE)
        self.assertEqual(len(set(alternates.values())), len(alternates))

    def test_language_without_a_name_is_omitted(self):
        alternates = build_alternate_urls(
            self._builder, dict(TWIGGY_SWORD, de=None), BASE)
        self.assertNotIn('de', alternates)

    def test_builder_returning_nothing_is_omitted(self):
        alternates = build_alternate_urls(lambda name: None, TWIGGY_SWORD, BASE)
        self.assertEqual(alternates, {})


class RedirectTest(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.alternates = {
            lang: BASE + '/encyclopedia/item/equipment/44-%s/' % normalise(name)
            for lang, name in TWIGGY_SWORD.items()
        }

    def _request(self, path='/encyclopedia/item/equipment/44-espada-de-maderucha/',
                 method='get', signed_in_language=None, **params):
        request = getattr(self.factory, method)(path, params)
        if signed_in_language is None:
            request.user = _AnonymousUser()
        else:
            request.user = _SignedInUser()
            request.COOKIES[settings.SESSION_COOKIE_NAME] = 'x'
            request._forced_language = signed_in_language
        return request

    def test_anonymous_visitor_is_never_redirected(self):
        # This is the property that keeps one URL bound to one language.
        # Every crawler is anonymous.
        request = self._request()
        self.assertIsNone(
            redirect_target_for_user(request, 'es', self.alternates))

    def test_request_without_session_cookie_never_touches_the_user(self):
        request = self.factory.get('/encyclopedia/item/equipment/44-twiggy-sword/')
        request.user = _ExplodingUser()  # accessing it would fail the test
        self.assertIsNone(explicit_user_language(request))

    def test_post_is_never_redirected(self):
        request = self._request(method='post', signed_in_language='fr')
        with _language(request):
            self.assertIsNone(
                redirect_target_for_user(request, 'es', self.alternates))

    def test_keep_parameter_lets_a_visitor_read_another_language(self):
        request = self._request(signed_in_language='fr', **{KEEP_LANGUAGE_PARAM: '1'})
        with _language(request):
            self.assertIsNone(
                redirect_target_for_user(request, 'es', self.alternates))

    def test_no_redirect_when_the_url_already_matches_the_choice(self):
        request = self._request(signed_in_language='es')
        with _language(request):
            self.assertIsNone(
                redirect_target_for_user(request, 'es', self.alternates))

    def test_no_redirect_when_the_target_is_the_current_path(self):
        # Guards against a loop even if the language detection disagrees.
        path = '/encyclopedia/item/equipment/44-epee-de-boisaille/'
        request = self._request(path=path, signed_in_language='fr')
        with _language(request):
            self.assertIsNone(
                redirect_target_for_user(request, 'es', self.alternates))

    def test_unknown_target_language_is_ignored(self):
        request = self._request(signed_in_language='fr')
        with _language(request):
            self.assertIsNone(
                redirect_target_for_user(request, 'es', {'es': self.alternates['es']}))


class VaryHeaderTest(TestCase):

    def test_cookie_is_added(self):
        response = mark_varies_on_cookie(HttpResponse())
        self.assertIn('Cookie', response['Vary'])

    def test_existing_vary_is_preserved(self):
        response = HttpResponse()
        response['Vary'] = 'Accept-Encoding'
        mark_varies_on_cookie(response)
        self.assertIn('Accept-Encoding', response['Vary'])
        self.assertIn('Cookie', response['Vary'])

    def test_cookie_is_not_repeated(self):
        response = HttpResponse()
        response['Vary'] = 'Cookie'
        mark_varies_on_cookie(response)
        self.assertEqual(response['Vary'].count('Cookie'), 1)


# --- test doubles ---------------------------------------------------------

class _AnonymousUser(object):
    is_authenticated = False


class _SignedInUser(object):
    is_authenticated = True


class _ExplodingUser(object):
    @property
    def is_authenticated(self):
        raise AssertionError(
            'request.user was read on a request with no session cookie, which '
            'makes Django add Vary: Cookie and stops the CDN caching the page')


class _language(object):
    """Stands in for the stored account language without touching the database."""

    def __init__(self, request):
        self.request = request

    def __enter__(self):
        import chardata.url_language as module
        self._real = module.explicit_user_language
        forced = getattr(self.request, '_forced_language', None)
        module.explicit_user_language = lambda request: forced
        return self

    def __exit__(self, *exc):
        import chardata.url_language as module
        module.explicit_user_language = self._real
        return False


class EncyclopediaItemPageTest(TestCase):
    """End to end, against the real item database.

    Reproduces exactly what Googlebot does: no Accept-Language header, no
    cookies. Before this change every one of these URLs answered in English and
    named the English URL as its canonical.
    """

    FR = '/encyclopedia/item/equipment/44-epee-de-boisaille/'
    ES = '/encyclopedia/item/equipment/44-espada-de-maderucha/'
    EN = '/encyclopedia/item/equipment/44-twiggy-sword/'

    def _fetch(self, path):
        # No HTTP_ACCEPT_LANGUAGE: this is the crawler's request.
        return self.client.get(path)

    def _head(self, path):
        response = self._fetch(path)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode('utf-8')

    def test_french_url_serves_french_to_a_crawler(self):
        html = self._head(self.FR)
        self.assertIn('Boisaille', html)
        self.assertNotIn('<title>Twiggy Sword', html)

    def test_spanish_url_serves_spanish_to_a_crawler(self):
        html = self._head(self.ES)
        self.assertIn('maderucha', html.lower())

    def test_each_url_is_its_own_canonical(self):
        # The regression that mattered: the French page declared the English
        # URL as canonical, so Google dropped it as a duplicate.
        for path in (self.FR, self.ES, self.EN):
            html = self._head(path)
            canonical = re.search(
                r'<link[^>]*rel="canonical"[^>]*>', html).group(0)
            self.assertIn(path, canonical,
                          '%s declared a canonical elsewhere: %s'
                          % (path, canonical))

    def test_hreflang_is_emitted_for_every_language(self):
        html = self._head(self.FR)
        for lang in ('en', 'fr', 'es', 'pt', 'de'):
            self.assertIn('hreflang="%s"' % lang, html)
        self.assertIn('hreflang="x-default"', html)

    @staticmethod
    def _alternate_links(html):
        """(hreflang, href) pairs, whatever order the minifier left them in.

        The HTML minifier rewrites <link rel="alternate" hreflang=".." href="..">
        with the attributes in another order, so anything matching them as a
        fixed sequence silently finds nothing and passes.
        """
        pairs = []
        for tag in re.findall(r'<link\b[^>]*hreflang=[^>]*>', html):
            lang = re.search(r'hreflang="([^"]+)"', tag)
            href = re.search(r'href="([^"]+)"', tag)
            if lang and href:
                pairs.append((lang.group(1), href.group(1)))
        return pairs

    def test_hreflang_targets_are_reciprocal(self):
        # Google ignores hreflang sets whose members do not point back.
        html = self._head(self.FR)
        targets = self._alternate_links(html)
        self.assertTrue(targets, 'no alternate links found in the page head')
        for lang, url in targets:
            if lang == 'x-default':
                continue
            path = url.replace(BASE, '')
            other = self._head(path)
            self.assertIn(self.FR, other,
                          '%s does not point back at the French page' % path)

    def test_accept_language_no_longer_changes_the_page(self):
        # The whole point: the URL decides, not the header.
        titles = set()
        for header in ('fr', 'es', 'en', 'pt'):
            response = self.client.get(self.ES, HTTP_ACCEPT_LANGUAGE=header)
            titles.add(re.search(r'<title>([^<]*)</title>',
                                 response.content.decode('utf-8')).group(1))
        self.assertEqual(len(titles), 1,
                         'the Spanish URL served %d different pages: %s'
                         % (len(titles), titles))

    def test_unknown_slug_still_resolves_by_id(self):
        # Old shared links carry stale slugs; they must keep working.
        response = self._fetch('/encyclopedia/item/equipment/44-whatever-slug/')
        self.assertEqual(response.status_code, 200)
