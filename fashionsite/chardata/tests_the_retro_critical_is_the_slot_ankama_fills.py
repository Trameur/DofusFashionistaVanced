# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""En Retro, le coup critique est la place qu'Ankama remplit, pas le plus gros.

Trouve en lisant le panneau des sorts d'un Iop Retro, puis en descendant
jusqu'a la source: `itemscraper/get_spells_retro.py` disait que les deux
listes d'effets d'un rang arrivent <<in no fixed order; the crit is the higher
roll>>. C'est une supposition, et le fichier d'Ankama dit autre chose.

**Ce que dit le fichier.** Mesure du 14 septembre 2026 sur les 2091 sorts du
lang Retro d'Ankama (VERSION 1254):

| ce qui est lu | nombre |
|---------------|--------|
| rangs lus, tous sorts confondus | 10632 |
| rangs qui ne peuvent pas sortir de critique | 3926 |
| ... dont l'avant-derniere case est VIDE | 3923 |
| ... dont elle est pleine | **3** |
| ... et parmi ces trois, identiques a la derniere case | **3** |
| lignes d'element ou l'avant-derniere case est strictement plus forte | 3786 |
| lignes ou les deux sont a egalite | 363 |
| lignes ou l'avant-derniere case est plus faible | **37** |

La case que le jeu ne lira jamais est celle du critique: 3923 temoins et zero
contre-exemple. Les trois exceptions sont les rangs 1 a 3 de Teleportation, ou
les deux cases portent exactement la meme ligne, donc aucune lecture ne les
separe. La place est fixe, et elle se lit sans deviner.

**Ce que la supposition changeait.** Un critique Retro est une valeur fixe
(`0d0+N`) face a un coup normal qui lance des des, donc il peut tomber dans la
fourchette normale. Piqure rang 1 frappe de 1 a 5 et critique a 3 exactement.
Sur ces 37 lignes, le site publiait les deux colonnes echangees. Quatre
arrivent au panneau, sur deux sorts de Feca:

    Attaque Nuageuse  normal  11-11  13-13  4-15 ...  ->  2-13  3-14  4-15 ...
    Attaque Nuageuse  crit     2-13   3-14 16-16 ...  -> 11-11 13-13 16-16 ...
    Retour du baton   normal  16-18  18-21 10-24 ...  ->  6-20  8-22 10-24 ...
    Retour du baton   crit     6-20   8-22 20-24 ...  -> 16-18 18-21 20-24 ...

L'echelle corrigee monte rang apres rang des deux cotes; l'ancienne redescendait
entre le rang 2 et le rang 3. C'est la meme reponse lue par l'autre bout.

`retro_raw` n'est pas dans le depot (.gitignore): le parcours qui lit le
fichier d'Ankama se met de cote quand il est absent, les autres non.
"""
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

#: Les deux sorts de Feca dont le panneau montrait les colonnes echangees, et
#: ce que le fichier d'Ankama donne pour leurs six rangs.
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
        """Un rang a la forme de Piqure: le normal lance 1 a 5, le critique
        vaut 3. Prendre <<le plus gros>> rend les deux colonnes a l'envers."""
        module = _decoder()

        def effet(formule, bas, haut):
            # La forme d'une ligne d'effet du fichier: formule, puis le haut
            # et le bas de la fourchette, puis l'identifiant de l'effet.
            return [formule, True, '', 0, 0, None, haut, bas, 99]

        niveau = [0] * 19 + [[effet('0d0+3', 3, None)],
                             [effet('1d5+0', 1, 5)]]
        self.assertEqual({'fire': ((1, 5), (3, 3))},
                         module.decode_level(niveau))

    def test_a_rank_with_no_critical_row_shows_the_same_on_both_sides(self):
        """Les 3554 rangs sans critique laissent la case vide; le panneau doit
        alors rendre le coup normal des deux cotes, pas zero."""
        module = _decoder()
        niveau = [0] * 19 + [[], [['1d5+0', True, '', 0, 0, None, 5, 1, 99]]]
        self.assertEqual({'fire': ((1, 5), (1, 5))},
                         module.decode_level(niveau))

    def test_the_two_feca_spells_carry_the_ladder_the_file_gives(self):
        """Ce que le lecteur voit. Les deux echelles montent rang apres rang,
        ce que l'ancienne lecture cassait entre le rang 2 et le rang 3."""
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
        """La regle elle-meme, relue chez Ankama. Se met de cote quand
        retro_raw est absent, ce qui est le cas sur un depot propre."""
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
