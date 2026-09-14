# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Un coup qui tombe dans un seul element est dessine une seule fois.

Trouve en lisant les fiches de sorts d'un Eniripsa Dofus 3. Scalpel, dont
Ankama ecrit <<Reduit la duree des effets sur la cible et occasionne des
dommages aux ennemis **ou** soigne les allies dans le meilleur element>>,
montrait **huit lignes** pour un seul lancer:

    COUP NORMAL
    Coup dans le meilleur element: 42 - 46
    42 - 46
    42 - 46
    42 - 46
    Coup dans le meilleur element: Soins 42 - 46
    Soins 42 - 46
    Soins 42 - 46
    Soins 42 - 46

Le generateur ecrit un coup <<dans le meilleur element>> comme un groupe
d'une ligne **par element**, parce qu'il faut bien une ligne par element pour
le noter; il n'etiquette que le premier. La table empilait donc les quatre
faces comme quatre coups, sans rien qui dise qu'une seule tombe.

**Ce n'est pas une lecture, c'est la source.** Dans le fichier d'Ankama
l'effet est **unique** et sans element: `get_spells.py` en fabrique quatre
lignes (`BEST_ELEMENT_TOKENS`) apres avoir lu, dans la description d'Ankama
elle-meme, <<Inflicts damage on enemies in the caster's best element>>. Le jeu
frappe une fois.

**Les deux moities du panneau se contredisaient.** Le meilleur tour, lui,
lisait deja la decoupe et en choisissait une face
(`_element_alternatives`). La table et le tour disaient donc deux choses du
meme sort. Elles lisent maintenant la meme fonction, `element_runs`.

**Portee, mesuree le 14 septembre 2026 sur les 1923 sorts des cinq
versions.** 195 suites, sur 91 sorts, portent une des trois declarations du
generateur. Touch en comptait deux de plus jusqu au 14 septembre au soir:
l Embuscade et la Fanfaronnade y etaient groupees a tort, voir
[[tests_touch_rows_that_land_together_are_not_a_choice]].

| version | sorts |
|---------|-------|
| dofus3 | 32 |
| beta | 32 |
| dofus2 | 26 |
| touch | 0 |
| retro | 1 |

86 autres suites, sur 23 sorts, n'en portent aucune: 30 sur Rekop (dix par
version, qui en compte 37 dont 27 declarees), 21 sur Arcane Torrent et 21 sur
Knell, etiquetees par palier, et 14 sur les sorts elementaires du Huppermage,
etiquetees par etat (`State 290` a `State 293`). **Rien dans les donnees ne
dit si une seule de leurs lignes tombe**, donc elles ne sont pas touchees.
Pour le Huppermage c'est probablement le cas, l'etat portant l'element charge,
mais l'etiquette nomme un etat et pas un choix: ce serait une supposition.

**Deux formes, parce que le jeu en a deux.** <<Meilleur element>> veut dire
que le jeu choisit, donc la table montre la face que le personnage frapperait,
celle que le tour compte. <<Au hasard>> et <<dans l'element de l'attaque>> ne
laissent pas le choix au lecteur: leurs faces restent, separees par <<ou>>.
Bluff, dont Ankama dit <<inflige aleatoirement des degats d'Air ou d'Eau>>, se
lit maintenant `Coup dans un element au hasard: 106 - 841 ou 105 - 787`.

