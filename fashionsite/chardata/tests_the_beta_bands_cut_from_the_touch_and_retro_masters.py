# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Touch Beta and Retro Beta bands keep the scene of their master and change only the label, and every cut of a band comes from one function."""
import importlib.util
import os
import unittest

from django.test import SimpleTestCase

from fashionistapulp.game_versions import version_keys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
BANDS = os.path.join(HERE, 'static', 'chardata', 'bands')
MASTER = {'touchbeta': 'touch', 'retrobeta': 'retro'}
SIZES = {'': (3476, 300), '_m': (2212, 300), '_s': (1400, 300)}
LABEL_LEFT = 2900
THEMES = ('dark', 'light')


def beta_folder():
    """The folder holding the beta bands: the shipped bands, or the one named by FASHIONISTA_BETA_BANDS, or None."""
    named = os.environ.get('FASHIONISTA_BETA_BANDS')
    for folder in (BANDS, named):
        if folder and os.path.isfile(os.path.join(folder, 'band_touchbeta_dark.webp')):
            return folder
    return None


KEPT = beta_folder()


def cutter():
    """The phone band cutter script, loaded by file path."""
    spec = importlib.util.spec_from_file_location('make_atelier_phone_bands', os.path.join(ROOT, 'scripts', 'make_atelier_phone_bands.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TheBandCutterTests(SimpleTestCase):

    def test_the_cutter_cuts_every_version_of_the_registry_staged_ones_included(self):
        self.assertEqual(version_keys(include_experimental=True), cutter().registry_versions())

    def test_the_tablet_cut_is_the_right_end_and_the_phone_cut_is_scene_plus_wordmark(self):
        from PIL import Image, ImageChops, ImageStat
        module = cutter()
        full = Image.open(os.path.join(BANDS, 'band_beta_dark.webp')).convert('RGB')
        for theme in THEMES:
            with self.subTest(theme=theme):
                tablet, phone = module.cut(full, theme)
                self.assertEqual(SIZES['_m'], tablet.size)
                self.assertEqual(SIZES['_s'], phone.size)
                self.assertEqual(0, sum(ImageStat.Stat(ImageChops.difference(tablet, full.crop((full.width - 2212, 0, full.width, 300)))).sum))
                scene = full.crop((module.SCENE_END - module.SMALL_WIDTH, 0, module.SCENE_END, 300))
                left = ImageChops.difference(phone.crop((0, 0, 300, 300)), scene.crop((0, 0, 300, 300)))
                self.assertEqual(0, sum(ImageStat.Stat(left).sum))

    def test_the_cuts_of_a_shipped_band_are_the_shipped_cuts(self):
        from PIL import Image, ImageChops, ImageStat
        module = cutter()
        for theme in THEMES:
            with self.subTest(theme=theme):
                full = Image.open(os.path.join(BANDS, 'band_touch_%s.webp' % theme)).convert('RGB')
                _, phone = module.cut(full, theme)
                shipped = Image.open(os.path.join(BANDS, 'band_touch_%s_s.webp' % theme)).convert('RGB')
                self.assertLess(sum(ImageStat.Stat(ImageChops.difference(phone, shipped)).mean) / 3.0, 3.0)


@unittest.skipUnless(KEPT, 'the beta bands are neither shipped nor named by FASHIONISTA_BETA_BANDS')
class TheBetaBandsOfTheTouchAndRetroMastersTests(SimpleTestCase):

    def path(self, key, theme, suffix):
        return os.path.join(KEPT, 'band_%s_%s%s.webp' % (key, theme, suffix))

    def test_the_twelve_files_exist_at_their_three_sizes(self):
        from PIL import Image
        for key in MASTER:
            for theme in THEMES:
                for suffix, size in SIZES.items():
                    with self.subTest(key=key, theme=theme, suffix=suffix):
                        self.assertEqual(size, Image.open(self.path(key, theme, suffix)).size)

    def test_the_scene_and_scissors_left_of_the_label_are_the_masters_pixels(self):
        from PIL import Image, ImageChops, ImageStat
        for key, master in MASTER.items():
            for theme in THEMES:
                with self.subTest(key=key, theme=theme):
                    beta = Image.open(self.path(key, theme, '')).convert('RGB').crop((0, 0, LABEL_LEFT, 300))
                    shipped = Image.open(os.path.join(BANDS, 'band_%s_%s.webp' % (master, theme))).convert('RGB').crop((0, 0, LABEL_LEFT, 300))
                    self.assertLess(sum(ImageStat.Stat(ImageChops.difference(beta, shipped)).mean) / 3.0, 3.0)

    def test_the_label_area_differs_from_the_master_label(self):
        from PIL import Image, ImageChops, ImageStat
        box = (LABEL_LEFT, 215, 3360, 285)
        for key, master in MASTER.items():
            for theme in THEMES:
                with self.subTest(key=key, theme=theme):
                    beta = Image.open(self.path(key, theme, '')).convert('RGB').crop(box)
                    shipped = Image.open(os.path.join(BANDS, 'band_%s_%s.webp' % (master, theme))).convert('RGB').crop(box)
                    self.assertGreater(sum(ImageStat.Stat(ImageChops.difference(beta, shipped)).mean) / 3.0, 2.0)

    def test_the_tablet_and_phone_cuts_come_from_the_full_band(self):
        from PIL import Image, ImageChops, ImageStat
        module = cutter()
        for key in MASTER:
            for theme in THEMES:
                with self.subTest(key=key, theme=theme):
                    full = Image.open(self.path(key, theme, '')).convert('RGB')
                    tablet, phone = module.cut(full, theme)
                    for image, suffix in ((tablet, '_m'), (phone, '_s')):
                        kept = Image.open(self.path(key, theme, suffix)).convert('RGB')
                        self.assertLess(sum(ImageStat.Stat(ImageChops.difference(image, kept)).mean) / 3.0, 3.0)

    def test_the_phone_cut_of_a_beta_band_has_the_master_scene_left_of_the_wordmark(self):
        from PIL import Image, ImageChops, ImageStat
        for key, master in MASTER.items():
            for theme in THEMES:
                with self.subTest(key=key, theme=theme):
                    beta = Image.open(self.path(key, theme, '_s')).convert('RGB').crop((0, 0, 500, 300))
                    shipped = Image.open(os.path.join(BANDS, 'band_%s_%s_s.webp' % (master, theme))).convert('RGB').crop((0, 0, 500, 300))
                    self.assertLess(sum(ImageStat.Stat(ImageChops.difference(beta, shipped)).mean) / 3.0, 3.0)
