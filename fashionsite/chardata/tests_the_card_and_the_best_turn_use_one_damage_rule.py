# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The spell card's damage formula must clamp a negative stat like the server does."""

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

_MULTIPLICATEUR = re.compile(r'var multiplier = 100 \+ ([^;]+);')
_PUISSANCE = re.compile(r"multiplier \+= ([^;]+);")


def _source_du_gabarit():
    with io.open(_GABARIT, encoding='utf-8') as fichier:
        return fichier.read()


class TheServerClampsAtZeroTests(SimpleTestCase):

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
        """Guards against a formula that ignores the stat entirely."""
        self.assertGreater(self._degats(int=100), self._degats(int=0))
        self.assertGreater(self._degats(pow=100), self._degats(pow=0))


class ThePageClampsTheSameWayTests(SimpleTestCase):
    """The page's JavaScript cannot run here; this reads its source instead."""

    def test_the_characteristic_is_clamped_before_multiplying(self):
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
        """spell_combo adds weapon power to power before the formula clamps the sum."""
        source = _source_du_gabarit()
        self.assertIn("power += totalStats['powweap'];", source)
        self.assertNotIn("multiplier += totalStats['powweap'];", source)

    def test_the_page_names_the_formula_it_follows(self):
        self.assertIn('calculate_damage', _source_du_gabarit())


class NoOtherUnclampedMultiplierRemainsTests(SimpleTestCase):
    """No other line in the page may multiply by an unclamped stat."""

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
