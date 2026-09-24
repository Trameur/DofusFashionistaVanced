# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Retro is the only version where a weapon has no per-turn use limit."""
import os
import sqlite3

from django.test import SimpleTestCase

PULP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'fashionistapulp', 'fashionistapulp')

# version -> (db file, weapons carrying a per-turn use limit)
BASES = {
    'dofus3': ('items.db', 766),
    'beta': ('items_beta.db', 766),
    'dofus2': ('items_dofus2.db', 723),
    'touch': ('items_touch.db', 698),
    'retro': ('items_retro.db', 0),
}


def _limited(fichier):
    chemin = os.path.join(PULP, fichier)
    base = sqlite3.connect('file:%s?mode=ro' % chemin.replace('\\', '/'),
                           uri=True)
    try:
        existe = base.execute(
            "select count(*) from sqlite_master where type='table' "
            "and name='weapon_uses_per_turn'").fetchone()[0]
        if not existe:
            return 0
        return base.execute(
            'select count(*) from weapon_uses_per_turn '
            'where value is not null and value > 0').fetchone()[0]
    finally:
        base.close()


class OnlyRetroLetsAWeaponSwingAllTurnTests(SimpleTestCase):

    def test_retro_carries_no_weapon_limit_and_the_others_do(self):
        compte = {version: _limited(fichier)
                  for version, (fichier, _attendu) in sorted(BASES.items())}
        attendu = {version: nombre
                   for version, (_fichier, nombre) in sorted(BASES.items())}
        self.assertEqual(attendu, compte)

    def test_the_castable_reads_that_absence_as_no_limit(self):
        """A Retro weapon has no limit; a modern one does."""
        from chardata.spell_combo import WeaponCastable

        class _Arme(object):
            name = 'temoin'
            ap = 4
            non_crit_hits = {}
            crit_hits = {}

        retro = _Arme()
        moderne = _Arme()
        moderne.uses_per_turn = 2
        self.assertIsNone(WeaponCastable(retro).limit)
        self.assertEqual(2, WeaponCastable(moderne).limit)
