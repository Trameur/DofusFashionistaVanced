# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Sur Touch, des lignes qui tombent ensemble ne sont pas un choix.

Trouve en cherchant, dans les clients modernes, les sorts qu'Ankama tire au
sort comme le Bluff de Retro. Un seul en porte la marque (l'Embuscade du
Steamer, `random` sur trois scripts lies), et en lisant sa fiche pour le
verifier, c'est un autre defaut qui est sorti.

**Ce que le site faisait.** Deux sorts Touch, l'Embuscade du Steamer et la
Fanfaronnade de l'Ecaflip, portaient trois lignes elementaires groupees en
<<Coup dans le meilleur element>>: la table en montrait une, le tour en
comptait une.

**Ce qu'Ankama en dit, dans sa propre phrase:**

    Embuscade      Occasionne des dommages Feu, Eau et Terre **ainsi que**
                   des degats dans le meilleur element du lanceur.
    Fanfaronnade   Occasionne des dommages Air, Eau, Terre **et** dans le
                   meilleur element.

Les trois elements sont nommes comme tombant, et le coup dans le meilleur
element est un **quatrieme**, pas leur resume.

**Les deux clients freres disent la meme chose.** Dofus 2 et Dofus 3 ecrivent
l'Embuscade en quatre lignes **sans aucun groupe**, sous la meme forme de
phrase (<<Occasionne des dommages Eau, Terre, Air et Feu>>), et les
additionnent. Touch a herite du meme sort et le rendait autrement.

**D'ou venait l'erreur.** Ces deux sorts portent l'effet <<meilleur element>>
(1200) **a cote** de lignes elementaires nommees, et cela avait ete lu comme
<<ces lignes SONT le coup dans le meilleur element, ecrit en clair>>, ce que
fait Dofus 3. Mais Dofus 3 **fabrique** ses lignes a partir d'un effet qui ne
nomme aucun element (voir
[[project-best-element-is-one-fabricated-row-set]]), alors que celles-ci sont
celles d'Ankama.

**Ce que la correction change, mesure le 14 septembre 2026 sur un lanceur a
400 dans chaque caracteristique:**

| sort | avant | apres |
|------|-------|-------|
| Embuscade | 80,2 | **240,8** |
| Fanfaronnade | 65,0 | **195,0** |

Exactement trois fois: le site en montrait un tiers.

**Ce que la correction ne fait pas.** Le quatrieme coup, celui dans le
meilleur element, n'est toujours pas dans nos donnees Touch: le generateur ne
lit pas l'effet 1200, comme pour les neuf autres sorts Touch qui n'ont que
cette ligne-la. Les deux sorts restent donc en dessous de ce que le jeu
frappe, et inventer une valeur serait pire que de la laisser manquer.

**Ce parcours en remplace un autre, qui disait le contraire.**
`TouchBestElementSpellsLandOneHitTests`, dans `tests.py`, demandait que ces
deux sorts soient des alternatives, et sa raison etait que <<Dofus 3 ecrit la
forme identique et la groupe>>. C'est ce rapprochement qui etait faux: Dofus 3
groupe ses sorts a element fabrique (Intimidation, Scalpel), et il ecrit
l'Embuscade, lui, en quatre lignes nommees **sans groupe**. Les deux formes se
ressemblent une fois generees et ne viennent pas du meme endroit. L'ancien
parcours est retire plutot que reecrit: ce qu'il surveillait d'utile, qu'aucun
sort Touch ne soit groupe sans qu'on ait lu Ankama, est ici.

