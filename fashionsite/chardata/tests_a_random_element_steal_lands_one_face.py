# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A steal drawn in one random element lands one face: the boomerangs score a quarter of their four rows."""

import copy

from django.test import SimpleTestCase
from django.utils import translation

from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spell_combo import Castable, best_turn
from chardata.spell_reference import get_spell_reference

PERFIDIOUS_BOOMERANG = 364
DIAMONDINE_BOOMERANG = 24007
BOOMERANGS = (PERFIDIOUS_BOOMERANG, DIAMONDINE_BOOMERANG)
VERSIONS = ('dofus3', 'beta', 'dofus2')
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
RANDOM_LABEL = 'Hit in one random element'

SAYS_RANDOM = {'en': 'random element', 'fr': 'aléatoire', 'es': 'aleatorio',
               'pt': 'aleatório', 'de': 'zufällig'}

_STATS = {'str': 400, 'int': 400, 'cha': 400, 'agi': 400, 'pow': 0, 'dam': 0,
          'cridam': 0, 'heals': 0, 'perspedam': 0, 'perweadam': 0,
          'permedam': 0, 'perrandam': 0, 'earthdam': 0, 'firedam': 0,
          'waterdam': 0, 'airdam': 0, 'neutdam': 0, 'ch': 0, 'final': 0,
          'negfinal': 0, 'pshdam': 0, 'ap': 12}


def _in_version(test, version):
    from fashionistapulp.structure import set_current_game_version
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)


def _spell(version, spell_id):
    return next(spell for spell in get_damage_spells_for_version(version)['default']
                if spell.spell_id == spell_id)


def _card(version, spell_id, language):
    for entries in get_spell_reference(version).values():
        for entry in entries:
            if entry.get('id') == spell_id:
                return ((entry.get('description') or {}).get(language) or '').lower()
    return ''


def _cast(version, spell_id):
    spell = _spell(version, spell_id)
    return Castable(spell, len(spell.level_req) - 1, crit=False)


def _turn(version, cast):
    return best_turn(dict(_STATS), [cast], cast.cost, game_version=version,
                     caster_level=200)[0]


