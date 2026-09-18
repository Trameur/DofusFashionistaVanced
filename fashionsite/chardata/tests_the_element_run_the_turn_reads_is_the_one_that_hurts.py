# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A best-element spell is scored on the run that hurts, not on the heals."""

import collections

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import (Castable, _average, _element_alternatives)
from chardata.spell_reference import reference_by_spell_id

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

# Average at rank 0, no crit, no gear
_MOITIE_QUI_FRAPPE = {
    ('dofus3', 'Eniripsa', 'Commotion'): 48.0,
    ('beta', 'Eniripsa', 'Commotion'): 48.0,
    ('dofus2', 'Eniripsa', 'Commotion'): 24.0,
    ('dofus3', 'Osamodas', 'Bear Cry'): 15.0,
    ('beta', 'Osamodas', 'Bear Cry'): 15.0,
    ('dofus3', 'Ecaflip', 'All or Nothing'): 17.0,
    ('beta', 'Ecaflip', 'All or Nothing'): 17.0,
    ('dofus2', 'Ecaflip', 'All or Nothing'): 9.0,
}

# Spells with a buff-only group, spells with several element runs
_AVEC_GROUPE_DE_BUFF = 13
_AVEC_PLUSIEURS_SERIES = 30

# Ebony Dofus hitting rows all wait on a state
_ZEROS_RESTANTS = 3
_SORT_DES_ZEROS_RESTANTS = 'Ebony Dofus'


def _tous_les_sorts():
    for version in VERSIONS:
        for classe, sorts in get_damage_spells_for_version(version).items():
            for sort in sorts:
                yield version, classe, sort


def _series(aggregates, effects):
    """All element runs of the spell, buff-only groups dropped."""
    aggregates = [(label, indices) for label, indices in (aggregates or [])
                  if not all(index < len(effects)
                             and effects[index].element.startswith('buff')
                             for index in indices)]
    if not aggregates or len(aggregates) < 2:
        return []
    toutes, courante, vus = [], [], set()
    for _label, indices in aggregates:
        if len(indices) != 1 or indices[0] >= len(effects):
            return []
        element = effects[indices[0]].element
        if element in vus:
            if len(courante) > 1:
                toutes.append(courante)
            courante, vus = [], set()
        vus.add(element)
        courante.append(set(indices))
    if len(courante) > 1:
        toutes.append(courante)
    return toutes


class TheTurnReadsTheHalfThatHurtsTests(SimpleTestCase):

    def test_each_moved_spell_is_scored_on_its_damage(self):
        for (version, classe, nom), attendu in _MOITIE_QUI_FRAPPE.items():
            with self.subTest(version=version, sort=nom):
                sorts = {s.name: s
                         for s in get_damage_spells_for_version(version)[classe]}
                self.assertIn(nom, sorts)
                lancer = Castable(sorts[nom], 0, crit=False)
                self.assertEqual(
                    attendu, _average(lancer.hits),
                    'the turn scores this cast on its ally half, so it spends '
                    'AP for nothing and contradicts its own damage table')

    def test_the_reader_no_longer_meets_a_bare_zero_that_could_hurt(self):
        """A cast with a row able to hurt scores zero only if its rows wait on a state."""
        restants = []
        expliques = []
        for version, _classe, sort in _tous_les_sorts():
            attente = set(getattr(sort, 'conditional', None) or {})
            differe = set(getattr(sort, 'delayed', None) or {})
            for rang in range(len(sort.level_req)):
                for crit in (False, True):
                    digest = sort.get_effects_digest()
                    rows = digest.crit_dams if crit else digest.non_crit_dams
                    effets = rows[rang] if rang < len(rows) else []
                    frappeuses = [i for i, e in enumerate(effets)
                                  if not e.element.startswith('buff')
                                  and not getattr(e, 'heals', False)
                                  and (e.min_dam or e.max_dam)]
                    if not frappeuses:
                        continue
                    if _average(Castable(sort, rang, crit=crit).hits) > 0:
                        continue
                    if all(i in attente or i in differe for i in frappeuses):
                        expliques.append((version, sort.name))
                        continue
                    restants.append((version, sort.name))
        self.assertEqual(
            [], restants,
            'the panel scores zero on %d casts that carry a row able to hurt '
            'and that nothing else explains: %s'
            % (len(restants), sorted(set(restants))[:8]))
        self.assertEqual(_ZEROS_RESTANTS, len(expliques),
                         'the casts whose hitting rows all wait on a state '
                         'were %d and are now %d'
                         % (_ZEROS_RESTANTS, len(expliques)))
        self.assertEqual(
            {_SORT_DES_ZEROS_RESTANTS}, {nom for _v, nom in expliques},
            'another spell now scores zero because its rows wait, and it has '
            'not been read: %s' % sorted(set(expliques)))

    def test_each_moved_spell_states_both_halves_in_its_card(self):
        for version, classe, nom in _MOITIE_QUI_FRAPPE:
            with self.subTest(sort=nom):
                sorts = {s.name: s
                         for s in get_damage_spells_for_version(version)[classe]}
                fiche = reference_by_spell_id(version, classe).get(
                    sorts[nom].spell_id)
                texte = ((fiche or {}).get('description', {}) or {}).get('fr')
                self.assertTrue(texte, '%s has no card' % nom)
                self.assertIn('soigne', texte.lower())
                self.assertNotIn(
                    'autour de la cible', texte.lower(),
                    'this card says the area is around the target, so its '
                    'loose row is not what a single target takes')


