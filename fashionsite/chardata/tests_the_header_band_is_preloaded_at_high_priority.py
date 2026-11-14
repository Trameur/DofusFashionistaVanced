# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The header band is the largest thing a phone waits for, so the head asks for it at high priority (the small phone band up to 760 px, the phone band up to 900 px, the wide band above, the wide one only on the home), no font is preloaded, and the old banner is fetched by the classic design only."""
import io
import os
import re

from django.test import TestCase

from chardata.tests_the_setup_stylesheet_support import STATIC

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata')
VERSIONS = (('/', 'dofus3', 'fashionista_banner_fading.webp'), ('/beta/', 'beta', 'fashionista_banner_fading_beta.webp'),
            ('/dofus2/', 'dofus2', 'fashionista_banner.jpg'), ('/retro/', 'retro', 'fashionista_banner.jpg'),
            ('/touch/', 'touch', 'fashionista_banner_fading.webp'))
SMALL = '(max-width:760px)'
PHONE = '(max-width:900px)'
MIDDLE = '(min-width:761px) and (max-width:900px)'
WIDE = '(min-width:901px)'


def source(name):
    with io.open(os.path.join(TEMPLATES, name), encoding='utf-8') as handle:
        return handle.read()


def preloaded(html):
    """The (url, media) pairs the head script of a page asks for in the modern design."""
    return re.findall(r"p\(k\?'[^']*':'([^']+)','(\([a-z-]+:\d+px\)(?: and \([a-z-]+:\d+px\))?)'\)", html)


class TheModernDesignPreloadsTheBandOfItsVersionTests(TestCase):

    def test_a_page_preloads_the_phone_band_and_the_wide_band_of_its_version_at_high_priority(self):
        for path, version in (('/encyclopedia/', 'dofus3'), ('/beta/encyclopedia/', 'beta')):
            with self.subTest(path=path):
                html = self.client.get(path).content.decode()
                self.assertEqual([('/static/chardata/bands/band_%s_light_s.webp' % version, SMALL),
                                  ('/static/chardata/bands/band_%s_light_m.webp' % version, MIDDLE),
                                  ('/static/chardata/bands/band_%s_light.webp' % version, WIDE)], preloaded(html))
                self.assertIn("l.setAttribute('fetchpriority','high')", html)
                self.assertIn("l.rel='preload';l.as='image'", html)

    def test_the_home_preloads_only_the_wide_band(self):
        html = self.client.get('/').content.decode()
        self.assertEqual([('/static/chardata/bands/band_dofus3_light.webp', WIDE)], preloaded(html))
        self.assertNotIn('_m.webp', html)
        self.assertNotIn('_s.webp', html)

    def test_the_dark_band_is_named_too(self):
        html = self.client.get('/encyclopedia/').content.decode()
        self.assertIn("k?'/static/chardata/bands/band_dofus3_dark_s.webp':", html)
        self.assertIn("k?'/static/chardata/bands/band_dofus3_dark_m.webp':", html)
        self.assertIn("k?'/static/chardata/bands/band_dofus3_dark.webp':", html)

    def test_the_preload_breakpoints_are_the_ones_the_phone_band_rules_use(self):
        with io.open(os.path.join(STATIC, 'modern.css'), encoding='utf-8') as handle:
            css = handle.read()
        block = re.search(r'@media \(max-width:(\d+)px\)\{\n((?:  html\.fm-modern\.fm-\w+ \.banner\[data-band="\w+"\] a\{ background-image:url\("bands/band_\w+_m\.webp"\); \}\n)+)\}', css)
        self.assertIsNotNone(block)
        self.assertEqual('900', block.group(1))
        self.assertEqual(12, block.group(2).count('_m.webp'))
        self.assertEqual('(max-width:%spx)' % block.group(1), PHONE)
        self.assertIn(MIDDLE, source('base.html'))
        self.assertIn(WIDE, source('base.html'))
        self.assertEqual(int(block.group(1)) + 1, int(re.search(r'min-width:(\d+)px', WIDE).group(1)))
        self.assertTrue(MIDDLE.endswith(PHONE))
        with io.open(os.path.join(STATIC, 'modern-nav.css'), encoding='utf-8') as handle:
            nav = handle.read()
        small = re.search(r'@media \(max-width:(\d+)px\)\{\n((?:  html\.fm-modern\.fm-\w+ \.banner\[data-band="\w+"\] a\{ background-image:url\("bands/band_\w+_s\.webp"\);[^}]*\}\n)+)\}', nav)
        self.assertIsNotNone(small)
        self.assertEqual(12, small.group(2).count('_s.webp'))
        self.assertEqual('(max-width:%spx)' % small.group(1), SMALL)
        self.assertIn(SMALL, source('base.html'))
        self.assertEqual(int(small.group(1)) + 1, int(re.search(r'min-width:(\d+)px', MIDDLE).group(1)))


class TheClassicDesignKeepsItsOwnBannerTests(TestCase):

    def header(self, path):
        html = self.client.get(path).content.decode()
        return html, re.search(r'<div[^>]*class="banner".*?</a>', html, re.S).group(0)

    def test_classic_preloads_the_banner_its_img_shows(self):
        for path, _, picture in VERSIONS:
            with self.subTest(path=path):
                html, header = self.header(path)
                preload = re.search(r"if\(!h\.classList\.contains\('fm-modern'\)\)\{p\('([^']+)'\);return;\}", html).group(1)
                self.assertEqual('/static/chardata/%s' % picture, preload)
                self.assertEqual(preload, re.search(r'data-fm-src="([^"]+)"', header).group(1))

    def test_the_old_banner_waits_for_the_classic_design(self):
        for path, _, _ in VERSIONS:
            with self.subTest(path=path):
                _, header = self.header(path)
                self.assertIn('data-fm-src="', header)
                self.assertNotRegex(re.sub(r'<noscript>.*?</noscript>', '', header), r'<img[^>]* src=')

    def test_a_visitor_without_scripts_still_sees_the_banner(self):
        for path, _, picture in VERSIONS:
            with self.subTest(path=path):
                html, header = self.header(path)
                fallback = re.search(r'<noscript>(<img[^>]*>)</noscript>', header).group(1)
                self.assertIn('src="/static/chardata/%s"' % picture, fallback)
                self.assertIn('alt="Dofus Fashionista"', fallback)
                self.assertRegex(fallback, r'width="\d+"')
                self.assertRegex(fallback, r'height="\d+"')
                self.assertRegex(header, r'<a [^>]*>\s*<img[^>]*data-fm-src.*?<noscript><img.*?</a>')
                self.assertIn('<noscript><style>.banner img[data-fm-src]{display:none}</style></noscript>', html)

    def test_classic_and_a_reload_after_the_switch_give_the_banner_its_picture(self):
        base = source('base.html')
        after_banner = base[base.index('<div class="char-overlay"') - 400:base.index('<div class="char-overlay"')]
        self.assertIn("contains('fm-modern'))return;", after_banner)
        self.assertIn("i.src=i.getAttribute('data-fm-src')", after_banner)
        toggle = re.search(r'function fmToggleDesign\(\)\{.*?\}\n', base, re.S).group(0)
        self.assertIn("location.reload()", toggle)


class NoFontIsPreloadedTests(TestCase):

    def test_base_html_preloads_no_font(self):
        base = source('base.html')
        self.assertNotRegex(base, r"as\s*=\s*['\"]?font")
        self.assertNotIn(".woff2", base)
        html = self.client.get('/').content.decode()
        self.assertNotIn('.woff2', html)
