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

"""The page language comes from the URL slug, not from Accept-Language."""

import re
import unicodedata

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from fashionistapulp.game_versions import version_keys

from chardata.url_language import (KEEP_LANGUAGE_PARAM, build_alternate_urls,
                                   explicit_user_language, language_from_slug,
                                   mark_varies_on_cookie,
                                   redirect_target_for_user)

BASE = 'https://dofusfashionista.gg'

# Item 44 names, from the item database
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
        """Untranslated proper nouns answer in English."""
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
        alternates = build_alternate_urls(self._builder, TWIGGY_SWORD, BASE,
                                          normalise)
        self.assertEqual(sorted(alternates), ['de', 'en', 'es', 'fr', 'pt'])

    def test_urls_are_absolute_and_localised(self):
        alternates = build_alternate_urls(self._builder, TWIGGY_SWORD, BASE,
                                          normalise)
        self.assertEqual(
            alternates['fr'],
            BASE + '/encyclopedia/item/equipment/44-epee-de-boisaille/')
        self.assertEqual(
            alternates['es'],
            BASE + '/encyclopedia/item/equipment/44-espada-de-maderucha/')

    def test_every_alternate_is_distinct(self):
        # Two languages on one URL tell Google they are the same page
        alternates = build_alternate_urls(self._builder, TWIGGY_SWORD, BASE,
                                          normalise)
        self.assertEqual(len(set(alternates.values())), len(alternates))

    def test_two_languages_sharing_a_name_do_not_share_a_url(self):
        shared = dict(TWIGGY_SWORD, pt=TWIGGY_SWORD['es'])
        alternates = build_alternate_urls(self._builder, shared, BASE,
                                          normalise)
        self.assertEqual(len(set(alternates.values())), len(alternates))
        self.assertIn('es', alternates)
        self.assertNotIn('pt', alternates)

    def test_language_without_a_name_is_omitted(self):
        alternates = build_alternate_urls(
            self._builder, dict(TWIGGY_SWORD, de=None), BASE, normalise)
        self.assertNotIn('de', alternates)

    def test_builder_returning_nothing_is_omitted(self):
        alternates = build_alternate_urls(lambda name: None, TWIGGY_SWORD,
                                          BASE, normalise)
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
        # Every crawler is anonymous
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
    """End to end, as a crawler: no Accept-Language, no cookies."""

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
        """(hreflang, href) pairs in any order, the minifier sorts attributes."""
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
    """The same rule, applied to monsters, resources and sets."""

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

        # Resources without a recipe 404: walk until one is published
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
            for lang, path in paths.items():
                self._assert_page_is_self_canonical(
                    path, item_set.localized_names[lang])
            checked += 1
            if checked == 2:
                break
        self.assertTrue(checked, 'no published bilingual set to check')

    def test_every_localised_page_type_emits_hreflang(self):
        # A view that forgets alternate_urls emits no hreflang
        html =self.client.get(
            '/encyclopedia/item/equipment/44-twiggy-sword/'
        ).content.decode('utf-8')
        self.assertIn('hreflang=', html)


