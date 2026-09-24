# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The AP/MP/range guide never claims three exo rings; only two ring slots exist."""

from django.test import TestCase

from chardata.guides_content import slug_for

WITNESS = {
    'en': 'three different items',
    'fr': 'trois objets différents',
    'es': 'tres objetos distintos',
    'pt': 'três itens diferentes',
    'de': 'drei verschiedenen Gegenständen',
}


class TheApMpRangeGuideTalksAboutItemsNotThreeRingsTests(TestCase):

    def test_the_guide_no_longer_names_three_rings(self):
        for langue, phrase in WITNESS.items():
            slug = slug_for('ap-mp-range-caps', langue)
            page = self.client.get(
                '/guides/%s/' % slug).content.decode('utf-8')
            with self.subTest(langue=langue):
                self.assertIn(phrase, page)
                self.assertNotIn('three +1 AP exo rings', page)
                self.assertNotIn('trois anneaux exo', page)
                self.assertNotIn('tres anillos exo', page)
                self.assertNotIn('três anéis exo', page)
                self.assertNotIn('drei Exo-Ringe', page)
