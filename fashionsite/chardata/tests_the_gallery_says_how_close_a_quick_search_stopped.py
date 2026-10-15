# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A gallery card of a quick search that stopped within its gap says how far from the best, not that the time ran out."""

import pickle

from django.core.cache import cache
from django.test import TestCase

from chardata.char_blobs import read_char_blob
from chardata.tests_the_gallery_shows_the_proof import LIMITE, PROUVE, _build_partage, _carte

QUICK = 'Within 3% of the best, not a proof'


def _stopped_within(char, tolerance):
    minimal = read_char_blob(char.minimal_solution, None, 'minimal_solution', char)
    minimal.proven = False
    if tolerance is not None:
        minimal.tolerance = tolerance
    char.minimal_solution = pickle.dumps(minimal)
    char.save()
    cache.clear()


class TheGalleryCardOfAQuickSearchTests(TestCase):

    def card(self, name):
        return _carte(self.client.get('/sharedbuilds/').content.decode('utf-8'), name)

    def test_a_stop_within_the_gap_says_how_far_and_not_the_time_limit(self):
        char = _build_partage('GalerieRapide')
        _stopped_within(char, 0.03)
        card = self.card('GalerieRapide')
        self.assertIn(QUICK, card)
        self.assertNotIn(LIMITE, card)
        self.assertNotIn(PROUVE, card)

    def test_a_stop_on_the_clock_keeps_the_time_limit_badge(self):
        char = _build_partage('GalerieHorloge')
        _stopped_within(char, None)
        card = self.card('GalerieHorloge')
        self.assertIn(LIMITE, card)
        self.assertNotIn('of the best', card)
