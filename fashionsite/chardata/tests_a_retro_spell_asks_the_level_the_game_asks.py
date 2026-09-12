# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le niveau requis d'un sort Retro est celui du jeu, pas une constante.

Le lecteur de sorts Retro ecrivait le niveau requis a la main:
`[1] * (n - 1) + [100]`, autrement dit <<tous les rangs sauf le dernier sont
accessibles au niveau 1, le dernier au niveau 100>>. La donnee du jeu le dit
pourtant, dans le slot 2 de chaque tableau de rang.

**Mesure du 12 septembre 2026** sur les 252 sorts de classe de
`classes_fr.json`: chaque classe porte exactement l'echelle 1, 3, 6, 9, 13,
17, 21, 26, 31, 36, 42, 48, 54, 60, 70, 80, 90, 100, plus 200 pour
l'invocation de Dopeul, et le rang 6 demande ce niveau **plus 100**. Un sort
appris a 36 atteint son rang 6 a 136, pas a 100.

Ce que la regle ecrite a la main faisait au panneau du meilleur tour, sur les
106 sorts de degats du module:

- **89 sur 106** portaient un niveau de base de 1 quand le jeu en demande de
  3 a 100;
- **106 sur 106** annoncaient leur dernier rang a 100;
- un personnage de **niveau 1 recevait 106 sorts la ou le jeu en donne 17**;
- un personnage de **niveau 100 les lisait tous au rang 6**, que le jeu
  refuse a tous les 106.

Le panneau promettait donc a un joueur Retro debutant un tour qu'il ne peut
pas jouer, avec des sorts qu'il n'a pas et a des rangs qu'il n'a pas montes.

Voir [[feedback-no-hardcoding]]: la donnee etait la, il suffisait de la lire.
"""

import io
import json
import os

from django.test import SimpleTestCase

#: L'echelle des dix-huit emplacements de sort d'une classe Retro, lue dans
#: classes_fr.json le 12 septembre 2026. `retro_raw` n'est pas dans le depot,
#: donc le nombre est ecrit ici avec sa source, pas devine.
ECHELLE = [1, 3, 6, 9, 13, 17, 21, 26, 31, 36, 42, 48, 54, 60, 70, 80, 90, 100]

#: L'artefact que le lecteur ecrit a cote du module, lui, est dans le depot.
ARTEFACT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper', 'retro',
    'retro_damage_spells.json')


def _sorts():
    from fashionistapulp.dofus_constants_retro_spells import (
        RETRO_DAMAGE_SPELLS)
    return [(classe, sort)
            for classe, sorts in RETRO_DAMAGE_SPELLS.items()
            for sort in sorts]


class TheLevelsComeFromTheGameTests(SimpleTestCase):

    def test_the_spells_do_not_all_ask_the_same_level(self):
        """La regle ecrite a la main donnait une seule forme aux 106 sorts.
        Le jeu en donne dix-huit, une par emplacement de la classe."""
        formes = {tuple(sort.level_req) for _classe, sort in _sorts()}
        self.assertEqual(18, len(formes), sorted(formes))

    def test_the_base_levels_are_the_ladder_the_game_uses(self):
        bases = {sort.level_req[0] for _classe, sort in _sorts()}
        self.assertEqual(set(ECHELLE), bases)

    def test_only_seventeen_spells_start_at_level_one(self):
        """Le panneau en offrait 106 a un personnage de niveau 1."""
        depart = [sort.name for _classe, sort in _sorts()
                  if sort.level_req[0] == 1]
        self.assertEqual(17, len(depart), sorted(depart))

    def test_the_last_rank_asks_a_hundred_levels_above_the_spell(self):
        """Ranks 1 a 5 se paient en points de sort, donc partagent le niveau
        du sort; le rang 6 demande ce niveau plus 100."""
        for classe, sort in _sorts():
            with self.subTest(classe=classe, sort=sort.name):
                req = list(sort.level_req)
                self.assertEqual(6, len(req))
                base = req[0]
                self.assertEqual([base] * 5, req[:5])
                self.assertEqual(base + 100, req[5])

    def test_the_module_says_what_the_scraper_wrote_beside_it(self):
        """Le module est genere; une retouche a la main y passerait inapercue
        sans ce rapprochement avec l'artefact du meme lecteur."""
        with io.open(ARTEFACT, encoding='utf-8') as fichier:
            artefact = json.load(fichier)
        attendu = {}
        entrees = (artefact.values() if isinstance(artefact, dict)
                   else [artefact])
        for sorts in entrees:
            for entree in sorts:
                if isinstance(entree, dict) and entree.get('level_reqs'):
                    attendu[entree['name']] = list(entree['level_reqs'])
        self.assertEqual(106, len(attendu), 'artefact incomplet')
        for _classe, sort in _sorts():
            with self.subTest(sort=sort.name):
                self.assertIn(sort.name, attendu)
                self.assertEqual(attendu[sort.name], list(sort.level_req))


class ThePanelFollowsTheLevelTests(SimpleTestCase):

    def _castables(self, char_class, level):
        from chardata.spell_combo import castable_spells
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version('retro')
        return castable_spells(char_class, level, 'retro')

    def test_a_beginner_is_offered_fewer_spells_than_a_level_two_hundred(self):
        """Mesure du 12 septembre 2026: le Cra Retro passe de 3 sorts
        jouables au niveau 1 a 18 au niveau 100. Avant, c'etait 18 partout."""
        for char_class in ('Cra', 'Iop', 'Xelor'):
            with self.subTest(classe=char_class):
                debutant = len(self._castables(char_class, 1))
                milieu = len(self._castables(char_class, 50))
                complet = len(self._castables(char_class, 200))
                self.assertLess(debutant, milieu)
                self.assertLess(milieu, complet)
                self.assertLessEqual(debutant * 3, complet)

    def test_no_spell_is_read_at_a_rank_the_level_refuses(self):
        """Le rang lu doit etre celui que le niveau atteint, et la donnee du
        jeu est maintenant ce qui le decide."""
        from chardata.spell_buffs import _decide_spell_level
        for niveau in (1, 20, 50, 100, 120, 150, 199):
            for char_class in ('Cra', 'Iop', 'Eniripsa'):
                for castable in self._castables(char_class, niveau):
                    spell = castable.spell
                    rang = _decide_spell_level(spell.level_req, niveau)
                    with self.subTest(niveau=niveau, sort=spell.name):
                        self.assertGreaterEqual(niveau,
                                                spell.level_req[rang])
