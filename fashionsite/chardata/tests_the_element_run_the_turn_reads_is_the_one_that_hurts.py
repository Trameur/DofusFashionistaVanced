# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un sort au meilleur element est lu sur la serie qui frappe, pas sur les soins.

Fin du fil ouvert aux lots 79 et 80. Ces deux-la avaient appris au tour a lire
la moitie qui frappe sur le chemin des **paliers**. Restait le chemin des
**alternatives par element**, que tous deux excluaient, et deux facons
distinctes de s'y tromper.

**Un groupe fait uniquement de buffs n'est pas un element.** Vacarme porte six
lignes, dont deux qui frappent, et ses agregats sont `[[0], [5]]`: la ligne 0
soigne, la ligne 5 est un `buff_final`. Les prendre pour deux elements faisait
croire a la forme <<meilleur element>> la ou il n'y en a pas, donc le repli
qui sait lire la moitie qui frappe ne jouait jamais. Le panneau depensait 3 PA
pour **zero**, sans note, et la table ne montrait que <<Soins 381 - 418>>.

**La premiere serie n'est pas toujours la bonne.** Tout ou Rien porte quatre
lignes qui soignent, une par element, puis quatre qui frappent. La fonction
gardait la premiere serie, donc la moitie alliee.

**Ce que le jeu dit**, fiches lues le 13 septembre 2026:

| sort | description |
|------|-------------|
| Vacarme | <<Soigne les allies ou occasionne des dommages Feu aux ennemis>> |
| Cri de l'Ours | <<Soigne les allies et vole de la vie dans l'element Terre aux ennemis en zone>> |
| Tout ou Rien | <<Soigne les allies et occasionne des dommages dans le meilleur element du lanceur aux ennemis en zone>> |

**Les deux regles sont etroites, et c'est mesure.** Sur les 1923 sorts des
cinq versions: 13 portent un groupe fait uniquement de buffs, dont 7 paires
sort/version changent de forme une fois ces groupes ecartes, et **34 lancers**
en sortent. 29 sorts portent plusieurs series d'elements et **un seul**
commence par une serie qui ne fait que soigner, d'ou **10 lancers** de plus.
Les 44 changements vont tous de zero vers une valeur positive, aucun a la
baisse, et aucun en Touch ni en Retro.

**Ce que ce garde mesure.** Sept tests, dont **trois tombent** quand on rend
aux deux fonctions leur comportement d'avant: celui des huit sorts deplaces,
celui des zeros restants, et celui qui compare la production a une lecture
miroir des series. Les quatre autres bornent les regles et tiennent des deux
cotes.

**Ce que le fil aura corrige en tout.** Le nombre de lancers qui portent une
ligne capable de frapper et que le panneau comptait zero passe de **230 a 3**
sur les 10292 des cinq versions. Les trois qui restent sont le Dofus Ebene,
dont toutes les lignes attendent un etat: un zero juste, d'une autre nature.
"""

import collections

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import (Castable, _average, _element_alternatives)
from chardata.spell_reference import reference_by_spell_id

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

#: Ce que chaque sort deplace doit compter au rang 0, hors coup critique,
#: avant tout equipement. Mesure du 13 septembre 2026.
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

#: Combien de sorts portent un groupe fait uniquement de buffs, et combien
#: portent plusieurs series d'elements. Les deux bornent les regles.
#:
#: 29 -> 30 le 17 septembre 2026 avec la beta 3.7.0.0: la Toxicite Scurvion
#: (12505) y passe de 4 lignes et une seule serie a 12 lignes et trois. Ankama
#: a bouge la charge, le generateur n'a pas bouge, et la regle des series ne
#: deplace toujours que Tout ou Rien.
_AVEC_GROUPE_DE_BUFF = 13
_AVEC_PLUSIEURS_SERIES = 30

#: Ce qui reste apres le fil entier, et pourquoi c'est juste.
_ZEROS_RESTANTS = 3
_SORT_DES_ZEROS_RESTANTS = 'Ebony Dofus'


def _tous_les_sorts():
    for version in VERSIONS:
        for classe, sorts in get_damage_spells_for_version(version).items():
            for sort in sorts:
                yield version, classe, sort


def _series(aggregates, effects):
    """Toutes les series d'elements du sort, pas seulement la premiere.

    Ecarte les groupes faits uniquement de buffs comme la production, sans
    quoi ce garde porterait une seconde version de la regle et dirait le
    contraire d'elle.
    """
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
        """Le test qui aurait attrape les deux defauts."""
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
        """La mesure qui ferme le fil: de 230 a 3.

        Un lancer qui porte une ligne capable de frapper et que le panneau
        compte zero est soit un tour sous-estime, soit un zero qu'il faut
        savoir expliquer. Il en reste trois, tous du meme objet, et leurs
        lignes attendent un etat que le lancer ne produit pas.
        """
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
        """La source est dans le garde, lue sur chacun des sorts deplaces."""
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
    """Les planchers. Sans eux, chaque regle pourrait s'etendre a des sorts
    sur lesquels elle n'a jamais ete mesuree."""

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
        """La regle des series ne doit deplacer que Tout ou Rien."""
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
        """Un vrai sort au meilleur element ne doit pas bouger."""
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
        """Chaque version est un jeu different, et ces deux-la n'ont aucun
        cas: la correction ne doit pas les toucher."""
        bouges = collections.Counter(
            version for version, _classe, _nom in _MOITIE_QUI_FRAPPE)
        self.assertNotIn('touch', bouges)
        self.assertNotIn('retro', bouges)
