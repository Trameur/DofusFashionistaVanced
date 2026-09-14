# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Le panneau dit sur quel groupe d'un sort il a compte.

Trouve en parcourant les panneaux du meilleur tour des 79 builds locaux. Un
sort a agregats ne pose **qu'un** groupe par lancer, et sa fiche les affiche
tous. Le Fletrissement d'un Xelor montre cinq lignes:

    Cumul 0: 26 - 29    Cumul 1: 32 - 35    Cumul 2: 38 - 42
    Cumul 3: 45 - 48    Cumul 4: 51 - 54

Le panneau annoncait `28` sans dire laquelle il avait lue. Le lecteur qui
verifiait le nombre trouvait cinq valeurs en face d'une seule, et rien pour
les relier.

**Ce que le libelle veut dire n'est pas devine.** Les agregats recouvrent au
moins sept mecaniques: le cumul par lancer, le cumul par ennemi dans la zone,
par invocation, par piege declenche, un etat, un tirage de carte, et
l'agrandissement de la zone. Ankama les distingue dans sa description, qui est
deja sur la page; nous, nous ne nommons que **le groupe lu**, ce qui est vrai
quelle que soit la mecanique. Le lecteur lit ensuite la phrase d'Ankama a
cote.

**Ce que le garde ne fait pas.** Il ne nomme rien quand le choix depend des
stats: un sort a alternatives d'element laisse `best_turn` prendre la
meilleure, et l'annoncer d'avance serait une supposition.

**Portee.** Mesure du 15 septembre 2026, 1044 tours sur toutes les classes des
cinq versions, a trois niveaux et quatre profils d'element: **60 tours (5,7%)
portent au moins une de ces notes**, 88 lignes de lancer sur 3982. Dont un Cra
de niveau 50 qui lance deux fois la Fleche d'Immobilisation, le sort dont
Ankama ecrit que les degats montent apres chaque lancer.
"""
import collections
import re

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import castable_spells, scored_group_label
from chardata.spells_view import _cast_note, _localized_aggregate_label

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

#: Le libelle sans ses chiffres, pour compter les familles.
_SANS_CHIFFRES = re.compile(r'\d+')


class _Digest(object):
    def __init__(self, aggregates, rows):
        self.aggregates = aggregates
        self.non_crit_dams = [rows]


class _Row(object):
    def __init__(self, element='fire', min_dam=10, max_dam=12, heals=False):
        self.element = element
        self.min_dam = min_dam
        self.max_dam = max_dam
        self.heals = heals


class TheLabelNamesTheGroupThatWasReadTests(SimpleTestCase):
    """La regle, sur des groupes fabriques: rien ne depend du catalogue."""

    def test_a_spell_with_a_single_group_names_nothing(self):
        digest = _Digest([('Stack 0', [0])], [_Row()])
        self.assertEqual('', scored_group_label(digest,
                                                digest.non_crit_dams[0]))

    def test_a_spell_with_no_aggregates_names_nothing(self):
        digest = _Digest(None, [_Row()])
        self.assertEqual('', scored_group_label(digest,
                                                digest.non_crit_dams[0]))

    def test_a_ladder_names_the_first_group_that_hurts(self):
        rows = [_Row(min_dam=10, max_dam=12), _Row(min_dam=20, max_dam=22)]
        digest = _Digest([('Stack 0', [0]), ('Stack 1', [1])], rows)
        self.assertEqual('Stack 0',
                         scored_group_label(digest, digest.non_crit_dams[0]))

    def test_a_group_of_heals_only_is_skipped_like_the_turn_skips_it(self):
        """Le panneau compte un tour sur une cible, donc il lit la moitie qui
        frappe. La note doit nommer ce qu'il a vraiment lu."""
        rows = [_Row(heals=True), _Row(min_dam=20, max_dam=22)]
        digest = _Digest([('Stack 0', [0]), ('Stack 1', [1])], rows)
        self.assertEqual('Stack 1',
                         scored_group_label(digest, digest.non_crit_dams[0]))

    def test_an_element_choice_is_not_named(self):
        """Quatre elements, un par groupe: c'est `best_turn` qui tranche,
        selon des stats que ce code ne connait pas."""
        rows = [_Row(element='earth'), _Row(element='fire'),
                _Row(element='water'), _Row(element='air')]
        digest = _Digest([('Earth', [0]), ('Fire', [1]),
                          ('Water', [2]), ('Air', [3])], rows)
        self.assertEqual('', scored_group_label(digest,
                                                digest.non_crit_dams[0]))