class LocalisedSitemapTest(TestCase):
    """Localised pages have to be submitted in the sitemaps."""

    def test_the_index_lists_a_file_per_submitted_language(self):
        xml = self.client.get('/sitemap.xml').content.decode('utf-8')
        for language in ('fr', 'es', 'pt'):
            for section in ('items', 'sets', 'resources', 'monsters'):
                self.assertIn('sitemap-%s-%s.xml' % (section, language), xml)

    def test_german_is_served_but_not_submitted(self):
        xml =self.client.get('/sitemap.xml').content.decode('utf-8')
        self.assertNotIn('sitemap-items-de.xml', xml)
        self.assertEqual(
            self.client.get(
                '/encyclopedia/item/equipment/44-holzernes-schwert/').status_code,
            200)

    def test_the_english_sections_keep_their_names(self):
        # Already submitted to Search Console
        xml =self.client.get('/sitemap.xml').content.decode('utf-8')
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
    """Links on a localised page stay in its language."""

    FRENCH = '/encyclopedia/item/equipment/44-epee-de-boisaille/'
    SPANISH = '/encyclopedia/item/equipment/44-espada-de-maderucha/'

    @staticmethod
    def _encyclopedia_links(html):
        return set(re.findall(r'href="(/(?:[a-z0-9]+/)?encyclopedia/[^"]*)"', html))

    @staticmethod
    def _without_hreflang(html):
        """Drops the hreflang links, which name other languages on purpose."""
        return re.sub(r'<link[^>]*hreflang[^>]*>', '', html)

    @staticmethod
    def _without_language_selector(html):
        """Drops the flag destinations, found by data-next whatever the tag."""
        return re.sub(r'<[a-z]+[^>]*data-next[^>]*>', '', html)

    def test_a_french_page_does_not_link_to_the_english_item(self):
        response = self.client.get(self.FRENCH)
        self.assertEqual(response.status_code, 200)
        body = self._without_language_selector(
            self._without_hreflang(response.content.decode('utf-8')))
        self.assertNotIn(
            '44-twiggy-sword', body,
            'the French item page links to the English URL outside hreflang')

    def test_links_on_a_spanish_page_answer_in_spanish(self):
        body =self._without_language_selector(self._without_hreflang(
            self.client.get(self.SPANISH).content.decode('utf-8')))
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

        VERSIONS =('/beta/', '/dofus2/', '/retro/', '/touch/')
        inattendues = [
            (path, lang) for path, lang in fugues
            if not path.startswith(VERSIONS)
        ]
        self.assertFalse(
            inattendues,
            'these entity links leave Spanish: %s' % inattendues)


class SubmittedUrlsAnswerTest(TestCase):
    """Every URL in a sitemap answers, sampled on the item sections."""

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
    """Pages with no name of their own carry their language in a prefix."""

    HUBS = ('/', '/guides/', '/encyclopedia/', '/encyclopedia/sets/',
            '/encyclopedia/monsters/')

    def test_the_english_urls_are_exactly_where_they_were(self):
        # prefix_default_language=False
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
        html =self.client.get(
            '/encyclopedia/item/equipment/44-espada-de-maderucha/'
        ).content.decode('utf-8')
        self.assertIn('/es/encyclopedia/', html)

    def test_an_entity_url_never_takes_a_prefix(self):
        # Entities carry their language in the slug
        self.assertEqual(
            self.client.get(
                '/es/encyclopedia/item/equipment/44-espada-de-maderucha/'
            ).status_code, 404)


class VersionAndLanguageMatrixTest(TestCase):
    """Every game version behaves like every other one."""

    VERSIONS = tuple(version_keys())
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
        """GameVersionMiddleware finds the version behind a language prefix."""
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
        # prefix_default_language=False
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


class UnprefixedUrlsKeepNegotiatingTest(TestCase):
    """Unprefixed urls still negotiate, though i18n_patterns forces English."""

    def _lang_of(self, path, **headers):
        html = self.client.get(path, **headers).content.decode('utf-8')
        declared = re.search(r'<html[^>]*lang="([^"]+)"', html)
        self.assertIsNotNone(declared, path)
        return declared.group(1).split('-')[0]

    def test_a_reader_keeps_the_language_their_browser_asks_for(self):
        for path in ('/faq/', '/about/', '/encyclopedia/', '/guides/'):
            for language in ('fr', 'es', 'pt'):
                with self.subTest(path=path, language=language):
                    self.assertEqual(
                        self._lang_of(path, HTTP_ACCEPT_LANGUAGE=language),
                        language)

    def test_a_crawler_always_gets_the_default_language(self):
        # No Accept-Language, no cookie: a crawler
        for path in ('/faq/', '/about/', '/encyclopedia/', '/guides/'):
            with self.subTest(path=path):
                self.assertEqual(self._lang_of(path), 'en')

    def test_a_prefixed_url_ignores_the_header_entirely(self):
        for language in ('fr', 'es', 'pt'):
            for header in ('en', 'de', 'fr'):
                with self.subTest(language=language, header=header):
                    self.assertEqual(
                        self._lang_of('/%s/encyclopedia/' % language,
                                      HTTP_ACCEPT_LANGUAGE=header),
                        language)

    def test_an_entity_url_ignores_the_header_too(self):
        # The slug carries the language
        for header in ('en', 'fr', 'de'):
            with self.subTest(header=header):
                self.assertEqual(
                    self._lang_of(
                        '/encyclopedia/item/equipment/44-espada-de-maderucha/',
                        HTTP_ACCEPT_LANGUAGE=header),
                    'es')


