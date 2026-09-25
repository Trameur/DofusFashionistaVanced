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

"""A guide's language comes from its URL slug, not from Accept-Language, which no crawler sends."""

import re

from django.test import TestCase

from chardata import guides_content
from chardata.guides_slugs import GUIDE_SLUGS

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')


class SlugTableTest(TestCase):
    """Guards the slug table: a guide added without its slugs, or two entries claiming one URL."""

    def test_every_guide_has_a_slug_in_every_language(self):
        missing = [
            (key, language)
            for key in guides_content.ordered_slugs()
            for language in LANGUAGES
            if not GUIDE_SLUGS.get(key, {}).get(language)
        ]
        self.assertFalse(
            missing,
            'guides_slugs.py is missing entries: %s' % missing)

    def test_no_two_entries_share_a_slug(self):
        seen = {}
        clashes = []
        for key, per_language in GUIDE_SLUGS.items():
            for language, slug in per_language.items():
                if slug in seen:
                    clashes.append((slug, seen[slug], (key, language)))
                seen[slug] = (key, language)
        self.assertFalse(
            clashes,
            'a slug must name one language, these name two: %s' % clashes)

    def test_the_english_slug_is_the_guide_key(self):
        # the English urls are already indexed, so the table must never redirect them
        for key in guides_content.ordered_slugs():
            self.assertEqual(GUIDE_SLUGS[key]['en'], key)

    def test_slugs_are_url_safe(self):
        for key, per_language in GUIDE_SLUGS.items():
            for language, slug in per_language.items():
                self.assertRegex(
                    slug, r'^[a-z0-9]+(?:-[a-z0-9]+)*$',
                    '%s/%s is not a clean slug: %r' % (key, language, slug))

    def test_resolution_round_trips(self):
        for key in guides_content.ordered_slugs():
            for language in LANGUAGES:
                slug = guides_content.slug_for(key, language)
                self.assertEqual(
                    guides_content.resolve_slug(slug), (key, language))

    def test_an_unknown_slug_resolves_to_nothing(self):
        self.assertEqual(guides_content.resolve_slug('not-a-guide'),
                         (None, None))


class GuidePageTest(TestCase):
    """End to end, reproducing a crawler: no Accept-Language, no cookies."""

    KEY = 'lock-and-dodge'

    def _fetch(self, slug):
        response = self.client.get('/guides/%s/' % slug)
        self.assertEqual(response.status_code, 200, slug)
        return response.content.decode('utf-8')

    def test_each_localised_url_serves_its_own_language(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                slug = guides_content.slug_for(self.KEY, language)
                html = self._fetch(slug)
                expected = guides_content.get_guide(
                    self.KEY, language)['title']
                # the title carries the language without depending on a particular sentence
                self.assertIn(expected.split(':')[0][:30], html)

    def test_the_html_lang_attribute_matches_the_url(self):
        # the html lang attribute is read by assistive tech and translation tooling
        for language in LANGUAGES:
            with self.subTest(language=language):
                slug = guides_content.slug_for(self.KEY, language)
                html = self._fetch(slug)
                declared = re.search(r'<html[^>]*lang="([^"]+)"', html)
                self.assertIsNotNone(declared, 'no lang attribute on %s' % slug)
                self.assertEqual(declared.group(1).split('-')[0], language)

    def test_each_url_is_its_own_canonical(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                slug = guides_content.slug_for(self.KEY, language)
                html = self._fetch(slug)
                canonical = re.search(
                    r'<link[^>]*rel="canonical"[^>]*>', html).group(0)
                self.assertIn('/guides/%s/' % slug, canonical)

    def test_hreflang_names_all_five_languages(self):
        html = self._fetch(guides_content.slug_for(self.KEY, 'fr'))
        for language in LANGUAGES:
            self.assertIn('hreflang="%s"' % language, html)

    def test_accept_language_no_longer_decides(self):
        slug = guides_content.slug_for(self.KEY, 'es')
        titles = set()
        for header in ('fr', 'en', 'de', 'pt'):
            response = self.client.get('/guides/%s/' % slug,
                                       HTTP_ACCEPT_LANGUAGE=header)
            titles.add(
                re.search(r'<title>([^<]*)</title>',
                          response.content.decode('utf-8')).group(1))
        self.assertEqual(
            len(titles), 1,
            'the Spanish URL served %d different pages: %s' % (
                len(titles), titles))

    def test_the_english_urls_still_answer(self):
        # Every guide key is a live URL today. None may start 404ing.
        for key in guides_content.ordered_slugs():
            with self.subTest(guide=key):
                self.assertEqual(
                    self.client.get('/guides/%s/' % key).status_code, 200)

    def test_internal_links_stay_in_the_page_language(self):
        # English slugs written into the body must be rewritten on a translated page
        html = self._fetch(guides_content.slug_for(self.KEY, 'fr'))
        body = html.split('<main')[-1] if '<main' in html else html
        # the language selector's own links are excluded, keyed on data-next whatever tag it wears
        body = re.sub(r'<[a-z]+[^>]*data-next[^>]*>', '', body)
        english_only = [
            key for key in guides_content.ordered_slugs()
            if 'href="/guides/%s/"' % key in body
            and guides_content.slug_for(key, 'fr') != key
        ]
        self.assertFalse(
            english_only,
            'French page links to English guide URLs: %s' % english_only)


class GuideSitemapTest(TestCase):

    def test_the_sitemap_submits_every_language(self):
        xml = self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        for language in LANGUAGES:
            slug = guides_content.slug_for('lock-and-dodge', language)
            self.assertIn('/guides/%s/' % slug, xml,
                          '%s guide missing from the sitemap' % language)

    def test_the_sitemap_grew_by_the_translations(self):
        xml = self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        guide_urls = re.findall(r'<loc>[^<]*/guides/([^/<]+)/</loc>', xml)
        distinct = set(guide_urls)
        # 32 guides x 5 languages, minus nothing: every slug is distinct.
        self.assertGreaterEqual(
            len(distinct), 5 * len(guides_content.ordered_slugs()),
            'expected one sitemap entry per guide and language, got %d'
            % len(distinct))


class GetGuideAcceptsEitherNameTest(TestCase):
    """get_guide() must also accept the localised slugs list_guides() hands back."""

    def test_a_localised_slug_is_accepted(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                slug = guides_content.slug_for('lock-and-dodge', language)
                data = guides_content.get_guide(slug, language)
                self.assertIsNotNone(data, slug)
                self.assertEqual(data['key'], 'lock-and-dodge')

    def test_the_key_is_still_accepted(self):
        data = guides_content.get_guide('lock-and-dodge', 'fr')
        self.assertIsNotNone(data)
        self.assertEqual(data['key'], 'lock-and-dodge')

    def test_chaining_list_guides_into_get_guide_works(self):
        for entry in guides_content.list_guides('fr', 'dofus3'):
            self.assertIsNotNone(
                guides_content.get_guide(entry['slug'], 'fr', 'dofus3'),
                entry['slug'])

    def test_an_unknown_name_is_still_none(self):
        self.assertIsNone(guides_content.get_guide('not-a-guide', 'fr'))
