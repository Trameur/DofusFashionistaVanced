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

# Item 44, read from the item database rather than written from memory: two
# of these were guessed wrong at first, and a fixture that invents its data
# proves nothing about the code it exercises.
TWIGGY_SWORD = {
    'en': 'Twiggy Sword',
    'fr': 'Épée de Boisaille',
    'es': 'Espada de maderucha',
    'pt': 'Espada de graveto',
    'de': 'Hölzernes Schwert',
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

    def test_unknown_slug_still_resolves_by_id(self):
        # Old shared links carry stale slugs; they must keep working.
        response = self._fetch('/encyclopedia/item/equipment/44-whatever-slug/')
        self.assertEqual(response.status_code, 200)


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


class LocalisedSitemapTest(TestCase):
    """The localised pages exist and are self-canonical, but nothing makes
    Google find them: /encyclopedia/ is a fixed path, so a crawler only ever
    sees its English form, which links only to English item URLs. They have to
    be submitted."""

    def test_the_index_lists_a_file_per_submitted_language(self):
        xml = self.client.get('/sitemap.xml').content.decode('utf-8')
        for language in ('fr', 'es', 'pt'):
            for section in ('items', 'sets', 'resources', 'monsters'):
                self.assertIn('sitemap-%s-%s.xml' % (section, language), xml)

    def test_german_is_served_but_not_submitted(self):
        # No measured German audience. The pages answer and hreflang points at
        # them, which is enough to be found; submitting 40 000 more URLs is not
        # worth the crawl budget until the numbers say otherwise.
        xml = self.client.get('/sitemap.xml').content.decode('utf-8')
        self.assertNotIn('sitemap-items-de.xml', xml)
        self.assertEqual(
            self.client.get(
                '/encyclopedia/item/equipment/44-holzernes-schwert/').status_code,
            200)

    def test_the_english_sections_keep_their_names(self):
        # Already submitted to Search Console; renaming them would lose their
        # history for nothing.
        xml = self.client.get('/sitemap.xml').content.decode('utf-8')
        for section in ('pages', 'items', 'sets', 'resources', 'monsters'):
            self.assertIn('sitemap-%s.xml' % section, xml)

    def test_a_localised_section_answers_and_carries_that_language(self):
        response = self.client.get('/sitemap-items-fr.xml')
        self.assertEqual(response.status_code, 200)
        xml = response.content.decode('utf-8')
        self.assertIn('<loc>', xml)
        self.assertIn('/44-epee-de-boisaille/', xml)

    def test_each_language_gets_different_urls(self):
        french = self.client.get('/sitemap-items-fr.xml').content.decode('utf-8')
        spanish = self.client.get('/sitemap-items-es.xml').content.decode('utf-8')
        self.assertNotEqual(french, spanish)
        self.assertIn('/44-espada-de-maderucha/', spanish)
        self.assertNotIn('/44-espada-de-maderucha/', french)

    def test_a_localised_section_stays_under_the_google_limit(self):
        xml = self.client.get('/sitemap-items-es.xml').content.decode('utf-8')
        self.assertLess(xml.count('<loc>'), 50000,
                        'Google refuses a sitemap over 50000 urls')

    def test_an_unknown_section_is_404(self):
        self.assertEqual(self.client.get('/sitemap-nope-xx.xml').status_code, 404)


class InternalLinksStayInLanguageTest(TestCase):
    """A localised page whose links point back at English URLs sends every
    visitor -- and every crawler -- straight out of the language it just
    reached, and tells Google the translations are unrelated pages."""

    FRENCH = '/encyclopedia/item/equipment/44-epee-de-boisaille/'
    SPANISH = '/encyclopedia/item/equipment/44-espada-de-maderucha/'

    @staticmethod
    def _encyclopedia_links(html):
        return set(re.findall(r'href="(/(?:[a-z0-9]+/)?encyclopedia/[^"]*)"', html))

    @staticmethod
    def _without_hreflang(html):
        """Drops the alternate block, which names the other languages on
        purpose. Stripping only the attribute leaves the tag and its href
        behind, which reads as an English link that is not one."""
        return re.sub(r'<link[^>]*hreflang[^>]*>', '', html)

    def test_a_french_page_does_not_link_to_the_english_item(self):
        response = self.client.get(self.FRENCH)
        self.assertEqual(response.status_code, 200)
        body = self._without_hreflang(response.content.decode('utf-8'))
        self.assertNotIn(
            '44-twiggy-sword', body,
            'the French item page links to the English URL outside hreflang')

    def test_links_on_a_spanish_page_answer_in_spanish(self):
        body = self._without_hreflang(
            self.client.get(self.SPANISH).content.decode('utf-8'))
        checked = 0
        fugues = []
        for path in sorted(self._encyclopedia_links(body))[:12]:
            response = self.client.get(path)
            if response.status_code != 200:
                continue
            declared = re.search(
                r'<html[^>]*lang="([^"]+)"',
                response.content.decode('utf-8'))
            self.assertIsNotNone(declared, path)
            if declared.group(1).split('-')[0] != 'es':
                fugues.append((path, declared.group(1)))
            checked += 1
        self.assertTrue(checked, 'no internal encyclopedia link to check')

        # Hubs on the default version now carry a language prefix, so nothing
        # there may leak. Version-prefixed hubs (/dofus2/encyclopedia/) are the
        # one case still unpublished per language: stacking two prefixes needs
        # its own pass. Narrowed to exactly that, so a new leak anywhere else
        # fails here.
        VERSIONS = ('/beta/', '/dofus2/', '/retro/', '/touch/')
        inattendues = [
            (path, lang) for path, lang in fugues
            if not path.startswith(VERSIONS)
        ]
        self.assertFalse(
            inattendues,
            'these entity links leave Spanish: %s' % inattendues)


class SubmittedUrlsAnswerTest(TestCase):
    """Every URL in a sitemap is a promise to Google.

    161 404 URLs are submitted once the localised sections are live. A 404
    among them burns crawl budget and reads as a quality signal.

    Deliberately narrow: building a section costs a scan of five game
    databases, so this samples the item sections -- 20 466 URLs each, by far
    the largest -- rather than every combination. The other sections share the
    same builder and the same code path.
    """

    SAMPLE = 4

    @staticmethod
    def _locations(xml):
        return re.findall(r'<loc>https?://[^/]+([^<]+)</loc>', xml)

    def _sample(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        locations = self._locations(response.content.decode('utf-8'))
        self.assertTrue(locations, '%s submits nothing' % path)
        step = max(1, len(locations) // self.SAMPLE)
        return locations[::step][:self.SAMPLE]

    def test_submitted_item_urls_answer_in_the_language_they_are_filed_under(self):
        for language in ('en', 'fr', 'es', 'pt'):
            name = 'items' if language == 'en' else 'items-%s' % language
            with self.subTest(language=language):
                for location in self._sample('/sitemap-%s.xml' % name):
                    response = self.client.get(location)
                    self.assertEqual(
                        response.status_code, 200,
                        '%s submits %s which does not answer'
                        % (name, location))
                    declared = re.search(
                        r'<html[^>]*lang="([^"]+)"',
                        response.content.decode('utf-8'))
                    self.assertIsNotNone(declared, location)
                    self.assertEqual(
                        declared.group(1).split('-')[0], language,
                        '%s is filed under %s but answers in %s'
                        % (location, language, declared.group(1)))

    def test_the_index_only_names_sections_that_exist(self):
        xml = self.client.get('/sitemap.xml').content.decode('utf-8')
        named = re.findall(r'/sitemap-([a-z-]+)\.xml', xml)
        self.assertTrue(named)
        for name in named:
            with self.subTest(section=name):
                self.assertEqual(
                    self.client.get('/sitemap-%s.xml' % name).status_code, 200,
                    'the index names sitemap-%s.xml, which does not answer'
                    % name)


class HubLanguagePrefixTest(TestCase):
    """Pages with no name of their own carry their language in a prefix.

    Everything else takes it from the entity name. A hub has no name, so
    without a prefix it exists only in English -- and the breadcrumb of a
    Spanish item page sent every reader and every crawler straight back to
    English on the first click.
    """

    HUBS = ('/', '/guides/', '/encyclopedia/', '/encyclopedia/sets/',
            '/encyclopedia/monsters/')

    def test_the_english_urls_are_exactly_where_they_were(self):
        # prefix_default_language=False. Nothing already indexed may move.
        for hub in self.HUBS:
            with self.subTest(hub=hub):
                self.assertEqual(self.client.get(hub).status_code, 200)

    def test_each_hub_gains_a_url_per_language(self):
        for hub in self.HUBS:
            for language in ('fr', 'es', 'pt', 'de'):
                with self.subTest(hub=hub, language=language):
                    self.assertEqual(
                        self.client.get('/%s%s' % (language, hub)).status_code,
                        200)

    def test_a_prefixed_hub_answers_in_that_language(self):
        for language in ('fr', 'es', 'pt'):
            with self.subTest(language=language):
                html = self.client.get(
                    '/%s/encyclopedia/' % language).content.decode('utf-8')
                declared = re.search(r'<html[^>]*lang="([^"]+)"', html)
                self.assertIsNotNone(declared)
                self.assertEqual(declared.group(1).split('-')[0], language)

    def test_the_breadcrumb_of_a_spanish_item_stays_spanish(self):
        # The finding that motivated this: /encyclopedia/ was the one link on
        # a Spanish page that left Spanish.
        html = self.client.get(
            '/encyclopedia/item/equipment/44-espada-de-maderucha/'
        ).content.decode('utf-8')
        self.assertIn('/es/encyclopedia/', html)

    def test_an_entity_url_never_takes_a_prefix(self):
        # Entities carry their language in the name; a prefix on top would be
        # a second URL for one page.
        self.assertEqual(
            self.client.get(
                '/es/encyclopedia/item/equipment/44-espada-de-maderucha/'
            ).status_code, 404)


class VersionAndLanguageMatrixTest(TestCase):
    """Every game version behaves like every other one.

    The rule cannot hold on the default version only: /encyclopedia/ answers in
    five languages, so /dofus2/encyclopedia/ has to as well, or the site says
    two different things depending on which version a reader is on.
    """

    VERSIONS = ('dofus3', 'beta', 'dofus2', 'retro', 'touch')
    LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
    HUBS = ('/', '/encyclopedia/', '/encyclopedia/sets/',
            '/encyclopedia/monsters/', '/guides/')

    @staticmethod
    def _path(version, language, hub):
        path = hub if version == 'dofus3' else '/%s%s' % (version, hub)
        # Language first: that is the order i18n_patterns builds.
        return path if language == 'en' else '/%s%s' % (language, path)

    def test_every_version_answers_in_every_language(self):
        for version in self.VERSIONS:
            for language in self.LANGUAGES:
                for hub in self.HUBS:
                    path = self._path(version, language, hub)
                    with self.subTest(path=path):
                        self.assertEqual(
                            self.client.get(path).status_code, 200, path)

    def test_the_page_answers_in_the_language_its_url_names(self):
        for version in self.VERSIONS:
            for language in self.LANGUAGES:
                path = self._path(version, language, '/encyclopedia/')
                with self.subTest(path=path):
                    html = self.client.get(path).content.decode('utf-8')
                    declared = re.search(r'<html[^>]*lang="([^"]+)"', html)
                    self.assertIsNotNone(declared, path)
                    self.assertEqual(declared.group(1).split('-')[0], language,
                                     path)

    def test_the_version_survives_a_language_prefix(self):
        """GameVersionMiddleware read the opening segment to find the version.
        With a language in front it found 'es', so every translated page fell
        back to the default version and served the wrong game's data."""
        from chardata.middleware import GameVersionMiddleware

        for version in self.VERSIONS:
            for language in self.LANGUAGES:
                path = self._path(version, language, '/encyclopedia/')
                with self.subTest(path=path):
                    seen = {}

                    def capture(request, seen=seen):
                        seen['version'] = request.game_version
                        from django.http import HttpResponse
                        return HttpResponse('')

                    from django.test import RequestFactory
                    GameVersionMiddleware(capture)(RequestFactory().get(path))
                    self.assertEqual(seen['version'], version, path)

    def test_english_urls_did_not_move(self):
        # prefix_default_language=False. Every English url stays put.
        for version in self.VERSIONS:
            for hub in self.HUBS:
                path = hub if version == 'dofus3' else '/%s%s' % (version, hub)
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)

    def test_reverse_gives_the_url_that_answers(self):
        from django.urls import reverse
        from django.utils import translation

        for version in self.VERSIONS:
            for language in self.LANGUAGES:
                name = ('encyclopedia' if version == 'dofus3'
                        else '%s:encyclopedia' % version)
                with self.subTest(version=version, language=language):
                    with translation.override(language):
                        url = reverse(name)
                    self.assertEqual(
                        url, self._path(version, language, '/encyclopedia/'))
                    self.assertEqual(self.client.get(url).status_code, 200)
