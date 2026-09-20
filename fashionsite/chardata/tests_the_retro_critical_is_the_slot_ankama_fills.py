# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""In Retro the critical roll is the slot Ankama fills, not the higher roll."""
import io
import json
import os
import sys
import unittest

from django.test import SimpleTestCase

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SCRAPER = os.path.join(RACINE, 'itemscraper')
BRUT = os.path.join(SCRAPER, 'retro_raw', 'spells_fr.json')

# Two Feca spells, with what Ankama's file gives for their six ranks
ECHANGES = {
    'Attaque Nuageuse': {
        'normal': ['2-13', '3-14', '4-15', '5-16', '7-18', '11-22'],
        'crit': ['11-11', '13-13', '16-16', '18-18', '20-20', '25-25'],
    },
    'Retour du bâton': {
        'normal': ['6-20', '8-22', '10-24', '12-26', '16-30', '21-35'],
        'crit': ['16-18', '18-21', '20-24', '22-27', '26-32', '31-37'],
    },
}


def _decoder():
    if SCRAPER not in sys.path:
        sys.path.insert(0, SCRAPER)
    import get_spells_retro
    return get_spells_retro


def _borne(texte):
    bas, haut = texte.split('-')
    return int(bas), int(haut)


class TheRetroCriticalIsTheSlotAnkamaFillsTests(SimpleTestCase):

    def test_the_decoder_reads_the_place_and_not_the_bigger_roll(self):
        module = _decoder()

        def effet(formule, bas, haut):
            # An effect line: formula, then the top and bottom of the range, then the effect id
            return [formule, True, '', 0, 0, None, haut, bas, 99]

        niveau = [0] * 19 + [[effet('0d0+3', 3, None)],
                             [effet('1d5+0', 1, 5)]]
        self.assertEqual({'fire': ((1, 5), (3, 3))},
                         module.decode_level(niveau))

    def test_a_rank_with_no_critical_row_shows_the_same_on_both_sides(self):
        module = _decoder()
        niveau = [0] * 19 + [[], [['1d5+0', True, '', 0, 0, None, 5, 1, 99]]]
        self.assertEqual({'fire': ((1, 5), (1, 5))},
                         module.decode_level(niveau))

    def test_the_two_feca_spells_carry_the_ladder_the_file_gives(self):
        from fashionistapulp.dofus_constants_retro_spells import (
            RETRO_DAMAGE_SPELLS)
        trouves = 0
        for sort in RETRO_DAMAGE_SPELLS.get('Feca', []):
            attendu = ECHANGES.get(sort.name)
            if attendu is None:
                continue
            trouves += 1
            lignes = {'normal': sort.effects.non_crit_ranges[0],
                      'crit': sort.effects.crit_ranges[0]}
            for cote, rangs in lignes.items():
                lus = ['%d-%d' % (r.min_dam, r.max_dam) for r in rangs]
                with self.subTest(sort=sort.name, cote=cote):
                    self.assertEqual(attendu[cote], lus)
                    bornes = [_borne(x) for x in lus]
                    for avant, apres in zip(bornes, bornes[1:]):
                        self.assertLessEqual(avant[0], apres[0], lus)
                        self.assertLessEqual(avant[1], apres[1], lus)
        self.assertEqual(2, trouves, 'the two Feca spells left the module')

    def test_ankamas_own_file_says_which_place_is_the_critical(self):
        if not os.path.exists(BRUT):
            raise unittest.SkipTest(
                'retro_raw is gitignored; run itemscraper/download_retro_langs'
                '.py to read Ankama"s own spell lang')
        module = _decoder()
        sorts = json.load(io.open(BRUT, encoding='utf-8', errors='replace'))
        vide, identique, contredit, lus = 0, 0, [], 0
        for identifiant, sort in sorts['S'].items():
            if not isinstance(sort, dict):
                continue
            for rang in ('l1', 'l2', 'l3', 'l4', 'l5', 'l6'):
                niveau = sort.get(rang)
                if not isinstance(niveau, list) or len(niveau) < 19:
                    continue
                if niveau[15]:
                    continue
                lus += 1
                critique = module._collect(niveau[-2])
                if not critique:
                    vide += 1
                elif critique == module._collect(niveau[-1]):
                    identique += 1
                else:
                    contredit.append((identifiant, sort.get('n'), rang))
        self.assertGreater(lus, 3000, 'only %d ranks cannot crit' % lus)
        self.assertEqual([], contredit,
                         'ranks that cannot crit yet carry a critical row of '
                         'their own: %s' % (contredit[:5],))
        self.assertEqual(lus, vide + identique)
        self.assertGreater(vide, 3000, 'only %d left the place empty' % vide)