class EverySubmittedPageIsItsOwnCanonicalTest(TestCase):
    """Every url of sitemap-pages.xml is its own canonical, on every version."""

    @staticmethod
    def _canonical(html):
        tag = re.search(r'<link[^>]*rel="canonical"[^>]*>', html)
        if tag is None:
            return None
        href = re.search(r'href="([^"]+)"', tag.group(0))
        return href.group(1) if href else None

    def test_every_url_in_the_pages_sitemap_is_its_own_canonical(self):
        xml = self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        locations = re.findall(r'<loc>([^<]+)</loc>', xml)
        self.assertTrue(locations, 'the pages sitemap submits nothing')

        divergentes = []
        for location in locations:
            path = location.replace('https://dofusfashionista.gg', '')
            response = self.client.get(path)
            if response.status_code != 200:
                divergentes.append((path, response.status_code))
                continue
            canonical = self._canonical(response.content.decode('utf-8'))
            if canonical != location:
                divergentes.append((path, canonical))
        self.assertFalse(
            divergentes,
            '%d submitted pages are not their own canonical: %s'
            % (len(divergentes), divergentes[:6]))


class LanguageSelectorTest(TestCase):
    """The flag has to work for a visitor who is not signed in."""

    PAGES = ('/guides/getting-started/',
             '/encyclopedia/item/equipment/44-twiggy-sword/')

    @staticmethod
    def _destination(html, language):
        """The flag's destination, in any attribute order and on any tag."""
        for tag in re.findall(r'<[a-z]+[^>]*>', html):
            if 'id="flag-%s"' % language not in tag:
                continue
            found = re.search(r'data-next="([^"]*)"', tag)
            return found.group(1) if found else None
        return None

    def test_the_flags_say_where_each_language_lives(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                html = self.client.get(page).content.decode('utf-8')
                for language in ('fr', 'es', 'pt'):
                    destination = self._destination(html, language)
                    self.assertTrue(
                        destination, 'no destination on the %s flag of %s'
                        % (language, page))
                    self.assertTrue(
                        destination.startswith('/'),
                        'the destination must be a path, not %r -- '
                        'set_language refuses another host' % destination)

    def test_each_destination_answers_in_its_own_language(self):
        for page in self.PAGES:
            html = self.client.get(page).content.decode('utf-8')
            for language in ('fr', 'es', 'pt'):
                destination = self._destination(html, language)
                self.assertTrue(destination)
                with self.subTest(page=page, language=language):
                    response = self.client.get(destination)
                    self.assertEqual(response.status_code, 200, destination)
                    declared = re.search(
                        r'<html[^>]*lang="([^"]+)"',
                        response.content.decode('utf-8'))
                    self.assertEqual(declared.group(1).split('-')[0], language)

    def test_the_form_carries_a_next_field(self):
        html = self.client.get(self.PAGES[0]).content.decode('utf-8')
        self.assertIn('name="next"', html)


class OneSlugFunctionTest(TestCase):
    """Published url and lookup build the slug with the same rule."""

    def test_the_two_agree_on_every_name_in_the_database(self):
        import sqlite3
        from chardata.encyclopedia_view import _normalized_slug
        from chardata.official_site import _slugify_name
        from fashionistapulp.fashionista_config import get_items_db_path

        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            names = [row[0] for row in conn.execute(
                'SELECT name FROM item_names UNION '
                'SELECT name FROM monster_names UNION '
                'SELECT name FROM items').fetchall() if row[0]]
        finally:
            conn.close()
        self.assertGreater(len(names), 1000, 'no names to check')

        divergentes = [
            name for name in names
            if _slugify_name(name, 'x') != (_normalized_slug(name) or 'x')
        ]
        self.assertFalse(
            divergentes,
            '%d names build one url and resolve to another: %s'
            % (len(divergentes), divergentes[:5]))

    def test_a_possessive_name_round_trips(self):
        from chardata.encyclopedia_view import _normalized_slug
        from chardata.official_site import _slugify_name

        published = _slugify_name("Coldbruela's Boots", 'item')
        self.assertEqual(_normalized_slug("Coldbruela's Boots"), published)
        # A slug stays the same when slugified again
        self.assertEqual(_normalized_slug(published), published)


class HubAlternatesTest(TestCase):
    """A hub announces its five languages with hreflang."""

    def test_a_hub_announces_its_translations(self):
        for path in ('/encyclopedia/', '/es/encyclopedia/',
                     '/retro/encyclopedia/monsters/', '/fr/guides/'):
            with self.subTest(path=path):
                html = self.client.get(path).content.decode('utf-8')
                for language in ('en', 'fr', 'es', 'pt', 'de'):
                    self.assertIn('hreflang="%s"' % language, html, path)

    def test_the_announced_urls_answer_in_that_language(self):
        html = self.client.get('/es/encyclopedia/').content.decode('utf-8')
        # Tag by tag: the minifier sorts attributes
        pairs = []
        for tag in re.findall(r'<link\b[^>]*hreflang=[^>]*>', html):
            code = re.search(r'hreflang="([^"]+)"', tag)
            href = re.search(r'href="([^"]+)"', tag)
            if code and href and code.group(1) != 'x-default':
                pairs.append((code.group(1), href.group(1)))
        self.assertTrue(pairs, 'no alternates on the Spanish hub')
        for language, url in pairs:
            path = url.replace('https://dofusfashionista.gg', '')
            with self.subTest(language=language, path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)
                declared = re.search(r'<html[^>]*lang="([^"]+)"',
                                     response.content.decode('utf-8'))
                self.assertEqual(declared.group(1).split('-')[0], language)

    def test_no_page_announces_an_alternate_that_is_not_there(self):
        """Every alternate a page announces answers."""
        announced = 0
        for path in ('/faq/', '/about/', '/es/faq/', '/encyclopedia/',
                     '/fr/guides/'):
            html = self.client.get(path).content.decode('utf-8')
            for tag in re.findall(r'<link\b[^>]*hreflang=[^>]*>', html):
                code = re.search(r'hreflang="([^"]+)"', tag)
                href = re.search(r'href="([^"]+)"', tag)
                if not code or not href:
                    continue
                announced += 1
                target = href.group(1).replace(
                    'https://dofusfashionista.gg', '')
                with self.subTest(page=path, alternate=code.group(1)):
                    self.assertEqual(
                        self.client.get(target).status_code, 200,
                        '%s announces %s, which does not answer'
                        % (path, target))
        self.assertGreater(
            announced, 0,
            'no page announced any alternate, so this test checked nothing')

    def test_every_hub_submitted_answers(self):
        xml = self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        hubs = [loc for loc in re.findall(r'<loc>([^<]+)</loc>', xml)
                if re.search(r'\.gg/(fr|es|pt)(/|$)', loc)]
        self.assertTrue(hubs, 'no localised hub is submitted')
        for loc in hubs:
            path = loc.replace('https://dofusfashionista.gg', '')
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200, path)


