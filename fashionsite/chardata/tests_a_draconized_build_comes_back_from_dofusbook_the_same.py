# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A draconized build sent to DofusBook and read back from the sheet that holds its totals keeps the same piece and the same Dracorune in every slot."""

import re
import urllib.parse
from unittest import mock

from django.test import TestCase

from chardata import dofusbook_export, dofusbook_import, text_build_view
from chardata.char_blobs import read_char_blob
from chardata.dofusbook_rune_fixtures import (LINK, RESISTANCE_KEY, draconize, export_page,
                                              forge_of, lines_of, opener, piece, public_payload, slot_code,
                                              stand_in_runes, variant_lines, worn_by)
from chardata.models import Char
from fashionistapulp.structure import set_current_game_version


class TheRoundTripTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        stand_in_runes(self)
        self.hat = piece('Hat', RESISTANCE_KEY)
        self.cloak = piece('Cloak', RESISTANCE_KEY, number=1)
        self.char = worn_by(self.client, [self.hat, self.cloak])
        self.sent = draconize(self.char, [(self.hat, RESISTANCE_KEY), (self.cloak, RESISTANCE_KEY)])

    def sheet(self):
        """Their sheet once the exported totals sit on the pieces: each slot holds its rune's lines."""
        return public_payload([
            (slot_code('Hat'), self.hat, variant_lines(self.hat, RESISTANCE_KEY)),
            (slot_code('Cloak'), self.cloak, variant_lines(self.cloak, RESISTANCE_KEY))])

    def test_the_export_carries_totals_the_sheet_agrees_with(self):
        page = export_page(self.client, self.char)
        forge = forge_of(page)
        positions = dofusbook_export.index_by_stat_key()
        moved = sum(lines_of(item)['neutresper'] for item in (self.hat, self.cloak))
        self.assertEqual(moved, forge[positions['earthresper']])
        self.assertEqual(-moved, forge[positions['neutresper']])

    def test_the_import_gives_back_the_same_item_and_rune_per_slot(self):
        payload = self.sheet()

        def reading(url, opener_=None):
            return dofusbook_import.read_build(url, opener=opener(payload))

        with mock.patch.object(text_build_view, 'read_build', reading):
            self.client.post('/import/text/', {'text': LINK, 'confirm': '1',
                                               'char_class': 'Iop', 'level': '200'})
        imported = Char.objects.order_by('-id').first()
        self.assertNotEqual(self.char.id, imported.id)
        back = read_char_blob(imported.minimal_solution, None, 'minimal_solution', imported)
        self.assertEqual(self.sent.dracorunes, back.dracorunes)
        self.assertEqual({slot: back.item_per_slot[slot] for slot in self.sent.dracorunes},
                         {slot: self.sent.item_per_slot[slot] for slot in self.sent.dracorunes})

    def test_the_link_alone_carries_totals_and_no_slot(self):
        link = re.search(r'stuff=([^"&\'<> ]+)',
                         export_page(self.client, self.char).content.decode('utf-8')).group(1)
        read = dofusbook_import.read_stuffer_link('www.dofusbook.net', urllib.parse.unquote(link))
        self.assertNotIn('dracorunes', read)
        self.assertTrue(read['fm_global'])
