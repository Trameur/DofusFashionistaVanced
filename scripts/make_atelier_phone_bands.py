# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Cut the phone bands from the shipped header bands.

Usage: py scripts/make_atelier_phone_bands.py [--bands-dir DIR]

Every version of the registry is cut, staged ones included. With --bands-dir the cuts read and write DIR instead of the site's bands folder.

band_<version>_<theme>_m.webp (tablets, 761 to 900 px): the right 2212 px of the header band, WebP quality 86. Up to 900 px the band link is at
most 874 px wide and 120 px high, so `cover` shows at most 2185 of the 300 px band's source columns, anchored right.

band_<version>_<theme>_s.webp (phones, up to 760 px): the game scene that lies left of the wordmark in the header band, followed by the
wordmark layer of the theme (scripts/atelier_band_wordmarks, the Gabriola wordmark of the header bands) pasted small at the right. Only
pixels of the header band and of the wordmark layer are used, scaled and composited, nothing is drawn.
"""
import importlib.util
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BANDS = os.path.join(HERE, '..', 'fashionsite', 'chardata', 'static', 'chardata', 'bands')
WORDMARKS = os.path.join(HERE, 'atelier_band_wordmarks')
WORDMARK_STYLE = {'dark': 'brakmar', 'light': 'bonta'}
WIDTH = 2212
QUALITY = 86
SCENE_END = 2040
SMALL_WIDTH = 1400
INK_BOX = (26, 24, 1338, 199)
INK_WIDTH = 610
MARGIN_RIGHT = 30
CENTER_Y = 0.66
REGISTRY = os.path.join(HERE, '..', 'fashionistapulp', 'fashionistapulp', 'game_versions.py')


def registry_versions():
    """Every key of the version registry, staged ones included, in page order."""
    spec = importlib.util.spec_from_file_location('band_game_versions', REGISTRY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.version_keys(include_experimental=True)


def cut(band, theme):
    """The tablet cut and the phone cut of one header band, as images."""
    tablet = band.crop((band.width - WIDTH, 0, band.width, band.height))
    scene = band.crop((SCENE_END - SMALL_WIDTH, 0, SCENE_END, band.height))
    mark = Image.open(os.path.join(WORDMARKS, 'wordmark_%s.png' % WORDMARK_STYLE[theme])).convert('RGBA')
    scale = INK_WIDTH / float(INK_BOX[2] - INK_BOX[0])
    mark = mark.resize((round(mark.width * scale), round(mark.height * scale)), Image.LANCZOS)
    left = SMALL_WIDTH - MARGIN_RIGHT - round(INK_BOX[2] * scale)
    top = round(band.height * CENTER_Y - (INK_BOX[1] + INK_BOX[3]) * scale / 2)
    scene.paste(mark, (left, top), mark)
    return tablet, scene


def main(bands_dir):
    for version in registry_versions():
        for theme in ('dark', 'light'):
            name = 'band_%s_%s' % (version, theme)
            band = Image.open(os.path.join(bands_dir, name + '.webp')).convert('RGB')
            tablet, phone = cut(band, theme)
            tablet.save(os.path.join(bands_dir, name + '_m.webp'), 'WEBP', quality=QUALITY, method=6)
            phone.save(os.path.join(bands_dir, name + '_s.webp'), 'WEBP', quality=QUALITY, method=6)


if __name__ == '__main__':
    main(os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--bands-dir' else BANDS)

