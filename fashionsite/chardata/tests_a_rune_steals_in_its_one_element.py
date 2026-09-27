# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Runification and Manifestation trigger the one rune under the enemy: its four element rows are the faces of one steal."""
import copy

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

VERSIONS = ('dofus3', 'beta')

RUNIFICATION = 13670
MANIFESTATION = 13710
RUNE_SPELLS = (RUNIFICATION, MANIFESTATION)

BEST = 'Hit in best element'

# Ankama's words, lower case: one rune, and the rune's element
SAYS = {
    'one_rune': {'en': "triggers one of the caster's runes", 'fr': 'déclenche une rune du lanceur',
                 'es': 'activa una runa del lanzador', 'pt': 'aciona uma runa do lançador',
                 'de': 'löst eine rune des zaubernden aus'},
    'its_element': {'en': "based on the rune's element", 'fr': "selon l'élément de la rune",
                    'es': 'según el elemento de esta', 'pt': 'de acordo com o elemento dela',
                    'de': 'dem element der rune entsprechend'},
}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version).get('Huppermage', [])
                if spell.spell_id == spell_id)


def _text(version, spell_id, language):
    for entry in get_spell_reference(version).get('Huppermage', []):
        if entry.get('id') == spell_id:
            text = (entry.get('description') or {}).get(language) or ''
            return text.replace('’', "'").lower()
    return ''


def _top_cast(spell):
    from chardata.spell_combo import Castable
    return Castable(spell, len(spell.level_req) - 1, False)


def _stats(version, **values):
    from fashionistapulp.structure import get_structure
    stats = {stat.key: 0 for stat in get_structure(version).get_stats_list()}
    stats.update(values)
    return stats


class TheFourStealsAreFacesOfOneTests(SimpleTestCase):

    def test_each_version_writes_the_steals_as_one_run_and_each_buff_apart(self):
        for version in VERSIONS:
            for spell_id in RUNE_SPELLS:
                spell = _spell(version, spell_id)
                elements = list(spell.effects.elements)
                aggregates = list(spell.aggregates)
                with self.subTest(version=version, spell=spell.name):
                    self.assertEqual(['earth', 'fire', 'water', 'air'], elements[:4])
                    self.assertEqual([(BEST, [0]), ('', [1]), ('', [2]), ('', [3])],
                                     aggregates[:4])
                    self.assertTrue(all(element.startswith('buff') for element in elements[4:]))
                    self.assertEqual([('', [index]) for index in range(4, len(elements))],
                                     aggregates[4:])

    def test_the_turn_lands_one_steal_the_caster_picks(self):
        from chardata.spell_combo import best_turn
        for version in VERSIONS:
            _in_version(self, version)
            for spell_id in RUNE_SPELLS:
                cast = _top_cast(_spell(version, spell_id))
                with self.subTest(version=version, spell=cast.name):
                    self.assertFalse(cast.random_draw)
                    self.assertEqual(4, len(cast.plain_alternatives))
                    for face in cast.plain_alternatives:
                        self.assertEqual(1, len(face))
                        self.assertTrue(face[0].steals)
                    stats = _stats(version, cha=800, pow=100)
                    total, _order = best_turn(stats, [cast], cast.cost, game_version=version)
                    alone = []
                    for face in cast.plain_alternatives:
                        one = copy.copy(cast)
                        one.plain_alternatives = one.alternatives = [face]
                        alone.append(best_turn(stats, [one], cast.cost,
                                               game_version=version)[0])
                    summed = copy.copy(cast)
                    summed.plain_alternatives = summed.alternatives = [
                        [face[0] for face in cast.plain_alternatives]]
                    self.assertAlmostEqual(max(alone), total, places=6)
                    self.assertLess(total, best_turn(stats, [summed], cast.cost,
                                                     game_version=version)[0])

    def test_the_table_shows_the_four_steals_as_one_line(self):
        from chardata.spells_view import convert_aggregates
        for version in VERSIONS:
            _in_version(self, version)
            for spell_id in RUNE_SPELLS:
                digest = _spell(version, spell_id).get_effects_digest()
                with self.subTest(version=version, spell=spell_id):
                    groups = convert_aggregates(digest.aggregates, version,
                                                digest.non_crit_dams[0])
                    self.assertEqual([0, 1, 2, 3], groups[0][1])
                    self.assertEqual('best', groups[0][2])


class AnkamasTextSaysOneRuneTests(SimpleTestCase):

    def test_in_five_languages_and_both_versions(self):
        for version in VERSIONS:
            for spell_id in RUNE_SPELLS:
                for rule, words in SAYS.items():
                    for language, said in words.items():
                        with self.subTest(version=version, spell=spell_id, rule=rule,
                                          language=language):
                            self.assertIn(said, _text(version, spell_id, language))

    def test_the_generator_quotes_the_card_of_each_version(self):
        generator = _generator()
        for version in VERSIONS:
            listed = generator.ONE_ELEMENT_FACES_BY_VERSION[version]
            for spell_id in RUNE_SPELLS:
                with self.subTest(version=version, spell=spell_id):
                    self.assertIn(listed[spell_id], _text(version, spell_id, 'fr'))
        self.assertNotIn(RUNIFICATION, generator.ONE_ELEMENT_FACES_BY_VERSION['dofus2'])
        self.assertNotIn(MANIFESTATION, generator.ONE_ELEMENT_FACES_BY_VERSION['dofus2'])
