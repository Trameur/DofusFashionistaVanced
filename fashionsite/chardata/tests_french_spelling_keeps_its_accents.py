# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""French copy keeps its accents: piece stays pièce, obsoletes stays obsolètes."""

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation


class FrenchSpellingKeepsItsAccentsTests(SimpleTestCase):

    def test_the_screenshot_note_says_piece_with_its_accent(self):
        with translation.override('fr'):
            rendu = Template(
                '{% load i18n %}{% trans "One screenshot per piece, '
                'tooltip visible. They are read inside your browser: no '
                'image leaves your machine." %}'
            ).render(Context())
        self.assertIn('pièce', rendu)
        self.assertNotIn(' piece,', rendu)

    def test_the_gallery_filter_says_obsoletes_with_its_accent(self):
        with translation.override('fr'):
            rendu = Template(
                '{% load i18n %}{% trans "Hide invalid or outdated '
                'builds" %}'
            ).render(Context())
        self.assertIn('obsolètes', rendu)
        self.assertNotIn('obsoletes', rendu)
