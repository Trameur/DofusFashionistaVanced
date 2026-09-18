# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Raising damage by a stat percent loses no point to float rounding."""

import copy

from django.test import SimpleTestCase


def _exact(base, percent):
    """Exact answer in integer arithmetic."""
    return (base * (100 + percent)) // 100


class TheHelperIsExactTests(SimpleTestCase):

    def test_the_case_that_broke_it(self):
        """25 raised by 360 percent is 115, not 114."""
        from fashionistapulp.dofus_constants import raised_by_percent
        self.assertEqual(115, raised_by_percent(25, 360))
        # What the old float form gave
        self.assertEqual(114, int((1 + 360 / 100.0) * 25))

    def test_it_never_differs_from_integer_arithmetic(self):
        """Same as integer arithmetic for every base and stat total."""
        from fashionistapulp.dofus_constants import raised_by_percent
        for base in range(0, 401):
            for percent in range(0, 1001, 1):
                attendu = _exact(base, percent)
                obtenu = raised_by_percent(base, percent)
                if obtenu != attendu:
                    self.fail('base %d, stat %d: %d au lieu de %d'
                              % (base, percent, obtenu, attendu))

    def test_a_float_stat_still_answers(self):
        """A float stat still truncates toward zero."""
        from fashionistapulp.dofus_constants import raised_by_percent
        self.assertEqual(115, raised_by_percent(25, 360.0))
        self.assertEqual(51, raised_by_percent(25.5, 100))


class TheFormulaIsExactEverywhereTests(SimpleTestCase):

    # Stat totals the old float form got wrong
    def _totaux_casses(self, bases):
        casses = []
        for total in range(0, 1501):
            if any(int((1 + total / 100.0) * base) != _exact(base, total)
                   for base in bases):
                casses.append(total)
        return casses

    def _bases_du_catalogue(self, version):
        from chardata.spell_buffs import get_damage_spells_for_version
        from chardata.version_compat import filter_classes_for_version
        from fashionistapulp.dofus_constants import CHARACTER_CLASSES
        from fashionistapulp.structure import set_current_game_version
        set_current_game_version(version)
        par_classe = get_damage_spells_for_version(version)
        valeurs = set()
        for classe in filter_classes_for_version(CHARACTER_CLASSES, version):
            for spell in par_classe.get(classe, []):
                digest = spell.get_effects_digest()
                for rang in (digest.non_crit_dams or []):
                    for effet in rang:
                        if str(effet.element).startswith('buff'):
                            continue
                        for base in (effet.min_dam, effet.max_dam):
                            if isinstance(base, int) and base > 0:
                                valeurs.add(base)
        return sorted(valeurs)

    def test_the_bad_stat_totals_still_exist_to_be_guarded(self):
        """The totals that broke the old form still exist."""
        bases = self._bases_du_catalogue('dofus3')
        self.assertGreater(len(bases), 100)
        casses = self._totaux_casses(bases)
        self.assertGreater(len(casses), 50,
                           'aucun total de stat ne casse l ancienne forme')

    def test_no_catalogue_value_loses_a_point_on_any_version(self):
        from fashionistapulp.dofus_constants import raised_by_percent
        from fashionistapulp.game_versions import version_keys
        vus = 0
        for version in version_keys():
            bases = self._bases_du_catalogue(version)
            self.assertTrue(bases, version)
            for total in self._totaux_casses(bases):
                for base in bases:
                    vus += 1
                    self.assertEqual(_exact(base, total),
                                     raised_by_percent(base, total),
                                     '%s: base %d, stat %d'
                                     % (version, base, total))
        self.assertGreater(vus, 10000, 'trop peu de couples verifies')


class TheTwoSidesAgreeTests(SimpleTestCase):

    def test_calculate_damage_answers_what_the_page_answers(self):
        """Same as the page's floor(base * (100 + stat) / 100) + flat."""
        from fashionistapulp.dofus_constants import (BaseDamage,
                                                     calculate_damage)
        stats = {'int': 100, 'pow': 260, 'firedam': 5, 'dam': 0, 'cridam': 0,
                 'perspedam': 0, 'perweadam': 0, 'heals': 0,
                 'str': 0, 'cha': 0, 'agi': 0,
                 'earthdam': 0, 'waterdam': 0, 'airdam': 0, 'neutdam': 0}
        ligne = BaseDamage(min_dam=22, max_dam=25, element='fire',
                           steals=False, heals=False)
        sortie = calculate_damage([copy.copy(ligne)], stats, False, True)
        self.assertEqual(1, len(sortie))
        self.assertEqual(120, int(round(sortie[0].max_dam)))
        # 22 * 4.6 = 101.2, truncated to 101, plus 5
        self.assertEqual(106, int(round(sortie[0].min_dam)))


class EveryCopyOfTheFormulaIsFixedTests(SimpleTestCase):

    def test_no_version_file_keeps_the_inexact_form(self):
        """All three constants files carry raised_by_percent."""
        import os

        import fashionistapulp
        racine = os.path.dirname(os.path.abspath(fashionistapulp.__file__))
        fichiers = ('dofus_constants.py', 'dofus_constants_beta.py',
                    'dofus_constants_dofus2.py')
        for nom in fichiers:
            chemin = os.path.join(racine, nom)
            with self.subTest(fichier=nom):
                with open(chemin, encoding='utf-8') as fichier:
                    source = fichier.read()
                self.assertNotIn('(1 + element_val / 100.0)', source)
                self.assertIn('def raised_by_percent', source)