class RepeatedVersionVariantTest(TestCase):
    """A variant is a copy of the live page only if data and picture match."""

    def setUp(self):
        from unittest import mock
        from chardata import image_store
        real = image_store._static_exists
        # Dofus 2 icons hidden, so its pages match Dofus 3 again
        hidden = mock.patch.object(
            image_store, '_static_exists',
            side_effect=lambda path: '/dofus2/' not in path and real(path))
        hidden.start()
        self.addCleanup(hidden.stop)
        # The sitemap caches its documents in the module
        from fashionsite import urls
        urls._SITEMAP_CACHES.clear()
        self.addCleanup(urls._SITEMAP_CACHES.clear)

    @staticmethod
    def _canonical(html):
        tag = re.search(r'<link[^>]*rel="canonical"[^>]*>', html)
        return re.search(r'href="([^"]+)"', tag.group(0)).group(1) if tag else None

    @staticmethod
    def _picture(html):
        for tag in re.findall(r'<img[^>]*>', html):
            if '/items/' in tag or '/pets/' in tag:
                found = re.search(r'src="([^"]+)"', tag)
                if found:
                    return found.group(1)
        return None

    @staticmethod
    def _copies(version):
        from chardata.version_content import (repeats_the_live_version,
                                              _cached_signatures)
        return [(key, value) for key, value in _cached_signatures(version).items()
                if repeats_the_live_version(version, *key)]

    def _pair(self, version):
        """(variant, live) urls of a copy both versions publish, or None."""
        from chardata.official_site import get_item_link
        for (ankama_type, ankama_id), (_digest, name, _kind) in self._copies(version):
            variant = get_item_link(ankama_type, ankama_id, name,
                                    game_version=version)
            live = get_item_link(ankama_type, ankama_id, name,
                                 game_version='dofus3')
            if not variant or not live:
                continue
            if (self.client.get(variant).status_code == 200
                    and self.client.get(live).status_code == 200):
                return variant, live
        return None

    def test_a_page_called_a_copy_shows_the_same_picture(self):
        """Compared on the rendered html."""
        pair =self._pair('beta') or self._pair('dofus2')
        self.assertIsNotNone(pair, 'no variant judged a copy to check')
        variant, live = pair
        self.assertEqual(
            self._picture(self.client.get(variant).content.decode('utf-8')),
            self._picture(self.client.get(live).content.decode('utf-8')),
            '%s is called a copy of %s but shows another picture'
            % (variant, live))

    def test_a_copy_points_at_the_live_page(self):
        pair = self._pair('beta') or self._pair('dofus2')
        self.assertIsNotNone(pair, 'no variant judged a copy to check')
        variant, live = pair
        self.assertEqual(
            self._canonical(self.client.get(variant).content.decode('utf-8')),
            'https://dofusfashionista.gg' + live)

    def test_a_copy_still_answers(self):
        # Canonical elsewhere, but still served
        pair =self._pair('beta') or self._pair('dofus2')
        self.assertIsNotNone(pair)
        self.assertEqual(self.client.get(pair[0]).status_code, 200)

    def test_a_copy_is_not_submitted(self):
        pair = self._pair('beta') or self._pair('dofus2')
        self.assertIsNotNone(pair)
        variant, live = pair
        xml = self.client.get('/sitemap-items.xml').content.decode('utf-8')
        self.assertNotIn('<loc>https://dofusfashionista.gg%s</loc>' % variant, xml)
        self.assertIn('<loc>https://dofusfashionista.gg%s</loc>' % live, xml)

    def test_a_different_picture_alone_makes_a_different_page(self):
        # Touch and Retro items all have their own render
        for version in ('touch', 'retro'):
            with self.subTest(version=version):
                copies = self._copies(version)
                self.assertFalse(
                    copies,
                    '%s pages called copies despite their own art: %s'
                    % (version, [key for key, _ in copies[:3]]))

    def test_the_live_page_is_never_a_copy_of_itself(self):
        from chardata.version_content import repeats_the_live_version
        self.assertFalse(repeats_the_live_version('dofus3', 'equipment', 44))
        self.assertFalse(repeats_the_live_version(None, 'equipment', 44))