class TheNoteSaysItOnlyWhenThereIsSomethingToSayTests(SimpleTestCase):
    """La note partage sa place avec celle qui explique un zero."""

    class _Castable(object):
        def __init__(self, group='', buffs=None, hits=None):
            self.scored_group = group
            self.buffs = buffs or []
            self.hits = hits or []

    def test_a_cast_that_shows_a_number_names_its_group(self):
        note = _cast_note(self._Castable(group='Stack 0'), 'Spell', {}, 28)
        self.assertEqual('counted on Stack 0', note)

    def test_a_cast_with_nothing_to_choose_says_nothing(self):
        self.assertEqual('', _cast_note(self._Castable(), 'Spell', {}, 28))

    def test_a_zero_keeps_the_note_that_explains_the_zero(self):
        """Le plancher de la paire: la note du groupe ne doit pas manger
        celle qui dit pourquoi un buff ne pose rien."""
        castable = self._Castable(group='Stack 0', buffs=[object()])
        note = _cast_note(castable, 'Spell', {}, 0)
        self.assertIn('no damage of its own', note)

    def test_the_note_is_translated_in_every_language(self):
        castable = self._Castable(group='Stack 0')
        seen = {}
        for language in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(language):
                seen[language] = _cast_note(castable, 'Spell', {}, 28)
        self.assertEqual('compte sur Cumul 0',
                         seen['fr'].replace('é', 'e'))
        self.assertEqual('contado en Acumulación 0', seen['es'])
        self.assertEqual('contado em Acúmulo 0', seen['pt'])
        self.assertEqual('mit Stapel 0 gewertet', seen['de'])
        self.assertEqual(len(set(seen.values())), len(seen),
                         'two languages share a wording: %s' % seen)

    def test_the_label_carries_the_number_into_every_language(self):
        """Sans cela, une traduction qui perdrait %(group)s passerait les
        egalites ci-dessus le jour ou le libelle changerait."""
        for language in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(language):
                for index in (0, 3):
                    note = _cast_note(self._Castable(
                        group='Stack %d' % index), 'Spell', {}, 28)
                    with self.subTest(language=language, stack=index):
                        self.assertIn(str(index), note, note)


class EveryVersionHasSpellsWorthNamingTests(SimpleTestCase):
    """Le plancher de la mesure: une regle qui ne nommerait rien passerait
    tous les tests ci-dessus."""

    #: Mesure du 15 septembre 2026, au rang le plus haut de chaque sort.
    #: Touch et Retro n'ont pas zero par accident: leurs catalogues ne
    #: portent que 2 et 1 sorts a plusieurs groupes, et les trois sont des
    #: choix d'element (<<Hit in best element>>, <<Hit in one random
    #: element>>), que la regle laisse expres sans nom.
    NAMED_BY_VERSION = {'dofus3': 34, 'beta': 34, 'dofus2': 20,
                        'touch': 0, 'retro': 0}

    @staticmethod
    def _named():
        shapes = collections.Counter()
        per_version = collections.Counter()
        for game_version in VERSIONS:
            for char_class in get_damage_spells_for_version(game_version):
                for castable in castable_spells(char_class, 200,
                                                game_version):
                    label = getattr(castable, 'scored_group', '')
                    if label:
                        per_version[game_version] += 1
                        shapes[_SANS_CHIFFRES.sub('N', label)] += 1
        return per_version, shapes

    def test_the_modern_versions_name_the_groups_they_have(self):
        per_version, shapes = self._named()
        missing = [version for version in ('dofus3', 'beta', 'dofus2')
                   if not per_version.get(version)]
        self.assertEqual([], missing,
                         'no spell names a group on %s' % missing)
        self.assertGreaterEqual(sum(per_version.values()), 40,
                                dict(per_version))
        self.assertIn('Stack N', shapes, dict(shapes))

    def test_touch_and_retro_have_no_ladder_to_name(self):
        """Chaque version est un jeu different, et le << Cumul >> est une
        construction du Dofus moderne. Ce test tombe le jour ou l'un des deux
        en gagne un, ce qui est exactement le moment ou il faut regarder."""
        per_version, _shapes = self._named()
        for game_version in ('touch', 'retro'):
            with self.subTest(game_version=game_version):
                self.assertEqual(0, per_version.get(game_version, 0))
        groups = []
        for game_version in ('touch', 'retro'):
            for char_class in get_damage_spells_for_version(game_version):
                for castable in castable_spells(char_class, 200,
                                                game_version):
                    aggregates = castable.spell.get_effects_digest().aggregates
                    if aggregates and len(aggregates) > 1:
                        groups.append((game_version, castable.name,
                                       aggregates[0][0]))
        self.assertEqual(3, len(groups), groups)
        for _version, _name, first_label in groups:
            with self.subTest(label=first_label):
                self.assertIn('element', first_label.lower())

    def test_the_named_groups_all_have_a_reader_facing_label(self):
        """Un libelle que `_localized_aggregate_label` ne sait pas traduire
        sortirait un identifiant brut a l'ecran."""
        raw = []
        for game_version in VERSIONS:
            for char_class in get_damage_spells_for_version(game_version):
                for castable in castable_spells(char_class, 200,
                                                game_version):
                    label = getattr(castable, 'scored_group', '')
                    if not label:
                        continue
                    shown = _localized_aggregate_label(label, game_version)
                    if shown and re.search(r'\bState \d', shown):
                        raw.append((game_version, castable.name, shown))
        self.assertEqual([], raw[:10],
                         'these notes would show a state id: %s' % raw[:10])
