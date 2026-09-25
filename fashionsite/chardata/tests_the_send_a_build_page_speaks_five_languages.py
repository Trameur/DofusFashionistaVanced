# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The developer page for sending builds renders in five languages, is linked where developers look, and its examples are valid builds."""

import html
import html.parser
import json
import unittest

from django.core.cache import cache
from django.test import TestCase

from chardata import fashionista_build
from chardata.management.commands import check_pages

PATH = '/developers/send-a-build/'

TITLES = {
    'en': 'Send a build to Dofus Fashionista',
    'fr': 'Envoyer un build sur Dofus Fashionista',
    'es': 'Enviar un build a Dofus Fashionista',
    'pt': 'Enviar um build para o Dofus Fashionista',
    'de': 'Einen Build an Dofus Fashionista schicken',
}


class _Page(html.parser.HTMLParser):
    """The examples' code blocks, the h1 and every link."""

    def __init__(self):
        super().__init__()
        self.examples = {}
        self.h1 = ''
        self.links = []
        self.canonicals = []
        self.scrollers = []
        self.ids = set()
        self.answer = ''
        self._example = None
        self._in_answer = False
        self._in_h1 = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs.get('href'))
        if (tag == 'pre' and 'dev-wrap' not in (attrs.get('class') or '')
                or tag == 'div' and 'dev-table-wrap' in (attrs.get('class') or '')):
            self.scrollers.append(attrs)
        if tag == 'pre' and attrs.get('aria-labelledby') == 'answer-title':
            self._in_answer = True
        if tag == 'code' and 'dev-example' in (attrs.get('class') or ''):
            self._example = attrs.get('data-game')
            self.examples[self._example] = ''
        elif tag == 'h1':
            self._in_h1 = True
        elif tag == 'a':
            self.links.append(attrs)

    def handle_endtag(self, tag):
        if tag == 'pre':
            self._in_answer = False
        if tag == 'code':
            self._example = None
        elif tag == 'h1':
            self._in_h1 = False

    def handle_data(self, data):
        if self._in_answer:
            self.answer += data
        if self._example:
            self.examples[self._example] += data
        if self._in_h1:
            self.h1 += data


def _read(page):
    parser = _Page()
    parser.feed(page.content.decode('utf-8'))
    return parser


class ThePageSpeaksEveryLanguageTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_each_language_prefix_serves_the_page_in_that_language(self):
        for language, title in TITLES.items():
            path = PATH if language == 'en' else '/%s%s' % (language, PATH)
            with self.subTest(language=language):
                page = self.client.get(path)
                self.assertEqual(200, page.status_code)
                self.assertContains(page, 'lang="%s"' % language)
                self.assertEqual(title, _read(page).h1.strip())
                canonical = [tag for tag in page.content.decode('utf-8').split('<link')
                             if 'rel="canonical"' in tag.split('>')[0]]
                self.assertEqual(1, len(canonical))
                self.assertIn('href="https://dofusfashionista.gg%s"' % path, canonical[0])

    def test_a_version_prefixed_copy_points_its_canonical_at_the_version_free_page(self):
        page = self.client.get('/fr/retro%s' % PATH)
        self.assertEqual(200, page.status_code)
        self.assertEqual(['https://dofusfashionista.gg/fr%s' % PATH], _read(page).canonicals)

    def test_every_documented_code_is_in_the_page_with_its_translated_meaning(self):
        page = self.client.get('/de%s' % PATH)
        for code, _text in fashionista_build.ERRORS + fashionista_build.WARNINGS:
            self.assertContains(page, '<code>%s</code>' % code)
        self.assertContains(page, 'Keiner dieser Gegenstände ist in unserem Katalog für dieses Spiel.')

    def test_every_block_that_scrolls_sideways_takes_the_focus_and_is_named(self):
        page = _read(self.client.get('/de%s' % PATH))
        self.assertGreater(len(page.scrollers), 8)
        for attrs in page.scrollers:
            with self.subTest(attrs=attrs):
                self.assertEqual('0', attrs.get('tabindex'))
                self.assertIn(attrs.get('aria-labelledby'), page.ids)

    def test_the_checker_on_the_page_sends_the_same_cookies_as_the_page(self):
        body = self.client.get(PATH).content.decode('utf-8')
        self.assertIn("credentials: 'same-origin'", body)
        self.assertNotIn("credentials: 'omit'", body)

    def test_the_server_section_shows_a_real_answer_and_how_to_post_it(self):
        page = self.client.get('/fr%s' % PATH)
        self.assertContains(page, '/api/v1/import/validate/?lang=fr')
        self.assertContains(page, '--data-binary @build.json')
        answer = json.loads(html.unescape(_read(page).answer))
        self.assertEqual((True, [], 0, 0), (answer['valid'], answer['errors'],
                                            answer['errors_omitted'], answer['warnings_omitted']))

    def test_the_code_samples_stay_in_english_in_every_language(self):
        for language in ('fr', 'pt'):
            page = self.client.get('/%s%s' % (language, PATH))
            self.assertContains(page, 'Open on Dofus Fashionista')
            self.assertContains(page, '<code>back_url</code>')


