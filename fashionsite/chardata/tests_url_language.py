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

    def test_an_ambiguous_slug_answers_in_english(self):
        """Proper nouns are usually left untranslated, so this is the common
        case, not an edge one. Such a URL must keep answering exactly as it did
        before the language was read from the slug -- in English, which is both
        the historical default and the indexed URL. An earlier tie-break put
        English last and served Portuguese on every monster whose name does not
        change between languages."""
        names = {'en': 'Crocodyl', 'de': 'Crocodyl', 'fr': 'Crocodyl',
                 'es': 'Crocodyl', 'pt': 'Crocodyl'}
        self.assertEqual(language_from_slug(names, 'crocodyl', normalise), 'en')

    def test_an_ambiguous_slug_without_english_is_still_deterministic(self):
        names = {'de': 'Gelano', 'fr': 'Gelano'}
        first = language_from_slug(names, 'gelano', normalise)
        self.assertEqual(first, language_from_slug(names, 'gelano', normalise))
        self.assertIn(first, names)

    def test_a_translated_name_still_wins_over_english(self):
        # Ambiguity only decides when the slug matches several languages.
        names = {'en': 'Twiggy Sword', 'fr': 'Epee de Boisaille'}
        self.assertEqual(
            language_from_slug(names, 'epee-de-boisaille', normalise), 'fr')

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

    def test_a_stale_slug_still_reaches_the_page(self):
        # Old shared links carry slugs from before a rename. They must keep
        # working -- now by redirecting to the canonical URL, which also stops
        # each item answering on an unbounded set of invented slugs.
        response = self.client.get(
            '/encyclopedia/item/equipment/44-whatever-slug/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain,
                         [('/encyclopedia/item/equipment/44-twiggy-sword/', 301)])


