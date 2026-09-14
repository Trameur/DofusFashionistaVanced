# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un coup que le jeu tire au sort est compte a ses chances, pas a sa
meilleure face.

Le lot 98 avait laisse une question ouverte: la table montre les deux faces du
Bluff separees par <<ou>>, mais `best_turn` en prenait la **meilleure**, alors
qu'Ankama ecrit <<Le Bluff inflige aleatoirement des degats d'Air ou d'Eau>>.
Le tour surestimait donc ce sort, et le lot d'alors disait qu'assumer 50/50
serait une invention.

**Ce n'en etait pas une: Ankama donne les chances dans son propre fichier.**
Chaque ligne d'effet Retro porte sa chance en pourcentage au slot 3, et les
lignes d'un meme tirage somment a 100. Bluff:

    ["0d0+55", true, "", 50, 0, null, null, 55, 96]   <- 50 %, Eau
    ["0d0+55", true, "", 50, 0, null, null, 55, 98]   <- 50 %, Air

**Mesure du 14 septembre 2026 sur les 2091 sorts du lang Retro:** 36 sorts
portent un jeu de valeurs qui somme a 100, et **chacun est une partition**:
50/50, 25/25/25/25, 20 cinq fois, et un **25/50/25** qui n'est pas uniforme.
C'est ce dernier qui distingue le slot d'une duree ou d'une valeur: une duree
ne somme pas a 100 en trois parts inegales. Partout ailleurs le slot vaut 0
(27467 lignes) ou porte une duree de glyphe (2, 3, 4).

**Ce que la correction change, mesure sur le sort lui-meme:**

| profil du lanceur | moyenne | meilleure face | le tour lisait |
|-------------------|---------|----------------|----------------|
| Agilite lourde | 174,4 | 282,6 | **+62 %** |
| equilibre | 144,4 | 144,4 | juste |
| Chance lourde | 174,4 | 282,6 | **+62 %** |

Un Ecaflip mono-element lisait donc son Bluff **une fois et demie trop haut**.
Sur un build equilibre les deux faces valent pareil et rien ne bouge, ce qui
est pourquoi le defaut ne se voyait pas sur les builds locaux.

**Ce que la correction ne fait pas.** Elle ne touche pas les sorts <<dans le
meilleur element>>: la, le jeu prend bien ce qui arrange le lanceur, et la
meilleure face est la bonne reponse. Le seul sort tire au sort que le site
modele est Bluff; Roulette et Souillure tirent un effet parmi plusieurs et ne
portent aucune ligne elementaire a grouper.

**La source est gardee a la generation.** `_screen_random_element` arrete le
generateur si la phrase d'Ankama change **ou** si les chances cessent d'etre
egales, plutot que de laisser une moyenne fausse entrer dans le module.
"""
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

#: Le slot d'une ligne d'effet Retro qui porte sa chance, en pourcentage.
CHANCE_SLOT = 3
RANGS = ('l1', 'l2', 'l3', 'l4', 'l5', 'l6')


def _stats(**ajouts):
    """Un profil complet: la formule de degats lit toutes les clefs."""
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
        """Les sorts <<dans le meilleur element>> gardent leur meilleure
        face: la, le jeu choisit pour le lanceur."""
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
        """Le nombre que ce lot corrige. Sur un profil mono-element les deux
        faces sont tres inegales, et la meilleure valait 62% de plus."""
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
        """Pourquoi le defaut ne se voyait pas: sur un build equilibre, la
        moyenne et la meilleure face sont le meme nombre."""
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
        """La regle relue chez Ankama. Se met de cote quand retro_raw est
        absent, ce qui est le cas sur un depot propre."""
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