class ThePageIsWhereDevelopersLookTests(TestCase):

    def test_the_import_page_links_it_in_every_language(self):
        for language in TITLES:
            prefix = '' if language == 'en' else '/' + language
            with self.subTest(language=language):
                page = self.client.get('%s/import/text/' % prefix)
                hrefs = [link.get('href') for link in _read(page).links]
                self.assertIn('%s%s' % (prefix, PATH), hrefs)

    def test_the_link_is_there_even_where_no_partner_site_is_read(self):
        from django.test import override_settings
        with override_settings(BUILD_SITES_ENABLED=()):
            page = self.client.get('/dofus2/import/text/', HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(page, 'Your site? Send builds to Dofus Fashionista')

    def test_the_sitemap_and_the_page_walker_reach_it(self):
        pages = self.client.get('/sitemap-pages.xml').content.decode('utf-8')
        self.assertIn('<loc>https://dofusfashionista.gg%s</loc>' % PATH, pages)
        self.assertIn(PATH, check_pages.PATHS)

    def test_the_api_root_points_to_it(self):
        self.assertEqual('https://dofusfashionista.gg%s' % PATH,
                         self.client.get('/api/v1/').json()['send_a_build'])


class TheExamplesAreValidBuildsTests(TestCase):

    def setUp(self):
        cache.clear()

    def _examples(self):
        examples = _read(self.client.get(PATH)).examples
        self.assertEqual({'dofus3', 'retro'}, set(examples))
        return {game: json.loads(html.unescape(text)) for game, text in examples.items()}

    def test_each_example_passes_the_validator_with_every_item_found(self):
        for game, payload in self._examples().items():
            with self.subTest(game=game):
                self.assertEqual(game, payload['game'])
                answer = fashionista_build.report(payload)
                self.assertTrue(answer['valid'], answer['errors'])
                self.assertEqual([], answer['warnings'])
                self.assertTrue(all(piece['found'] for piece in answer['items']))

    def test_each_example_validates_against_the_published_schema(self):
        try:
            import jsonschema
        except ImportError:
            raise unittest.SkipTest('jsonschema not installed')
        schema = self.client.get(fashionista_build.SCHEMA_PATH).json()
        for game, payload in self._examples().items():
            with self.subTest(game=game):
                jsonschema.validate(payload, schema,
                                    cls=jsonschema.Draft202012Validator)

    def test_the_example_links_open_their_preview(self):
        links = [link['href'] for link in _read(self.client.get(PATH)).links
                 if '/import/build/?data=' in link.get('href', '')]
        self.assertEqual(2, len(links))
        for href in links:
            with self.subTest(href=href[:40]):
                page = self.client.get(href, HTTP_ACCEPT_LANGUAGE='en')
                self.assertContains(page, 'Build received: Example build')