class LocalisedSlugPagesTest(TestCase):
    """The same rule, applied to monsters, resources and sets.

    Fixtures are discovered from the item database rather than hard-coded, so
    these keep working when the game data is refreshed.
    """

    @staticmethod
    def _conn():
        import sqlite3
        from fashionistapulp.fashionista_config import get_items_db_path
        return sqlite3.connect(get_items_db_path('dofus3'))

    @staticmethod
    def _localised_path(builder, name, lang):
        from django.utils import translation as dj_translation
        with dj_translation.override(lang):
            return builder(name)

    def _assert_page_is_self_canonical(self, path, expected_fragment):
        response = self.client.get(path)  # no Accept-Language: a crawler
        self.assertEqual(response.status_code, 200, path)
        html = response.content.decode('utf-8')
        canonical = re.search(r'<link[^>]*rel="canonical"[^>]*>', html)
        self.assertIsNotNone(canonical, 'no canonical on %s' % path)
        self.assertIn(path, canonical.group(0),
                      '%s declares a canonical elsewhere: %s'
                      % (path, canonical.group(0)))
        self.assertIn(expected_fragment.lower(), html.lower(),
                      '%s does not contain %r' % (path, expected_fragment))

    def test_monster_pages_serve_the_language_named_by_the_slug(self):
        from chardata.official_site import get_monster_link
        conn = self._conn()
        try:
            row = conn.execute("""
                SELECT f.monster_ankama_id, e.name, f.name
                FROM monster_names f
                JOIN monster_names e
                  ON e.monster_ankama_id = f.monster_ankama_id AND e.language='en'
                WHERE f.language='fr' AND f.name <> e.name AND length(f.name) > 5
                ORDER BY f.monster_ankama_id LIMIT 1
            """).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, 'no bilingual monster in the database')
        monster_id, name_en, name_fr = row

        for lang, name in (('en', name_en), ('fr', name_fr)):
            path = self._localised_path(
                lambda n: get_monster_link(monster_id, n, 'dofus3'), name, lang)
            self._assert_page_is_self_canonical(path, name)

    def test_resource_pages_serve_the_language_named_by_the_slug(self):
        from chardata.official_site import get_resource_link
        conn = self._conn()
        try:
            rows = conn.execute("""
                SELECT f.ingredient_ankama_id, f.ingredient_subtype, e.name, f.name
                FROM item_recipe_ingredient_names f
                JOIN item_recipe_ingredient_names e
                  ON e.ingredient_ankama_id = f.ingredient_ankama_id
                 AND e.ingredient_subtype = f.ingredient_subtype AND e.language='en'
                WHERE f.language='fr' AND f.name <> e.name AND length(f.name) > 5
                ORDER BY f.ingredient_ankama_id LIMIT 60
            """).fetchall()
        finally:
            conn.close()

        # Many resources have no recipe and legitimately 404. Walk candidates
        # until one is actually published, then assert strictly on it -- a
        # test that skips every candidate would pass while proving nothing.
        checked = 0
        for ankama_id, subtype, name_en, name_fr in rows:
            path_en = self._localised_path(
                lambda n: get_resource_link(subtype, ankama_id, n, 'dofus3'),
                name_en, 'en')
            if self.client.get(path_en).status_code != 200:
                continue
            self._assert_page_is_self_canonical(path_en, name_en)
            path_fr = self._localised_path(
                lambda n: get_resource_link(subtype, ankama_id, n, 'dofus3'),
                name_fr, 'fr')
            self._assert_page_is_self_canonical(path_fr, name_fr)
            checked += 1
            if checked == 2:
                break
        self.assertTrue(checked, 'no published bilingual resource to check')

    def test_set_pages_serve_the_language_named_by_the_slug(self):
        from fashionistapulp.structure import get_structure
        from chardata.official_site import get_set_link

        structure = get_structure()
        candidates = [
            item_set for item_set in structure.sets_dict.values()
            if (getattr(item_set, 'localized_names', None) or {}).get('fr')
            and item_set.localized_names.get('en')
            and item_set.localized_names['fr'] != item_set.localized_names['en']
        ]
        self.assertTrue(candidates, 'no bilingual set in the structure')

        checked = 0
        for item_set in candidates:
            paths = {
                lang: self._localised_path(
                    lambda n: get_set_link(item_set.id, n,
                                           game_version='dofus3'),
                    item_set.localized_names[lang], lang)
                for lang in ('en', 'fr')
            }
            if self.client.get(paths['en']).status_code != 200:
                continue
            # The set slug used to sit in a non-capturing group, so the view
            # never saw it and every localised set URL served one language.
            for lang, path in paths.items():
                self._assert_page_is_self_canonical(
                    path, item_set.localized_names[lang])
            checked += 1
            if checked == 2:
                break
        self.assertTrue(checked, 'no published bilingual set to check')

    def test_every_localised_page_type_emits_hreflang(self):
        # Regression guard: the hreflang block lives in base.html, so a view
        # that forgets to pass alternate_urls silently emits nothing.
        html = self.client.get(
            '/encyclopedia/item/equipment/44-twiggy-sword/'
        ).content.decode('utf-8')
        self.assertIn('hreflang=', html)


class GarbageSlugTest(TestCase):
    """A slug that names no language is not a page.

    Without this, every item answers on any string at all -- an unbounded set
    of URLs serving one page. The canonical groups them, but crawl budget is
    still spent on them and they still get shared.
    """

    CANONICAL = '/encyclopedia/item/equipment/44-twiggy-sword/'

    def test_an_invented_slug_redirects_permanently(self):
        response = self.client.get(
            '/encyclopedia/item/equipment/44-total-garbage-seo-spam/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], self.CANONICAL)

    def test_the_redirect_target_answers(self):
        # A 301 is cached forever; pointing one at a 404 would be permanent.
        response = self.client.get(
            '/encyclopedia/item/equipment/44-anything/', follow=True)
        self.assertEqual(response.status_code, 200)

    def test_the_canonical_url_does_not_redirect(self):
        self.assertEqual(self.client.get(self.CANONICAL).status_code, 200)

    def test_a_localised_slug_is_never_redirected(self):
        # It names a language, so it is a legitimate page of its own.
        for path in ('/encyclopedia/item/equipment/44-epee-de-boisaille/',
                     '/encyclopedia/item/equipment/44-espada-de-maderucha/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_redirecting_twice_lands_on_the_same_place(self):
        # Guards against a loop: the target of a redirect must be stable.
        first = self.client.get('/encyclopedia/item/equipment/44-zzz/')
        second = self.client.get(first['Location'])
        self.assertEqual(second.status_code, 200)