**La citation est relue a la generation.** `_named_rows_also_land` arrete le
generateur si Ankama reformule, plutot que de laisser un groupement dont la
raison a expire.
"""
import io
import json
import os

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version

RACINE = os.path.dirname(os.path.abspath(__file__))
REFERENCE = os.path.join(RACINE, 'spell_reference', 'touch.json')

#: Le sort, sa classe, et le morceau de la phrase d'Ankama qui dit que ses
#: lignes nommees tombent a cote du coup dans le meilleur element.
ENSEMBLE = {
    'Embuscade': ('Foggernaut', 'Ambush',
                  'and damage in the caster’s best element'),
    'Fanfaronnade': ('Ecaflip', 'Bravado', 'and best-element damage'),
}


def _touch_spell(class_name, spell_name):
    for spell in get_damage_spells_for_version('touch')[class_name]:
        if spell.name == spell_name:
            return spell
    raise AssertionError('%s/%s left the Touch table'
                         % (class_name, spell_name))


def _reference_description(class_name, english_name):
    data = json.load(io.open(REFERENCE, encoding='utf-8', errors='replace'))
    for entry in data.get(class_name, []):
        names = entry.get('name') or {}
        if english_name in [str(value) for value in names.values()]:
            return (entry.get('description') or {}).get('en') or ''
    raise AssertionError('%s not in the Touch reference' % english_name)


class TouchRowsThatLandTogetherAreNotAChoiceTests(SimpleTestCase):

    def test_the_two_spells_add_their_rows_up(self):
        for spell_name, (class_name, _english, _quote) in sorted(
                ENSEMBLE.items()):
            spell = _touch_spell(class_name, spell_name)
            digest = spell.get_effects_digest()
            with self.subTest(sort=spell_name):
                self.assertEqual([], list(digest.aggregates or []),
                                 'grouped again, so the panel shows one hit '
                                 'of three')
                lignes = (digest.non_crit_dams or [[]])[0]
                elements = [ligne.element for ligne in lignes]
                self.assertEqual(3, len(elements), elements)
                self.assertEqual(3, len(set(elements)),
                                 'the three rows must be three elements')

    def test_ankama_says_the_named_rows_land_beside_the_best_one(self):
        """La phrase qui autorise la somme, relue dans la reference Touch du
        depot."""
        for spell_name, (class_name, english, quote) in sorted(
                ENSEMBLE.items()):
            texte = _reference_description(class_name, english)
            with self.subTest(sort=spell_name):
                self.assertTrue(texte, english)
                # L'apostrophe d'Ankama est typographique dans ce fichier.
                normalise = texte.replace('’', "'")
                self.assertIn(quote.replace('’', "'"), normalise,
                              'Ankama reworded it: %r' % texte[:160])

    def test_the_sibling_clients_write_the_same_spell_without_a_group(self):
        """Le temoin de l'autre cote: la ou le site lit les lignes d'Ankama
        telles quelles, il les additionne deja."""
        for version in ('dofus2', 'dofus3'):
            spell = None
            for spells in get_damage_spells_for_version(version).values():
                for candidate in spells:
                    if candidate.name == 'Ambush':
                        spell = candidate
            with self.subTest(version=version):
                self.assertIsNotNone(spell)
                digest = spell.get_effects_digest()
                self.assertEqual([], list(digest.aggregates or []))
                lignes = (digest.non_crit_dams or [[]])[0]
                self.assertEqual(4, len(lignes), lignes)

    def test_a_fabricated_best_element_group_is_untouched(self):
        """Ce que la correction ne doit pas emporter: Dofus 3 fabrique ses
        lignes a partir d'un effet sans element, et celles-la sont bien les
        faces d'un seul coup."""
        garde = 0
        for spells in get_damage_spells_for_version('dofus3').values():
            for spell in spells:
                if any(label == 'Hit in best element'
                       for label, _indices in (spell.aggregates or [])):
                    garde += 1
        self.assertEqual(31, garde,
                         'the Dofus 3 groups moved, and this lot did not '
                         'touch them')
        # Touch en groupe six depuis le meme jour, et ceux-la le meritent:
        # leurs lignes sont fabriquees a partir de l'effet 1200, voir
        # [[tests_a_touch_spell_whose_only_damage_is_best_element_shows_it]].
        # Ce qui ne doit pas revenir, ce sont ces deux-ci.
        for spells in get_damage_spells_for_version('touch').values():
            for spell in spells:
                if spell.name not in ENSEMBLE:
                    continue
                self.assertFalse(
                    [label for label, _indices in (spell.aggregates or [])
                     if label == 'Hit in best element'],
                    '%s is grouped again' % spell.name)
