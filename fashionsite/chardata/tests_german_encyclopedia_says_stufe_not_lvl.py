# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The German encyclopedia card meta says Stufe, the word the game uses."""

from django.test import TestCase


class GermanEncyclopediaSaysStufeNotLvlTests(TestCase):

    def test_the_card_meta_says_stufe(self):
        page = self.client.get('/de/encyclopedia/').content.decode('utf-8')
        self.assertIn('encyclopedia-card-meta', page)
        self.assertIn('Stufe', page)
        self.assertNotIn('Lvl.', page)
