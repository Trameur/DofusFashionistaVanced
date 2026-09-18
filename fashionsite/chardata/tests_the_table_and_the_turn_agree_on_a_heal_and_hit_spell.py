# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A spell that heals allies and hits enemies shows both, in the table and the turn."""

import io
import os
import re

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, _average, rows_that_always_land
from chardata.spell_reference import reference_by_spell_id
from chardata.spells_view import _always_land_by_rank

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

_VERSIONS_TOUCHEES = {'dofus3', 'beta', 'dofus2'}

# Spell/version pairs the rule reaches
_SORTS_TOUCHES = 49

# Words of the French spell card
_SOIGNE = re.compile(r'soigne', re.I)
_FRAPPE = re.compile(r'(dommages|vole de la vie).{0,40}ennemis', re.I | re.S)
# Area around the target, the target itself excluded
_AUTOUR = re.compile(r'autour de la cible', re.I)

# Loose row hits the area around the target, and the kept group already hits
_ZONE_AUTOUR = (('dofus3', 'Cra', 'Exploding Arrow'),
                ('dofus3', 'Cra', 'Boomerang Arrow'))


def _tous_les_sorts():
    for version in VERSIONS:
        for classe, sorts in get_damage_spells_for_version(version).items():
            for sort in sorts:
                yield version, classe, sort


def _joue(sort):
    """[(crit, rank index, rows)] where the rule picks rows."""
    digest = sort.get_effects_digest()
    attente = getattr(sort, 'conditional', None) or {}
    trouves = []
    for crit, rangs in ((False, digest.non_crit_dams),
                        (True, digest.crit_dams)):
        for index, effets in enumerate(rangs or []):
            lignes = rows_that_always_land(digest, effets, attente)
            if lignes:
                trouves.append((crit, index, tuple(lignes)))
    return trouves


class ASpellThatHealsAndHitsShowsBothTests(SimpleTestCase):

    def test_the_hitting_row_outside_every_group_is_read(self):
        sorts = {s.name: s
                 for s in get_damage_spells_for_version('dofus2')['Eniripsa']}
        for nom in ('Raucous Word', 'Turbulent Word'):
            with self.subTest(sort=nom):
                self.assertIn(nom, sorts)
                lancer = Castable(sorts[nom], 0, crit=False)
                self.assertGreater(
                    _average(lancer.hits), 0,
                    'the turn scores this cast on its heal alone, so it '
                    'understates the turn and contradicts the damage table')

    def test_the_rule_reaches_exactly_the_spells_it_was_measured_on(self):
        touches = {(v, c, s.name) for v, c, s in _tous_les_sorts() if _joue(s)}
        self.assertEqual(
            _SORTS_TOUCHES, len(touches),
            'the rule now reaches %d spells, not the %d it was measured on: %s'
            % (len(touches), _SORTS_TOUCHES, sorted(touches)[:6]))
        self.assertEqual(_VERSIONS_TOUCHEES, {v for v, _c, _n in touches})

    def test_a_row_that_hits_the_area_around_the_target_is_left_out(self):
        for version, classe, nom in _ZONE_AUTOUR:
            with self.subTest(sort=nom):
                sorts = {s.name: s
                         for s in get_damage_spells_for_version(version)[classe]}
                self.assertIn(nom, sorts)
                self.assertEqual(
                    [], _joue(sorts[nom]),
                    'the rule reaches a cast whose loose row hits the area '
                    'around the target, not the target')

    def test_each_touched_spell_states_both_halves_in_its_card(self):
        sans_les_deux = []
        avec_autour = []
        for version, classe, sort in _tous_les_sorts():
            if not _joue(sort):
                continue
            fiche = reference_by_spell_id(version, classe).get(sort.spell_id)
            texte = ((fiche or {}).get('description', {}) or {}).get('fr') or ''
            if not (_SOIGNE.search(texte) and _FRAPPE.search(texte)):
                sans_les_deux.append((version, classe, sort.name))
            if _AUTOUR.search(texte):
                avec_autour.append((version, classe, sort.name))
        self.assertEqual(
            [], sans_les_deux,
            'these no longer state both halves, so the rule loses its source')
        self.assertEqual(
            [], avec_autour,
            'these say the area is around the target, so their loose row is '
            'not what a single target takes')


class ThePageIsToldAndDoesNotRecomputeTests(SimpleTestCase):

    def _source(self, nom):
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'templates', 'chardata', nom)
        with io.open(chemin, encoding='utf-8') as fichier:
            return fichier.read()

    def test_the_damage_table_reads_what_the_server_decided(self):
        source = self._source('spells.html')
        self.assertIn('function aggregatesWithRowsThatAlwaysLand(', source)
        self.assertIn("spell.always_land[isCrit ? 'crit' : 'non_crit']", source)
        self.assertIn('aggregates = aggregatesWithRowsThatAlwaysLand(', source)

    def test_the_table_asks_per_rank_and_per_crit(self):
        """The rows vary by rank and by crit, as on Alchemical Word."""
        source = self._source('spells.html')
        self.assertIn('function getHits(spell, damage, isCrit, rank) {', source)

    def test_the_export_is_absent_from_every_spell_the_rule_leaves_alone(self):
        portent = 0
        total = 0
        for _version, _classe, sort in _tous_les_sorts():
            total += 1
            export = _always_land_by_rank(sort, sort.get_effects_digest())
            if export is None:
                continue
            portent += 1
            self.assertTrue(_joue(sort),
                            '%s ships the key with nothing to say' % sort.name)
        self.assertEqual(_SORTS_TOUCHES, portent)
        self.assertGreater(total, 1900)

    def test_the_export_separates_the_critical_rows(self):
        sorts = {s.name: s
                 for s in get_damage_spells_for_version('dofus3')['Eniripsa']}
        alchimique = sorts.get('Alchemical Word')
        self.assertIsNotNone(alchimique, 'Alchemical Word left the catalogue')
        export = _always_land_by_rank(alchimique,
                                      alchimique.get_effects_digest())
        self.assertIsNotNone(export)
        self.assertIn('non_crit', export)
        self.assertNotEqual(
            export.get('non_crit'), export.get('crit'),
            'the two sides of this spell agree again, so the split it was '
            'measured on is gone')
