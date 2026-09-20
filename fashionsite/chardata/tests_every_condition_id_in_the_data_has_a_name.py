# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every condition id present in the data has a name in the table structure reads."""
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
        for condition_id, nom in WEIRD_CONDITION_FROM_ID.items():
            if nom != 'light_set':
                continue
            with self.subTest(condition_id=condition_id):
                self.assertIn(condition_id, LIGHT_SET_LIMIT_FROM_ID)
                self.assertGreaterEqual(LIGHT_SET_LIMIT_FROM_ID[condition_id],
                                        1)
