# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Retro est la seule version ou une arme frappe tant qu'il reste des PA.

Trouve en lisant le meilleur tour d'un Cra Retro: il lance quatre fois la
meme epee, 5 PA chacune, sur ses 21 PA. Aucune des quatre autres versions ne
le ferait avec une arme limitee.

**La regle est celle d'Ankama, pas notre lecture du jeu.** Dans le client
Retro (lang des objets 1260), **chacune des 4363 armes** porte exactement
huit champs:

    [twoHanded, _, crit_chance, crit_failure, maxRange, minRange, ap,
     crit_bonus]

Aucun n'est un nombre d'utilisations. Le champ n'existe pas dans ce client-la,
alors que les quatre autres versions le portent:

| version | armes qui portent une limite |
|---------|------------------------------|
| dofus3 | 766 |
| beta | 766 |
| dofus2 | 723 |
| touch | 698 |
| **retro** | **0** |

Mesure du 14 septembre 2026, sur les bases d'objets du depot.

**Ce que ce parcours protege.** Le code lisait `uses_per_turn` et tombait sur
rien en Retro, ce qui donnait la bonne reponse par accident: la table
`weapon_uses_per_turn` n'existe pas dans `items_retro.db`, et
`structure.py` la saute quand elle manque. Le jour ou un rebuild Retro se
mettrait a l'ecrire, le tour Retro changerait sans que rien ne le dise. Le
nombre est donc ici, avec les quatre autres a cote de lui pour que l'absence
se lise comme une absence et non comme un oubli.
"""
import os
import sqlite3

from django.test import SimpleTestCase

PULP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'fashionistapulp', 'fashionistapulp')

#: version -> (fichier, armes qui portent une limite le 14 septembre 2026)
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
        """Ce que le tour en fait: une arme Retro n'a pas de limite, une arme
        moderne en a une."""
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
