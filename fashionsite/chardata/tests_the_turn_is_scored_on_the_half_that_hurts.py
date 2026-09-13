# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un sort qui frappe les ennemis n'est pas note sur sa moitie qui soigne.

Trouve en jouant: un Eniripsa Dofus 2 de niveau 45, cree depuis les pages du
site. Son meilleur tour depensait 2 PA sur <<Peinture de Guerre>> et lui
comptait **zero**, sans meme une note.

**Ce n'etait pas une note qui manquait, c'etait un tour sous-estime.** La
table des degats de la meme page montrait pourtant les deux moities du sort,
<<Soins 22 a 26>> **et** <<25 - 27>>: seul le panneau perdait la seconde. Le
tour passe de 175 a **208**, dix-neuf pour cent de plus.

**Ce que le jeu dit de ces sorts, dans ses propres mots** (fiche du client,
lue le 20 septembre 2026):

| sort | description |
|------|-------------|
| Peinture de Guerre | <<occasionne des dommages Terre aux ennemis ou soigne les allies>> |
| Pinceau Tribal | <<soigne les allies ou occasionne des dommages Terre aux ennemis>> |
| Mot Secret | <<Soigne les allies et occasionne des dommages Air aux ennemis en zone>> |

Le panneau compte <<un seul tour sur une cible>>, et cette cible est un
ennemi: c'est la moitie qui frappe qu'il doit lire.

