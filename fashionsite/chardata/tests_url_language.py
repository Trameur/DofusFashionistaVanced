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

    @staticmethod
    def _without_language_selector(html):
        """Drops the flag destinations. The English flag naming the English
        url is the selector working, not a link leaving the language."""
        return re.sub(r'<img[^>]*data-next[^>]*>', '', html)

    def test_a_french_page_does_not_link_to_the_english_item(self):
        response = self.client.get(self.FRENCH)
        self.assertEqual(response.status_code, 200)
        body = self._without_language_selector(
            self._without_hreflang(response.content.decode('utf-8')))
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


class UnprefixedUrlsKeepNegotiatingTest(TestCase):
    """Two properties that have to hold at once, and nearly did not.

    Django forces the default language on every unprefixed url as soon as
    i18n_patterns is used with prefix_default_language=False. Adding prefixes
    for the hub pages therefore turned the whole site English for readers --
    /faq/, /setup/, every solution page -- while the tests for the encyclopedia
    stayed green, because those pages take their language from the slug.
    """

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
        # No Accept-Language, no cookie: exactly Googlebot. The url stays
        # deterministic for indexing without forcing English on readers.
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
        # These carry the language in the slug, so no header may move them.
        for header in ('en', 'fr', 'de'):
            with self.subTest(header=header):
                self.assertEqual(
                    self._lang_of(
                        '/encyclopedia/item/equipment/44-espada-de-maderucha/',
                        HTTP_ACCEPT_LANGUAGE=header),
                    'es')


class EverySubmittedPageIsItsOwnCanonicalTest(TestCase):
    """The check that would have caught the versioned guides.

    An adversarial review found 44 of the 256 urls in sitemap-pages.xml
    declaring a canonical no sitemap contained: guides under a version prefix
    built their url with reverse() while a non-default language was active, so
    /retro/guides/coups-critiques/ named /fr/retro/guides/... as canonical.
    Telling Google a submitted page is a copy of an unsubmitted one is exactly
    the defect this whole change set exists to remove.

    Earlier tests only looked at dofus3, which is where the blind spot was.
    """

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
    """The flag has to work for a visitor who is not signed in.

    On a page whose language lives in its url, coming back to the same url
    re-imposes the language being left, so the selector did nothing at all on
    the encyclopedia and the guides -- the two largest families of pages.
    Signed-in visitors were carried by the profile redirect and hid it.
    """

    PAGES = ('/guides/getting-started/',
             '/encyclopedia/item/equipment/44-twiggy-sword/')

    @staticmethod
    def _destination(html, language):
        """The flag's destination, whatever order the minifier left the
        attributes in -- it sorts them alphabetically, so data-next comes
        before id and any fixed-order pattern silently finds nothing."""
        for tag in re.findall(r'<img[^>]*>', html):
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
    """The url a page is published at and the slug it is looked up by must be
    produced by the same rule.

    They were not: official_site._slugify_name drops "'s" and
    encyclopedia_view._normalized_slug did not. An item called "Coldbruela's
    Boots" was published at /...-coldbruela-boots/ and looked up as
    "coldbruela-s-boots", so the lookup found nothing, the page fell back to
    the negotiated language, and a crawler read English on a url submitted as
    Spanish. Roughly 46 urls were affected -- few, but the invariant "one url,
    one language" was simply false for them.
    """

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
        # And the published slug resolves to itself, so a second pass over an
        # already-slugified url cannot drift.
        self.assertEqual(_normalized_slug(published), published)


