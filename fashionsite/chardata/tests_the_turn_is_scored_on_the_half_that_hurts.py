# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell that hurts enemies is scored on its damage half, not its heal half."""

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import (Castable, _average, _element_alternatives,
                                  _first_group_that_hurts)
from chardata.spell_reference import reference_by_spell_id

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

# Panel average at rank 0, no crit, no gear
_MOITIE_QUI_FRAPPE = {
    'Warpaint': 6.5,
    'Tribal Paintbrush': 16.5,
    'Secret Word': 30.0,
}

# Both halves, as the French spell card words them
_MOTS_DU_JEU = ('soigne les alli', 'ennemis')


def _groupes(sort, rang, crit=False):
    """Lines of each aggregate group, or None when the fallback does not apply."""
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


def _hits_sans_buffs(effets):
    """(index, line) pairs without buff lines, as production passes them."""
    return [(index, effet) for index, effet in enumerate(effets)
            if not effet.element.startswith('buff')]


def _tous_les_sorts():
    for version in VERSIONS:
        for classe, sorts in get_damage_spells_for_version(version).items():
            for sort in sorts:
                yield version, classe, sort


class TheHealHalfIsNeverWhatTheTurnIsScoredOnTests(SimpleTestCase):

    def test_the_three_spells_are_scored_on_the_damage_they_deal(self):
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
        sautes_pour_autre_chose = []
        for version, classe, sort in _tous_les_sorts():
            for rang in range(len(sort.level_req)):
                groupes = _groupes(sort, rang)
                if not groupes:
                    continue
                digest = sort.get_effects_digest()
                effets_du_rang = (digest.non_crit_dams[rang]
                                  if rang < len(digest.non_crit_dams)
                                  else [])
                retenu = _first_group_that_hurts(
                    digest.aggregates, _hits_sans_buffs(effets_du_rang))
                premier = set(digest.aggregates[0][1])
                if retenu == premier:
                    continue
                if not _soigne_entierement(groupes[0]):
                    sautes_pour_autre_chose.append(
                        (version, classe, sort.name, rang))
        self.assertEqual([], sautes_pour_autre_chose)

    def test_the_rule_moves_these_three_spells_and_no_others(self):
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
                retenu = _first_group_that_hurts(
                    digest.aggregates, _hits_sans_buffs(effets))
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
                retenu = _first_group_that_hurts(
                    digest.aggregates, _hits_sans_buffs(effets))
                with self.subTest(version=version, sort=sort.name, rang=rang):
                    self.assertEqual(set(digest.aggregates[0][1]), retenu)
                gardes += 1
        self.assertGreaterEqual(
            gardes, 200,
            'only %d stacking casts were checked, so this floor proves very '
            'little' % gardes)

    def test_the_fallback_keeps_the_first_group_when_none_can_hurt(self):
        class _Ligne(object):
            def __init__(self, soigne):
                self.heals = soigne
                self.min_dam = 5
                self.max_dam = 7

        lignes = list(enumerate([_Ligne(True), _Ligne(True)]))
        self.assertEqual({0}, _first_group_that_hurts([('', [0]), ('', [1])],
                                                      lignes))


class TheFallbackActuallyAsksTheRuleTests(SimpleTestCase):
    """`landed` must call the rule; the tests above call it directly."""

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
