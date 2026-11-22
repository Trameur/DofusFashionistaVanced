# -*- coding: utf-8 -*-
"""The Beta counts Ta Po, Ta Invo, Gata Pa and Gata Pme like the others, with the game's notice."""
import json
import re

from django.test import SimpleTestCase, TestCase
from django.utils.translation import override

from chardata.forgemagie_transcendance import get_transcendence_runes
from chardata.solution_result import attach_transcendence
from chardata.transcendence_advice import best_transcendence
from fashionistapulp.structure import set_current_game_version

NEW_IDS = (29679, 29680, 29681, 29682)
NEW_NAMES_FR = ('Rune Gata Pa', 'Rune Gata Pme', 'Rune Ta Po', 'Rune Ta Invo')
_CONFIG = re.compile(r'<script[^>]*\bid="fm-config"[^>]*>(.*?)</script>', re.S)


class Piece(object):
    item_added = True
    type = 'Ring'
    id = None
    stats = {}
    base_stats = None
    exo_overrides = None
    assumed_exo = None
    dracorune = None


class TheRunesTheBetaAddsAreOnlyOnTheBetaTests(SimpleTestCase):

    def test_the_beta_lists_eighty_five_runes_with_the_four_new_ones(self):
        runes = get_transcendence_runes('beta')
        self.assertEqual(85, len(runes))
        self.assertEqual(set(NEW_IDS), {r['id'] for r in runes if r.get('beta_only')})

    def test_dofus3_and_dofus2_list_eighty_one_and_none_of_the_four(self):
        for version in ('dofus3', 'dofus2'):
            with self.subTest(version=version):
                runes = get_transcendence_runes(version)
                self.assertEqual(81, len(runes))
                self.assertFalse({r['id'] for r in runes} & set(NEW_IDS))


class TheBetaToolShowsTheFourRunesWithTheirNoticeTests(TestCase):

    def _runes(self, language):
        response = self.client.get('/beta/forgemagie/',
                                   headers={'accept-language': language})
        self.assertEqual(200, response.status_code)
        config = json.loads(_CONFIG.search(response.content.decode('utf-8')).group(1))
        return {rune['id']: rune for entry in config['transcendence'].values()
                for rune in entry['runes']}, response

    def test_the_beta_tool_lists_the_four_runes_with_the_notice_in_french(self):
        runes, response = self._runes('fr')
        self.assertTrue(set(NEW_IDS) <= set(runes))
        self.assertEqual(sorted(NEW_NAMES_FR),
                         sorted(runes[i]['name'] for i in NEW_IDS))
        for rune_id in NEW_IDS:
            self.assertIn('Disponible uniquement en', runes[rune_id]['notice'])
        self.assertEqual('', runes[20492]['notice'])
        self.assertContains(response, 'Disponible uniquement en')

    def test_the_beta_tool_lists_the_four_runes_with_the_notice_in_english(self):
        runes, response = self._runes('en')
        for rune_id in NEW_IDS:
            self.assertEqual('Available only in the beta.', runes[rune_id]['notice'])
        self.assertContains(response, 'Available only in the beta.')

    def test_the_dofus3_tool_lists_none_of_them_and_no_notice(self):
        response = self.client.get('/forgemagie/', headers={'accept-language': 'en'})
        config = json.loads(_CONFIG.search(response.content.decode('utf-8')).group(1))
        runes = [r for entry in config['transcendence'].values() for r in entry['runes']]
        self.assertEqual(81, len(runes))
        self.assertFalse({r['id'] for r in runes} & set(NEW_IDS))
        self.assertFalse([r for r in runes if r['notice']])
        self.assertNotContains(response, 'Available only in the beta.')


class TheTipNamesGataPaOnABetaPieceTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('beta')

    def tearDown(self):
        set_current_game_version('dofus3')

    def _tip(self, language, **changes):
        piece = Piece()
        for name, value in changes.items():
            setattr(piece, name, value)
        with override(language):
            attach_transcendence(piece, {'ap': 1})
        return piece.transcendence

    def test_a_beta_piece_with_no_ap_line_gets_rune_gata_pa(self):
        tip = self._tip('fr', stats={'vit': 10}, base_stats={'vit': 10})
        self.assertTrue(tip.startswith('Rune Gata Pa: +1'), tip)

    def test_the_tip_speaks_the_readers_language(self):
        tip = self._tip('en', stats={'vit': 10}, base_stats={'vit': 10})
        self.assertTrue(tip.startswith('Ap Gatra Rune: +1'), tip)

    def test_a_beta_piece_with_an_ap_line_gets_no_gata_pa(self):
        rune = best_transcendence('beta', {'ap': 1}, {'ap': 1}, 'Ring')
        self.assertIsNone(rune)
        self.assertIsNone(self._tip('fr', stats={'ap': 1}, base_stats={'ap': 1}))

    def test_dofus3_never_names_gata_pa(self):
        rune = best_transcendence('dofus3', {}, {'ap': 1}, 'Ring')
        self.assertIsNone(rune)