class PageHitPathTest(TestCase):
    """One page counts as one page, whatever prefixes its url carries."""

    def test_prefixes_collapse_to_one_shape(self):
        from chardata.middleware import normalise_path
        for path, version in (('/encyclopedia/', 'dofus3'),
                              ('/dofus2/encyclopedia/', 'dofus2'),
                              ('/es/encyclopedia/', 'dofus3'),
                              ('/es/dofus2/encyclopedia/', 'dofus2'),
                              ('/pt/retro/encyclopedia/', 'retro')):
            with self.subTest(path=path):
                self.assertEqual(normalise_path(path, version),
                                 '/encyclopedia/')

    def test_the_home_page_stays_the_home_page(self):
        from chardata.middleware import normalise_path
        for path in ('/', '/es/', '/fr/'):
            with self.subTest(path=path):
                self.assertEqual(normalise_path(path, 'dofus3'), '/')

    def test_a_localised_slug_is_kept(self):
        # The slug names the page; only the prefixes are noise.
        from chardata.middleware import normalise_path
        self.assertEqual(
            normalise_path('/fr/guides/tacle-et-fuite/', 'dofus3'),
            '/guides/tacle-et-fuite/')

    def test_shared_builds_still_collapse(self):
        from chardata.middleware import normalise_path
        self.assertEqual(
            normalise_path('/s/Ocra/MzUzV.JJqQ__/', 'dofus3'), '/s/<build>/')


class PrivatePagesStayOutOfSearchTest(TestCase):
    """A page that is empty unless you are signed in is not content."""

    def test_the_project_list_is_not_indexable(self):
        html = self.client.get('/loadprojects/').content.decode('utf-8')
        self.assertIn('noindex', html)

    def test_it_is_no_longer_submitted(self):
        xml = self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        self.assertNotIn('/loadprojects/', xml)

    def test_the_public_landing_is_still_submitted(self):
        # /setup/ is the public "create a project" page
        xml =self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        self.assertIn('<loc>https://dofusfashionista.gg/setup/</loc>', xml)
        self.assertEqual(self.client.get('/setup/').status_code, 200)


