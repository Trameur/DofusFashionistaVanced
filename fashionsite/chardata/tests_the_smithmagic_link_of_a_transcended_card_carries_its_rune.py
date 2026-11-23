# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Smithmagic link of a transcended card carries its rune id, next to the Dracorune key when it has one, and every other link stays as it was."""
import re
from urllib.parse import quote

from django.template.loader import render_to_string
from django.utils.translation import override

from chardata.dracorune_fixtures import BetaModelTestCase
from chardata.forgemagie_transcendance import get_transcendence_by_stat
from chardata.transcendence_card_fixtures import (card_of, draconizable_hat, minimal_with,
                                                  plain_pieces, rune_of_stat)
from fashionistapulp.modelresult import model_result_from_minimal


class TheSmithmagicLinkOfATranscendedCardCarriesItsRuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.rune = rune_of_stat('vit')
        self.hat = plain_pieces('Hat', 'beta', 1, self.rune)[0]

    def link(self, saved=None, dracorunes=None, hat=None):
        hat = hat or self.hat
        result = model_result_from_minimal(minimal_with({'hat': hat.id}, saved, dracorunes))
        with override('en'):
            _piece, page = card_of(result, 'hat')
        found = re.findall(r'href="([^"]*forgemagie/\?item=%d[^"]*)"' % hat.id, page)
        self.assertEqual(1, len(found))
        return found[0]

    def test_a_transcended_card_links_the_item_with_its_rune_id(self):
        link = self.link({'hat': (self.hat.id, self.rune['id'])})
        self.assertTrue(link.endswith('?item=%d&amp;transcendence=%d' % (self.hat.id, self.rune['id'])))

    def test_a_plain_card_links_the_item_alone(self):
        link = self.link()
        self.assertTrue(link.endswith('?item=%d' % self.hat.id))
        self.assertNotIn('transcendence', link)

    def test_a_card_with_a_rune_and_a_dracorune_carries_both_parameters(self):
        hat, key = draconizable_hat()
        rune = rune_of_stat('vit')
        link = self.link({'hat': (hat.id, rune['id'])}, {'hat': (hat.id, key)}, hat)
        self.assertTrue(link.endswith('?item=%d&amp;dracorune=%s&amp;transcendence=%d'
                                      % (hat.id, quote(key, safe=''), rune['id'])))

    def test_a_dracorune_alone_adds_no_rune_parameter(self):
        hat, key = draconizable_hat()
        link = self.link(None, {'hat': (hat.id, key)}, hat)
        self.assertTrue(link.endswith('?item=%d&amp;dracorune=%s' % (hat.id, quote(key, safe=''))))

    def test_the_parameter_is_the_id_the_page_config_uses_for_that_rune(self):
        offered = {rune['id'] for entry in get_transcendence_by_stat('beta', 'en').values()
                   for rune in entry['runes']}
        link = self.link({'hat': (self.hat.id, self.rune['id'])})
        self.assertIn(int(link.rsplit('transcendence=', 1)[1]), offered)

    def test_a_card_without_a_rune_attribute_renders_the_link_unchanged(self):
        class Bare:
            id = 7
            mageable = True
            dracorune = None
            slot = 'hat'
        page = render_to_string('chardata/solution_item.html', {'item': Bare(),
                                                                'current_game_version': 'beta'})
        self.assertNotIn('transcendence=', page)
