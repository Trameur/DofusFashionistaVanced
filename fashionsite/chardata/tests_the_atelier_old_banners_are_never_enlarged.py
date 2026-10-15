# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The 1024px banners of Dofus 2 and Retro are never drawn wider than they are, the wide banner covers the band, both sit on a band coloured by tokens, and the class illustration is anchored to the right."""
import io
import os

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, chain_of, declared, stylesheet, winning

MODERN = stylesheet('modern.css')
SHEETS = [('home.css', stylesheet('home.css')), ('responsive.css', stylesheet('responsive.css')), ('modern.css', MODERN)]
ANCESTORS = (('html', {}), ('body', {'class': 'body-base'}), ('div', {'class': 'add-banner'}), ('div', {'class': 'everything'}),
             ('div', {'class': 'banner'}), ('a', {}))
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'chardata', 'base.html')
JPG = {'width': '1024', 'height': '200'}
WEBP = {'width': '2560', 'height': '500'}


def picture(attrs, width):
    return lambda prop: winning(SHEETS, chain_of(ANCESTORS, 'img', attrs, ('fm-modern', 'fm-light')), prop, width)


def jpeg_size(data):
    at = 2
    while at < len(data):
        marker = data[at + 1]
        length = int.from_bytes(data[at + 2:at + 4], 'big')
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[at + 7:at + 9], 'big'), int.from_bytes(data[at + 5:at + 7], 'big')
        at += 2 + length
    raise ValueError('no frame header')


def markup():
    with io.open(TEMPLATE, encoding='utf-8') as handle:
        return handle.read()


class TheOldBannersAreNeverEnlargedTests(SimpleTestCase):

    def test_the_template_gives_each_banner_the_size_the_selectors_assume(self):
        self.assertRegex(markup(), r'fashionista_banner\.jpg" %\}"[^>]*width="1024" height="200"')
        self.assertRegex(markup(), r'fashionista_banner_fading\.webp" %\}"[^>]*width="2560" height="500"')

    def test_from_901_the_jpg_has_its_natural_width_as_a_ceiling_and_no_stretch(self):
        for width in (901, 1280, 1920, 2560):
            with self.subTest(width=width):
                look = picture(JPG, width)
                self.assertEqual('auto', look('width')[0])
                self.assertIn('1024px', look('max-width')[0])
                self.assertEqual('contain', look('object-fit')[0])

    def test_up_to_900_the_jpg_fits_the_window_which_is_narrower_than_the_picture(self):
        for width in (375, 768, 900):
            with self.subTest(width=width):
                self.assertEqual('100%', picture(JPG, width)('max-width')[0])
                self.assertLess(width, 1024)

    def test_the_wide_banner_covers_the_band_instead_of_stretching(self):
        for width in (901, 1920, 2560):
            with self.subTest(width=width):
                look = picture(WEBP, width)
                self.assertEqual('cover', look('object-fit')[0])
                self.assertEqual('100%', look('height')[0])

    def test_the_band_is_coloured_with_atelier_tokens_only(self):
        chain = chain_of(ANCESTORS[:4], 'div', {'class': 'banner'}, ('fm-modern', 'fm-light'))
        background = winning(SHEETS, chain, 'background', 1920)[0]
        self.assertIn('var(--fm-bg-2)', background)
        self.assertIn('var(--fm-surface-3)', background)
        self.assertNotRegex(background, r'#[0-9a-fA-F]{3,6}|rgba?\(')

    def test_the_class_illustration_is_anchored_to_the_right_of_the_band_from_901_up(self):
        chain = chain_of(ANCESTORS[:4], 'div', {'class': 'char-overlay'}, ('fm-modern', 'fm-light'))
        self.assertEqual('auto', winning(SHEETS, chain, 'left', 901)[0])
        self.assertEqual('0', winning(SHEETS, chain, 'right', 1920)[0])
        self.assertEqual('0', winning(SHEETS, chain, 'left', 900)[0])

    def test_the_illustration_still_hides_on_phones_and_cannot_swallow_a_click(self):
        chain = chain_of(ANCESTORS[:4], 'div', {'class': 'char-overlay'}, ('fm-modern', 'fm-light'))
        self.assertEqual('none', winning(SHEETS, chain, 'display', 900)[0])
        self.assertEqual('block', winning(SHEETS, chain, 'display', 901)[0])
        self.assertEqual('none', declared(MODERN, 'html.fm-modern .char-overlay', 'pointer-events')[0])

    def test_the_banner_files_are_the_pictures_the_selectors_assume(self):
        with io.open(os.path.join(STATIC, 'fashionista_banner.jpg'), 'rb') as handle:
            data = handle.read()
        self.assertEqual((1024, 200), jpeg_size(data))
        with io.open(os.path.join(STATIC, 'fashionista_banner_fading.webp'), 'rb') as handle:
            head = handle.read(32)
        self.assertEqual((b'RIFF', b'WEBP'), (head[:4], head[8:12]))
