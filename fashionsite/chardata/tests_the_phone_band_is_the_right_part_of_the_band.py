# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Up to 900 px the header band is drawn from a phone band, the right 2212 px of the full band at the same scale and position, so a phone downloads about half the bytes for the same picture."""
import os
import re

from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import STATIC, read_css
from fashionistapulp.game_versions import GAME_VERSIONS

THEMES = ('dark', 'light')
CSS = read_css('modern.css')
PHONE_WIDTH = 2212


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

    def test_the_phone_band_is_wide_enough_for_the_widest_phone_view(self):
        rule = re.search(r'@media \(max-width:900px\)\{ html\.fm-modern \.banner\[data-band\] a\{ height:min\((\d+)px,calc\(\(100vw - (\d+)px\) / (\d+)\)\); \} \}', CSS)
        height, gutter, ratio = (int(rule.group(i)) for i in (1, 2, 3))
        full_height = 300
        widest_link = 900 - gutter
        visible = widest_link / (min(height, widest_link / ratio) / full_height)
        self.assertLessEqual(visible, PHONE_WIDTH)


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
