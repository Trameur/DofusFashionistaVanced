# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Atelier fonts are woff2 files served from /static/, each declared by a relative @font-face url, licensed beside the files, loaded from no other host, and covering every letter of the five languages."""
import glob
import io
import os
import re
import unittest

from django.test import SimpleTestCase

from chardata.csp import build_policy
from chardata.tests_the_setup_stylesheet_support import STATIC, read_css

FONT_DIR = os.path.join(STATIC, 'font')
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
FACE = re.compile(r'@font-face\s*\{([^}]*)\}')
FAMILIES = {'IM Fell English SC': ('400',), 'Barlow': ('400', '600', '700')}
THIRD_PARTY_FONT_HOSTS = ('fonts.googleapis.com', 'fonts.gstatic.com', 'use.typekit.net', 'fast.fonts.net',
                          'use.fontawesome.com', 'kit.fontawesome.com', 'fonts.bunny.net', 'fonts.adobe.com')
ALPHABETS = {
    'de': 'ÄÖÜäöüß',
    'es': 'ÁÉÍÓÚÜÑáéíóúüñ¿¡ªº',
    'fr': 'ÀÂÆÇÈÉÊËÎÏÔŒÙÛÜŸàâæçèéêëîïôœùûüÿ«»',
    'pt': 'ÀÁÂÃÇÉÊÍÓÔÕÚàáâãçéêíóôõú',
    'en': 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,;:!?\'"()-/&%+*=<>@#$',
    'punctuation': '\u2018\u2019\u201c\u201d\u2026\u2013\u2014\u00a0\u20ac\u00d7\u00b0\u2022\u00b7',
}


def faces():
    found = []
    for body in FACE.findall(read_css('modern.css')):
        declarations = dict((piece.split(':', 1)[0].strip(), piece.split(':', 1)[1].strip())
                            for piece in body.split(';') if ':' in piece)
        found.append(declarations)
    return found


def text_files(folder, extensions):
    for root, _, names in os.walk(folder):
        for name in names:
            if name.endswith(extensions):
                yield os.path.join(root, name)


class EveryFaceNamesAWoff2FileThatExistsTests(SimpleTestCase):

    def test_the_four_expected_faces_are_declared(self):
        declared = sorted((face['font-family'].strip('"'), face['font-weight']) for face in faces())
        wanted = sorted((family, weight) for family, weights in FAMILIES.items() for weight in weights)
        self.assertEqual(wanted, declared)

    def test_every_src_is_one_relative_woff2_url(self):
        for face in faces():
            with self.subTest(face=face['font-family'], weight=face['font-weight']):
                found = re.fullmatch(r'url\("([^"]+)"\) format\("woff2"\)', face['src'])
                self.assertIsNotNone(found, face['src'])
                path = found.group(1)
                self.assertTrue(path.endswith('.woff2'))
                self.assertFalse(path.startswith(('/', 'http', '//', 'data:')), path)

    def test_every_file_a_face_names_exists_and_is_a_real_woff2(self):
        for face in faces():
            path = os.path.join(STATIC, re.search(r'url\("([^"]+)"\)', face['src']).group(1))
            with self.subTest(path=path):
                self.assertTrue(os.path.isfile(path))
                with io.open(path, 'rb') as handle:
                    self.assertEqual(b'wOF2', handle.read(4))

    def test_every_face_swaps_so_text_shows_before_the_font_arrives(self):
        for face in faces():
            with self.subTest(face=face['font-family'], weight=face['font-weight']):
                self.assertEqual('swap', face['font-display'])

    def test_no_woff2_file_sits_in_the_folder_without_a_face_that_names_it(self):
        named = {os.path.basename(re.search(r'url\("([^"]+)"\)', face['src']).group(1)) for face in faces()}
        on_disk = {os.path.basename(path) for path in glob.glob(os.path.join(FONT_DIR, '*.woff2'))}
        self.assertEqual(named, on_disk)

    def test_the_four_files_weigh_under_250_kb_together(self):
        total = sum(os.path.getsize(path) for path in glob.glob(os.path.join(FONT_DIR, '*.woff2')))
        self.assertLess(total, 250 * 1024, total)

    def test_each_family_ships_its_open_font_licence_beside_the_files(self):
        for name in ('OFL-IMFellEnglishSC.txt', 'OFL-Barlow.txt'):
            with self.subTest(name=name):
                with io.open(os.path.join(FONT_DIR, name), encoding='utf-8') as handle:
                    self.assertIn('SIL OPEN FONT LICENSE Version 1.1', handle.read())


class NoFontComesFromAnotherHostTests(SimpleTestCase):

    def test_no_template_and_no_stylesheet_names_a_third_party_font_host(self):
        found = []
        paths = list(text_files(TEMPLATES, ('.html', '.txt'))) + list(text_files(STATIC, ('.css', '.js')))
        for path in paths:
            with io.open(path, encoding='utf-8', errors='replace') as handle:
                source = handle.read()
            found += [(os.path.basename(path), host) for host in THIRD_PARTY_FONT_HOSTS if host in source]
        self.assertEqual([], found)

    def test_no_font_face_anywhere_loads_a_url_that_leaves_the_site(self):
        leaving = []
        for path in text_files(STATIC, ('.css',)):
            with io.open(path, encoding='utf-8', errors='replace') as handle:
                source = re.sub(r'/\*.*?\*/', '', handle.read(), flags=re.S)
            for body in FACE.findall(source):
                leaving += [(os.path.basename(path), url) for url in re.findall(r'url\(\s*["\']?([^)"\']+)', body)
                            if re.match(r'(https?:)?//', url)]
        self.assertEqual([], leaving)

    def test_no_stylesheet_imports_a_remote_font_sheet(self):
        imports = []
        for path in text_files(STATIC, ('.css',)):
            with io.open(path, encoding='utf-8', errors='replace') as handle:
                imports += [(os.path.basename(path), line) for line in handle.read().splitlines()
                            if re.match(r'\s*@import\b.*(https?:)?//', line)]
        self.assertEqual([], imports)

    def test_the_font_source_of_the_content_security_policy_is_still_this_site_and_inline_data(self):
        directive = [part for part in build_policy().split('; ') if part.startswith('font-src')]
        self.assertEqual(["font-src 'self' data:"], directive)

    def test_the_preload_links_name_font_files_that_exist(self):
        with io.open(os.path.join(TEMPLATES, 'chardata', 'base.html'), encoding='utf-8') as handle:
            source = handle.read()
        names = re.findall(r'chardata/font/([\w-]+\.woff2)', source)
        self.assertEqual(['Barlow-Regular.woff2', 'IMFellEnglishSC-Regular.woff2'], sorted(names))
        for name in names:
            self.assertTrue(os.path.isfile(os.path.join(FONT_DIR, name)), name)


try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None


@unittest.skipIf(TTFont is None, 'fontTools is not installed')
class TheFilesCoverTheFiveLanguagesTests(SimpleTestCase):

    def test_every_face_has_a_glyph_for_every_letter_of_de_en_es_fr_pt(self):
        for path in sorted(glob.glob(os.path.join(FONT_DIR, '*.woff2'))):
            cmap = TTFont(path).getBestCmap()
            for language, letters in ALPHABETS.items():
                with self.subTest(file=os.path.basename(path), language=language):
                    self.assertEqual([], [char for char in letters if ord(char) not in cmap])