class TheBoomerangsLandOneElementTests(SimpleTestCase):

    def test_each_face_is_one_steal_drawn_by_the_game(self):
        for version in VERSIONS:
            for spell_id in BOOMERANGS:
                with self.subTest(version=version, spell=spell_id):
                    _in_version(self, version)
                    cast = _cast(version, spell_id)
                    self.assertTrue(cast.random_draw)
                    self.assertEqual([1, 1, 1, 1], [len(face) for face in cast.plain_alternatives])
                    self.assertTrue(all(face[0].steals for face in cast.plain_alternatives))

    def test_the_cast_scores_a_quarter_of_the_four_rows_summed(self):
        for version in VERSIONS:
            for spell_id in BOOMERANGS:
                with self.subTest(version=version, spell=spell_id):
                    _in_version(self, version)
                    cast = _cast(version, spell_id)
                    summed = copy.copy(cast)
                    summed.random_draw = False
                    summed.plain_alternatives = [sum(cast.plain_alternatives, [])]
                    summed.crit_alternatives = [sum(cast.crit_alternatives, [])]
                    summed.alternatives = summed.plain_alternatives
                    self.assertAlmostEqual(_turn(version, summed) / 4, _turn(version, cast))

    def test_the_page_joins_the_four_faces_with_or(self):
        from chardata.spells_view import convert_aggregates
        for version in VERSIONS:
            for spell_id in BOOMERANGS:
                with self.subTest(version=version, spell=spell_id):
                    spell = _spell(version, spell_id)
                    rows = spell.get_effects_digest().non_crit_dams[0]
                    with translation.override('en'):
                        groups = convert_aggregates(spell.aggregates, version, rows)
                    if spell_id == PERFIDIOUS_BOOMERANG:
                        self.assertEqual([RANDOM_LABEL, [0, 4, 1, 5, 2, 6, 3, 7], 'one',
                                          [[0, 4], [1, 5], [2, 6], [3, 7]]], groups[0])
                    else:
                        self.assertEqual([RANDOM_LABEL, [0, 1, 2, 3], 'one'], groups[0])

    def test_each_buff_rides_the_steal_of_its_own_element(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                rows = _spell(version, PERFIDIOUS_BOOMERANG).get_effects_digest().non_crit_dams[0]
                self.assertEqual(['earth', 'fire', 'water', 'air', 'buff_str', 'buff_int',
                                  'buff_cha', 'buff_agi'], [row.element for row in rows])
                aggregates = _spell(version, PERFIDIOUS_BOOMERANG).aggregates
                self.assertEqual([[0, 4], [1, 5], [2, 6], [3, 7]],
                                 [list(indexes) for _label, indexes in aggregates])

    def test_the_cast_lands_one_buff_so_the_panel_holds_a_quarter_of_each(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _in_version(self, version)
                cast = _cast(version, PERFIDIOUS_BOOMERANG)
                self.assertEqual({'str': 40, 'int': 40, 'cha': 40, 'agi': 40}, cast.buff_deltas(1))
                self.assertEqual({}, _cast(version, DIAMONDINE_BOOMERANG).buff_deltas(1))
                crit = Castable(_spell(version, PERFIDIOUS_BOOMERANG),
                                len(_spell(version, PERFIDIOUS_BOOMERANG).level_req) - 1, crit=True)
                self.assertEqual({'str': 45, 'int': 45, 'cha': 45, 'agi': 45}, crit.buff_deltas(1))
                self.assertEqual(160, sum(cast.buff_deltas(1).values()))

    def test_the_buffs_do_not_change_what_the_cast_scores(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                _in_version(self, version)
                cast = _cast(version, PERFIDIOUS_BOOMERANG)
                self.assertEqual([1, 1, 1, 1], [len(face) for face in cast.plain_alternatives])

    def test_the_card_says_random_in_every_language(self):
        for version in VERSIONS:
            for spell_id in BOOMERANGS:
                for language in LANGUAGES:
                    with self.subTest(version=version, spell=spell_id, language=language):
                        self.assertIn(SAYS_RANDOM[language], _card(version, spell_id, language))


class TheGeneratorReadsOneDrawPerElementTests(SimpleTestCase):

    def _generator(self):
        from chardata.tests import itemscraper_module
        return itemscraper_module('generate_damage_spells')

    def _rows(self):
        return [{'element': element, 'steals': True, 'heals': False, 'ranges': ['26-29'],
                 'triggers': 'I', 'situation': 'A|80,1,0'}
                for element in ('EARTH', 'FIRE', 'WATER', 'AIR')]

    def _spell(self, groups, chance):
        ids = {'EARTH': 1, 'FIRE': 2, 'WATER': 3, 'AIR': 4}
        effects = [{'effect_id': 91, 'effect_element': ids[row['element']],
                    'dice': {'min': 26, 'max': 29}, 'target_mask': 'A', 'triggers': 'I',
                    'random': chance, 'group': group,
                    'effect_metadata': {'category': 2, 'description': {
                        'en': '#1{{~1~2 to }}#2 %s steal' % row['element'].title()}}}
                   for row, group in zip(self._rows(), groups)]
        return {'ankama_id': 1, 'levels': [{'effects': effects, 'critical_effects': []}]}

    def test_four_steals_in_one_group_are_one_random_hit(self):
        runs, problem = self._generator()._drawn_runs(self._spell([0, 0, 0, 0], 25), self._rows(), [])
        self.assertIsNone(problem)
        self.assertEqual([[0, 1, 2, 3]], runs)

    def test_four_steals_in_four_groups_are_one_random_hit(self):
        runs, problem = self._generator()._drawn_runs(self._spell([4, 3, 2, 1], 12.5), self._rows(), [])
        self.assertIsNone(problem)
        self.assertEqual([[0, 1, 2, 3]], runs)

    def test_a_buff_of_a_drawn_group_joins_the_face_of_that_group(self):
        generator = self._generator()
        aggregates = [(RANDOM_LABEL, [0]), ('', [1]), ('', [2]), ('', [3]),
                      ('', [4]), ('', [5]), ('', [6]), ('', [7]), ('', [8])]
        buffs = [{'group': group} for group in (4, 3, 2, 1)] + [{'group': None}]
        drawn = {0: 4, 1: 3, 2: 2, 3: 1}
        paired = generator._pair_buffs_with_their_draw(
            aggregates, [[0, 1, 2, 3]], drawn, buffs, 4)
        self.assertEqual([(RANDOM_LABEL, [0, 4]), ('', [1, 5]), ('', [2, 6]), ('', [3, 7]),
                          ('', [8])], paired)

    def test_a_buff_outside_every_drawn_group_stays_alone(self):
        generator = self._generator()
        aggregates = [(RANDOM_LABEL, [0]), ('', [1]), ('', [2]), ('', [3]), ('', [4])]
        paired = generator._pair_buffs_with_their_draw(
            aggregates, [[0, 1, 2, 3]], {0: 4, 1: 3, 2: 2, 3: 1}, [{'group': 9}], 4)
        self.assertEqual(aggregates, paired)

    def test_the_run_is_labelled_one_random_element(self):
        generator = self._generator()
        aggregates = generator._build_drawn_aggregates(
            [[0, 1, 2, 3]], 4, 4, ['EARTH', 'FIRE', 'WATER', 'AIR'])
        self.assertEqual((RANDOM_LABEL, [0]), aggregates[0])