class SubmittedHubCanonicalIgnoresTheBrowserTests(TestCase):
    """A submitted url names itself, whatever language the browser asks for."""

    HUBS = ('/encyclopedia/', '/encyclopedia/sets/', '/encyclopedia/monsters/')
    HEADERS = ('fr', 'es', 'pt', 'de', 'es-ES,es;q=0.9', '')

    def _canonical(self, html):
        tag = re.search(r'<link[^>]*canonical[^>]*>', html)
        self.assertIsNotNone(tag, 'no canonical tag at all')
        href = re.search(r'href="([^"]+)"', tag.group(0))
        self.assertIsNotNone(href, tag.group(0))
        return href.group(1)

    def test_an_unprefixed_hub_stays_its_own_canonical(self):
        for hub in self.HUBS:
            attendu = 'https://dofusfashionista.gg%s' % hub
            for header in self.HEADERS:
                page = self.client.get(hub, HTTP_ACCEPT_LANGUAGE=header)
                self.assertEqual(page.status_code, 200, hub)
                self.assertEqual(
                    self._canonical(page.content.decode('utf-8')), attendu,
                    '%s served with Accept-Language %r names another url'
                    % (hub, header))

    def test_a_prefixed_hub_stays_its_own_canonical(self):
        for prefix in ('/fr', '/es', '/pt'):
            for hub in self.HUBS:
                path = prefix + hub
                attendu = 'https://dofusfashionista.gg%s' % path
                for header in ('en', 'de', ''):
                    page = self.client.get(path, HTTP_ACCEPT_LANGUAGE=header)
                    self.assertEqual(page.status_code, 200, path)
                    self.assertEqual(
                        self._canonical(page.content.decode('utf-8')), attendu,
                        '%s served with Accept-Language %r names another url'
                        % (path, header))

    def test_the_canonical_never_contradicts_the_hreflang_block(self):
        """The canonical url is among the page's own alternates."""
        for header in ('es', 'fr', ''):
            html = self.client.get(
                '/encyclopedia/', HTTP_ACCEPT_LANGUAGE=header
            ).content.decode('utf-8')
            canonical = self._canonical(html)
            alternates = {}
            for tag in re.findall(r'<link[^>]*hreflang[^>]*>', html):
                lang = re.search(r'hreflang="([^"]+)"', tag)
                href = re.search(r'href="([^"]+)"', tag)
                if lang and href:
                    alternates.setdefault(href.group(1), set()).add(lang.group(1))
            self.assertIn(canonical, alternates,
                          'canonical %s is not among the alternates' % canonical)
            self.assertIn(
                'en', alternates[canonical],
                'the unprefixed hub is listed as %s in its own hreflang block '
                'while canonicalising to %s'
                % (sorted(alternates[canonical]), canonical))

    def test_breadcrumbs_still_follow_the_language_of_the_page(self):
        """The canonical follows the url; links keep following the page."""
        english = self.client.get(
            '/encyclopedia/item/equipment/44-twiggy-sword/')
        self.assertEqual(english.status_code, 200)
        spanish_url = None
        for tag in re.findall(r'<link[^>]*hreflang="es"[^>]*>',
                              english.content.decode('utf-8')):
            href = re.search(r'href="([^"]+)"', tag)
            if href:
                spanish_url = href.group(1)
        self.assertIsNotNone(spanish_url, 'the item page declares no es alternate')

        path = spanish_url.replace('https://dofusfashionista.gg', '')
        page = self.client.get(path)
        self.assertEqual(page.status_code, 200, path)
        html = page.content.decode('utf-8')
        self.assertIn('<html lang="es"', html,
                      '%s is not served in Spanish' % path)
        self.assertIn('https://dofusfashionista.gg/es/encyclopedia/', html,
                      'a Spanish page links to a hub that is not Spanish')


