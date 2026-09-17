# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Tout identifiant de condition present dans les donnees porte un nom.

`structure.read_weird_conditions_table` fait `WEIRD_CONDITION_FROM_ID[id]`,
sans defaut: un identifiant que la table de noms ignore leve une KeyError au
chargement du catalogue, donc sur toutes les pages de cette version, et
seulement apres un re-scrape.

Trouve en passant la beta a 3.7.0.0 le 17 septembre 2026. Ankama y a change la
regle des trophees: les 73 trophees restants sont passes de <<Set bonus < 3>> a
<<Set bonus < 2>>, et les 15 Carapaces ont perdu la condition. Le scraper ecrit
alors l'identifiant 3 la ou il ecrivait 1, et la base de la beta a porte cet
identifiant pour la premiere fois.

Ce coup-ci ca tient, parce que `structure.py` lit la table de noms de
`dofus_constants.py`, qui connait 1, 2 et 3. Mais `dofus_constants_beta.py` en
porte une copie qui ne connait que 1 et 2: le jour ou la lecture passerait par
la copie d'une version, la beta tomberait. Le parcours ci-dessous mesure ce que
les bases contiennent vraiment, pour qu'un identifiant 4 se voie ici et pas sur
une page.

Mesure du 17 septembre 2026, apres le re-scrape des cinq versions, en lignes:

| version | identifiants presents |
|---------|-----------------------|
| dofus3  | 1 (87), 2 (25) |
| beta    | 2 (25), 3 (73) |
| dofus2  | 2 (32), 3 (87) |
| touch   | 3 (71) |
| retro   | table vide |

L'identifiant 3 n'a donc jamais ete propre a Touch: dofus2 en portait deja 87
lignes avant ce lot. C'est une regle de jeu par version, pas une propriete de
l'identifiant.
"""
import os
import sqlite3
import unittest

from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import (LIGHT_SET_LIMIT_FROM_ID,
                                             WEIRD_CONDITION_FROM_ID)

PULP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'fashionistapulp', 'fashionistapulp')

BASES = {
    'dofus3': 'items.db',
    'beta': 'items_beta.db',
    'dofus2': 'items_dofus2.db',
    'touch': 'items_touch.db',
    'retro': 'items_retro.db',
}


def _condition_ids(chemin):
    connexion = sqlite3.connect('file:%s?mode=ro' % chemin, uri=True)
    try:
        table = connexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'item_weird_conditions'").fetchone()
        if not table:
            return None
        return sorted(row[0] for row in connexion.execute(
            'SELECT DISTINCT condition_id FROM item_weird_conditions'))
    finally:
        connexion.close()


class EveryConditionIdInTheDataHasANameTests(SimpleTestCase):

    def test_every_id_the_databases_carry_is_named(self):
        vus = {}
        for version, fichier in sorted(BASES.items()):
            chemin = os.path.join(PULP, fichier)
            if not os.path.exists(chemin):
                raise unittest.SkipTest('%s is absent' % fichier)
            ids = _condition_ids(chemin)
            if ids is None:
                continue
            vus[version] = ids
            for condition_id in ids:
                with self.subTest(version=version, condition_id=condition_id):
                    self.assertIn(condition_id, WEIRD_CONDITION_FROM_ID)
        self.assertTrue(vus, 'no database carried the table')

    def test_every_light_set_id_carries_its_cap(self):
        """Un identifiant light_set sans plafond retomberait sur 2, donc sur la
        regle de l'autre variante, en silence."""
        for condition_id, nom in WEIRD_CONDITION_FROM_ID.items():
            if nom != 'light_set':
                continue
            with self.subTest(condition_id=condition_id):
                self.assertIn(condition_id, LIGHT_SET_LIMIT_FROM_ID)
                self.assertGreaterEqual(LIGHT_SET_LIMIT_FROM_ID[condition_id],
                                        1)