class TheTwoRulesStayNarrowTests(SimpleTestCase):

    def test_a_group_made_only_of_buffs_is_still_rare(self):
        porteurs = set()
        for version, classe, sort in _tous_les_sorts():
            digest = sort.get_effects_digest()
            for effets in (digest.non_crit_dams or []):
                for _label, indices in (digest.aggregates or []):
                    lignes = [effets[i] for i in indices if i < len(effets)]
                    if lignes and all(e.element.startswith('buff')
                                      for e in lignes):
                        porteurs.add((version, classe, sort.name))
        self.assertEqual(
            _AVEC_GROUPE_DE_BUFF, len(porteurs),
            'the shape this rule was measured on moved: %d spells carry a '
            'buff-only group, not %d' % (len(porteurs), _AVEC_GROUPE_DE_BUFF))

    def test_only_one_spell_starts_its_element_runs_with_heals(self):
        plusieurs = set()
        soigne_dabord = set()
        for version, classe, sort in _tous_les_sorts():
            digest = sort.get_effects_digest()
            for effets in (digest.non_crit_dams or []):
                toutes = _series(digest.aggregates, effets)
                if len(toutes) < 2:
                    continue
                plusieurs.add((version, classe, sort.name))
                if all(getattr(effets[i], 'heals', False)
                       for groupe in toutes[0] for i in groupe):
                    soigne_dabord.add((version, classe, sort.name))
        self.assertEqual(_AVEC_PLUSIEURS_SERIES, len(plusieurs))
        self.assertEqual(
            {'All or Nothing'}, {nom for _v, _c, nom in soigne_dabord},
            'another spell now starts with a healing run, and it has not been '
            'read against its card: %s' % sorted(soigne_dabord))

    def test_a_run_that_hurts_first_is_kept(self):
        gardes = 0
        for version, classe, sort in _tous_les_sorts():
            digest = sort.get_effects_digest()
            for effets in (digest.non_crit_dams or []):
                toutes = _series(digest.aggregates, effets)
                if not toutes:
                    continue
                if all(getattr(effets[i], 'heals', False)
                       for groupe in toutes[0] for i in groupe):
                    continue
                with self.subTest(version=version, sort=sort.name):
                    self.assertEqual(
                        toutes[0],
                        _element_alternatives(digest.aggregates, effets))
                gardes += 1
        self.assertGreaterEqual(
            gardes, 50,
            'only %d best-element casts were checked, so this floor proves '
            'very little' % gardes)

    def test_neither_rule_reaches_touch_or_retro(self):
        bouges = collections.Counter(
            version for version, _classe, _nom in _MOITIE_QUI_FRAPPE)
        self.assertNotIn('touch', bouges)
        self.assertNotIn('retro', bouges)