**Pourquoi la regle se dit par le soin et non par le zero.** Le repli de
`Castable` prenait toujours le premier groupe d'agregats, ce qui est juste
pour un sort a paliers (<<premier groupe = rien d'accumule>>). Mesure du
20 septembre 2026 sur les 1923 sorts des cinq versions: huit lancers
retenaient un groupe qui ne frappe pas alors qu'un autre groupe du meme
lancer frappe, et **les huit** avaient un groupe retenu fait **uniquement**
de lignes qui soignent. Aucun ne l'etait pour une autre raison. Sauter les
groupes <<a zero>> aurait au contraire efface de vrais zeros: 227 lancers
portent une ligne qui frappe quelque part et valent zero pour d'autres
raisons, qui ne sont pas celle-ci.

**L'etendue, mesuree lancer par lancer.** Sur les 10292 lancers des cinq
versions, rangs et coups critiques compris, **34 changent**, tous Eniripsa,
tous en dofus3, beta et dofus2, **tous de zero vers une valeur positive**.
Aucun ne baisse, aucune autre classe ni version ne bouge. Touch et Retro
n'ont aucun cas.

**Ce que ce garde mesure.** Sept tests, dont **deux tombent** quand on rend
au repli son `aggregates[0]`: celui des trois sorts et celui qui verifie que
le repli appelle bien la regle. Les cinq autres sont des planchers, et ils
tiennent des deux cotes par construction: ils appellent la regle directement.

Un huitieme test avait ete ecrit, qui demandait le vrai panneau d'un Eniripsa
de niveau 45 et parcourait ses lancers. Il **passait des deux cotes**: le
solveur ne retient pas ce sort sur l'equipement qu'il trouve en test, donc la
boucle n'assurait rien. Il a ete retire plutot que garde comme preuve.

Voir [[project-item-card-beats-hidden-spell]]: la fiche du sort dit ce qu'il
fait, et c'est elle qui a tranche.
"""

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import (Castable, _average, _element_alternatives,
                                  _first_group_that_hurts)
from chardata.spell_reference import reference_by_spell_id

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

#: Les trois sorts et ce que le panneau doit leur compter au rang 0, hors
#: coup critique, avant tout equipement. Mesure du 20 septembre 2026.
_MOITIE_QUI_FRAPPE = {
    'Warpaint': 6.5,
    'Tribal Paintbrush': 16.5,
    'Secret Word': 30.0,
}

#: Les deux moities que la fiche du jeu enonce, en francais. Le test lit la
#: fiche, il ne recopie pas une traduction.
_MOTS_DU_JEU = ('soigne les alli', 'ennemis')


def _groupes(sort, rang, crit=False):
    """Les lignes de chaque groupe d'agregats, quand le repli s'applique."""
    digest = sort.get_effects_digest()
    rows = digest.crit_dams if crit else digest.non_crit_dams
    effets = rows[rang] if rang < len(rows) else []
    if not digest.aggregates or len(digest.aggregates) < 2:
        return None
    if _element_alternatives(digest.aggregates, effets) is not None:
        return None
    attente = set(getattr(sort, 'conditional', None) or {})
    sortie = []
    for _label, indices in digest.aggregates:
        sortie.append([effets[i] for i in indices
                       if i < len(effets)
                       and not effets[i].element.startswith('buff')
                       and i not in attente
                       and (effets[i].min_dam or effets[i].max_dam)])
    return sortie


def _soigne_entierement(lignes):
    return bool(lignes) and all(getattr(e, 'heals', False) for e in lignes)


def _tous_les_sorts():
    for version in VERSIONS:
        for classe, sorts in get_damage_spells_for_version(version).items():
            for sort in sorts:
                yield version, classe, sort


class TheHealHalfIsNeverWhatTheTurnIsScoredOnTests(SimpleTestCase):

    def test_the_three_spells_are_scored_on_the_damage_they_deal(self):
        """Le test qui aurait attrape le defaut."""
        for version in ('dofus3', 'beta', 'dofus2'):
            sorts = {s.name: s
                     for s in get_damage_spells_for_version(version)['Eniripsa']}
            for nom, attendu in _MOITIE_QUI_FRAPPE.items():
                if nom not in sorts:
                    continue
                with self.subTest(version=version, sort=nom):
                    lancer = Castable(sorts[nom], 0, crit=False)
                    self.assertEqual(
                        attendu, _average(lancer.hits),
                        'the panel scores this cast on its ally half, so it '
                        'understates the turn')

    def test_only_a_group_that_heals_throughout_is_ever_skipped(self):
        """Ce qui autorise la regle, et la borne.

        Si un groupe saute pour une autre raison que <<il ne fait que
        soigner>>, la regle n'est plus celle que le jeu enonce et elle
        efface un vrai zero.
        """
        sautes_pour_autre_chose = []
        for version, classe, sort in _tous_les_sorts():
            for rang in range(len(sort.level_req)):
                groupes = _groupes(sort, rang)
                if not groupes:
                    continue
                digest = sort.get_effects_digest()
                retenu = _first_group_that_hurts(
                    digest.aggregates,
                    list(enumerate(digest.non_crit_dams[rang]
                                   if rang < len(digest.non_crit_dams)
                                   else [])))
                premier = set(digest.aggregates[0][1])
                if retenu == premier:
                    continue
                if not _soigne_entierement(groupes[0]):
                    sautes_pour_autre_chose.append(
                        (version, classe, sort.name, rang))
        self.assertEqual([], sautes_pour_autre_chose)

    def test_the_rule_moves_these_three_spells_and_no_others(self):
        """L'etendue, sans avoir besoin d'un <<avant>>: le groupe retenu ne
        s'ecarte du premier que pour ces trois sorts."""
        bouges = set()
        for version, classe, sort in _tous_les_sorts():
            for rang in range(len(sort.level_req)):
                digest = sort.get_effects_digest()
                if not digest.aggregates or len(digest.aggregates) < 2:
                    continue
                rows = digest.non_crit_dams
                effets = rows[rang] if rang < len(rows) else []
                if _element_alternatives(digest.aggregates, effets) is not None:
                    continue
                retenu = _first_group_that_hurts(digest.aggregates,
                                                 list(enumerate(effets)))
                if retenu != set(digest.aggregates[0][1]):
                    bouges.add((version, classe, sort.name))
        self.assertEqual(
            set(_MOITIE_QUI_FRAPPE), {nom for _v, _c, nom in bouges},
            'the rule reaches spells it was not measured on: %s' % sorted(bouges))
        self.assertEqual(
            {'Eniripsa'}, {classe for _v, classe, _n in bouges})
        self.assertEqual(
            {'dofus3', 'beta', 'dofus2'}, {v for v, _c, _n in bouges},
            'Touch and Retro carried no case when this was measured')


class TheGameItselfSaysTheseSpellsHurtAnEnemyTests(SimpleTestCase):

    def test_each_spell_card_states_both_halves(self):
        """La source de la regle est dans le test, pas seulement dans un
        commentaire: la fiche du client dit les deux moities."""
        sorts = {s.name: s
                 for s in get_damage_spells_for_version('dofus3')['Eniripsa']}
        fiches = reference_by_spell_id('dofus3', 'Eniripsa')
        for nom in _MOITIE_QUI_FRAPPE:
            with self.subTest(sort=nom):
                self.assertIn(nom, sorts)
                fiche = fiches.get(sorts[nom].spell_id)
                self.assertIsNotNone(fiche, '%s has no card' % nom)
                texte = (fiche['description'].get('fr') or '').lower()
                for mot in _MOTS_DU_JEU:
                    self.assertIn(
                        mot, texte,
                        '%s no longer states both halves, so the rule loses '
                        'its source' % nom)


class AStackingCastStillStartsFromNothingBuiltUpTests(SimpleTestCase):
    """Le plancher. Sans lui, la regle pourrait deplacer tous les sorts a
    paliers et personne ne le verrait."""

    def test_a_first_group_that_hurts_is_kept(self):
        gardes = 0
        for version, classe, sort in _tous_les_sorts():
            for rang in range(len(sort.level_req)):
                groupes = _groupes(sort, rang)
                if not groupes or not groupes[0]:
                    continue
                if _soigne_entierement(groupes[0]):
                    continue
                digest = sort.get_effects_digest()
                rows = digest.non_crit_dams
                effets = rows[rang] if rang < len(rows) else []
                retenu = _first_group_that_hurts(digest.aggregates,
                                                 list(enumerate(effets)))
                with self.subTest(version=version, sort=sort.name, rang=rang):
                    self.assertEqual(set(digest.aggregates[0][1]), retenu)
                gardes += 1
        self.assertGreaterEqual(
            gardes, 200,
            'only %d stacking casts were checked, so this floor proves very '
            'little' % gardes)

    def test_the_fallback_keeps_the_first_group_when_none_can_hurt(self):
        """Le bord que la donnee ne porte pas aujourd'hui: aucun lancer n'a
        tous ses groupes en soins. On le pose donc directement, pour que la
        regle n'invente pas de degats si un tel sort arrivait."""
        class _Ligne(object):
            def __init__(self, soigne):
                self.heals = soigne
                self.min_dam = 5
                self.max_dam = 7

        lignes = list(enumerate([_Ligne(True), _Ligne(True)]))
        self.assertEqual({0}, _first_group_that_hurts([('', [0]), ('', [1])],
                                                      lignes))


class TheFallbackActuallyAsksTheRuleTests(SimpleTestCase):
    """`landed` pourrait reprendre `aggregates[0]` sans qu'un seul des tests
    ci-dessus bouge: ils appellent la regle directement. C'est l'etat exact
    dans lequel j'ai mesure la morsure du garde, et rien ne le gardait."""

    def test_the_cast_builder_reads_the_group_that_hurts(self):
        import io
        import os
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'spell_combo.py')
        with io.open(chemin, encoding='utf-8') as fichier:
            source = fichier.read()
        debut = source.index('def landed(')
        corps = source[debut:debut + 1400]
        self.assertIn('_first_group_that_hurts(digest.aggregates, hits)',
                      corps)
        self.assertNotIn('groups = ([set(digest.aggregates[0][1])]', corps)
