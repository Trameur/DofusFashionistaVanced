# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu switch shows and hides every Wakfu URL, and nothing else on the site moves."""
import re
from html.parser import HTMLParser

from django.core.cache import cache
from django.test import TestCase
from django.urls import URLResolver, get_resolver
from django.utils import translation
from django.utils.translation import gettext

from chardata.served_versions import version_by_prefix
from chardata.wakfu_flag_for_tests import wakfu_flag
from fashionistapulp.game_versions import GAME_VERSIONS, version_keys

HOST = 'https://dofusfashionista.gg'
LANGUAGES = ('', 'fr', 'es', 'pt', 'de')
LANDINGS = ['/%swakfu/' % (language + '/' if language else '') for language in LANGUAGES]
OFF_PAGES = ('/', '/fr/', '/encyclopedia/')
SITEMAP_WAKFU_URL = re.compile(
    r'  <url>\n    <loc>[^<]*/wakfu/[^<]*</loc>\n    <changefreq>[^<]*</changefreq>\n'
    r'    <priority>[^<]*</priority>\n  </url>\n?')


class _Page(HTMLParser):
    """The version selector links and the hreflang alternates of a page."""

    def __init__(self, html):
        super().__init__()
        self.switcher = []
        self.alternates = {}
        self._open = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'version-link' in (attrs.get('class') or '').split():
            self._open = [attrs.get('href'), '']
        if tag == 'link' and attrs.get('rel') == 'alternate' and attrs.get('hreflang'):
            self.alternates[attrs['hreflang']] = attrs.get('href')

    def handle_data(self, data):
        if self._open is not None:
            self._open[1] += data

    def handle_endtag(self, tag):
        if tag == 'a' and self._open is not None:
            self.switcher.append((self._open[0], self._open[1].strip()))
            self._open = None


def _namespaces(patterns, found=None):
    found = set() if found is None else found
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            if pattern.namespace:
                found.add(pattern.namespace)
            _namespaces(pattern.url_patterns, found)
    return found


class TheWakfuFlagHidesAndShowsEveryWakfuUrlTests(TestCase):
    def setUp(self):
        cache.clear()

    def _html(self, path):
        return self.client.get(path).content.decode('utf-8')

    def _sitemaps(self):
        index = self._html('/sitemap.xml')
        paths = ['/' + child.split(HOST + '/', 1)[1]
                 for child in re.findall(r'<loc>([^<]+)</loc>', index)]
        return dict({'/sitemap.xml': index}, **{path: self._html(path) for path in paths})

    def test_with_the_flag_off_every_landing_is_missing(self):
        with wakfu_flag(False):
            for path in LANDINGS:
                with self.subTest(path=path):
                    self.assertEqual(404, self.client.get(path).status_code)

    def test_the_resolver_has_a_wakfu_namespace_only_with_the_flag_on(self):
        with wakfu_flag(False):
            self.assertNotIn('wakfu', _namespaces(get_resolver().url_patterns))
        with wakfu_flag(True):
            self.assertIn('wakfu', _namespaces(get_resolver().url_patterns))

    def test_with_the_flag_off_only_the_dofus_prefixes_are_served(self):
        with wakfu_flag(False):
            self.assertEqual({'beta', 'dofus2', 'touch', 'retro'}, set(version_by_prefix()))

    def test_with_the_flag_off_the_selector_lists_the_dofus_versions(self):
        with wakfu_flag(False):
            response = self.client.get('/')
        self.assertEqual(version_keys(), [key for key, _label in
                                          response.context['active_game_versions']])

    def test_with_the_flag_off_no_page_or_sitemap_names_wakfu(self):
        with wakfu_flag(False):
            for path in OFF_PAGES:
                with self.subTest(path=path):
                    self.assertNotIn('wakfu', self._html(path).lower())
            for path, xml in self._sitemaps().items():
                with self.subTest(path=path):
                    self.assertNotIn('wakfu', xml.lower())

    def test_with_the_flag_on_each_landing_is_the_wakfu_site(self):
        with wakfu_flag(True):
            for path in LANDINGS:
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(200, response.status_code)
                    self.assertEqual('wakfu', response.context['current_game_version'])
                    self.assertEqual(GAME_VERSIONS['wakfu'].label,
                                     response.context['current_game_version_label'])
                    self.assertEqual('Wakfu', response.context['current_game_version_label'])

    def test_with_the_flag_on_the_selector_links_the_wakfu_landing(self):
        with wakfu_flag(True):
            for page, expected in (('/', '/wakfu/'), ('/fr/', '/fr/wakfu/')):
                with self.subTest(page=page):
                    self.assertIn((expected, 'Wakfu'), _Page(self._html(page)).switcher)

    def test_on_a_wakfu_page_the_dofus_3_link_leaves_wakfu(self):
        with wakfu_flag(True):
            for page, expected in (('/wakfu/', '/'), ('/fr/wakfu/', '/fr/')):
                with self.subTest(page=page):
                    self.assertIn((expected, 'Dofus 3'), _Page(self._html(page)).switcher)

    def test_every_selector_link_answers_something(self):
        with wakfu_flag(True):
            for page in ('/', '/encyclopedia/', '/encyclopedia/sets/', '/wakfu/'):
                for href, label in _Page(self._html(page)).switcher:
                    with self.subTest(page=page, label=label):
                        self.assertNotEqual(404, self.client.get(href).status_code, href)

    def test_the_sitemap_gains_the_wakfu_landings_and_nothing_else(self):
        with wakfu_flag(False):
            off = self._sitemaps()
        cache.clear()
        with wakfu_flag(True):
            on = self._sitemaps()
        self.assertEqual(set(off), set(on))
        pages = on['/sitemap-pages.xml']
        for prefix in ('', '/fr', '/es', '/pt'):
            self.assertIn('<loc>%s%s/wakfu/</loc>' % (HOST, prefix), pages)
        self.assertNotIn('/de/wakfu/', pages)
        for path, xml in on.items():
            with self.subTest(path=path):
                self.assertEqual(off[path], SITEMAP_WAKFU_URL.sub('', xml))

    def test_the_landing_names_its_language_alternates(self):
        with wakfu_flag(True):
            alternates = _Page(self._html('/wakfu/')).alternates
        expected = {'en': HOST + '/wakfu/', 'fr': HOST + '/fr/wakfu/',
                    'es': HOST + '/es/wakfu/', 'pt': HOST + '/pt/wakfu/',
                    'de': HOST + '/de/wakfu/', 'x-default': HOST + '/wakfu/'}
        self.assertEqual(expected, alternates)

    def test_the_landing_title_is_translated_in_each_site_language(self):
        english = 'Wakfu Build Optimizer'
        with wakfu_flag(True):
            for language in ('fr', 'es', 'pt', 'de'):
                with self.subTest(language=language):
                    with translation.override(language):
                        translated = gettext(english)
                    self.assertNotEqual(english, translated)
                    html = self._html('/%s/wakfu/' % language)
                    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S).group(1)
                    self.assertEqual(translated, h1.strip())

    def test_robots_are_the_same_bytes_in_both_states(self):
        with wakfu_flag(False):
            off = self.client.get('/robots.txt').content
        with wakfu_flag(True):
            on = self.client.get('/robots.txt').content
        self.assertEqual(off, on)

    def test_the_dofus_encyclopedia_links_no_wakfu_encyclopedia(self):
        with wakfu_flag(True):
            html = self._html('/encyclopedia/')
        self.assertNotIn('/wakfu/encyclopedia', html)
