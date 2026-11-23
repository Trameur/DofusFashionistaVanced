# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A transcended build sent to DofusBook and read back from the sheet that holds its totals keeps the same pieces and the same totals, with the rune line as a recorded roll and no transcendence."""

import re
import urllib.parse
from unittest import mock

from django.test import TestCase

from chardata import dofusbook_export, dofusbook_import, text_build_view
from chardata.char_blobs import read_char_blob
from chardata.dofusbook_rune_fixtures import (LINK, RESISTANCE_KEY, export_page, forge_of, lines_of,
                                              opener, piece, public_payload, slot_code,
                                              stand_in_runes, structure, worn_by)
from chardata.inventory_solver import get_effective_stat_overrides
from chardata.models import Char
from chardata.solution import get_solution
from chardata.tests_a_dofusbook_export_carries_the_transcendence_totals import (
    rune_for, stand_in_transcendences, transcend)
from fashionistapulp.structure import set_current_game_version


class TheRoundTripTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        stand_in_runes(self)
        stand_in_transcendences(self)
        self.hat = piece('Hat', RESISTANCE_KEY)
        self.rune = rune_for(self.hat, 'int')
        self.char = worn_by(self.client, [self.hat])
        self.sent = transcend(self.char, [(self.hat, self.rune)])
        self.worn = {item.slot: item for item in get_solution(self.char).item_list if item.item_added}

    def sheet(self):
        """Their sheet once the exported totals sit on the piece: the slot holds the rune line as a value above the catalogue."""
        lines = lines_of(self.hat)
        lines['int'] = lines.get('int', 0) + self.rune['bonus']
        return public_payload([(slot_code('Hat'), self.hat, lines)])

    def imported(self):
        payload = self.sheet()

        def reading(url, opener_=None):
            return dofusbook_import.read_build(url, opener=opener(payload))

        with mock.patch.object(text_build_view, 'read_build', reading):
            self.client.post('/import/text/', {'text': LINK, 'confirm': '1',
                                               'char_class': 'Iop', 'level': '200'})
        imported = Char.objects.order_by('-id').first()
        self.assertNotEqual(self.char.id, imported.id)
        return imported

    def test_the_export_carries_the_rune_bonus_in_the_global_forgemagie(self):
        forge = forge_of(export_page(self.client, self.char))
        position = dofusbook_export.index_by_stat_key()['int']
        scroll = dofusbook_export.SCROLL_STEP if forge[position] >= dofusbook_export.SCROLL_STEP else 0
        self.assertEqual(self.rune['bonus'], forge[position] - scroll)

    def test_the_sheet_gives_back_the_same_pieces_and_totals_with_the_rune_line_as_a_recorded_roll(self):
        imported = self.imported()
        back = read_char_blob(imported.minimal_solution, None, 'minimal_solution', imported)
        self.assertEqual({slot: self.sent.item_per_slot[slot] for slot in self.sent.transcendences},
                         {slot: back.item_per_slot[slot] for slot in self.sent.transcendences})
        int_id = structure().get_stat_by_key('int').id
        self.assertEqual(lines_of(self.hat).get('int', 0) + self.rune['bonus'],
                         get_effective_stat_overrides(imported)[self.hat.id][int_id])
        again = {item.slot: item for item in get_solution(imported).item_list if item.item_added}
        slot = next(iter(self.sent.transcendences))
        self.assertEqual(self.worn[slot].stats['int'], again[slot].stats['int'])

    def test_the_import_invents_no_transcendence(self):
        imported = self.imported()
        back = read_char_blob(imported.minimal_solution, None, 'minimal_solution', imported)
        self.assertFalse(getattr(back, 'transcendences', None))
        for item in get_solution(imported).item_list:
            self.assertFalse(getattr(item, 'transcendence_rune', None))

    def test_the_link_carries_the_rune_bonus_as_the_global_forgemagie_total(self):
        link = re.search(r'stuff=([^"&\'<> ]+)',
                         export_page(self.client, self.char).content.decode('utf-8')).group(1)
        read = dofusbook_import.read_stuffer_link('www.dofusbook.net', urllib.parse.unquote(link))
        position = dofusbook_export.index_by_stat_key()['int']
        self.assertEqual(self.rune['bonus'], read['fm_global'][dofusbook_export.VE[position]])
