# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""La fiche d'un sort et le meilleur tour comptent avec la meme regle.

Trouve en exercant le panneau des sorts d'un Cra Dofus 2. La fiche de
<<Fleche Detonante>> affichait `0 ( vole 0 + 0)` pendant que le meilleur tour,
sur la meme page et le meme build, lui comptait **63 par lancer**.

Les deux ne calculaient pas pareil. La formule du serveur,
`dofus_constants.calculate_damage`, **borne la caracteristique et la Puissance
a zero** avant de multiplier:

    element_val = max(char_stats[...], 0)
    element_val = element_val + max(char_stats['pow'], 0)

Celle de la page ne les bornait pas: `100 + totalStats[mainStat]`. Des qu'une
caracteristique passait sous zero, le multiplicateur devenait negatif et la
fiche tombait a zero.

**Ce n'est pas qu'une affaire de fixtures absurdes.** Mesure du 14 septembre
2026 sur l'instantane local (79 builds, une copie de production plus des
lignes de test):

| build | version | niveau | caracteristiques | fiches en desaccord |
|-------|---------|--------|------------------|---------------------|
| 71 | dofus3 | 30 | -20 en For, Int, Cha | 11 sorts sur 14 |
| 86 | dofus2 | 30 | -785 | 12 sorts sur 13 |

Cinq des 79 builds portent au moins une caracteristique negative. A bas
niveau la base est a zero, donc une seule piece a malus suffit.

Apres: zero desaccord, et la fiche de <<Fleche Detonante>> affiche
<<60 (vole 26 + 34) a 64 (vole 29 + 35)>> la ou le tour compte 63.

Le JavaScript de la page ne peut pas etre execute ici. Ce garde tient donc
les deux bouts: la regle du serveur est verifiee en l'appelant, celle de la
page en lisant son texte, et aucun des deux cotes ne peut perdre sa borne
sans qu'un test tombe.
"""

import copy
import io
import os
import re

from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import BaseDamage, calculate_damage

_GABARIT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'templates', 'chardata', 'spells.html')

_SOCLE = {'agi': 0, 'str': 0, 'int': 0, 'cha': 0, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0}

#: La ligne que la page multiplie: `100 + <caracteristique>`.
_MULTIPLICATEUR = re.compile(r'var multiplier = 100 \+ ([^;]+);')
#: Et l'ajout de la Puissance, juste apres.
_PUISSANCE = re.compile(r"multiplier \+= ([^;]+);")


def _source_du_gabarit():
    with io.open(_GABARIT, encoding='utf-8') as fichier:
        return fichier.read()


class TheServerClampsAtZeroTests(SimpleTestCase):
    """La regle de reference, verifiee en appelant la formule elle-meme."""

    def _degats(self, **stats):
        ligne = BaseDamage(min_dam=100, max_dam=100, element='fire',
                           steals=False, heals=False)
        sortie = calculate_damage([copy.copy(ligne)],
                                  dict(_SOCLE, **stats), False, True)
        return int(sortie[0].max_dam)

    def test_a_negative_characteristic_counts_as_zero(self):
        self.assertEqual(self._degats(int=0), self._degats(int=-785))
        self.assertEqual(self._degats(int=0), self._degats(int=-20))

    def test_a_negative_power_counts_as_zero(self):
        self.assertEqual(self._degats(pow=0), self._degats(pow=-300))

    def test_the_formula_still_reads_a_positive_one(self):
        """Le plancher: sans lui, une formule qui rendrait toujours la meme
        chose passerait les deux tests ci-dessus."""
        self.assertGreater(self._degats(int=100), self._degats(int=0))
        self.assertGreater(self._degats(pow=100), self._degats(pow=0))


class ThePageClampsTheSameWayTests(SimpleTestCase):
    """Le JavaScript de la page ne s'execute pas ici; on lit sa formule."""

    def test_the_characteristic_is_clamped_before_multiplying(self):
        """Le test qui aurait attrape le defaut."""
        trouve = _MULTIPLICATEUR.search(_source_du_gabarit())
        self.assertIsNotNone(trouve, 'la formule de la page a disparu')
        self.assertIn('Math.max(', trouve.group(1),
                      'la page multiplie par une caracteristique non bornee: '
                      '%s' % trouve.group(1))

    def test_power_is_clamped_too(self):
        source = _source_du_gabarit()
        ajouts = [morceau for morceau in _PUISSANCE.findall(source)
                  if 'pow' in morceau.lower()]
        self.assertTrue(ajouts, 'la page n ajoute plus la Puissance')
        for ajout in ajouts:
            with self.subTest(ligne=ajout.strip()):
                self.assertIn('Math.max(', ajout)

    def test_weapon_power_is_folded_in_before_the_clamp(self):
        """`spell_combo` ajoute la Puissance d'arme a la Puissance AVANT
        d'appeler la formule, qui borne ensuite la somme. L'ajouter apres, et
        non bornee, etait une troisieme regle: le garde l'a attrapee."""
        source = _source_du_gabarit()
        self.assertIn("power += totalStats['powweap'];", source)
        self.assertNotIn("multiplier += totalStats['powweap'];", source)

    def test_the_page_names_the_formula_it_follows(self):
        """Une regle, un endroit: la page doit dire laquelle elle suit, sinon
        les deux repartiront chacune de leur cote."""
        self.assertIn('calculate_damage', _source_du_gabarit())


class NoOtherUnclampedMultiplierRemainsTests(SimpleTestCase):
    """L'invariant, pas un cas: aucune autre ligne de la page ne doit
    multiplier par une caracteristique brute."""

    def test_no_multiplier_reads_a_characteristic_without_clamping(self):
        fautifs = []
        for numero, ligne in enumerate(_source_du_gabarit().split('\n'), 1):
            if 'multiplier' not in ligne:
                continue
            if '100 + ' not in ligne and '+= ' not in ligne:
                continue
            if 'Math.max(' in ligne or 'totalStats' not in ligne:
                continue
            fautifs.append((numero, ligne.strip()[:90]))
        self.assertEqual([], fautifs)
