# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le pourcentage de degats ne perd plus un point a l'arrondi.

`calculate_damage` majorait la valeur de base ainsi:

    int((1 + element_val / 100.0) * dam.min_dam)

En binaire, `1 + 360 / 100.0` vaut **4.5999999999999996**. Une valeur de base
de 25 donne donc **114.99999999999999**, tronquee a **114**, quand la valeur
exacte est 115. Multiplier avant de diviser garde les entiers exacts, ce que la
page des sorts fait deja de son cote en JavaScript.

**Comment le defaut est sorti.** En comparant, sur un meme build, ce que la
page calcule et ce que le serveur calcule pour chaque sort: deux formules pour
la meme question. Sur un Cra de niveau 200 de la copie locale, stat principale
plus Puissance a 360 pour le feu, **7 de ses 49 sorts annoncaient un nombre
different dans la table et dans le panneau**. Fleche Radieuse: la table disait
120, le panneau 119, et c'est la table qui avait raison.

**Ampleur, mesuree le 12 septembre 2026.** Le defaut a besoin de deux
coincidences: un `1 + x/100` inexact en binaire ET un produit qui tombe juste
sous l'entier. Il ne se produit donc que pour **102 des 1501 totaux de stat de
0 a 1500**, soit 6,8 %. Mais quand il se produit il touche jusqu'a **11,1 % des
valeurs de degats du catalogue** (531 sur 4770 en Dofus 3, au total 720), et
4,5 % au total 360.

Il atteignait trois surfaces, toutes celles qui appellent `calculate_damage`:
le panneau du meilleur tour, les degats de l'arme sur la page du build, et la
fenetre de comparaison d'objets.

La correction est dans les trois fichiers de constantes qui portent la formule
(`dofus_constants`, `_beta`, `_dofus2`). Les deux derniers ne servent plus que
leurs tables de sorts, mais laisser une copie connue fausse d'une formule est
un piege pour qui la relira.
"""

import copy

from django.test import SimpleTestCase


def _exact(base, percent):
    """La reponse exacte, en arithmetique entiere et sans flottant."""
    return (base * (100 + percent)) // 100


class TheHelperIsExactTests(SimpleTestCase):

    def test_the_case_that_broke_it(self):
        """25 points de base majores de 360 pour cent font 115, pas 114."""
        from fashionistapulp.dofus_constants import raised_by_percent
        self.assertEqual(115, raised_by_percent(25, 360))
        # Ce que l'ancienne forme donnait, pour que le test dise ce qu'il garde.
        self.assertEqual(114, int((1 + 360 / 100.0) * 25))

    def test_it_never_differs_from_integer_arithmetic(self):
        """Balayage large: aucune valeur de base et aucun total de stat ne doit
        s'ecarter de la reponse entiere exacte."""
        from fashionistapulp.dofus_constants import raised_by_percent
        for base in range(0, 401):
            for percent in range(0, 1001, 1):
                attendu = _exact(base, percent)
                obtenu = raised_by_percent(base, percent)
                if obtenu != attendu:
                    self.fail('base %d, stat %d: %d au lieu de %d'
                              % (base, percent, obtenu, attendu))

    def test_a_float_stat_still_answers(self):
        """Les stats peuvent arriver en flottant; la fonction ne doit pas
        exploser, et reste une troncature vers zero comme avant."""
        from fashionistapulp.dofus_constants import raised_by_percent
        self.assertEqual(115, raised_by_percent(25, 360.0))
        self.assertEqual(51, raised_by_percent(25.5, 100))


class TheFormulaIsExactEverywhereTests(SimpleTestCase):

    #: Les totaux de stat qui cassaient l'ancienne forme, pris dans le balayage
    #: du 12 septembre 2026: 102 des 1501 totaux de 0 a 1500.
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
        """Sans ces totaux le test ne garderait rien: c'est eux qui faisaient
        perdre un point."""
        bases = self._bases_du_catalogue('dofus3')
        self.assertGreater(len(bases), 100)
        casses = self._totaux_casses(bases)
        self.assertGreater(len(casses), 50,
                           'aucun total de stat ne casse l ancienne forme')

    def test_no_catalogue_value_loses_a_point_on_any_version(self):
        """Sur les cinq catalogues et sur les totaux de stat qui cassaient
        l'ancienne forme, la formule doit repondre la valeur entiere exacte."""
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
        """La page calcule `floor(base * (100 + stat) / 100) + lineaire`. Le
        serveur doit donner le meme nombre, sinon la table et le panneau se
        contredisent sur la meme page, ce qui etait le cas sur 7 sorts.

        Le cas est celui de Fleche Radieuse: base 25 en feu, Intelligence 100
        plus Puissance 260, 5 de dommages Feu. La page disait 120.
        """
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
        # 22 * 4.6 = 101.2, tronque a 101, plus 5.
        self.assertEqual(106, int(round(sortie[0].min_dam)))


class EveryCopyOfTheFormulaIsFixedTests(SimpleTestCase):

    def test_no_version_file_keeps_the_inexact_form(self):
        """Trois fichiers portent la meme formule. En laisser un avec la forme
        inexacte trompe qui le relira, et la remettrait en circulation."""
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