class ALanguageSitemapOnlyHoldsThatLanguageTests(TestCase):
    """A translated sitemap must not submit another language's url."""

    HUB = '/encyclopedia/monsters/'

    def _locations(self, name):
        xml = self.client.get('/sitemap-%s.xml' % name).content.decode('utf-8')
        return re.findall(r'<loc>([^<]+)</loc>', xml)

    def test_no_translated_sitemap_submits_an_unprefixed_hub(self):
        for language in ('fr', 'es', 'pt'):
            for location in self._locations('monsters-%s' % language):
                path = location.replace('https://dofusfashionista.gg', '')
                if path.endswith(self.HUB):
                    self.assertTrue(
                        path.startswith('/%s/' % language),
                        'the %s sitemap submits %s, which is not in %s'
                        % (language, path, language))

    def test_the_english_sitemap_still_submits_its_hub(self):
        """No other sitemap submits the unprefixed hub."""
        paths = [l.replace('https://dofusfashionista.gg', '')
                 for l in self._locations('monsters')]
        self.assertIn(self.HUB, paths)

    def test_a_hub_is_submitted_once_and_only_once(self):
        counted = {}
        for name in ('monsters', 'monsters-fr', 'monsters-es', 'monsters-pt',
                     'pages'):
            for location in self._locations(name):
                if location.endswith(self.HUB):
                    counted[location] = counted.get(location, 0) + 1
        repeated = {url: n for url, n in counted.items() if n > 1}
        self.assertEqual(repeated, {}, 'submitted more than once: %s' % repeated)


class HreflangNamesTheCanonicalTests(TestCase):
    """Google drops an hreflang group that does not name the page itself."""

    NAVIGATEUR = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0'

    # ?q=sword&page=2 is canonical at the bare list
    NAMES_ITSELF = (
        '/',
        '/guides/',
        '/encyclopedia/',
        '/encyclopedia/sets/',
        '/encyclopedia/monsters/',
        '/encyclopedia/?q=sword&page=2',
        '/fr/encyclopedia/',
        '/de/guides/',
        '/retro/encyclopedia/',
        '/fr/retro/encyclopedia/',
        '/encyclopedia/item/equipment/44-twiggy-sword/',
        '/guides/resistance-explained/',
    )

    # Lists sort by translated name: page N differs per language
    PUBLISHES_NOTHING = (
        '/encyclopedia/?page=7',
        '/encyclopedia/sets/?page=3',
        '/encyclopedia/monsters/?page=5',
        '/fr/encyclopedia/?page=7',
        '/retro/encyclopedia/?page=3',
    )

    def _head(self, url):
        response = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en',
                                   HTTP_USER_AGENT=self.NAVIGATEUR)
        self.assertEqual(response.status_code, 200,
                         '%s answered %s' % (url, response.status_code))
        html = response.content.decode('utf-8', 'replace')
        canonical = re.search(r'<link[^>]*canonical[^>]*>', html)
        canonical = (re.search(r'href="([^"]*)"', canonical.group(0)).group(1)
                     if canonical else None)
        alternates = {}
        for tag in re.finditer(r'<link[^>]*hreflang="([^"]+)"[^>]*>', html):
            alternates[tag.group(1)] = re.search(
                r'href="([^"]*)"', tag.group(0)).group(1)
        return canonical, alternates

    def test_a_published_group_contains_the_canonical(self):
        # Item pages carry their language in the slug, not in a prefix
        checked = 0
        wrong = []
        for url in self.NAMES_ITSELF:
            canonical, alternates = self._head(url)
            self.assertTrue(alternates, '%s publishes no group at all' % url)
            checked += 1
            named = [lang for lang, alt in alternates.items()
                     if alt == canonical and lang != 'x-default']
            if not named:
                wrong.append((url, canonical, sorted(alternates.values())[:3]))
        self.assertFalse(
            wrong, 'these pages declare translations without naming '
            'themselves: %s' % wrong[:4])
        self.assertEqual(checked, len(self.NAMES_ITSELF))

    def test_a_slice_of_a_list_publishes_no_group(self):
        for url in self.PUBLISHES_NOTHING:
            _canonical, alternates = self._head(url)
            self.assertFalse(
                alternates,
                '%s is one slice of a list; the same page number in another '
                'language is a different set of items, so it may not claim '
                'them as translations: %s' % (url, sorted(alternates)))

    def test_a_slice_keeps_its_language_flags(self):
        # The alternates also feed the language flags
        for url in self.PUBLISHES_NOTHING:
            response = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en',
                                       HTTP_USER_AGENT=self.NAVIGATEUR)
            html = response.content.decode('utf-8', 'replace')
            flags = re.findall(r'id="flag-([a-z]{2})"', html)
            self.assertEqual(
                len(flags), 4,
                '%s offers %s instead of four language flags' % (url, flags))
