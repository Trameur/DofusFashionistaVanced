# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On a phone, the German header of the weights table fits the 80 pixel column the shared sheet gives it."""
from django.test import SimpleTestCase

from chardata.tests_the_setup_stylesheet_support import declared, stylesheet

SETUP = stylesheet('modern-setup.css')
SHARED = stylesheet('responsive.css')
HEAD = 'html.fm-modern .tunnel-weights .wm-head'


class TheGermanHeaderTests(SimpleTestCase):

    def test_the_header_is_spaced_out_capitals(self):
        self.assertEqual(('.1em', False), declared(SETUP, HEAD, 'letter-spacing'))
        self.assertEqual(('uppercase', False), declared(SETUP, HEAD, 'text-transform'))

    def test_the_columns_narrow_to_72_and_80_pixels_under_480(self):
        self.assertEqual(('18px minmax(0, 1fr) 72px 80px', True),
                         declared(SHARED, '.wm-head', 'grid-template-columns', '(max-width: 480px)'))

    def test_german_tightens_its_letters_at_that_width_only(self):
        self.assertEqual(('.02em', False), declared(SETUP, HEAD + ':lang(de)', 'letter-spacing', '(max-width:480px)'))
        self.assertIsNone(declared(SETUP, HEAD + ':lang(de)', 'letter-spacing'))
