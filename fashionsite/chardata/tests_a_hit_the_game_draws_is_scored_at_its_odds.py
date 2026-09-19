# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A hit the game draws at random is scored at its odds."""
import io
import json
import os
import unittest

from django.test import SimpleTestCase

from chardata.spell_combo import (_draw_is_random, best_turn,
                                  castable_spells)
from fashionistapulp.dofus_constants import STAT_NAME_TO_KEY

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
BRUT = os.path.join(RACINE, 'itemscraper', 'retro_raw', 'spells_fr.json')

CHANCE_SLOT = 3
RANGS = ('l1', 'l2', 'l3', 'l4', 'l5', 'l6')


def _stats(**ajouts):
    profil = {cle: 0 for cle in STAT_NAME_TO_KEY.values()}
    profil.update(ajouts)
    return profil


def _bluff():
    for spell in castable_spells('Ecaflip', 200, 'retro'):
        if spell.name == 'Bluff':
            return spell
    raise AssertionError('Bluff left the Retro catalogue')


class AHitTheGameDrawsIsScoredAtItsOddsTests(SimpleTestCase):

    def test_only_the_drawn_spell_carries_the_flag(self):
        tires = [spell.name
                 for spell in castable_spells('Ecaflip', 200, 'retro')
                 if spell.random_draw]
        self.assertEqual(['Bluff'], tires)
        for classe in ('Iop', 'Eniripsa', 'Cra'):
            for version in ('dofus3', 'retro'):
                with self.subTest(classe=classe, version=version):
                    self.assertEqual(
                        [], [spell.name for spell
                             in castable_spells(classe, 200, version)
                             if spell.random_draw])

    def test_the_flag_reads_the_label_the_generator_writes(self):
        self.assertTrue(_draw_is_random(
            [('Hit in one random element', [0]), ('', [1])]))
        self.assertFalse(_draw_is_random(
            [('Hit in best element', [0]), ('', [1])]))
        self.assertFalse(_draw_is_random([]))
        self.assertFalse(_draw_is_random(None))

    def test_the_turn_takes_the_mean_and_not_the_better_face(self):
        bluff = _bluff()
        self.assertTrue(bluff.random_draw)
        self.assertEqual(2, len(bluff.alternatives))
        for profil in (_stats(agi=600, airdam=60, dam=40),
                       _stats(cha=600, waterdam=60, dam=40)):
            bluff.random_draw = True
            moyenne, _ordre = best_turn(profil, [bluff], bluff.cost,
                                        game_version='retro',
                                        caster_level=200)
            bluff.random_draw = False
            meilleure, _ordre = best_turn(profil, [bluff], bluff.cost,
                                          game_version='retro',
                                          caster_level=200)
            bluff.random_draw = True
            with self.subTest(profil='mono-element'):
                self.assertGreater(meilleure, moyenne * 1.5,
                                   '%s contre %s' % (meilleure, moyenne))

    def test_two_equal_faces_move_nothing(self):
        bluff = _bluff()
        profil = _stats(agi=300, cha=300, dam=40)
        bluff.random_draw = True
        moyenne, _ordre = best_turn(profil, [bluff], bluff.cost,
                                    game_version='retro', caster_level=200)
        bluff.random_draw = False
        meilleure, _ordre = best_turn(profil, [bluff], bluff.cost,
                                      game_version='retro', caster_level=200)
        bluff.random_draw = True
        self.assertAlmostEqual(moyenne, meilleure, places=6)

    def test_ankama_is_where_the_odds_come_from(self):
        if not os.path.exists(BRUT):
            raise unittest.SkipTest(
                'retro_raw is gitignored; download the Retro spell lang to '
                'read Ankama"s own chances')
        sorts = json.load(io.open(BRUT, encoding='utf-8', errors='replace'))
        bluff = sorts['S']['109']
        self.assertIn('aleatoirement',
                      (bluff.get('d') or '').replace('é', 'e').lower())
        vus = 0
        partitions = 0
        for identifiant, sort in sorts['S'].items():
            if not isinstance(sort, dict):
                continue
            for rang in RANGS:
                niveau = sort.get(rang)
                if not isinstance(niveau, list) or len(niveau) < 2:
                    continue
                for liste in (niveau[-2], niveau[-1]):
                    chances = [effet[CHANCE_SLOT] for effet in (liste or [])
                               if isinstance(effet, list)
                               and len(effet) > CHANCE_SLOT
                               and effet[CHANCE_SLOT]]
                    if len(chances) > 1 and sum(chances) == 100:
                        partitions += 1
                        if identifiant == '109':
                            vus += 1
                            self.assertEqual([50, 50], chances)
        self.assertGreater(vus, 0, 'Bluff no longer carries its chances')
        self.assertGreater(partitions, 300, partitions)
