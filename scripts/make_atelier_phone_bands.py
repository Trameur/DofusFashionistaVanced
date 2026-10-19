# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Cut the phone bands: the right 2212 px of each shipped header band, saved again as WebP quality 86.

Usage: py scripts/make_atelier_phone_bands.py
Up to 900 px the band link is at most 874 px wide and 120 px high, so `cover` shows at most 2185 of the 300 px band's
source columns, anchored right (see the phone band rules of modern.css and tests_the_phone_band_is_the_right_part_of_the_band).
"""
import os

from PIL import Image

BANDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fashionsite', 'chardata', 'static', 'chardata', 'bands')
WIDTH = 2212
QUALITY = 86

for version in ('dofus3', 'beta', 'dofus2', 'retro', 'touch', 'wakfu'):
    for theme in ('dark', 'light'):
        name = 'band_%s_%s' % (version, theme)
        band = Image.open(os.path.join(BANDS, name + '.webp')).convert('RGB')
        band.crop((band.width - WIDTH, 0, band.width, band.height)).save(
            os.path.join(BANDS, name + '_m.webp'), 'WEBP', quality=QUALITY, method=6)
