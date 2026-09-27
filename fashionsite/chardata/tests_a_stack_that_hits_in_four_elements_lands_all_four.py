# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Knell and Arcane Torrent hit in four named elements on every cast: each stack is one group of four rows, not four faces."""
import copy

from django.test import SimpleTestCase

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_reference import get_spell_reference

VERSIONS = ('dofus3', 'beta', 'dofus2')

KNELL = 13300
ARCANE_TORRENT = 14342
CLASS_OF = {KNELL: 'Xelor', ARCANE_TORRENT: 'Huppermage'}
STACKS = 7

# Ankama's words, lower case: the four elements joined by "and"
SAYS = {
    KNELL: {
        'dofus3': {'en': 'inflicts fire, water, air and earth damage',
                   'fr': 'occasionne des dommages feu, eau, air et terre',
                   'es': 'ocasiona daños de fuego, agua, aire y tierra',
                   'pt': 'inflige danos de fogo, água, ar e terra',
                   'de': 'feuer-, wasser-, luft- und erdschaden'},
        'beta': {'en': 'inflicts fire, water, air and earth damage',
                 'fr': 'occasionne des dommages feu, eau, air et terre',
                 'es': 'ocasiona daños de fuego, agua, aire y tierra',
                 'pt': 'inflige danos de fogo, água, ar e terra',
                 'de': 'feuer-, wasser-, luft- und erdschaden'},
        'dofus2': {'en': 'inflicts air, water, earth and fire damage',
                   'fr': 'occasionne des dommages air, eau, terre et feu',
                   'es': 'ocasiona daños de aire, agua, tierra y fuego',
                   'pt': 'inflige danos de ar, água, terra e fogo',
                   'de': 'luft-, wasser-, erd- und feuerschaden'},
    },
    ARCANE_TORRENT: {
        version: {'en': 'inflicts air, earth, fire and water damage',
                  'fr': 'occasionne des dommages air, terre, feu et eau',
                  'es': 'ocasiona daños de aire, tierra, fuego y agua',
                  'pt': 'inflige danos de ar, terra, fogo e água',
                  'de': 'luft-, erd-, feuer- und wasserschaden'}
        for version in VERSIONS},
}


def _generator():
    from chardata.tests import itemscraper_module
    return itemscraper_module('generate_damage_spells')


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version).get(CLASS_OF[spell_id], [])
                if spell.spell_id == spell_id)


def _text(version, spell_id, language):
    for entry in get_spell_reference(version).get(CLASS_OF[spell_id], []):
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


def _with_rows(cast, rows):
    one = copy.copy(cast)
    one.plain_alternatives = one.alternatives = [list(rows)]
    one.crit_alternatives = []
    one.crit_rate = 0
    return one


class EachStackIsOneGroupOfFourTests(SimpleTestCase):

    def test_each_version_writes_one_group_per_stack(self):
        for version in VERSIONS:
            for spell_id in CLASS_OF:
                spell = _spell(version, spell_id)
                elements = list(spell.effects.elements)
                with self.subTest(version=version, spell=spell.name):
                    self.assertEqual(4 * STACKS, len(elements))
                    self.assertEqual(
                        [('Stack %d' % stack, list(range(4 * stack, 4 * stack + 4)))
                         for stack in range(STACKS)],
                        list(spell.aggregates))
                    for stack in range(STACKS):
                        self.assertEqual(elements[:4], elements[4 * stack:4 * stack + 4])
                    self.assertEqual({'fire', 'water', 'air', 'earth'}, set(elements[:4]))

    def test_the_rows_follow_the_elements_ankama_names(self):
        for version in VERSIONS:
            for spell_id in CLASS_OF:
                said = SAYS[spell_id][version]['en']
                named = said.replace('inflicts ', '').replace(' damage', '')
                named = [word.strip() for word in named.replace(' and ', ', ').split(',')]
                elements = list(_spell(version, spell_id).effects.elements)[:4]
                with self.subTest(version=version, spell=spell_id):
                    self.assertEqual(named, elements)


