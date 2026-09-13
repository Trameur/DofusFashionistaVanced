# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le bloc des degats differes s'additionne.

Le panneau du meilleur tour reporte a part ce que le tour place mais qui ne
tombe pas maintenant: un poison, une bombe, tout ce que la donnee du jeu
marque comme differe. Il arrondissait **chaque ligne** de son cote et **le
total** du sien, ce qui est exactement le defaut corrige a la section 58 pour
l'echelle des lancers, laisse en place dans ce bloc-la.

**Ce qui l'avait cache.** Un panneau ne montre qu'une ligne par SORT, pas par
lancer. Deux lignes demandent donc deux sorts differes dans le meme tour, et
le tour optimal se concentre presque toujours sur le meilleur: sur les 73
builds de la base locale, 15 portaient des degats differes et **tous les 15
n'avaient qu'une seule ligne**, ou l'ecart est impossible. Le premier examen
avait donc rendu <<zero ecart>> sans rien prouver.

**Mesure du 14 septembre 2026**, sur le cas qui atteint deux lignes, un
Osamodas Dofus 2 oriente Chance: sur **384 panneaux a deux lignes, 75
affichaient un total qui n'etait pas la somme des lignes au-dessus** (19,5 %).
A 550 de Chance, les lignes disaient 214 et 290, soit 504, sous un total de
503.

La correction suit la meme regle que l'echelle des lancers: le cumul est
arrondi une seule fois et chaque ligne est sa difference avec la precedente.
**Le total garde sa valeur** (c'est le nombre exact) et c'est la ligne qui
s'ajuste: 214 et 289 sous 503.
"""

from django.test import SimpleTestCase

#: Les points mesures divergents le 14 septembre 2026, avec la Chance qui les
#: produit. Ce ne sont pas des valeurs choisies au hasard: chacun affichait un
#: total faux avant le changement.
_CHANCES_TEMOINS = (550, 557, 662, 669, 704, 711)

_VERSION = 'dofus2'
_CLASSE = 'Osamodas'


class _Char(object):
    char_class = _CLASSE
    level = 200


class _Solution(object):
    """Ce que le panneau lit d'une solution: ses stats, et ses objets."""

    def __init__(self, stats):
        self._stats = stats
        self.items = {}

    def get_stats_total(self):
        return self._stats


def _stats(chance, ap=12):
    from fashionistapulp.structure import get_structure
    stats = dict((cle, 0) for cle in get_structure(_VERSION).stat_dict_key)
    stats.update({'ap': ap, 'str': 60, 'int': 60, 'agi': 60, 'pow': 30,
                  'earthdam': 40, 'firedam': 40, 'waterdam': 40,
                  'airdam': 40, 'neutdam': 40, 'perspedam': 30, 'ch': 20,
                  'cha': chance})
    return stats


def _panneau(chance, ap=12):
    from chardata.spells_view import _best_combo
    from fashionistapulp.structure import set_current_game_version
    set_current_game_version(_VERSION)
    return _best_combo(_Char(), _Solution(_stats(chance, ap)), _VERSION)


class TheDelayedRowsAddUpToTheirTotalTests(SimpleTestCase):

    def test_the_witnesses_still_show_two_rows(self):
        """Le plancher, et c'est lui qui manquait la premiere fois.

        Avec une seule ligne, arrondir la ligne ou la somme donne le meme
        entier: le test passerait sans rien garder. Il exige donc que chaque
        temoin atteigne bien deux lignes.
        """
        maigres = []
        for chance in _CHANCES_TEMOINS:
            panneau = _panneau(chance)
            self.assertIsNotNone(panneau, chance)
            lignes = panneau.get('later') or []
            if len(lignes) < 2:
                maigres.append((chance, len(lignes)))
        self.assertFalse(
            maigres,
            'these witnesses no longer reach two delayed rows, so the check '
            'below proves nothing: %s' % maigres)

    def test_the_rows_add_up_to_the_total(self):
        faux = []
        for chance in _CHANCES_TEMOINS:
            panneau = _panneau(chance)
            lignes = panneau.get('later') or []
            somme = sum(ligne['damage'] for ligne in lignes)
            if somme != panneau.get('later_total'):
                faux.append((chance, [l['damage'] for l in lignes], somme,
                             panneau.get('later_total')))
        self.assertFalse(
            faux,
            'the delayed rows do not add up to the total printed above them, '
            'which a reader checking the addition sees: %s' % faux)

    def test_the_total_keeps_the_accurate_value(self):
        """La correction devait bouger la LIGNE, pas le total.

        Gonfler le total pour qu'il colle aux lignes arrondies aurait rendu le
        panneau coherent et faux: le total est le seul des deux qui soit exact.
        A 550 de Chance il valait 503 avant le changement, il vaut 503 apres.
        """
        panneau = _panneau(550)
        self.assertEqual(503, panneau['later_total'])
        self.assertEqual([214, 289],
                         [ligne['damage'] for ligne in panneau['later']])

    def test_a_single_row_still_says_the_whole_total(self):
        """Le cas courant, que la correction ne doit pas abimer: une ligne,
        et elle porte tout le total."""
        vus = 0
        for chance in (200, 300, 400):
            panneau = _panneau(chance)
            if panneau is None:
                continue
            lignes = panneau.get('later') or []
            if len(lignes) != 1:
                continue
            vus += 1
            self.assertEqual(lignes[0]['damage'], panneau['later_total'],
                             chance)
        self.assertGreater(vus, 0, 'no single-row panel reached')
