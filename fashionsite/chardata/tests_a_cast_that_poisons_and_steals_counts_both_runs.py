# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A cast that poisons at turn end and steals at once counts both hits."""

import copy

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import (Castable, best_turn, delayed_damage,
                                   runs_landing_together)

BLACK_FIRE = 33228

FACES = 4

VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spells in get_damage_spells_for_version(version).values()
                for spell in spells if spell.spell_id == spell_id)


def _stats(version, **values):
    from fashionistapulp.structure import get_structure
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update(values)
    return stats


def _top_cast(spell, crit=False):
    return Castable(spell, len(spell.level_req) - 1, crit)


def _one_run_only(cast):
    """The same cast with only the first row of each face."""
    only = copy.copy(cast)
    only.plain_alternatives = [face[:1] for face in cast.plain_alternatives]
    only.crit_alternatives = [face[:1] for face in cast.crit_alternatives]
    only.alternatives = (only.crit_alternatives if cast.crit
                         else only.plain_alternatives)
    only.hits = only.alternatives[0]
    return only


AURA_WORD = {'en': 'Bellaura', 'fr': 'Bellaura', 'es': 'belaura', 'pt': 'Belaura', 'de': 'Bellaura'}


class TheTwoRunsOfOneCastLandTogetherTests(SimpleTestCase):

    def test_each_face_holds_the_late_row_and_the_instant_row(self):
        _in_version(self, 'beta')
        cast = _top_cast(_spell('beta', BLACK_FIRE))
        for alternatives in (cast.plain_alternatives, cast.crit_alternatives):
            self.assertEqual(FACES, len(alternatives))
            for face in alternatives:
                self.assertEqual(2, len(face))
                self.assertEqual(face[0].element, face[1].element)
                self.assertEqual([True, False],
                                 [id(row) in cast.late_by_effect for row in face])

    def test_the_turn_counts_both_hits(self):
        _in_version(self, 'beta')
        stats = _stats('beta', cha=800, pow=100)
        cast = _top_cast(_spell('beta', BLACK_FIRE))
        both = best_turn(stats, [cast], cast.cost, game_version='beta')[0]
        late = best_turn(stats, [_one_run_only(cast)], cast.cost, game_version='beta')[0]
        self.assertGreater(late, 0)
        self.assertAlmostEqual(2 * late, both, places=6)

    def test_only_the_poison_is_counted_as_late(self):
        _in_version(self, 'beta')
        stats = _stats('beta', cha=800, pow=100)
        cast = _top_cast(_spell('beta', BLACK_FIRE))
        order = [(cast.name, 0)]
        total = best_turn(stats, [cast], cast.cost, game_version='beta')[0]
        late = delayed_damage(stats, [cast], order, game_version='beta')[cast.name]
        self.assertAlmostEqual(total / 2, late, places=6)

    def test_no_other_spell_of_any_version_pairs_two_runs(self):
        paired = set()
        for version in VERSIONS:
            _in_version(self, version)
            for classe, spells in get_damage_spells_for_version(version).items():
                for spell in spells:
                    digest = spell.get_effects_digest()
                    late = getattr(spell, 'delayed', None) or {}
                    waiting = getattr(spell, 'conditional', None) or {}
                    for rows in digest.non_crit_dams:
                        if runs_landing_together(digest.aggregates, rows, late, waiting):
                            paired.add((version, spell.name))
        self.assertEqual({('beta', 'Black Fire')}, paired)

    def test_the_page_says_the_steal_needs_the_bellaura(self):
        from django.utils import translation
        from chardata.spells_view import _cast_note
        _in_version(self, 'beta')
        cast = _top_cast(_spell('beta', BLACK_FIRE))
        self.assertTrue(cast.counts_both_runs)
        notes = {}
        for language in ('en', 'fr', 'es', 'pt', 'de'):
            with translation.override(language):
                notes[language] = _cast_note(cast, cast.name, set(), 243.0, 'beta')
            self.assertIn(AURA_WORD[language], notes[language])
        self.assertEqual(5, len(set(notes.values())))
