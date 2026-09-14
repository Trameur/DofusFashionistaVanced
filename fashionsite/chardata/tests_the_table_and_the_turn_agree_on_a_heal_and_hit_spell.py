# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un sort qui soigne les allies ET frappe les ennemis montre les deux.

Suite du lot 79, et correction de ce qu'il laissait a moitie. Ce lot-la avait
appris au meilleur tour a lire la moitie qui frappe quand le sort porte deux
groupes d'agregats. Restait la forme la plus courante du meme sort: **un seul
groupe, qui ne contient que le soin**, la ligne qui frappe n'appartenant a
aucun groupe.

Sur l'Eniripsa Dofus 2 de niveau 45, <<Mot Tapageur>> affichait <<Soins
77 - 90>> et rien d'autre, alors que le sort frappe aussi pour 125 - 138.

**La table et le panneau se contredisaient.** Le lot 79 ayant corrige le
panneau seul, la page en serait sortie avec un tour qui compte une valeur que
sa propre table ne montre pas. Les deux lisent donc desormais **la meme liste,
calculee une fois cote serveur**: `rows_that_always_land`. Ce depot a paye
trois copies d'une regle de niveau pour avoir oublie cette discipline.

**Ce que le jeu dit.** Les sorts touches portent tous, sans exception, les
deux moities dans leur fiche: <<Soigne les allies et occasionne des dommages X
aux ennemis en zone>>. Verifie sur la population entiere et non sur un
echantillon, le 13 septembre 2026, et le test le refait a chaque passage.
Aucun ne dit <<autour de la cible>>.

**Ce que la regle n'autorise pas, et c'est mesure.** Compter toutes les
lignes hors groupe changerait **726** lancers la ou la regle livree en
changeait 193, et ce serait faux: la Fleche Explosive porte deux lignes de
9-11 Feu et sa fiche dit que la seconde touche <<les ennemis en zone
**autour de la cible**>>. La compter doublerait les degats sur une cible
unique. La regle ne lit ces lignes que lorsque le groupe retenu **ne fait
que soigner**.

**L'etendue.** Sur les 10292 lancers des cinq versions, rangs et coups
critiques compris, **193 changent**, tous de zero vers une valeur positive,
aucun a la baisse. Trois versions: dofus3, beta, dofus2. Touch et Retro n'ont
aucun cas.

**Pourquoi l'export est par rang ET par critique.** La forme varie vraiment:
Mot Alchimique change entre le coup normal et le coup critique sur deux de
ses rangs, Coeur de Dragon sur un. Une liste globale au sort aurait menti sur
cinq cas.
"""

import io
import os
import re

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, _average, rows_that_always_land
from chardata.spell_reference import reference_by_spell_id
from chardata.spells_view import _always_land_by_rank

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

#: Les versions qui portent des cas, mesurees le 13 septembre 2026.
_VERSIONS_TOUCHEES = {'dofus3', 'beta', 'dofus2'}

#: Combien de paires sort/version la regle touche. Elles etaient 44 le
#: 13 septembre 2026; le lot 81 en a ajoute cinq, Vacarme sur trois
#: versions et Cri de l'Ours sur deux, en rendant a ces sorts le chemin
#: des paliers dont un groupe de buffs les avait ecartes.
_SORTS_TOUCHES = 49

#: Les mots du jeu. On lit la fiche, on ne recopie pas une traduction.
_SOIGNE = re.compile(r'soigne', re.I)
_FRAPPE = re.compile(r'(dommages|vole de la vie).{0,40}ennemis', re.I | re.S)
#: La forme qui EXCLUT la cible: la zone est autour d'elle, pas sur elle.
_AUTOUR = re.compile(r'autour de la cible', re.I)

#: Deux sorts dont la ligne hors groupe frappe la zone AUTOUR de la cible.
#: Ils tiennent la porte fermee: leur groupe retenu frappe deja, donc la
#: regle ne doit rien leur ajouter.
_ZONE_AUTOUR = (('dofus3', 'Cra', 'Exploding Arrow'),
                ('dofus3', 'Cra', 'Boomerang Arrow'))


def _tous_les_sorts():
    for version in VERSIONS:
        for classe, sorts in get_damage_spells_for_version(version).items():
            for sort in sorts:
                yield version, classe, sort


def _joue(sort):
    """Les rangs et critiques ou la regle designe des lignes."""
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
        """Le test qui aurait attrape le defaut."""
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
        """Le plancher qui empeche la regle large.

        Ces deux sorts portent aussi une ligne hors groupe, et leur fiche dit
        qu'elle touche la zone **autour** de la cible. La compter doublerait
        le sort sur une cible unique.
        """
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
        """La source est dans le garde, pas seulement dans un commentaire, et
        elle est lue sur **tous** les sorts touches, pas sur un echantillon."""
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
        """La forme varie vraiment avec l'un et avec l'autre: Mot Alchimique
        change entre coup normal et coup critique sur deux rangs, Coeur de
        Dragon sur un. Un `getHits` sans le rang ne saurait pas quoi lire."""
        source = self._source('spells.html')
        self.assertIn('function getHits(spell, damage, isCrit, rank) {', source)

    def test_the_export_is_absent_from_every_spell_the_rule_leaves_alone(self):
        """Le cout: la clef ne pese que sur les sorts concernes."""
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
        """Si les deux se confondaient, cinq cas mentiraient."""
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
