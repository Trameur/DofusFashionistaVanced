# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The damage panel names which aggregate group of a spell it counted."""
import collections
import re

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import castable_spells, scored_group_label
from chardata.spells_view import _cast_note, _localized_aggregate_label

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')

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
    """The rule on hand-built groups, no catalogue."""

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
        """The turn only counts the group that hits, so the note names that one."""
        rows = [_Row(heals=True), _Row(min_dam=20, max_dam=22)]
        digest = _Digest([('Stack 0', [0]), ('Stack 1', [1])], rows)
        self.assertEqual('Stack 1',
                         scored_group_label(digest, digest.non_crit_dams[0]))

    def test_an_element_choice_is_not_named(self):
        """One group per element: best_turn picks it from the stats."""
        rows = [_Row(element='earth'), _Row(element='fire'),
                _Row(element='water'), _Row(element='air')]
        digest = _Digest([('Earth', [0]), ('Fire', [1]),
                          ('Water', [2]), ('Air', [3])], rows)
        self.assertEqual('', scored_group_label(digest,
                                                digest.non_crit_dams[0]))


class TheNoteSaysItOnlyWhenThereIsSomethingToSayTests(SimpleTestCase):
    """The group note shares its slot with the note explaining a zero."""

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
        """Every translation keeps %(group)s."""
        for language in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(language):
                for index in (0, 3):
                    note = _cast_note(self._Castable(
                        group='Stack %d' % index), 'Spell', {}, 28)
                    with self.subTest(language=language, stack=index):
                        self.assertIn(str(index), note, note)


class EveryVersionHasSpellsWorthNamingTests(SimpleTestCase):
    # Touch and Retro groups are all element choices, left unnamed
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
        """Stacks are a modern Dofus mechanic, Touch and Retro have none."""
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
        self.assertEqual(7, len(groups), groups)
        for _version, _name, first_label in groups:
            with self.subTest(label=first_label):
                self.assertIn('element', first_label.lower())

    def test_the_named_groups_all_have_a_reader_facing_label(self):
        """No named group shows a raw state id."""
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