**Suite.** Sur Bluff, `best_turn` prenait la meilleure des deux faces alors
que le jeu tire au sort. Corrige depuis, sur les chances qu'Ankama donne
lui-meme: voir [[tests_a_hit_the_game_draws_is_scored_at_its_odds]].
"""
from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import element_runs
from chardata.spells_view import convert_aggregates, _one_lands_kind

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

#: Ce que la mesure du 14 septembre 2026 a compte, version par version. Un
#: sort qui sort de la portee, ou qui y entre, doit se voir ici.
SORTS_DECLARES = {'dofus3': 32, 'beta': 32, 'dofus2': 26, 'touch': 0,
                  'retro': 1}
SUITES_DECLAREES = 195
SUITES_NON_DECLAREES = 86


def _rows_of(spell):
    digest = spell.get_effects_digest()
    return digest, (digest.non_crit_dams[0] if digest.non_crit_dams else [])


def _find(version, class_name, spell_name):
    for spell in get_damage_spells_for_version(version)[class_name]:
        if spell.name == spell_name:
            return spell
    raise AssertionError('%s/%s/%s left the catalogue'
                         % (version, class_name, spell_name))


class AHitThatLandsInOneElementIsDrawnOnceTests(SimpleTestCase):

    def test_the_witness_that_showed_eight_lines_shows_two(self):
        spell = _find('dofus3', 'Eniripsa', 'Scalpel')
        digest, rows = _rows_of(spell)
        self.assertEqual(8, len(digest.aggregates),
                         'the generator no longer writes one group per '
                         'element: %s' % (digest.aggregates,))
        groups = convert_aggregates(digest.aggregates, 'dofus3', rows)
        self.assertEqual(2, len(groups), groups)
        self.assertEqual([[0, 1, 2, 3], [4, 5, 6, 7]],
                         [group[1] for group in groups])
        self.assertEqual(['best', 'best'], [group[2] for group in groups])
        self.assertFalse(rows[0].heals)
        self.assertTrue(rows[4].heals,
                        'the second group is no longer the healing half')

    def test_a_random_element_keeps_its_faces(self):
        """Le jeu ne laisse pas le choix, donc la table n'en designe pas."""
        spell = _find('retro', 'Ecaflip', 'Bluff')
        digest, rows = _rows_of(spell)
        groups = convert_aggregates(digest.aggregates, 'retro', rows)
        self.assertEqual(1, len(groups), groups)
        self.assertEqual([0, 1], groups[0][1])
        self.assertEqual('one', groups[0][2])
        self.assertEqual({'air', 'water'},
                         {rows[0].element, rows[1].element})

    def test_the_table_and_the_turn_read_the_same_cut(self):
        """L'invariant. Chaque groupe fusionne est exactement une suite, et
        une suite est ce que le tour lit pour en choisir une face."""
        checked = 0
        for version in VERSIONS:
            for class_name, spells in get_damage_spells_for_version(
                    version).items():
                for spell in spells:
                    digest, rows = _rows_of(spell)
                    if not digest.aggregates or not rows:
                        continue
                    declared = {
                        tuple(index for _label, indices in run
                              for index in indices)
                        for run in element_runs(digest.aggregates, rows)
                        if any(_one_lands_kind(label)
                               for label, _indices in run)}
                    if not declared:
                        continue
                    groups = convert_aggregates(digest.aggregates, version,
                                                rows)
                    merged = {tuple(group[1]) for group in groups
                              if len(group) > 2}
                    with self.subTest(version=version, spell=spell.name):
                        self.assertEqual(declared, merged)
                    checked += 1
        self.assertEqual(sum(SORTS_DECLARES.values()), checked)

    def test_the_scope_is_the_one_that_was_measured(self):
        by_version, declared, undeclared = {}, 0, 0
        for version in VERSIONS:
            touched = set()
            for class_name, spells in get_damage_spells_for_version(
                    version).items():
                for spell in spells:
                    digest, rows = _rows_of(spell)
                    if not rows:
                        continue
                    for run in element_runs(digest.aggregates, rows):
                        if any(_one_lands_kind(label)
                               for label, _indices in run):
                            declared += 1
                            touched.add((class_name, spell.name))
                        else:
                            undeclared += 1
            by_version[version] = len(touched)
        self.assertEqual(SORTS_DECLARES, by_version)
        self.assertEqual(SUITES_DECLAREES, declared)
        self.assertEqual(SUITES_NON_DECLAREES, undeclared,
                         'runs the generator does not declare must stay '
                         'untouched, and their number must be stated')

    def test_a_run_the_generator_did_not_declare_is_left_alone(self):
        """Les quatre lignes du Vol Elementaire sont etiquetees par etat, pas
        par un choix. Les fusionner serait supposer ce que les donnees ne
        disent pas, meme si l'etat porte sans doute l'element charge."""
        spell = _find('dofus3', 'Huppermage', 'Elemental Drain')
        digest, rows = _rows_of(spell)
        runs = element_runs(digest.aggregates, rows)
        self.assertEqual(1, len(runs), len(runs))
        self.assertEqual(4, len(runs[0]))
        self.assertFalse([run for run in runs
                          if any(_one_lands_kind(label)
                                 for label, _indices in run)])
        groups = convert_aggregates(digest.aggregates, 'dofus3', rows)
        self.assertEqual(len(digest.aggregates), len(groups))
        self.assertFalse([group for group in groups if len(group) > 2])

    def test_the_weapon_keeps_its_groups_built_by_hand(self):
        """Sans lignes, aucune fusion n'est tentee: l'arme batit ses groupes
        elle-meme et n'a pas d'element de rechange."""
        aggregates = [('', [0, 1]), ('', [2])]
        self.assertEqual([['', [0, 1]], ['', [2]]],
                         convert_aggregates(aggregates))