class HubAlternatesTest(TestCase):
    """A hub that answers in five languages but says so nowhere is only half
    published: Google has no way to know the five are the same page, and no
    sitemap invited it to look."""

    def test_a_hub_announces_its_translations(self):
        for path in ('/encyclopedia/', '/es/encyclopedia/',
                     '/retro/encyclopedia/monsters/', '/fr/guides/'):
            with self.subTest(path=path):
                html = self.client.get(path).content.decode('utf-8')
                for language in ('en', 'fr', 'es', 'pt', 'de'):
                    self.assertIn('hreflang="%s"' % language, html, path)

    def test_the_announced_urls_answer_in_that_language(self):
        html = self.client.get('/es/encyclopedia/').content.decode('utf-8')
        # Parsed tag by tag: the minifier sorts attributes, so hreflang and
        # href arrive in either order and a fixed-order pattern finds nothing.
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

    def test_a_page_with_no_translated_url_announces_none(self):
        # /faq/ lives outside i18n_patterns, so /es/faq/ does not exist.
        # Pointing hreflang at a 404 is worse than pointing at nothing.
        html = self.client.get('/faq/').content.decode('utf-8')
        self.assertNotIn('hreflang=', html)
        self.assertEqual(self.client.get('/es/faq/').status_code, 404)

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
    """A version variant only claims to be its own page when it shows
    something the live one does not.

    The picture decides, and it decides almost everywhere. This is a gear
    *appearance* optimizer: two pages carrying identical numbers and a
    different render are two different pages to the people who come here.

        matching on data      after counting the picture
        beta    3796    ->    38
        dofus2   531    ->    530
        touch     48    ->    0
        retro     51    ->    0

    Comparing data alone would have merged 3458 pages into a page showing a
    different item -- every Touch and Retro one among them. Fixtures are found
    in the catalogues rather than written down here, so the tests keep meaning
    something after a game update.
    """

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
        """A variant judged a copy, with its live counterpart. None if there
        is no such item that both versions actually publish."""
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
        """End to end, because a helper agreeing with itself proves nothing.

        Rendered html is compared, so a mistake in resolving the item type --
        which is what picks the picture directory -- cannot hide here.
        """
        pair = self._pair('beta') or self._pair('dofus2')
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
        # It points elsewhere; it is not withdrawn. A reader on that branch
        # still needs the page.
        pair = self._pair('beta') or self._pair('dofus2')
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
        # Every Touch and Retro item matching on data carries its own render,
        # so none of them may be called a copy.
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
    """One page counts as one page, whatever prefixes its url carries.

    Versions were already collapsed. Languages were not, so the same page
    would have split across five rows the moment prefixed urls went live --
    and /es/dofus2/encyclopedia/ was worse: with the version no longer at the
    front, "dofus2" was mistaken for an id.
    """

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
    """A page that is empty unless you are signed in is not content.

    /loadprojects/ was submitted to the sitemap and drew 3795 impressions for
    4 clicks over ninety days: Google ranked, and readers found nothing. Its
    per-project siblings are already disallowed in robots.txt; the plural
    escaped because the rule reads */loadproject/ and this one carries an s.
    """

    def test_the_project_list_is_not_indexable(self):
        html = self.client.get('/loadprojects/').content.decode('utf-8')
        self.assertIn('noindex', html)

    def test_it_is_no_longer_submitted(self):
        xml = self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        self.assertNotIn('/loadprojects/', xml)

    def test_the_public_landing_is_still_submitted(self):
        # /setup/ is the public "create a project" page and must stay.
        xml = self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        self.assertIn('<loc>https://dofusfashionista.gg/setup/</loc>', xml)
        self.assertEqual(self.client.get('/setup/').status_code, 200)


class SubmittedHubCanonicalIgnoresTheBrowserTests(TestCase):
    """A submitted url must name itself, whatever language the browser asks for.

    Hub pages answer on two urls -- /encyclopedia/ and /es/encyclopedia/ -- and
    the unprefixed one is served in whatever language the reader negotiated. Its
    canonical used to be built from that served language, so a Spanish reader's
    copy of /encyclopedia/ declared /es/encyclopedia/ canonical while the same
    <head> listed /encyclopedia/ as the English alternate and the x-default: a
    submitted url contradicting its own hreflang block.

    EverySubmittedPageIsItsOwnCanonicalTest cannot see this -- it sends no
    Accept-Language, so English stays active and every canonical is
    self-referential. This one varies the header, which is the whole point.
    """

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
        """Whatever the canonical names, the page must be listed under that
        same url in its own alternates."""
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
        """The canonical follows the url; links must keep following the page.

        Fixing one by breaking the other would send a Spanish reader to the
        English hub on the first click -- the very thing the language prefix on
        hub urls exists to prevent.

        The Spanish url is read off the English page's own hreflang block
        rather than spelled out here: an invented slug would test a 404.
        """
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
    """A translated sitemap must not submit another language's url.

    Entity urls carry their language in the slug, so they look unprefixed and
    that is correct. Hub urls carry it in a path prefix, and the monster
    sitemap emitted its hub for every language: /encyclopedia/monsters/ --
    the English one -- appeared in the French, Spanish and Portuguese sitemaps
    as well as its own. The same url submitted four times, telling Google the
    translated sitemaps contain a page they do not.
    """

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
        """Removing it everywhere would drop the English hub entirely: no other
        sitemap submits the unprefixed one."""
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
