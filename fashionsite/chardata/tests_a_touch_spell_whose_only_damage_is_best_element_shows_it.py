# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un sort Touch dont tous les degats sont <<dans le meilleur element>> les
montre.

Trouve en lisant le panneau des sorts d'un Iop Touch. <<Intimidation>> y avait
sa fiche, son cout, sa portee, sa phrase d'Ankama, et **aucun degat**: ni coup
normal, ni coup critique. Le meilleur tour ne pouvait pas la lancer non plus.

**Pourquoi elle etait vide.** Sa seule ligne de degats est l'effet 1200
d'Ankama, `#1 a #2 (meilleur element)`, qui ne nomme aucun element. La lire
veut dire ecrire une ligne par element, et la question qui bloquait etait:
lesquels?

**Reponse, le 14 septembre 2026: les quatre qui ont une caracteristique a
eux.** Le neutre n'en est pas: la formule de degats du site lit le neutre sur
la Force exactement comme elle lit la Terre (`DAMAGE_TYPE_TO_MAIN_STAT`), donc
une face neutre ne pourrait jamais etre la meilleure pour son propre compte.
Le generateur de Dofus 3 ecrit les quatre memes.

**Mesure sur le backend d'Ankama, le meme jour:** 11 sorts de classe portent
l'effet 1200. Deux le portent a cote de lignes nommees, et ceux-la sont un
autre cas (voir
[[tests_touch_rows_that_land_together_are_not_a_choice]]). Les neuf autres ne
l'ont que lui, et **six** sont lus ici:

| sort | classe | dernier rang |
|------|--------|--------------|
| Fleche Cinglante | Cra | 26-30 |
| Punition | Sacrieur | 37-40 |
| Vol du Temps | Xelor | 33-36 |
| Epee Divine | Iop | 22-24 |
| Intimidation | Iop | 10-12 |
| Projection | Sacrieur | 12-14 |

**Trois restent dehors, chacun sur la phrase d'Ankama:**

- **Flasque Explosive** (Pandawa): les degats ne sont pas ceux du lanceur,
  <<la CIBLE infligera des dommages ... autour de sa cellule d'arrivee
  lorsqu'elle est lancee>>, et le lancer demande l'etat Porteur.
- **Fouet** (Osamodas): <<Tue une invocation de classe du lanceur>> d'abord,
  donc compter ses degats suppose une invocation a sacrifier, que le tour ne
  modele pas. Il porte en plus deux lignes 1200 par grade.
- **Carnavalo** (Zobal): deux lignes par grade aussi, la seconde pour l'etat
  Psychopathe, et le tour ne suppose aucun etat en force.

La table Touch passe donc de 174 a 180 sorts, en **ajouts seulement**: aucun
sort deja present n'a bouge.

**Les quatre faces sont bien une seule frappe.** Elles sont groupees comme
celles de Dofus 3, donc la table en dessine **une** ligne, celle que le
personnage frapperait, et le tour compte la meme
([[tests_a_hit_that_lands_in_one_element_is_drawn_once]]).

**La citation est relue a la generation.** `_best_element_is_the_whole_hit`
arrete le generateur si Ankama reformule, plutot que de laisser six sorts
compter des degats dont la raison a expire.
"""
from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import DAMAGE_TYPE_TO_MAIN_STAT
from fashionistapulp.dofus_constants_touch_spells import TOUCH_DAMAGE_SPELLS

#: Ce que chacun frappe a son dernier rang, lu sur le backend d'Ankama.
LUS = {
    'Flèche Cinglante': ('Cra', 26, 30),
    'Punition': ('Sacrier', 37, 40),
    'Vol du Temps': ('Xelor', 33, 36),
    'Epée Divine': ('Iop', 22, 24),
    'Intimidation': ('Iop', 10, 12),
    'Projection': ('Sacrier', 12, 14),
}

#: Ceux qui restent dehors, et qui doivent le rester tant que leur phrase dit
#: ce qu'elle dit.
DEHORS = ('Flasque Explosive', 'Fouet', 'Carnavalo')

FACES = ('earth', 'fire', 'water', 'air')


def _touch_spells():
    for class_name, spells in TOUCH_DAMAGE_SPELLS.items():
        for spell in spells:
            yield class_name, spell


class ATouchSpellWhoseOnlyDamageIsBestElementShowsItTests(SimpleTestCase):

    def test_the_six_spells_hit_in_four_faces_of_the_same_size(self):
        vus = {}
        for class_name, spell in _touch_spells():
            if spell.name not in LUS:
                continue
            vus[spell.name] = class_name
            attendue_classe, low, high = LUS[spell.name]
            digest = spell.get_effects_digest()
            rows = digest.non_crit_dams[-1]
            with self.subTest(sort=spell.name):
                self.assertEqual(attendue_classe, class_name)
                self.assertEqual(list(FACES),
                                 [row.element for row in rows])
                self.assertEqual({(low, high)},
                                 {(row.min_dam, row.max_dam) for row in rows},
                                 'the four faces are one hit, so they hold '
                                 'one value')
        self.assertEqual(set(LUS), set(vus), 'a spell left the Touch table')

    def test_the_four_faces_are_one_hit_and_not_four(self):
        for _class_name, spell in _touch_spells():
            if spell.name not in LUS:
                continue
            labels = [label for label, _indices in (spell.aggregates or [])]
            with self.subTest(sort=spell.name):
                self.assertEqual(4, len(labels), labels)
                self.assertEqual('Hit in best element', labels[0])
                self.assertEqual(['', '', ''], labels[1:])

    def test_neutral_is_not_a_face_because_it_has_no_stat_of_its_own(self):
        """Ce qui autorise quatre et non cinq: le neutre se lit sur la meme
        caracteristique que la terre, donc il ne peut pas etre le meilleur
        pour son propre compte."""
        self.assertEqual(DAMAGE_TYPE_TO_MAIN_STAT['neut'],
                         DAMAGE_TYPE_TO_MAIN_STAT['earth'])
        for _class_name, spell in _touch_spells():
            if spell.name not in LUS:
                continue
            with self.subTest(sort=spell.name):
                self.assertNotIn('neutral',
                                 [row.element
                                  for row in spell.get_effects_digest()
                                  .non_crit_dams[-1]])

    def test_the_three_that_stay_out_stay_out(self):
        """Leur raison est dans la phrase d'Ankama, pas dans un oubli: un
        rebuild qui les fait entrer est un sort que personne n'a relu."""
        present = {spell.name for _class_name, spell in _touch_spells()}
        for name in DEHORS:
            with self.subTest(sort=name):
                self.assertNotIn(name, present)

    def test_the_table_grew_by_exactly_those_six(self):
        total = sum(1 for _class_name, _spell in _touch_spells())
        self.assertEqual(180, total,
                         'the Touch table held 174 before these six')
        grouped = [spell.name for _class_name, spell in _touch_spells()
                   if any(label == 'Hit in best element'
                          for label, _indices in (spell.aggregates or []))]
        self.assertEqual(sorted(LUS), sorted(grouped),
                         'only the spells read on Ankama\'s sentence carry '
                         'the group')
