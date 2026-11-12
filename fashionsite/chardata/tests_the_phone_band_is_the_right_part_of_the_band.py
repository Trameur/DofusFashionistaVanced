# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Up to 900 px the header band is drawn from a phone band, the right 2212 px of the full band at the same scale and position, so a phone downloads about half the bytes for the same picture."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, chain_of, media_applies, read_css, stylesheet, winning
from fashionistapulp.game_versions import GAME_VERSIONS

THEMES = ('dark', 'light')
CSS = read_css('modern.css')
MODERN = stylesheet('modern.css')
SHEETS = [('home.css', stylesheet('home.css')), ('responsive.css', stylesheet('responsive.css')), ('modern.css', MODERN)]
PHONE_WIDTH = 2212
ROOT = 'html.fm-modern'
BAND = (('html', {}), ('body', {'class': 'body-base'}), ('div', {'class': 'add-banner'}), ('div', {'class': 'everything'}))
FIXED = re.compile(r'(\d+)px')
FOLLOWS_THE_WINDOW = re.compile(r'max\((\d+)px,calc\(100vw \* (\d+) / (\d+)\)\)')


def band_height(width):
    """The height in pixels --fm-band-h gives the band at a window width, read from the root rules of modern.css."""
    found = None
    for rule in MODERN:
        if ROOT in rule['selectors'] and '--fm-band-h' in rule['declarations'] and media_applies(rule['media'], width):
            found = rule['declarations']['--fm-band-h'][0]
    fixed = FIXED.fullmatch(found)
    if fixed:
        return float(fixed.group(1))
    follows = FOLLOWS_THE_WINDOW.fullmatch(found)
    if follows is None:
        raise ValueError('unreadable band height %r' % found)
    return max(float(follows.group(1)), width * float(follows.group(2)) / float(follows.group(3)))


def picture_height(path):
    from PIL import Image
    with Image.open(path) as picture:
        return picture.height


def band_path(version, theme, phone):
    return os.path.join(STATIC, 'bands', 'band_%s_%s%s.webp' % (version, theme, '_m' if phone else ''))


class ThePhoneBandIsDrawnUnder900Tests(SimpleTestCase):

    def phone_block(self):
        return re.search(r'@media \(max-width:900px\)\{((?:\s*html\.fm-modern\.fm-\w+ \.banner\[data-band="\w+"\] a\{[^}]*\})+)\s*\}', CSS).group(1)

    def test_every_version_and_theme_has_a_phone_band_drawn_under_900(self):
        block = self.phone_block()
        for version in GAME_VERSIONS:
            for theme in THEMES:
                with self.subTest(version=version, theme=theme):
                    rule = 'html.fm-modern.fm-%s .banner[data-band="%s"] a{ background-image:url("bands/band_%s_%s_m.webp"); }' % (theme, version, version, theme)
                    self.assertIn(rule, block)
                    self.assertTrue(os.path.isfile(band_path(version, theme, True)))

    def test_the_phone_band_rules_come_after_the_wide_band_rules(self):
        self.assertGreater(CSS.index('bands/band_dofus3_dark_m.webp'), CSS.index('bands/band_wakfu_light.webp'))

    def test_the_band_link_fills_the_banner_which_takes_the_band_height(self):
        banner = chain_of(BAND, 'div', {'class': 'banner', 'data-band': 'dofus3'}, ('fm-modern', 'fm-light'))
        link = chain_of(BAND + (('div', {'class': 'banner', 'data-band': 'dofus3'}),), 'a', {}, ('fm-modern', 'fm-light'))
        for width in (320, 375, 390, 440, 619, 620, 760, 761, 900):
            with self.subTest(width=width):
                self.assertEqual('var(--fm-band-h)', winning(SHEETS, banner, 'height', width)[0])
                self.assertEqual('100%', winning(SHEETS, link, 'height', width)[0])
                self.assertEqual('100%', winning(SHEETS, link, 'width', width)[0])
                self.assertEqual('cover', winning(SHEETS, link, 'background-size', width)[0])

    def test_the_phone_band_is_wide_enough_for_every_phone_view(self):
        full_height = picture_height(band_path('dofus3', 'dark', True))
        for width in range(320, 901):
            with self.subTest(width=width):
                self.assertLessEqual(width / (band_height(width) / full_height), PHONE_WIDTH + 1e-6)


class ThePhoneBandIsTheRightEndOfTheBandTests(SimpleTestCase):

    def test_the_phone_band_shows_the_right_end_of_the_full_band(self):
        from PIL import Image, ImageChops, ImageStat
        for version in GAME_VERSIONS:
            for theme in THEMES:
                with self.subTest(version=version, theme=theme):
                    full = Image.open(band_path(version, theme, False)).convert('RGB')
                    phone = Image.open(band_path(version, theme, True)).convert('RGB')
                    self.assertEqual((PHONE_WIDTH, full.height), phone.size)
                    right = full.crop((full.width - PHONE_WIDTH, 0, full.width, full.height))
                    mean = sum(ImageStat.Stat(ImageChops.difference(right, phone)).mean) / 3.0
                    self.assertLess(mean, 2.0, mean)

    def test_the_phone_bands_weigh_less_than_the_full_bands(self):
        for version in GAME_VERSIONS:
            for theme in THEMES:
                with self.subTest(version=version, theme=theme):
                    self.assertLess(os.path.getsize(band_path(version, theme, True)), os.path.getsize(band_path(version, theme, False)))
