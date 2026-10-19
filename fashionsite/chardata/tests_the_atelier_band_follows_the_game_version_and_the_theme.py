# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The modern header band is the picture of the current game version in the current theme, every registered version and both themes name a file that exists, and the classic header keeps its own markup."""
import os
import re

from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.context_processors import band_version, game_version
from chardata.tests_the_setup_stylesheet_support import STATIC, read_css
from fashionistapulp.game_versions import GAME_VERSIONS

THEMES = ('dark', 'light')
CSS = read_css('modern.css')
CLASSIC_IMAGES = {
    'beta': 'fashionista_banner_fading_beta.webp',
    'dofus2': 'fashionista_banner.jpg',
    'retro': 'fashionista_banner.jpg',
    'dofus3': 'fashionista_banner_fading.webp',
    'touch': 'fashionista_banner_fading.webp',
}


def band_file(version, theme):
    return os.path.join(STATIC, 'bands', 'band_%s_%s.webp' % (version, theme))


def context_for(version):
    request = RequestFactory().get('/')
    request.game_version = version
    return game_version(request)


class TheBandFilesTests(SimpleTestCase):

    def test_every_registered_version_has_a_band_in_both_themes(self):
        for version in GAME_VERSIONS:
            for theme in THEMES:
                with self.subTest(version=version, theme=theme):
                    path = band_file(version, theme)
                    self.assertTrue(os.path.isfile(path))
                    with open(path, 'rb') as handle:
                        head = handle.read(12)
                    self.assertEqual((b'RIFF', b'WEBP'), (head[:4], head[8:12]))

    def test_every_registered_version_selects_its_own_band(self):
        for version in GAME_VERSIONS:
            with self.subTest(version=version):
                self.assertEqual(version, band_version(version))
                self.assertEqual(version, context_for(version)['game_band'])

    def test_a_version_without_a_band_falls_back_to_dofus3(self):
        self.assertEqual('dofus3', band_version('unknown'))
        self.assertTrue(os.path.isfile(band_file(band_version('unknown'), 'dark')))


class TheStylesheetNamesEveryBandTests(SimpleTestCase):

    def test_each_band_is_drawn_for_its_version_under_its_theme(self):
        for version in GAME_VERSIONS:
            for theme in THEMES:
                with self.subTest(version=version, theme=theme):
                    selector = 'html.fm-modern.fm-%s .banner[data-band="%s"] a{' % (theme, version)
                    start = CSS.index(selector)
                    rule = CSS[start:CSS.index('}', start)]
                    self.assertIn('url("bands/band_%s_%s.webp")' % (version, theme), rule)

    def test_every_band_url_in_the_stylesheet_is_an_existing_file(self):
        urls = re.findall(r'url\("(bands/[^"]+)"\)', CSS)
        self.assertEqual(len(GAME_VERSIONS) * len(THEMES), len([url for url in urls if not url.endswith('_m.webp')]))
        self.assertEqual(len(GAME_VERSIONS) * len(THEMES), len([url for url in urls if url.endswith('_m.webp')]))
        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(os.path.isfile(os.path.join(STATIC, url)))

    def test_the_band_stays_covering_and_anchored_to_the_right(self):
        rule = re.search(r'html\.fm-modern \.banner\[data-band\] a\{([^}]*)\}', CSS).group(1)
        self.assertIn('background-size:cover', rule)
        self.assertIn('background-position:right center', rule)

    def test_the_finished_band_is_not_dimmed_by_the_banner_gradient(self):
        self.assertIn('html.fm-modern .banner[data-band]::after{ content:none; }', CSS)


class TheHeaderMarkupTests(TestCase):

    def header(self, path):
        html = self.client.get(path).content.decode()
        return re.search(r'<div[^>]*class="banner".*?</a>', html, re.S).group(0)

    def test_the_modern_band_carries_the_version_of_the_page(self):
        for path, version in (('/', 'dofus3'), ('/beta/', 'beta'), ('/dofus2/', 'dofus2'), ('/retro/', 'retro'), ('/touch/', 'touch')):
            with self.subTest(path=path):
                self.assertIn('data-band="%s"' % version, self.header(path))

    def test_the_classic_picture_and_link_are_the_ones_they_were(self):
        for path, version in (('/', 'dofus3'), ('/beta/', 'beta'), ('/dofus2/', 'dofus2'), ('/retro/', 'retro'), ('/touch/', 'touch')):
            with self.subTest(path=path):
                header = self.header(path)
                self.assertIn('/static/chardata/%s"' % CLASSIC_IMAGES[version], header)
                self.assertEqual(1, re.sub(r'<noscript>.*?</noscript>', '', header, flags=re.S).count('<img'))
                self.assertIn('alt="Dofus Fashionista"', header)