class TheTurnLandsTheFourElementsTests(SimpleTestCase):

    def test_one_cast_scores_the_four_rows_of_its_first_stack(self):
        for version in VERSIONS:
            _in_version(self, version)
            for spell_id in CLASS_OF:
                cast = _top_cast(_spell(version, spell_id))
                with self.subTest(version=version, spell=cast.name):
                    self.assertFalse(cast.random_draw)
                    self.assertEqual(1, len(cast.plain_alternatives))
                    self.assertEqual(4, len(cast.hits))
                    self.assertEqual({'fire', 'water', 'air', 'earth'},
                                     {row.element for row in cast.hits})
                    self.assertEqual('Stack 0', cast.scored_group)

    def test_the_turn_adds_the_four_hits_up(self):
        from chardata.spell_combo import best_turn
        for version in VERSIONS:
            _in_version(self, version)
            stats = _stats(version, str=400, int=500, cha=600, agi=700, pow=50)
            for spell_id in CLASS_OF:
                cast = _top_cast(_spell(version, spell_id))
                whole = _with_rows(cast, cast.hits)
                total, _order = best_turn(stats, [whole], cast.cost, game_version=version)
                alone = [best_turn(stats, [_with_rows(cast, [row])], cast.cost,
                                   game_version=version)[0] for row in cast.hits]
                with self.subTest(version=version, spell=cast.name):
                    self.assertGreater(min(alone), 0)
                    self.assertAlmostEqual(sum(alone), total, places=6)
                    self.assertGreater(total, max(alone))

    def test_the_table_shows_each_stack_as_one_summed_line(self):
        from chardata.spells_view import convert_aggregates
        for version in VERSIONS:
            _in_version(self, version)
            for spell_id in CLASS_OF:
                digest = _spell(version, spell_id).get_effects_digest()
                groups = convert_aggregates(digest.aggregates, version,
                                            digest.non_crit_dams[0])
                with self.subTest(version=version, spell=spell_id):
                    self.assertEqual(STACKS, len(groups))
                    for stack, group in enumerate(groups):
                        self.assertEqual(list(range(4 * stack, 4 * stack + 4)), group[1])
                        self.assertEqual(2, len(group))


class OnlyTheseStacksLandWholeTests(SimpleTestCase):

    def test_no_other_stack_group_holds_several_rows(self):
        for version in VERSIONS:
            whole = set()
            read = 0
            for spells in get_damage_spells_for_version(version).values():
                for spell in spells:
                    read += 1
                    for label, indices in spell.aggregates or []:
                        if str(label).startswith('Stack ') and len(indices) > 1:
                            whole.add(spell.spell_id)
            with self.subTest(version=version):
                self.assertGreater(read, 400)
                self.assertEqual({KNELL, ARCANE_TORRENT}, whole)


class AnkamasTextListsTheFourElementsTests(SimpleTestCase):

    def test_in_five_languages_and_three_versions(self):
        for version in VERSIONS:
            for spell_id in CLASS_OF:
                for language, said in SAYS[spell_id][version].items():
                    with self.subTest(version=version, spell=spell_id, language=language):
                        self.assertIn(said, _text(version, spell_id, language))


class TheGeneratorRuleTests(SimpleTestCase):

    @staticmethod
    def _rows(*shapes):
        return [dict({'element': element, 'situation': 'A|71,1,0', 'triggers': 'I',
                      'ranges': ['6']}, **extra) for element, extra in shapes]

    def _lands_together(self, rows, spell_id=1, levels=()):
        return _generator()._stack_rows_land_together(
            {'ankama_id': spell_id, 'levels': list(levels)}, rows)

    def test_four_elements_in_one_situation_land_together(self):
        rows = self._rows(('FIRE', {}), ('WATER', {}), ('AIR', {}), ('EARTH', {}))
        self.assertTrue(self._lands_together(rows))

    def test_faces_and_late_rows_stay_apart(self):
        cases = {
            'two situations': self._rows(('FIRE', {}), ('WATER', {'situation': 'a|71,1,0'})),
            'a heal': self._rows(('FIRE', {}), ('WATER', {'heals': True})),
            'one element twice': self._rows(('WATER', {}), ('WATER', {})),
            'a start of turn row': self._rows(('WATER', {}), ('FIRE', {'triggers': 'TB'})),
            'a delay': self._rows(('WATER', {}), ('FIRE', {'delay': 1})),
            'a best element face': self._rows(('WATER', {'best_element_group': 'g'}),
                                              ('FIRE', {'best_element_group': 'g'})),
            'one row': self._rows(('FIRE', {})),
            'no situation': self._rows(('FIRE', {'situation': None}),
                                       ('WATER', {'situation': None})),
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                self.assertFalse(self._lands_together(rows))

    def test_a_row_the_game_rolls_for_stays_apart(self):
        rolled = {'random': 50, 'group': 1, 'effect_element': 2, 'target_mask': 'A',
                  'dice': {'min': 6, 'max': 6},
                  'effect_metadata': {'category': 2, 'description': {'en': 'Fire damage'}}}
        rows = self._rows(('FIRE', {}), ('WATER', {}))
        self.assertTrue(self._lands_together(rows))
        self.assertFalse(self._lands_together(rows, levels=[{'effects': [rolled]}]))

    def test_a_spell_listed_as_one_element_faces_stays_apart(self):
        generator = _generator()
        listed = next(iter(generator.ONE_ELEMENT_FACES))
        rows = self._rows(('FIRE', {}), ('WATER', {}), ('AIR', {}), ('EARTH', {}))
        self.assertFalse(self._lands_together(rows, spell_id=listed))
