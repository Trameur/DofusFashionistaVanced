# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The 1024px banners of Dofus 2 and Retro are never drawn wider than they are, the wide banner covers the band, both sit on a band coloured by a token that is the same in both themes, and the class illustration never shows in the modern design so it cannot swallow a click on the band."""
import io
import os

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, chain_of, stylesheet, winning

MODERN = stylesheet('modern.css')
NAV = stylesheet('modern-nav.css')
SHEETS = [('home.css', stylesheet('home.css')), ('responsive.css', stylesheet('responsive.css')), ('modern.css', MODERN),
          ('modern-nav.css', NAV)]
ANCESTORS = (('html', {}), ('body', {'class': 'body-base'}), ('div', {'class': 'add-banner'}), ('div', {'class': 'everything'}),
             ('div', {'class': 'banner', 'data-band': 'dofus2'}), ('a', {}))
THEMES = (('fm-modern', 'fm-light'), ('fm-modern', 'fm-dark'))
WIDTHS = (375, 768, 900, 901, 1280, 1920, 2560)
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'base.html')
JPG = {'width': '1024', 'height': '200'}
WEBP = {'width': '2560', 'height': '500'}


def picture(attrs, width, classes=THEMES[0]):
    return lambda prop: winning(SHEETS, chain_of(ANCESTORS, 'img', attrs, classes), prop, width)


def jpeg_size(data):
    at = 2
    while at < len(data):
        marker = data[at + 1]
        length = int.from_bytes(data[at + 2:at + 4], 'big')
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[at + 7:at + 9], 'big'), int.from_bytes(data[at + 5:at + 7], 'big')
        at += 2 + length
    raise ValueError('no frame header')


def pseudo_sheets(kind):
    return [(name, [dict(rule, selectors=[selector[:-len(kind)] for selector in rule['selectors'] if selector.endswith(kind)])
                    for rule in rules]) for name, rules in SHEETS]


def markup():
    with io.open(TEMPLATE, encoding='utf-8') as handle:
        return handle.read()


class TheOldBannersAreNeverEnlargedTests(SimpleTestCase):

    def test_the_template_gives_each_banner_the_size_the_selectors_assume(self):
        self.assertRegex(markup(), r'fashionista_banner\.jpg" %\}"[^>]*width="1024" height="200"')
        self.assertRegex(markup(), r'fashionista_banner_fading\.webp" %\}"[^>]*width="2560" height="500"')

    def test_at_every_width_the_jpg_has_its_natural_width_and_the_window_as_ceilings_and_no_stretch(self):
        for classes in THEMES:
            for width in WIDTHS:
                with self.subTest(width=width, classes=classes):
                    look = picture(JPG, width, classes)
                    self.assertEqual('auto', look('width')[0])
                    self.assertEqual('min(100%,1024px)', look('max-width')[0])
                    self.assertEqual('contain', look('object-fit')[0])

    def test_the_wide_banner_covers_the_band_instead_of_stretching(self):
        for width in WIDTHS:
            with self.subTest(width=width):
                look = picture(WEBP, width)
                self.assertEqual('cover', look('object-fit')[0])
                self.assertEqual('100%', look('height')[0])

    def test_the_band_is_coloured_by_one_token_that_is_the_same_in_both_themes(self):
        for classes in THEMES:
            chain = chain_of(ANCESTORS[:4], 'div', {'class': 'banner', 'data-band': 'dofus2'}, classes)
            for width in WIDTHS:
                with self.subTest(classes=classes, width=width):
                    self.assertEqual('var(--fm-band-bg)', winning(SHEETS, chain, 'background', width)[0])
        declared_at = [(rule['selectors'], rule['media'], rule['declarations']['--fm-band-bg'][0])
                       for sheet in (MODERN, NAV) for rule in sheet if '--fm-band-bg' in rule['declarations']]
        self.assertEqual([(['html.fm-modern'], None, '#1a1209')], declared_at)

    def test_the_class_illustration_never_shows_in_the_modern_design_so_it_cannot_swallow_a_click(self):
        for classes in THEMES:
            for parent in (ANCESTORS[:4], ANCESTORS[:3]):
                chain = chain_of(parent, 'div', {'class': 'char-overlay'}, classes)
                for width in WIDTHS:
                    with self.subTest(classes=classes, parent=parent[-1], width=width):
                        found = winning(SHEETS, chain, 'display', width)
                        self.assertEqual(('none', 'modern.css'), found[:2])

    def test_nothing_is_drawn_over_the_band_or_its_link(self):
        hosts = ((ANCESTORS[:4], 'div', {'class': 'banner'}), (ANCESTORS[:4], 'div', {'class': 'banner', 'data-band': 'dofus2'}),
                 (ANCESTORS[:5], 'a', {}))
        for classes in THEMES:
            for parent, tag, attrs in hosts:
                chain = chain_of(parent, tag, attrs, classes)
                for kind in ('::before', '::after'):
                    for width in WIDTHS:
                        with self.subTest(classes=classes, host=(tag, attrs), kind=kind, width=width):
                            found = winning(pseudo_sheets(kind), chain, 'content', width)
                            self.assertIn(None if found is None else found[0], (None, 'none'))

    def test_the_banner_files_are_the_pictures_the_selectors_assume(self):
        with io.open(os.path.join(STATIC, 'fashionista_banner.jpg'), 'rb') as handle:
            data = handle.read()
        self.assertEqual((1024, 200), jpeg_size(data))
        with io.open(os.path.join(STATIC, 'fashionista_banner_fading.webp'), 'rb') as handle:
            head = handle.read(32)
        self.assertEqual((b'RIFF', b'WEBP'), (head[:4], head[8:12]))
